# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Summarize an A/B study written by run.py.

Reads runs.jsonl (one line per agent run, exported by run.py) and writes:
  <out>/runs.csv        every run with its score and cost
  <out>/ab_tasks.csv    per-task paired comparison
  <out>/ab_summary.csv  per-arm aggregates and paired statistics
  <out>/ab_report.md    a short report

Speedup here is the official SWE-fficiency speedup ratio versus the expert patch
(human_speedup_ratio in the harness report): the correctness-adjusted model speedup
divided by the expert speedup. A run that fails correctness counts as speedup 1.0
before that division, exactly as the official report does.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
from collections import defaultdict
from pathlib import Path

ARMS = ("baseline", "skill")
TIE_BAND = math.log(1.05)  # |log ratio| below this is a tie (5 percent either way)
FLOOR = 0.001  # the official report floors the per-task ratio at 0.001
BOOT_N = 10_000
BOOT_SEED = 12345
MIN_BOOT_TASKS = 5  # with fewer paired tasks a bootstrap CI says nothing; none is reported


def load_runs(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def logsr(r: dict) -> float | None:
    v = r.get("speedup_vs_expert")
    if v is None or isinstance(v, str):
        return None
    return math.log(max(float(v), FLOOR))


def hmean(xs: list[float]) -> float | None:
    xs = [max(x, FLOOR) for x in xs]
    return len(xs) / sum(1 / x for x in xs) if xs else None


def mean(xs):
    xs = [x for x in xs if x is not None]
    return statistics.fmean(xs) if xs else None


def median(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def rate(xs):
    xs = [bool(x) for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def boot_ci(values: list[float], stat, n=BOOT_N, seed=BOOT_SEED):
    if len(values) < MIN_BOOT_TASKS:
        return None, None
    rng = random.Random(seed)
    draws = sorted(stat([rng.choice(values) for _ in values]) for _ in range(n))
    return draws[int(0.025 * n)], draws[int(0.975 * n) - 1]


def fmt(x, nd=3):
    if x is None:
        return "n/a"
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return str(x)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("runs", type=Path, help="runs.jsonl from the study directory")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--label", default=None, help="label for the report, e.g. PILOT")
    args = ap.parse_args()

    runs = load_runs(args.runs)
    study = runs[0]["study"] if runs else "unknown"
    label = args.label or ("PILOT" if "pilot" in study else "")
    args.out.mkdir(parents=True, exist_ok=True)

    # Per-run table.
    cols = list(runs[0].keys()) if runs else []
    with open(args.out / "runs.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in runs:
            w.writerow(r)

    # Per task and arm: geometric mean of the speedup ratio over runs.
    by = defaultdict(lambda: defaultdict(list))
    for r in runs:
        by[r["instance_id"]][r["arm"]].append(r)
    unscored = [r for r in runs if logsr(r) is None]

    task_rows = []
    for iid in sorted(by, key=lambda i: min(r["position"] or 0 for a in by[i].values() for r in a)):
        row = {"instance_id": iid}
        for arm in ARMS:
            ls = [logsr(r) for r in by[iid].get(arm, []) if logsr(r) is not None]
            row[f"{arm}_runs"] = len(ls)
            row[f"{arm}_mean_log_sr"] = mean(ls)
            row[f"{arm}_sr"] = math.exp(row[f"{arm}_mean_log_sr"]) if ls else None
            row[f"{arm}_correct_rate"] = rate([r.get("correct") == 1.0 for r in by[iid].get(arm, [])])
        if row["baseline_runs"] and row["skill_runs"]:
            d = row["skill_mean_log_sr"] - row["baseline_mean_log_sr"]
            row["log_diff"] = d
            row["sr_ratio"] = math.exp(d)
            row["sr_diff"] = row["skill_sr"] - row["baseline_sr"]
            row["result"] = "tie" if abs(d) < TIE_BAND else ("win" if d > 0 else "loss")
        task_rows.append(row)
    paired = [r for r in task_rows if "log_diff" in r]

    with open(args.out / "ab_tasks.csv", "w", newline="") as f:
        fields = ["instance_id"] + [f"{a}_{k}" for a in ARMS for k in ("runs", "sr", "mean_log_sr", "correct_rate")] + [
            "sr_diff", "sr_ratio", "log_diff", "result"]
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in task_rows:
            w.writerow({k: r.get(k) for k in fields})

    # Per-arm aggregates over tasks (paired tasks only) and over runs (cost metrics).
    summary = []

    def add(metric, b, s, diff=None, lo=None, hi=None, n=None, note=""):
        summary.append({"metric": metric, "baseline": b, "skill": s, "diff_skill_minus_baseline": diff,
                        "ci95_low": lo, "ci95_high": hi, "n": n, "note": note})

    n = len(paired)
    b_log = [r["baseline_mean_log_sr"] for r in paired]
    s_log = [r["skill_mean_log_sr"] for r in paired]
    diffs = [r["log_diff"] for r in paired]
    lo, hi = boot_ci(diffs, statistics.fmean)
    add("mean_log_speedup_vs_expert", mean(b_log), mean(s_log), mean(diffs), lo, hi, n,
        "per-task mean of log SR over runs, then mean over tasks; CI = paired bootstrap over tasks")
    add("geometric_mean_speedup_vs_expert", math.exp(mean(b_log)) if b_log else None,
        math.exp(mean(s_log)) if s_log else None, math.exp(mean(diffs)) if diffs else None,
        math.exp(lo) if lo is not None else None, math.exp(hi) if hi is not None else None, n,
        "diff column is the skill/baseline ratio")
    b_sr = [r["baseline_sr"] for r in paired]
    s_sr = [r["skill_sr"] for r in paired]
    sr_diffs = [r["sr_diff"] for r in paired]
    lo, hi = boot_ci(sr_diffs, statistics.fmean)
    add("mean_paired_speedup_difference", mean(b_sr), mean(s_sr), mean(sr_diffs), lo, hi, n,
        "per-task SR (geometric mean over runs); diff = mean over tasks of skill SR minus baseline SR")
    add("median_speedup_vs_expert", median(b_sr), median(s_sr), median(sr_diffs), None, None, n,
        "diff column is the median of the per-task differences")
    hb, hs = hmean(b_sr), hmean(s_sr)
    pairs_idx = list(range(n))

    def hm_diff(idx):
        return hmean([s_sr[i] for i in idx]) - hmean([b_sr[i] for i in idx])

    lo, hi = boot_ci(pairs_idx, hm_diff)
    add("harmonic_mean_speedup_vs_expert", hb, hs, (hs - hb) if hb and hs else None, lo, hi, n,
        "the official SWE-fficiency aggregate (floor 0.001)")
    wins = sum(r["result"] == "win" for r in paired)
    ties = sum(r["result"] == "tie" for r in paired)
    losses = sum(r["result"] == "loss" for r in paired)
    add("win_tie_loss", None, None, f"{wins}/{ties}/{losses}", None, None, n,
        "skill vs baseline per task; tie = within 5 percent")

    arm_runs = {a: [r for r in runs if r["arm"] == a] for a in ARMS}
    add("runs", len(arm_runs["baseline"]), len(arm_runs["skill"]), None, None, None, None, "agent runs completed")
    add("correct_rate", rate([r.get("correct") == 1.0 for r in arm_runs["baseline"]]),
        rate([r.get("correct") == 1.0 for r in arm_runs["skill"]]), None, None, None, None, "per run")
    for key in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens",
                "num_turns", "wall_sec", "tool_calls", "total_cost_usd_equiv"):
        b = [r.get(key) for r in arm_runs["baseline"]]
        s = [r.get(key) for r in arm_runs["skill"]]
        mb, ms = mean(b), mean(s)
        add(f"mean_{key}", mb, ms, (ms - mb) if mb is not None and ms is not None else None, None, None, None, "per run")
        add(f"median_{key}", median(b), median(s), None, None, None, None, "per run")
    for key in ("skill_fired", "timing_before_first_edit", "profiler_before_first_edit"):
        add(f"rate_{key}", rate([r.get(key) for r in arm_runs["baseline"]]),
            rate([r.get(key) for r in arm_runs["skill"]]), None, None, None, None, "per run")

    with open(args.out / "ab_summary.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
        w.writeheader()
        for row in summary:
            w.writerow(row)

    # Markdown report.
    title = f"# SWE-fficiency A/B: performance-ladder-review ({label + ', ' if label else ''}study `{study}`)"
    lines = [title, ""]
    if label:
        lines += [f"**{label} numbers.** {len(paired)} paired task(s). These numbers show the harness works; "
                  "they are not evidence for or against the skill.", ""]
    lines += ["## Per run", "",
              "| Task | Arm | Run | Outcome | Correct | Speedup | Expert speedup | Speedup vs expert | Turns | Wall (s) "
              "| Output tokens | Skill fired | Timed before first edit |",
              "| --- | --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |"]
    for r in runs:
        lines.append(
            f"| {r['instance_id']} | {r['arm']} | {r['run']} | {r['outcome']} | {fmt(r.get('correct'), 0)} | "
            f"{fmt(r.get('speedup'))} | {fmt(r.get('gold_speedup'))} | {fmt(r.get('speedup_vs_expert'))} | "
            f"{fmt(r.get('num_turns'))} | {fmt(r.get('wall_sec'), 0)} | {fmt(r.get('output_tokens'))} | "
            f"{r.get('skill_fired')} | {r.get('timing_before_first_edit')} |")
    lines += ["", "## Paired by task", "",
              "| Task | Baseline SR | Skill SR | Skill / baseline | Result |", "| --- | ---: | ---: | ---: | --- |"]
    for r in task_rows:
        lines.append(f"| {r['instance_id']} | {fmt(r.get('baseline_sr'))} | {fmt(r.get('skill_sr'))} | "
                     f"{fmt(r.get('sr_ratio'))} | {r.get('result', 'unpaired')} |")
    lines += ["", "## Aggregates", "", "| Metric | Baseline | Skill | Skill minus baseline | 95% CI | n |",
              "| --- | ---: | ---: | ---: | --- | ---: |"]
    for s in summary:
        ci = f"{fmt(s['ci95_low'])} to {fmt(s['ci95_high'])}" if s["ci95_low"] is not None else "n/a"
        lines.append(f"| {s['metric']} | {fmt(s['baseline'])} | {fmt(s['skill'])} | "
                     f"{fmt(s['diff_skill_minus_baseline'])} | {ci} | {fmt(s['n'])} |")
    lines += ["", "## Notes", "",
              "- SR is the official speedup ratio versus the expert patch. Failed correctness counts as no speedup.",
              "- Per-task values are geometric means over runs. Ties are within 5 percent.",
              f"- Bootstrap: {BOOT_N} resamples of tasks with replacement, seed {BOOT_SEED}; no CI is reported with fewer than {MIN_BOOT_TASKS} paired tasks.",
              "- Token counts come from the CLI result event and cover the whole run.",
              "- 'Timed before first edit' is a transcript heuristic: a Bash call that runs timing or profiling code "
              "before the first edit to a tracked repository file.",
              ]
    if unscored:
        lines.append(f"- {len(unscored)} run(s) had no official score and are left out of the speedup statistics.")
    (args.out / "ab_report.md").write_text("\n".join(lines) + "\n")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
