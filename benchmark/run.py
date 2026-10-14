# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "datasets>=3.0",
#   "huggingface_hub>=0.25",
#   "jinja2>=3.1",
# ]
# ///
"""A/B benchmark of the performance-ladder-review skill on SWE-fficiency.

Subcommands:
  select     sample the task list (tasks.json) from the replay-stable instances
  setup      clone the official harness at a pinned commit and fetch the pinned CLI
  preflight  one-turn probe: model id, credentials, and skill visibility per arm
  run        agent runs plus official scoring, checkpointed and resumable
  status     print the checkpoint summary for a study
  cleanup    remove leftover benchmark containers and images

Run it inside WSL (Docker lives there). See README.md for the method.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import datetime as dt
import fcntl
import hashlib
import io
import json
import math
import os
import random
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from collections import defaultdict
from pathlib import Path
from zoneinfo import ZoneInfo

BENCH_DIR = Path(__file__).resolve().parent
SKILL_DIR = BENCH_DIR.parent / "skills" / "performance-ladder-review"
TASKS_FILE = BENCH_DIR / "tasks.json"

DATASET = "swefficiency/swefficiency"
HARNESS_REPO = "https://github.com/swefficiency/swefficiency.git"
HARNESS_COMMIT = "12d32a2d6800824a7d84bdb6797b5708e7b7957f"
AUDIT_COMMIT = "44a1cb86a9f765b0375b4cfb479641f3c19f0774"
AUDIT_CSV_URL = (
    "https://raw.githubusercontent.com/chenzhi-cz/performance-optimization-benchmark-reliability/"
    f"{AUDIT_COMMIT}/data/swefficiency_cross_machine_valid_tasks.csv"
)
IMAGE_REPO = "swefficiency/swefficiency-images"
IMAGE_TEMPLATE = "ghcr.io/swefficiency/swefficiency-images:{iid}"
PROMPT_TEMPLATE_REL = "scripts/inference/templates/cursor_instruction_prompt.txt.j2"

DEFAULTS = {
    "model": "claude-sonnet-5-5",
    "cli_version": "2.1.238",
    "max_turns": 100,
    "run_timeout_sec": 3600,
    "score_timeout_sec": 7200,
    "arms": ["baseline", "skill"],
    "mem_limit": "32g",  # the official inference harness default (custom.py)
    "limit_backoff_sec": 900,
}
SELECT_SEED = 20261014
N_TASKS = 40

ARM_SKILL = "skill"
ARM_BASELINE = "baseline"

WORKDIR = Path(os.environ.get("PLR_WORKDIR", Path.home() / "plr-bench"))
CRED_CANDIDATES = [
    os.environ.get("PLR_CREDENTIALS", ""),
    str(Path.home() / ".claude" / ".credentials.json"),
    "/mnt/c/Users/johnr/.claude/.credentials.json",
]
CONTAINER_CFG = "/root/.plr-claude"
# Same environment for both arms. The CLI ships bundled skills (simplify, code-review,
# deep-research and others) that would otherwise load in both arms; they are switched
# off so the only skill either arm can see is the one under test.
ISOLATION_ENV = {
    "DISABLE_AUTOUPDATER": "1",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    "CLAUDE_CODE_DISABLE_BUNDLED_SKILLS": "1",
    "CLAUDE_CODE_DISABLE_POLICY_SKILLS": "1",
    "CLAUDE_CODE_DISABLE_CLAUDE_API_SKILL": "1",
    "TZ": "UTC",
}
CONTAINER_PROMPT = "/tmp/plr_prompt.txt"


# ----------------------------------------------------------------- utilities


def log(msg: str) -> None:
    stamp = dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[{stamp}] {msg}", flush=True)


def now_iso() -> str:
    return dt.datetime.now(dt.UTC).isoformat(timespec="seconds")


def sh(cmd: list[str], *, check: bool = True, timeout: float | None = None, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, timeout=timeout, text=True, capture_output=True, **kw)


def atomic_write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=False))
    os.replace(tmp, path)


def http_json(url: str, headers: dict | None = None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def free_gb(path: str) -> float:
    st = os.statvfs(path)
    return st.f_bavail * st.f_frsize / 1e9


def disk_snapshot() -> dict:
    snap = {"wsl_root_free_gb": round(free_gb("/"), 2)}
    if os.path.isdir("/mnt/c"):
        snap["host_c_free_gb"] = round(free_gb("/mnt/c"), 2)
    return snap


def find_credentials() -> Path:
    for c in CRED_CANDIDATES:
        if c and Path(c).is_file():
            return Path(c)
    sys.exit("No Claude Code credentials file found. Set PLR_CREDENTIALS to its path.")


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ------------------------------------------------------------- CPU pinning


def pinned_cpuset() -> dict:
    """Mirror swefficiency.harness.cpu_assignment.allocate_whole_cores(1, 4, 2, reserve_cores=4).

    The scoring harness pins its single worker this way, so agent containers get the
    same logical CPUs and see the same machine the scorer measures on.
    """
    sys_cpu = Path("/sys/devices/system/cpu")
    seen, cores = set(), []
    for entry in sys_cpu.iterdir():
        name = entry.name
        if not name.startswith("cpu") or not name[3:].isdigit():
            continue
        cpu = int(name[3:])
        if cpu in seen:
            continue
        try:
            text = (entry / "topology" / "thread_siblings_list").read_text().strip()
            sibs = sorted(set(_parse_cpu_list(text)))
        except FileNotFoundError:
            sibs = [cpu]
        seen.update(sibs)
        node = 0
        for n in entry.glob("node*"):
            if n.name[4:].isdigit():
                node = int(n.name[4:])
        cores.append((sibs, node))
    cores.sort(key=lambda t: (t[1], t[0][0]))
    cores = cores[4:]
    if len(cores) < 2:
        sys.exit("Not enough physical cores for the 4-vCPU pinning used by the harness.")
    chosen = sorted(c for sibs, _ in cores[:2] for c in sibs[:2])
    mems = ",".join(sorted({str(n) for _, n in cores[:2]}))
    return {"cpuset_cpus": ",".join(map(str, chosen)), "cpuset_mems": mems, "cpus": len(chosen)}


def _parse_cpu_list(s: str) -> list[int]:
    out = []
    for part in s.split(","):
        if "-" in part:
            a, b = part.split("-")
            out.extend(range(int(a), int(b) + 1))
        elif part:
            out.append(int(part))
    return out


# ---------------------------------------------------------------- dataset


def dataset_sha() -> str:
    from huggingface_hub import HfApi

    return HfApi().dataset_info(DATASET).sha


def load_dataset_rows(revision: str | None) -> dict[str, dict]:
    import datasets

    ds = datasets.load_dataset(DATASET, split="test", revision=revision)
    return {row["instance_id"]: row for row in ds}


def image_compressed_size(iid: str, token: str) -> int:
    url = f"https://ghcr.io/v2/{IMAGE_REPO}/manifests/{iid}"
    accept = ",".join(
        [
            "application/vnd.oci.image.manifest.v1+json",
            "application/vnd.docker.distribution.manifest.v2+json",
            "application/vnd.oci.image.index.v1+json",
            "application/vnd.docker.distribution.manifest.list.v2+json",
        ]
    )
    m = http_json(url, {"Authorization": f"Bearer {token}", "Accept": accept})
    if "manifests" in m:  # multi-platform index: pick linux/amd64
        for sub in m["manifests"]:
            p = sub.get("platform", {})
            if p.get("os") == "linux" and p.get("architecture") == "amd64":
                m = http_json(
                    f"https://ghcr.io/v2/{IMAGE_REPO}/manifests/{sub['digest']}",
                    {"Authorization": f"Bearer {token}", "Accept": accept},
                )
                break
    return sum(layer["size"] for layer in m["layers"])


# ----------------------------------------------------------------- select


def cmd_select(args) -> None:
    """Sample N_TASKS replay-stable instances, stratified by repo, with a fixed seed."""
    with urllib.request.urlopen(AUDIT_CSV_URL, timeout=60) as r:
        rows = list(csv.DictReader(io.StringIO(r.read().decode())))
    stable = sorted(r["task_id"] for r in rows if r["benchmark"] == "swefficiency")
    log(f"audit list: {len(stable)} replay-stable SWE-fficiency instances")

    sha = dataset_sha()
    data = load_dataset_rows(sha)
    missing = [i for i in stable if i not in data]
    if missing:
        sys.exit(f"{len(missing)} audit instances are not in the dataset, e.g. {missing[:3]}")

    by_repo: dict[str, list[str]] = defaultdict(list)
    for iid in stable:
        by_repo[data[iid]["repo"]].append(iid)

    # Proportional allocation with the largest-remainder method, at least one per repo.
    total = len(stable)
    quotas = {repo: N_TASKS * len(ids) / total for repo, ids in by_repo.items()}
    alloc = {repo: max(1, math.floor(q)) for repo, q in quotas.items()}
    while sum(alloc.values()) < N_TASKS:
        repo = max(quotas, key=lambda r: (quotas[r] - alloc[r], r))
        alloc[repo] += 1
    while sum(alloc.values()) > N_TASKS:
        repo = min((r for r in alloc if alloc[r] > 1), key=lambda r: (quotas[r] - alloc[r], r))
        alloc[repo] -= 1

    rng = random.Random(SELECT_SEED)
    chosen = []
    for repo in sorted(by_repo):
        chosen.extend(rng.sample(sorted(by_repo[repo]), alloc[repo]))

    token = http_json(f"https://ghcr.io/token?scope=repository:{IMAGE_REPO}:pull")["token"]
    sizes = {}
    for iid in chosen:
        sizes[iid] = image_compressed_size(iid, token)
        time.sleep(0.2)

    # Study order: the two smallest images first (pilot), the rest in a seeded shuffle.
    by_size = sorted(chosen, key=lambda i: (sizes[i], i))
    pilot = by_size[:2]
    rest = sorted(set(chosen) - set(pilot))
    random.Random(SELECT_SEED + 1).shuffle(rest)
    order = pilot + rest

    out = {
        "method": {
            "source_list": "Cross-machine original-rule valid SWE-fficiency tasks from the reliability audit "
            "(arXiv 2607.01211), the 'replay-stable' set: the reference patch met the benchmark's own validity "
            "rule in all 12 replays (4 GCP machine types x 3 rounds).",
            "source_url": AUDIT_CSV_URL,
            "source_count": len(stable),
            "dataset": DATASET,
            "dataset_revision": sha,
            "sampling": "stratified by repo, proportional allocation (largest remainder, minimum 1 per repo), "
            "random.Random(seed).sample within each repo over the sorted instance ids",
            "seed": SELECT_SEED,
            "n": N_TASKS,
            "per_repo_population": {r: len(v) for r, v in sorted(by_repo.items())},
            "per_repo_sample": dict(sorted(alloc.items())),
            "order": "first two = smallest compressed image size (pilot); the rest shuffled with seed+1",
            "image_size_source": "sum of compressed layer sizes in the ghcr.io manifest at selection time",
            "selected_at": now_iso(),
        },
        "tasks": [
            {
                "position": n + 1,
                "instance_id": iid,
                "repo": data[iid]["repo"],
                "image": IMAGE_TEMPLATE.format(iid=iid),
                "image_compressed_bytes": sizes[iid],
                "pilot": iid in pilot,
            }
            for n, iid in enumerate(order)
        ],
    }
    atomic_write_json(TASKS_FILE, out)
    log(f"wrote {TASKS_FILE} ({len(order)} tasks); pilot = {pilot}")


# ------------------------------------------------------------------ setup


def harness_dir() -> Path:
    return WORKDIR / "swefficiency"


def cli_binary(version: str) -> Path:
    return WORKDIR / "cache" / f"claude-{version}" / "package" / "claude"


def cmd_setup(args) -> None:
    WORKDIR.mkdir(parents=True, exist_ok=True)
    h = harness_dir()
    if not h.exists():
        sh(["git", "clone", HARNESS_REPO, str(h)], timeout=900)
    head = sh(["git", "-C", str(h), "rev-parse", "HEAD"]).stdout.strip()
    if head != HARNESS_COMMIT:
        sh(["git", "-C", str(h), "fetch", "--depth", "50", "origin"], check=False, timeout=900)
        sh(["git", "-C", str(h), "checkout", HARNESS_COMMIT], timeout=300)
    log(f"harness at {HARNESS_COMMIT}")
    uv = shutil.which("uv") or str(Path.home() / ".local" / "bin" / "uv")
    subprocess.run([uv, "sync", "--python", "3.12"], cwd=h, check=True)

    version = args.cli_version
    binp = cli_binary(version)
    if not binp.exists():
        d = binp.parent.parent
        d.mkdir(parents=True, exist_ok=True)
        subprocess.run(["npm", "pack", f"@anthropic-ai/claude-code-linux-x64@{version}"], cwd=d, check=True)
        tgz = next(d.glob("*.tgz"))
        subprocess.run(["tar", "xzf", tgz.name], cwd=d, check=True)
    out = sh([str(binp), "--version"]).stdout.strip()
    if not out.startswith(version):
        sys.exit(f"CLI version mismatch: {out}")
    log(f"Claude Code CLI {out}, sha256 {sha256_file(binp)}")


# ---------------------------------------------------------- study state


class Study:
    def __init__(self, name: str):
        self.name = name
        self.dir = WORKDIR / "studies" / name
        self.dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.dir / "state.json"
        self.state = json.loads(self.state_path.read_text()) if self.state_path.exists() else {}
        self._lock = None

    def lock(self) -> None:
        self._lock = open(self.dir / "lock", "w")
        try:
            fcntl.flock(self._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            sys.exit(f"another run.py holds the lock for study {self.name}")

    def save(self) -> None:
        self.state["updated_at"] = now_iso()
        atomic_write_json(self.state_path, self.state)

    def task(self, iid: str) -> dict:
        return self.state.setdefault("tasks", {}).setdefault(iid, {"steps": {}})

    def step(self, iid: str, key: str) -> dict:
        return self.task(iid)["steps"].setdefault(key, {"status": "pending"})

    def done(self, iid: str, key: str) -> bool:
        return self.task(iid)["steps"].get(key, {}).get("status") == "done"


# ------------------------------------------------------------ rate limits


LIMIT_PATTERNS = re.compile(
    r"usage limit|rate limit|rate_limit|hit your limit|reached your .*limit|limit reached|"
    r"session limit|weekly limit|429|overloaded|529|resets? (at )?\d",
    re.IGNORECASE,
)
AUTH_PATTERNS = re.compile(
    r"invalid api key|authentication_error|oauth token has expired|please run /login|not logged in|401",
    re.IGNORECASE,
)


def parse_reset(text: str, now: dt.datetime | None = None) -> dt.datetime | None:
    """Find a reset time in a limit message. The container runs with TZ=UTC."""
    now = now or dt.datetime.now(dt.UTC)
    m = re.search(r"\|(\d{10})\b", text)
    if m:
        return dt.datetime.fromtimestamp(int(m.group(1)), dt.UTC)
    m = re.search(
        r"reset[s]?\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*(?:\(([^)]+)\))?",
        text,
        re.IGNORECASE,
    )
    if not m:
        return None
    hour, minute = int(m.group(1)), int(m.group(2) or 0)
    ampm = (m.group(3) or "").lower()
    if ampm == "pm" and hour != 12:
        hour += 12
    if ampm == "am" and hour == 12:
        hour = 0
    tz = dt.UTC
    if m.group(4):
        with contextlib.suppress(Exception):
            tz = ZoneInfo(m.group(4).strip())
    local_now = now.astimezone(tz)
    cand = local_now.replace(hour=hour % 24, minute=minute, second=0, microsecond=0)
    if cand <= local_now:
        cand += dt.timedelta(days=1)
    return cand.astimezone(dt.UTC)


def sleep_until(study: Study, until: dt.datetime, reason: str) -> None:
    study.state["waiting"] = {"until": until.isoformat(timespec="seconds"), "reason": reason}
    study.save()
    log(f"rate limit: sleeping until {until.isoformat(timespec='seconds')} ({reason[:160]})")
    while True:
        left = (until - dt.datetime.now(dt.UTC)).total_seconds()
        if left <= 0:
            break
        time.sleep(min(left, 60))
    study.state.pop("waiting", None)
    study.save()


# ---------------------------------------------------------- transcripts


EDIT_TOOLS = {"Edit", "MultiEdit", "Write", "NotebookEdit"}
TIMING_RE = re.compile(
    r"timeit|perf_counter|time\.time\(|process_time|/usr/bin/time|\btime\s+python|hyperfine|"
    r"cProfile|profile\b|pyinstrument|py-spy|line_profiler|kernprof|yappi|scalene|memray|perf stat|"
    r"--durations|asv\b",
    re.IGNORECASE,
)
PROFILER_RE = re.compile(
    r"cProfile|pstats|pyinstrument|py-spy|line_profiler|kernprof|yappi|scalene|perf record|perf stat", re.IGNORECASE
)
# Bash commands that write files: in-place sed/perl, patches, and Python heredocs that
# open a file for writing. Counted as an edit only when the command names a tracked file.
BASH_EDIT_RE = re.compile(
    r"\bsed\s+-i|\bgit\s+apply\b|\bpatch\s+-p|\bperl\s+-pi|open\([^)]*,\s*['\"][wa]|write_text\(|"
    r"\bcat\s*>\s*\S+\.py|\btee\s+\S+\.py",
    re.IGNORECASE,
)


def _rel(path: str) -> str:
    p = path.replace("\\", "/")
    for prefix in ("/testbed/", "./"):
        p = p.removeprefix(prefix)
    return p


def analyze_transcript(lines: list[str], tracked: set[str]) -> dict:
    """Pull per-run metrics out of a stream-json transcript."""
    events = []
    for line in lines:
        line = line.strip()
        if not line.startswith("{"):
            continue
        with contextlib.suppress(json.JSONDecodeError):
            events.append(json.loads(line))
    init = next((e for e in events if e.get("type") == "system" and e.get("subtype") == "init"), {})
    result = next((e for e in reversed(events) if e.get("type") == "result"), None)

    tool_calls: list[dict] = []
    for e in events:
        if e.get("type") != "assistant":
            continue
        for block in (e.get("message") or {}).get("content") or []:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                tool_calls.append({"name": block.get("name"), "input": block.get("input") or {}})

    tool_counts: dict[str, int] = defaultdict(int)
    for c in tool_calls:
        tool_counts[c["name"]] += 1

    skill_calls = [
        c for c in tool_calls
        if c["name"] == "Skill" and "performance-ladder-review" in json.dumps(c["input"])
    ]

    # First edit to a tracked repository file.
    first_edit = None
    for idx, c in enumerate(tool_calls):
        if c["name"] in EDIT_TOOLS:
            path = c["input"].get("file_path") or c["input"].get("notebook_path") or ""
            if _rel(path) in tracked:
                first_edit = idx
                break
        if c["name"] == "Bash" and BASH_EDIT_RE.search(c["input"].get("command", "")):
            cmd = c["input"].get("command", "")
            if any("/" in t and t in cmd for t in tracked):
                first_edit = idx
                break
    before = tool_calls if first_edit is None else tool_calls[:first_edit]

    # Scripts written before the first edit that contain timing code count when run.
    timing_scripts = set()
    for c in before:
        if c["name"] == "Write" and TIMING_RE.search(c["input"].get("content", "")):
            timing_scripts.add(Path(c["input"].get("file_path", "")).name)
    timed = profiled = False
    for c in before:
        if c["name"] != "Bash":
            continue
        cmd = c["input"].get("command", "")
        if TIMING_RE.search(cmd) or any(s and s in cmd for s in timing_scripts):
            timed = True
        if PROFILER_RE.search(cmd):
            profiled = True
    for c in before:
        if c["name"] == "Write" and PROFILER_RE.search(c["input"].get("content", "")):
            name = Path(c["input"].get("file_path", "")).name
            if any(name and name in d["input"].get("command", "") for d in before if d["name"] == "Bash"):
                profiled = True

    usage = (result or {}).get("usage") or {}
    return {
        "has_result": result is not None,
        "result_subtype": (result or {}).get("subtype"),
        "is_error": (result or {}).get("is_error"),
        "result_text": ((result or {}).get("result") or "")[:2000],
        "session_id": (result or init).get("session_id"),
        "init_model": init.get("model"),
        "init_cli_version": init.get("claude_code_version"),
        "init_skills": init.get("skills"),
        "init_tools": init.get("tools"),
        "init_mcp_servers": init.get("mcp_servers"),
        "init_plugins": init.get("plugins"),
        "num_turns": (result or {}).get("num_turns"),
        "duration_ms": (result or {}).get("duration_ms"),
        "duration_api_ms": (result or {}).get("duration_api_ms"),
        "total_cost_usd": (result or {}).get("total_cost_usd"),
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "cache_creation_input_tokens": usage.get("cache_creation_input_tokens"),
        "cache_read_input_tokens": usage.get("cache_read_input_tokens"),
        "model_usage": (result or {}).get("modelUsage"),
        "tool_calls": len(tool_calls),
        "tool_counts": dict(tool_counts),
        "skill_fired": bool(skill_calls),
        "skill_calls": len(skill_calls),
        "first_edit_tool_index": first_edit,
        "timing_before_first_edit": timed,
        "profiler_before_first_edit": profiled,
    }


# ------------------------------------------------------------- docker ops


def docker(*args: str, check: bool = True, timeout: float | None = None) -> subprocess.CompletedProcess:
    return sh(["docker", *args], check=check, timeout=timeout)


def image_present(image: str) -> bool:
    return docker("image", "inspect", image, check=False).returncode == 0


def image_size(image: str) -> int | None:
    r = docker("image", "inspect", "-f", "{{.Size}}", image, check=False)
    return int(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip().isdigit() else None


def eval_tag(iid: str) -> str:
    return f"sweb.eval.x86_64.{iid}:latest"


def remove_task_images(iid: str) -> None:
    for ref in (eval_tag(iid), IMAGE_TEMPLATE.format(iid=iid)):
        docker("image", "rm", "-f", ref, check=False, timeout=600)


def agent_containers() -> list[str]:
    r = docker("ps", "-a", "--filter", "label=plr.role=agent", "--format", "{{.Names}}", check=False)
    return [n for n in r.stdout.split() if n]


# --------------------------------------------------------------- prompt


def render_prompt(row: dict) -> str:
    """Render the official SWE-fficiency instruction template, unchanged.

    The official spec leaves workspace_dir_name unset, which renders /testbed/repo even
    though the repository is checked out at /testbed. It is set to the empty string so the
    <uploaded_files> path points at the real checkout (/testbed/). Both arms get the
    identical text.
    """
    import jinja2

    text = (harness_dir() / PROMPT_TEMPLATE_REL).read_text()
    env = jinja2.Environment(undefined=jinja2.StrictUndefined, keep_trailing_newline=True)
    return env.from_string(text).render(instance=row, vars={"workspace_dir_name": ""})


# ------------------------------------------------------------- agent run


def build_config_dir(arm: str, cred_src: Path) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="plr-cfg-", dir=WORKDIR / "tmp"))
    os.chmod(tmp, 0o700)
    cfg = tmp / "cfg"
    cfg.mkdir()
    shutil.copyfile(cred_src, cfg / ".credentials.json")
    os.chmod(cfg / ".credentials.json", 0o600)
    if arm == ARM_SKILL:
        shutil.copytree(SKILL_DIR, cfg / "skills" / "performance-ladder-review")
    return tmp


def sync_refreshed_credentials(container: str, sent_hash: str, cred_src: Path) -> str:
    """If the CLI refreshed its OAuth token during the run, carry the new token home.

    Refresh tokens rotate on use, so a refreshed copy left inside a deleted container
    would leave the source file holding a dead refresh token. The write-back only
    happens when the source file is unchanged since the copy was made (compare-and-swap).
    """
    tmpdir = Path(tempfile.mkdtemp(prefix="plr-cred-", dir=WORKDIR / "tmp"))
    try:
        r = docker("cp", f"{container}:{CONTAINER_CFG}/.credentials.json", str(tmpdir / "c.json"), check=False)
        if r.returncode != 0:
            return "missing"
        got = tmpdir / "c.json"
        if sha256_file(got) == sent_hash:
            return "unchanged"
        try:
            json.loads(got.read_text())
        except json.JSONDecodeError:
            return "refreshed-but-unreadable"
        if sha256_file(cred_src) != sent_hash:
            return "refreshed-but-source-changed"
        shutil.copyfile(got, cred_src.with_name(cred_src.name + ".plr-tmp"))
        os.replace(cred_src.with_name(cred_src.name + ".plr-tmp"), cred_src)
        return "refreshed-written-back"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def run_agent(study: Study, cfg: dict, row: dict, arm: str, k: int, cpuset: dict) -> dict:
    iid = row["instance_id"]
    run_dir = study.dir / "runs" / iid / f"{arm}-r{k}"
    run_dir.mkdir(parents=True, exist_ok=True)
    name = f"plr-{study.name}-{iid}-{arm}-r{k}".replace("_", "-")[:120]
    image = IMAGE_TEMPLATE.format(iid=iid)
    docker("rm", "-f", name, check=False)

    prompt = render_prompt(row)
    (run_dir / "prompt.txt").write_text(prompt)
    cred_src = find_credentials()
    cfg_tmp = build_config_dir(arm, cred_src)
    sent_hash = sha256_file(cfg_tmp / "cfg" / ".credentials.json")
    meta: dict = {"container": name, "arm": arm, "run": k, "instance_id": iid}
    try:
        docker(
            "create", "--name", name, "--label", "plr.role=agent", "--user", "root", "-w", "/testbed",
            "--cpuset-cpus", cpuset["cpuset_cpus"], "--cpuset-mems", cpuset["cpuset_mems"],
            "--cpus", str(cpuset["cpus"]), "--memory", cfg["mem_limit"], "--memory-swap", cfg["mem_limit"],
            "-e", "TZ=UTC", image, "tail", "-f", "/dev/null",
        )
        docker("start", name)
        docker("cp", str(cli_binary(cfg["cli_version"])), f"{name}:/usr/local/bin/claude", timeout=600)
        docker("cp", str(run_dir / "prompt.txt"), f"{name}:{CONTAINER_PROMPT}")
        docker("cp", str(cfg_tmp / "cfg"), f"{name}:{CONTAINER_CFG}")
    finally:
        shutil.rmtree(cfg_tmp, ignore_errors=True)  # host copy of the credentials goes now

    base = docker("exec", name, "git", "-C", "/testbed", "rev-parse", "HEAD").stdout.strip()
    meta["base_commit_in_container"] = base

    claude_cmd = (
        f"timeout -k 30 {cfg['run_timeout_sec']} claude -p --output-format stream-json --verbose "
        f"--model {shlex.quote(cfg['model'])} --max-turns {cfg['max_turns']} "
        f"--dangerously-skip-permissions < {CONTAINER_PROMPT}"
    )
    env = {"CLAUDE_CONFIG_DIR": CONTAINER_CFG, "IS_SANDBOX": "1", **ISOLATION_ENV}
    exec_cmd = ["docker", "exec", "-w", "/testbed"]
    for k_, v in env.items():
        exec_cmd += ["-e", f"{k_}={v}"]
    exec_cmd += [name, "/bin/bash", "-lc", claude_cmd]

    t0 = time.time()
    meta["started_at"] = now_iso()
    with open(run_dir / "transcript.jsonl", "w") as out, open(run_dir / "stderr.log", "w") as err:
        try:
            proc = subprocess.run(exec_cmd, check=False, stdout=out, stderr=err, timeout=cfg["run_timeout_sec"] + 300)
            meta["exit_code"] = proc.returncode
        except subprocess.TimeoutExpired:
            meta["exit_code"] = "host-timeout"
            docker("exec", name, "pkill", "-f", "claude", check=False)
    meta["wall_sec"] = round(time.time() - t0, 1)
    meta["finished_at"] = now_iso()
    meta["timed_out"] = meta["exit_code"] in (124, 137, "host-timeout")

    meta["credentials"] = sync_refreshed_credentials(name, sent_hash, cred_src)

    diff = docker("exec", "-w", "/testbed", name, "/bin/bash", "-lc", "git diff --binary HEAD", check=False, timeout=600)
    (run_dir / "patch.diff").write_text(diff.stdout)
    meta["patch_bytes"] = len(diff.stdout.encode())
    stat = docker("exec", "-w", "/testbed", name, "git", "diff", "--stat", "HEAD", check=False)
    (run_dir / "diffstat.txt").write_text(stat.stdout)
    tracked_out = docker("exec", "-w", "/testbed", name, "git", "ls-files", check=False, timeout=300).stdout
    (run_dir / "tracked.txt").write_text(tracked_out)
    tracked = set(tracked_out.splitlines())
    docker("rm", "-f", name, check=False, timeout=600)

    lines = (run_dir / "transcript.jsonl").read_text(errors="replace").splitlines()
    metrics = analyze_transcript(lines, tracked)
    meta.update(metrics)
    stderr_text = (run_dir / "stderr.log").read_text(errors="replace")[-4000:]
    meta["stderr_tail"] = stderr_text[-800:]

    errored = bool(metrics.get("is_error")) or not metrics["has_result"]
    result_text = (metrics.get("result_text") or "") if errored else ""
    failure_text = f"{result_text} {stderr_text}"
    if metrics.get("result_subtype") == "error_max_turns":
        meta["outcome"] = "error_max_turns"
    elif errored and AUTH_PATTERNS.search(failure_text) and not metrics.get("num_turns"):
        meta["outcome"] = "auth_error"
    elif errored and LIMIT_PATTERNS.search(failure_text):
        meta["outcome"] = "rate_limited"
        reset = parse_reset(failure_text)
        meta["reset_at"] = reset.isoformat(timespec="seconds") if reset else None
    elif meta["timed_out"]:
        meta["outcome"] = "timeout"
    elif not metrics["has_result"]:
        meta["outcome"] = "crashed"
    else:
        meta["outcome"] = metrics.get("result_subtype") or "success"
    atomic_write_json(run_dir / "metrics.json", meta)
    return meta


# ----------------------------------------------------------------- scoring


def model_name(arm: str, k: int) -> str:
    return f"plr-{arm}-r{k}"


def swefficiency_cli(args: list[str], cwd: Path, log_file: Path, timeout: int) -> int:
    uv = shutil.which("uv") or str(Path.home() / ".local" / "bin" / "uv")
    cmd = [uv, "run", "--project", str(harness_dir()), "swefficiency", *args]
    with open(log_file, "a") as f:
        f.write(f"\n$ {' '.join(shlex.quote(c) for c in cmd)}\n")
        f.flush()
        proc = subprocess.run(cmd, check=False, cwd=cwd, stdout=f, stderr=subprocess.STDOUT, timeout=timeout)
    return proc.returncode


def score(study: Study, cfg: dict, iid: str, model: str, patch_path: Path | None) -> dict:
    """Run the official evaluation for one instance and one prediction set."""
    if agent_containers():
        raise RuntimeError("an agent container is running; refusing to score (timing noise)")
    sdir = study.dir / "scoring"
    sdir.mkdir(exist_ok=True)
    log_file = sdir / f"{iid}.{model}.log"
    args = ["eval", "--run_id", study.name, "--num_workers", "1", "--instances_regex", f"^{re.escape(iid)}$", "--force_rerun"]
    if patch_path is not None:
        pred_dir = sdir / "predictions" / model
        pred_dir.mkdir(parents=True, exist_ok=True)
        pred_file = pred_dir / f"{iid}.jsonl"
        pred = {"instance_id": iid, "model_patch": patch_path.read_text(), "model_name_or_path": model}
        pred_file.write_text(json.dumps(pred) + "\n")
        args += ["--prediction_path", str(pred_file)]
    t0 = time.time()
    rc = swefficiency_cli(args, sdir, log_file, cfg["score_timeout_sec"] + 600)
    res = {"eval_exit_code": rc, "eval_wall_sec": round(time.time() - t0, 1)}
    inst_dir = sdir / "logs" / "run_evaluation" / study.name / model / iid
    perf = inst_dir / "perf_summary.txt"
    res["perf_summary"] = perf.read_text() if perf.exists() else None
    res["correctness_ran"] = (inst_dir / "covering_test_status.json").exists()
    return res


def report_row(study: Study, iid: str, model: str) -> dict | None:
    sdir = study.dir / "scoring"
    gold = sdir / "logs" / "run_evaluation" / study.name / "gold"
    pred = sdir / "logs" / "run_evaluation" / study.name / model
    out = sdir / "reports"
    log_file = sdir / f"{iid}.{model}.report.log"
    rc = swefficiency_cli(
        ["report", "--gold_run", str(gold), "--pred_run", str(pred), "--report_output", str(out), "--num_workers", "4"],
        sdir, log_file, 3600,
    )
    csv_path = out / f"eval_report_{model}.csv"
    if rc != 0 or not csv_path.exists():
        return None
    with open(csv_path) as f:
        for r in csv.DictReader(f):
            if r["instance_id"] == iid:
                return {k: _num(v) for k, v in r.items()}
    return None


def _num(v: str):
    try:
        return float(v)
    except (TypeError, ValueError):
        return v


# --------------------------------------------------------------------- run


def arm_order(task_pos: int, k: int, arms: list[str]) -> list[str]:
    """Counterbalance which arm goes first: alternate by task position and run index."""
    return list(arms) if (task_pos + k) % 2 == 0 else list(reversed(arms))


def cmd_run(args) -> None:
    tasks_doc = json.loads(TASKS_FILE.read_text())
    tasks = tasks_doc["tasks"]
    if args.tasks:
        tasks = tasks[: args.tasks]
    if args.only:
        tasks = [t for t in tasks if t["instance_id"] in args.only]

    study = Study(args.study)
    study.lock()
    (WORKDIR / "tmp").mkdir(exist_ok=True)
    cfg = dict(DEFAULTS)
    cfg.update({"model": args.model, "cli_version": args.cli_version, "runs": args.runs})
    prev = study.state.get("config")
    if prev and any(prev.get(key) != cfg.get(key) for key in ("model", "cli_version", "max_turns", "run_timeout_sec")):
        sys.exit(f"study {study.name} was started with a different config: {prev}")
    cpuset = pinned_cpuset()
    study.state.setdefault("config", {**cfg, "cpuset": cpuset, "harness_commit": HARNESS_COMMIT,
                                      "dataset_revision": tasks_doc["method"]["dataset_revision"],
                                      "cli_sha256": sha256_file(cli_binary(cfg["cli_version"])),
                                      "skill_tree_sha256": tree_hash(SKILL_DIR)})
    study.state.setdefault("created_at", now_iso())
    study.save()

    rev_now = dataset_sha()
    if rev_now != tasks_doc["method"]["dataset_revision"]:
        log(f"WARNING: dataset revision moved ({rev_now}); the official harness loads the latest revision")
    rows = load_dataset_rows(tasks_doc["method"]["dataset_revision"])

    for t in tasks:
        iid = t["instance_id"]
        st = study.task(iid)
        if st.get("complete"):
            log(f"{iid}: complete, skipping")
            continue
        row = rows[iid]
        st.setdefault("position", t["position"])
        image = IMAGE_TEMPLATE.format(iid=iid)

        # 1. pull
        if not image_present(image):
            need = t["image_compressed_bytes"] * 3.5 / 1e9 + 8
            have = free_gb("/mnt/c") if os.path.isdir("/mnt/c") else free_gb("/")
            if have < need:
                sys.exit(f"{iid}: only {have:.1f} GB free on the disk holding the WSL image, need about {need:.1f}")
            s = study.step(iid, "pull")
            s["disk_before"] = disk_snapshot()
            t0 = time.time()
            log(f"{iid}: pulling {image}")
            docker("pull", image, timeout=7200)
            s.update(status="done", pull_sec=round(time.time() - t0, 1), image_bytes=image_size(image),
                     disk_after=disk_snapshot(), at=now_iso())
            study.save()
        elif not study.done(iid, "pull"):
            study.step(iid, "pull").update(status="done", note="image already local", image_bytes=image_size(image),
                                           disk_after=disk_snapshot(), at=now_iso())
            study.save()
        docker("tag", image, eval_tag(iid))  # keeps the scorer from deleting and re-pulling between evals

        # 2. agent runs
        for k in range(1, args.runs + 1):
            for arm in arm_order(t["position"], k, cfg["arms"]):
                key = f"agent:{arm}:{k}"
                if study.done(iid, key):
                    continue
                while True:
                    s = study.step(iid, key)
                    s["attempts"] = s.get("attempts", 0) + 1
                    s["status"] = "running"
                    study.save()
                    log(f"{iid}: agent {arm} r{k} (attempt {s['attempts']})")
                    meta = run_agent(study, cfg, row, arm, k, cpuset)
                    s["last"] = {key_: meta.get(key_) for key_ in ("outcome", "wall_sec", "num_turns", "reset_at")}
                    if meta["outcome"] == "auth_error":
                        s["status"] = "auth_error"
                        study.save()
                        sys.exit(f"{iid}: authentication failed; sign in to Claude Code again (see README). "
                                 f"Rerun the same command afterwards to resume.")
                    if meta["outcome"] == "rate_limited":
                        s.setdefault("limit_hits", []).append({"at": now_iso(), "reset_at": meta.get("reset_at")})
                        s["status"] = "pending"
                        study.save()
                        backoff = dt.datetime.now(dt.UTC) + dt.timedelta(seconds=cfg["limit_backoff_sec"])
                        until = backoff
                        if meta.get("reset_at"):
                            parsed = dt.datetime.fromisoformat(meta["reset_at"]) + dt.timedelta(minutes=2)
                            if dt.datetime.now(dt.UTC) < parsed < backoff + dt.timedelta(days=8):
                                until = parsed
                        sleep_until(study, until, meta.get("result_text") or meta.get("stderr_tail") or "")
                        continue  # rerun this arm from a fresh container
                    s.update(status="done", metrics=meta, at=now_iso())
                    study.save()
                    log(f"{iid}: {arm} r{k} -> {meta['outcome']}, {meta['wall_sec']} s, "
                        f"{meta.get('num_turns')} turns, skill_fired={meta.get('skill_fired')}")
                    break

        # 3. scoring with the official harness (no agent is running at this point)
        jobs = [("gold", None)] + [
            (model_name(arm, k), study.dir / "runs" / iid / f"{arm}-r{k}" / "patch.diff")
            for k in range(1, args.runs + 1) for arm in cfg["arms"]
        ]
        for model, patch in jobs:
            key = f"score:{model}"
            if study.done(iid, key):
                continue
            s = study.step(iid, key)
            s["status"] = "running"
            study.save()
            log(f"{iid}: scoring {model}")
            res = score(study, cfg, iid, model, patch)
            s.update(res)
            s["status"] = "done" if res["eval_exit_code"] == 0 else "error"
            s["at"] = now_iso()
            study.save()
            if res["eval_exit_code"] != 0:
                sys.exit(f"{iid}: official eval failed for {model}; see {study.dir / 'scoring'}")

        for model, _ in jobs[1:]:
            key = f"report:{model}"
            if study.done(iid, key):
                continue
            row_out = report_row(study, iid, model)
            s = study.step(iid, key)
            s.update(status="done" if row_out else "error", row=row_out, at=now_iso())
            study.save()

        # 4. cleanup
        s = study.step(iid, "cleanup")
        s["disk_before"] = disk_snapshot()
        remove_task_images(iid)
        docker("container", "prune", "-f", "--filter", "label=plr.role=agent", check=False)
        s.update(status="done", disk_after=disk_snapshot(), at=now_iso())
        st["complete"] = True
        study.save()
        export_runs(study)
        log(f"{iid}: complete")
    export_runs(study)
    log("all requested tasks complete")


def tree_hash(root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file():
            h.update(str(p.relative_to(root)).replace("\\", "/").encode())
            h.update(p.read_bytes())
    return h.hexdigest()


def export_runs(study: Study) -> None:
    """Flatten the checkpoint into runs.jsonl (one line per agent run) for analyze.py."""
    out = []
    for iid, t in (study.state.get("tasks") or {}).items():
        steps = t["steps"]
        for key, s in steps.items():
            if not key.startswith("agent:") or s.get("status") != "done":
                continue
            _, arm, k = key.split(":")
            m = s["metrics"]
            rep = (steps.get(f"report:{model_name(arm, int(k))}") or {}).get("row") or {}
            out.append({
                "study": study.name, "instance_id": iid, "position": t.get("position"), "arm": arm, "run": int(k),
                "outcome": m.get("outcome"), "attempts": s.get("attempts"),
                "correct": rep.get("correctness"), "correctness_pct": rep.get("correctness_pct"),
                "raw_speedup": rep.get("raw_pred_speedup_ratio"), "speedup": rep.get("pred_speedup_ratio"),
                "gold_speedup": rep.get("gold_speedup_ratio"), "speedup_vs_expert": rep.get("human_speedup_ratio"),
                "wall_sec": m.get("wall_sec"), "duration_ms": m.get("duration_ms"), "num_turns": m.get("num_turns"),
                "input_tokens": m.get("input_tokens"), "output_tokens": m.get("output_tokens"),
                "cache_creation_input_tokens": m.get("cache_creation_input_tokens"),
                "cache_read_input_tokens": m.get("cache_read_input_tokens"),
                "total_cost_usd_equiv": m.get("total_cost_usd"), "tool_calls": m.get("tool_calls"),
                "skill_fired": m.get("skill_fired"), "skill_calls": m.get("skill_calls"),
                "skill_listed": "performance-ladder-review" in json.dumps(m.get("init_skills") or []),
                "timing_before_first_edit": m.get("timing_before_first_edit"),
                "profiler_before_first_edit": m.get("profiler_before_first_edit"),
                "patch_bytes": m.get("patch_bytes"), "model": m.get("init_model"),
                "cli_version": m.get("init_cli_version"), "started_at": m.get("started_at"),
            })
    out.sort(key=lambda r: (r["position"] or 0, r["arm"], r["run"]))
    with open(study.dir / "runs.jsonl", "w") as f:
        f.writelines(json.dumps(r) + "\n" for r in out)


# --------------------------------------------------------------- preflight


def cmd_preflight(args) -> None:
    """One-turn probe per arm on the host (not in a task container)."""
    (WORKDIR / "tmp").mkdir(exist_ok=True)
    cred_src = find_credentials()
    for arm in DEFAULTS["arms"]:
        tmp = build_config_dir(arm, cred_src)
        sent = sha256_file(tmp / "cfg" / ".credentials.json")
        try:
            env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE", "ANTHROPIC"))}
            env.update(CLAUDE_CONFIG_DIR=str(tmp / "cfg"), **ISOLATION_ENV)
            r = subprocess.run(
                [str(cli_binary(args.cli_version)), "-p", "--output-format", "stream-json", "--verbose",
                 "--model", args.model, "--max-turns", "1", "Reply with the single word OK."],
                check=False, cwd=tmp, env=env, capture_output=True, text=True, timeout=300,
            )
            m = analyze_transcript(r.stdout.splitlines(), set())
            new = tmp / "cfg" / ".credentials.json"
            if new.exists() and sha256_file(new) != sent and sha256_file(cred_src) == sent:
                shutil.copyfile(new, cred_src)
            print(json.dumps({
                "arm": arm, "exit": r.returncode, "model": m["init_model"], "cli": m["init_cli_version"],
                "skill_listed": "performance-ladder-review" in json.dumps(m["init_skills"] or []),
                "skills": m["init_skills"], "mcp_servers": m["init_mcp_servers"], "plugins": m["init_plugins"],
                "result": m["result_text"][:200], "is_error": m["is_error"],
                "usage": {k: m[k] for k in ("input_tokens", "output_tokens", "cache_creation_input_tokens",
                                            "cache_read_input_tokens")},
                "model_usage_keys": list((m["model_usage"] or {}).keys()),
                "stderr": r.stderr[-300:],
            }, indent=1))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


def cmd_reanalyze(args) -> None:
    """Recompute transcript metrics from saved transcripts, then re-export runs.jsonl."""
    study = Study(args.study)
    study.lock()
    for iid, t in (study.state.get("tasks") or {}).items():
        for key, s in t["steps"].items():
            if not key.startswith("agent:") or s.get("status") != "done":
                continue
            _, arm, k = key.split(":")
            run_dir = study.dir / "runs" / iid / f"{arm}-r{k}"
            tracked_file = run_dir / "tracked.txt"
            tracked = set(tracked_file.read_text().splitlines()) if tracked_file.exists() else set()
            lines = (run_dir / "transcript.jsonl").read_text(errors="replace").splitlines()
            s["metrics"].update(analyze_transcript(lines, tracked))
            s["metrics"]["tracked_list_available"] = tracked_file.exists()
            atomic_write_json(run_dir / "metrics.json", s["metrics"])
    study.save()
    export_runs(study)
    log(f"reanalyzed {study.name}")


def cmd_status(args) -> None:
    study = Study(args.study)
    tasks = study.state.get("tasks", {})
    print(json.dumps({"waiting": study.state.get("waiting"), "updated_at": study.state.get("updated_at")}))
    for iid, t in tasks.items():
        steps = {k: v.get("status") for k, v in t["steps"].items()}
        print(iid, "complete" if t.get("complete") else "in progress", json.dumps(steps))


def cmd_cleanup(args) -> None:
    for n in agent_containers():
        docker("rm", "-f", n, check=False)
    if args.images:
        tasks = json.loads(TASKS_FILE.read_text())["tasks"]
        for t in tasks:
            remove_task_images(t["instance_id"])
    log("cleanup done")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("select")
    p = sub.add_parser("setup")
    p.add_argument("--cli-version", default=DEFAULTS["cli_version"])
    p = sub.add_parser("preflight")
    p.add_argument("--model", default=DEFAULTS["model"])
    p.add_argument("--cli-version", default=DEFAULTS["cli_version"])
    p = sub.add_parser("run")
    p.add_argument("--study", required=True, help="study name, e.g. pilot or full")
    p.add_argument("--tasks", type=int, help="use the first N tasks of tasks.json")
    p.add_argument("--only", nargs="*", help="restrict to these instance ids")
    p.add_argument("--runs", type=int, default=1, help="runs per arm per task")
    p.add_argument("--model", default=DEFAULTS["model"])
    p.add_argument("--cli-version", default=DEFAULTS["cli_version"])
    p = sub.add_parser("status")
    p.add_argument("--study", required=True)
    p = sub.add_parser("reanalyze")
    p.add_argument("--study", required=True)
    p = sub.add_parser("cleanup")
    p.add_argument("--images", action="store_true", help="also remove every task image from tasks.json")
    args = ap.parse_args()
    {"select": cmd_select, "setup": cmd_setup, "preflight": cmd_preflight, "run": cmd_run,
     "status": cmd_status, "reanalyze": cmd_reanalyze, "cleanup": cmd_cleanup}[args.cmd](args)


if __name__ == "__main__":
    main()
