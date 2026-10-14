# SWE-fficiency A/B benchmark

This directory holds an independent A/B test of the `performance-ladder-review` skill on
[SWE-fficiency](https://github.com/swefficiency/swefficiency) (ICML 2026; code Apache-2.0, data
CC-BY 4.0). Both arms run the same Claude Code CLI, model and prompt on the same task containers.
The only difference is that the skill arm has the skill installed. Scoring uses the official
SWE-fficiency harness, unchanged.

| File | Purpose |
| --- | --- |
| `run.py` | Orchestrator: task selection, setup, agent runs, official scoring, checkpoint and resume |
| `analyze.py` | Paired statistics and a short report from a study's `runs.jsonl` |
| `tasks.json` | The 40 sampled tasks, in study order, with the sampling method |
| `results/` | Published outputs (`results/pilot/` holds the pilot) |

## Method

### Tasks

The pool is the 411 SWE-fficiency instances that the reliability audit
([arXiv 2607.01211](https://arxiv.org/abs/2607.01211)) found "cross-machine original-rule valid":
the expert patch met the benchmark's own validity rule in all 12 replays (4 Google Cloud machine
types times 3 rounds). The audit publishes the list in its
[data repository](https://github.com/chenzhi-cz/performance-optimization-benchmark-reliability)
(`data/swefficiency_cross_machine_valid_tasks.csv`, pinned to commit `44a1cb8`). These are the
"replay-stable" instances.

`run.py select` draws 40 of them with seed 20261014, stratified by repository with proportional
allocation (largest remainder, at least one per repository). The pool is heavily pandas (236 of
411), so the sample is too (23 of 40). The first two tasks in `tasks.json` are the two with the
smallest compressed images (the pilot); the other 38 follow in a seeded shuffle. The Hugging Face
dataset revision is recorded in `tasks.json` and used for every later step.

### Agent runs

Each run starts a fresh container from the official instance image
(`ghcr.io/swefficiency/swefficiency-images:<instance_id>`), as the official inference harness
(`scripts/inference/custom.py`) does. The pinned Claude Code CLI binary (2.1.238, linux-x64, sha256
recorded in the study state) is copied into the container, and the agent runs inside it as root
from `/testbed` through `/bin/bash -lc`, the same way the official harness runs Cursor CLI. The
agent can therefore build, test, and time the workload in the exact environment the scorer uses.
This is more faithful than running the CLI in WSL and proxying commands through `docker exec`, and
it needs no Node.js because the CLI ships as a native binary.

Command, for both arms:

```text
timeout -k 30 3600 claude -p --output-format stream-json --verbose \
  --model claude-sonnet-5-5 --max-turns 100 --dangerously-skip-permissions < prompt.txt
```

- **Prompt.** The official SWE-fficiency instruction template
  (`scripts/inference/templates/cursor_instruction_prompt.txt.j2`), rendered with the instance row.
  The text is unchanged, quirks included (it mentions a `/workspace` directory and a "finish
  command"). One variable differs from the shipped spec: `workspace_dir_name` is set to the empty
  string, so `<uploaded_files>` reads `/testbed/` (where the repository actually is) and not
  `/testbed/repo`, which does not exist.
- **Model.** `claude-sonnet-5-5` for both arms, checked by `run.py preflight`. The init event of
  every run records the model actually used.
- **Caps.** 100 turns (`--max-turns`) and 60 minutes wall clock (`timeout`). SWE-fficiency's paper
  setup allows 3 hours and 100 actions; 60 minutes is the owner's budget choice.
- **Resources.** The container is pinned to the same 4 logical CPUs that the official scorer pins
  its single worker to (whole physical cores, first 4 cores reserved for the host), with the
  official 32 GB memory cap. The host has 15 GB, so the real limit is the host.

### Isolation and fairness controls

- Each run gets a fresh `CLAUDE_CONFIG_DIR` (`/root/.plr-claude` inside the container) holding only
  `.credentials.json`. The skill arm also gets `skills/performance-ladder-review/`, copied from this
  repository. Nothing else: no CLAUDE.md, settings, hooks, plugins, MCP servers, or memory.
- The CLI's bundled skills are switched off in both arms (`CLAUDE_CODE_DISABLE_BUNDLED_SKILLS=1`,
  `CLAUDE_CODE_DISABLE_POLICY_SKILLS=1`, `CLAUDE_CODE_DISABLE_CLAUDE_API_SKILL=1`). With them on,
  both arms would see `simplify`, `code-review`, `deep-research` and others. After the switch, the
  baseline arm lists only the built-in `doctor` command and the skill arm lists
  `performance-ladder-review` plus `doctor`. Each run's init event records the list.
- Auto-update and nonessential traffic are off (`DISABLE_AUTOUPDATER`,
  `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC`). The container clock is UTC.
- Same CLI binary, model, prompt, image, CPU set and caps in both arms. The study state records the
  CLI hash, the skill tree hash, the harness commit and the dataset revision, and a study refuses
  to resume under a different model or CLI version.
- Arm order alternates by task position and run index, so neither arm always runs first.
- The credentials file is never printed, logged, or committed. The host-side copy is deleted as
  soon as it is in the container, and the container is deleted after the run.

### What each run records

`runs/<instance>/<arm>-r<k>/` in the study directory holds `prompt.txt`, `transcript.jsonl` (the
full stream-json transcript), `stderr.log`, `patch.diff` (the prediction: `git diff --binary HEAD`
at the end of the run, as the official harness extracts it), `diffstat.txt`, `tracked.txt`, and
`metrics.json`:

- tokens (input, output, cache creation, cache read) and the CLI's cost-equivalent figure, from the
  final `result` event
- turns, CLI duration and wall time, tool calls by tool, outcome (success, max turns, timeout, crash)
- `skill_fired`: the transcript has a `Skill` tool call for `performance-ladder-review`
- `timing_before_first_edit` and `profiler_before_first_edit`: a heuristic over the transcript. The
  first edit is the first Edit, MultiEdit, Write or NotebookEdit call on a tracked repository file,
  or a Bash command that writes a file (`sed -i`, `git apply`, `patch`, a Python `open(..., "w")`
  heredoc) and names a tracked file. Before that point, a Bash call that runs timing code
  (`timeit`, `perf_counter`, `time python`, a script written earlier with timing code) sets the
  first flag; a profiler (`cProfile`, `pyinstrument`, `py-spy`, `line_profiler` and similar) sets
  the second.

### Scoring

Scoring is the official harness at commit `12d32a2`, run through its own CLI:

```text
swefficiency eval --run_id <study> --num_workers 1 --instances_regex '^<id>$' --force_rerun \
  [--prediction_path <one-line jsonl>]
swefficiency report --gold_run .../gold --pred_run .../<model name>
```

Each task is scored only after all of its agent runs finish, and `run.py` refuses to score while
any agent container exists, so agent work never overlaps a timing run. The gold (expert) patch is
scored once per task. Each agent run is scored as its own prediction set (`plr-<arm>-r<k>`). The
per-run numbers come from the official report CSV: `correctness`, `pred_speedup_ratio`,
`gold_speedup_ratio`, and `human_speedup_ratio` (speedup versus the expert, the benchmark's SR). A
run that fails the correctness tests scores speedup 1.0 before the division by the expert speedup,
as in the official report.

### Analysis

`analyze.py` takes the per-run SR, averages it in log space over the runs of each task and arm, and
pairs the arms by task. It reports the per-task difference, win/tie/loss (tie within 5 percent),
mean log SR, geometric mean, median, harmonic mean (the official aggregate, floored at 0.001), and
a 95 percent bootstrap CI over tasks (10,000 resamples, seed 12345; omitted below 5 paired tasks) for the mean paired log
difference, the mean paired SR difference, and the harmonic mean difference. It also reports
tokens, turns, wall time and tool calls per arm, and the rates of `skill_fired` and timing before
the first edit.

### Deviations from the official setup

- **Hardware.** A 16-thread laptop CPU (i9-11900H) under WSL2, not a GCP `n2-standard-64`. Laptop
  clocks move with temperature and power, so timings are noisier. The audit's stable task list
  reduces, but does not remove, this risk. Gold and prediction runs for a task are scored back to
  back on the same pinned cores.
- **Docker daemon pinning.** `scripts/vm/setup_docker.sh` pins dockerd to the first 4 physical
  cores and caps its memory. It needs sudo and a systemd-managed dockerd, so it has not been
  applied. The owner can run it once inside WSL (`sudo scripts/vm/setup_docker.sh 1G 800M` from the
  harness directory) before the full study.
- **Image reuse during scoring.** The scorer deletes the instance image after each evaluation and
  pulls it again for the next. `run.py` adds a local tag (`sweb.eval.x86_64.<id>:latest`) to the
  pulled image so the scorer treats it as pre-existing and keeps it. The image content is
  unchanged; this only saves repeated multi-GB pulls. `run.py` deletes both tags after the task.
- **Time cap.** 60 minutes per run instead of 3 hours.
- **Prompt variable.** `workspace_dir_name` as described above.

## How to run

Everything runs inside WSL, where Docker lives. Keep the work directory on the WSL file system
(default `~/plr-bench`, override with `PLR_WORKDIR`).

```bash
R=/mnt/c/Users/johnr/OneDrive/Documents/GitHub/performance-ladder-review/benchmark/run.py
uv run $R setup        # clone the harness at the pinned commit, fetch the pinned CLI
uv run $R preflight    # one-turn probe per arm: model, credentials, skill visibility
uv run $R run --study pilot --tasks 2 --runs 1     # the pilot
uv run $R run --study full --tasks 40 --runs 3    # the full study
uv run $R status --study full
uv run $R reanalyze --study full   # recompute transcript metrics from saved transcripts
uv run analyze.py ~/plr-bench/studies/full/runs.jsonl --out results/full
```

`run.py select` regenerates `tasks.json`; only run it to change the sample.

Credentials: `run.py` reads the Claude Code credentials file from `PLR_CREDENTIALS`, else
`~/.claude/.credentials.json` in WSL, else `/mnt/c/Users/johnr/.claude/.credentials.json`. If the
CLI refreshes its OAuth token during a run, the refreshed file is written back to the source, but
only when the source has not changed since it was copied. Refresh tokens rotate on use, so
dropping the refreshed copy would leave the owner's own file holding a dead token.

Run long studies detached so they survive a closed terminal, and keep a WSL session open (WSL can
stop an idle distribution):

```bash
setsid nohup uv run $R run --study full --tasks 40 --runs 3 > ~/plr-bench/studies/full.log 2>&1 &
```

## Resuming

`run.py` writes `studies/<study>/state.json` after every step: pull, each agent run, each scoring
job, each report, and cleanup. Rerunning the same command skips finished work. An agent run that
was interrupted is restarted from a fresh container; a scoring job that was interrupted is rerun
with `--force_rerun`.

Usage limits: when a run ends with a limit error (usage limit, rate limit, 429 or overloaded), the
run is discarded, the reset time is parsed from the message (a Unix timestamp after `|`, or "resets
3pm (Zone)"), and `run.py` sleeps until two minutes after it. With no parseable time it backs off
15 minutes. The arm then reruns from scratch, and the attempt count is kept in the state. An
authentication failure stops the study with a message; sign in again and rerun the same command.

## Pilot (2026-10-14)

The owner decided the pilot is the whole study: 2 tasks, 2 arms, 1 run per arm. Results are in
`results/pilot/` (`ab_report.md`, `ab_summary.csv`, `ab_tasks.csv`, `runs.csv`, and the four
patches) and summarized in the top-level README. Operational notes:

- All four agent runs ended on their own in 92 to 130 seconds and 9 to 15 turns. None hit a cap,
  a usage limit, or a retry, and none refreshed the OAuth token.
- Scoring dominated the time. Each official evaluation took 285 to 475 seconds, and a task with a
  gold run plus two predictions took 16 minutes (sympy) and 22 minutes (astropy). End to end, the
  tasks took 22 and 30 minutes, including a 92-second image pull for astropy.
- Saving `tracked.txt` and the wider first-edit heuristic were added while the pilot was running.
  For the pilot, `tracked.txt` was captured from each live container by hand (the same
  `git ls-files` command), and the metrics were recomputed with `run.py reanalyze`.

## Disk

Only one instance image is on disk at a time. Compressed images are 1.4 to 3.5 GB (3 to 12 GB
unpacked). `run.py` refuses to pull when free space on the drive holding the WSL disk is under
about 3.5 times the compressed size plus 8 GB. The WSL virtual disk grows to its high-water mark
and does not shrink when images are deleted; reclaiming that space on C: needs
`wsl --shutdown` and a compaction (`Optimize-VHD`, or `diskpart` with `compact vdisk`) on the
Windows side.
