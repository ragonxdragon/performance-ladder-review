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
| `results/` | Published outputs: `results/pilot/`, `results/pilot2/`, `results/round3/`, `results/combined/` |

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
  setup allows 3 hours and 100 actions; I capped runs at 60 minutes to fit a subscription budget.
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
a 95 percent bootstrap CI over tasks (10,000 resamples, seed 12345; omitted below 5 paired
tasks) for the mean paired log difference, the mean paired SR difference, and the harmonic mean
difference. It also reports tokens, turns, wall time and tool calls per arm, the rates of
`skill_fired` and timing before the first edit, and host-adjusted correctness. Tasks marked not
scorable are left out of the speedup statistics. Several `runs.jsonl` files can be passed at once
for a combined view.

### Deviations from the official setup

- **Hardware.** A 16-thread laptop CPU (i9-11900H) under WSL2, not a GCP `n2-standard-64`. Laptop
  clocks move with temperature and power, so timings are noisier. The audit's stable task list
  reduces, but does not remove, this risk. Gold and prediction runs for a task are scored back to
  back on the same pinned cores.
- **Docker daemon pinning.** `scripts/vm/setup_docker.sh` pins dockerd to the first 4 physical
  cores and caps its memory. It needs sudo and a systemd-managed dockerd, so it has not been
  applied. It can be applied once inside WSL (`sudo scripts/vm/setup_docker.sh 1G 800M` from the
  harness directory) before a larger run.
- **Image reuse during scoring.** The scorer deletes the instance image after each evaluation and
  pulls it again for the next. `run.py` adds a local tag (`sweb.eval.x86_64.<id>:latest`) to the
  pulled image so the scorer treats it as pre-existing and keeps it. The image content is
  unchanged; this only saves repeated multi-GB pulls. `run.py` deletes both tags after the task.
- **Time cap.** 60 minutes per run instead of 3 hours, enforced on both monotonic and wall time.
- **Prompt variable.** `workspace_dir_name` as described above.
- **Memory.** The host has 15 GB; the benchmark recommends 16 GB per worker. Tasks whose workload
  runs out of memory under the expert patch are marked not scorable.
- **Host power.** Agent and timing runs wait for AC power, and scoring steps that span a host pause
  are rerun (see "Pilot rounds").
- **Gold gate (round 3).** The expert patch is scored before the agent runs instead of after, so a
  task the host cannot measure is swapped out before any agent time is spent.

## How to run

Everything runs inside WSL, where Docker lives. Keep the work directory on the WSL file system
(default `~/plr-bench`, override with `PLR_WORKDIR`).

```bash
R=/mnt/c/Users/johnr/OneDrive/Documents/GitHub/performance-ladder-review/benchmark/run.py
uv run $R setup        # clone the harness at the pinned commit, fetch the pinned CLI
uv run $R preflight    # one-turn probe per arm: model, credentials, skill visibility
uv run $R run --study pilot --tasks 2 --runs 1     # round 1
uv run $R run --study pilot2 --only numpy__numpy-19608 pydata__xarray-9808 --runs 1   # round 2
uv run $R run --study round3 --gold-gate --need 2 --runs 2 --only astropy__astropy-7924 \
  sympy__sympy-20384 sympy__sympy-23696 astropy__astropy-13898 scikit-learn__scikit-learn-22235   # round 3
uv run $R run --study full --tasks 40 --runs 3    # all 40 tasks, 3 runs per arm
uv run $R status --study full
uv run $R reanalyze --study full   # recompute transcript metrics from saved transcripts
uv run analyze.py ~/plr-bench/studies/full/runs.jsonl --out results/full
uv run analyze.py ~/plr-bench/studies/pilot/runs.jsonl ~/plr-bench/studies/pilot2/runs.jsonl \
  ~/plr-bench/studies/round3/runs.jsonl --out results/combined
```

`run.py select` regenerates `tasks.json`; only run it to change the sample.

Credentials: `run.py` reads the Claude Code credentials file from `PLR_CREDENTIALS`, else
`~/.claude/.credentials.json` in WSL, else `/mnt/c/Users/johnr/.claude/.credentials.json`. If the
CLI refreshes its OAuth token during a run, the refreshed file is written back to the source, but
only when the source has not changed since it was copied. Refresh tokens rotate on use, so
dropping the refreshed copy would leave the source file holding a dead token.

Run long studies on AC power with the lid open, detached so they survive a closed terminal, and
keep a WSL session open (WSL can stop an idle distribution):

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

## Pilot rounds (2026-10-14 and 2026-10-15)

The study ran as three pilot rounds of 2 tasks each, both arms, with the same model, CLI, prompt,
caps and isolation: 1 run per arm in rounds 1 and 2, 2 runs per arm in round 3. Outputs are in
`results/pilot/` (round 1), `results/pilot2/` (round 2), `results/round3/` (round 3) and
`results/combined/` (all rounds, for reference only, since the rounds use different skill
versions). The top-level README summarizes them.

### Round 1: original skill, sympy-12640 and astropy-6941

- All four agent runs ended on their own in 92 to 130 seconds and 9 to 15 turns. None hit a cap,
  a usage limit, or a retry, and none refreshed the OAuth token.
- Scoring dominated the time: each official evaluation took 285 to 475 seconds, and the tasks took
  22 and 30 minutes end to end.
- Round 1 ran before `run.py` saved `tracked.txt`. Its `tracked.txt` files come from the same
  `git ls-files` command run in each live container, and its metrics come from `run.py reanalyze`.

### Diagnosis and skill revision

Both arms made the same first fix on both tasks. On sympy the two patches are nearly identical
(dense fast paths for `_eval_add` and `_eval_matrix_mul`). The official gap between them (2.94
against 2.09 times the expert) is inside this host's noise: the unmodified code measured 0.011 s,
0.025 s and 0.034 s in the three scoring runs.

Astropy decided the round. Both arms first cached `_get_representation_info`. The baseline then
re-profiled, read the slicing path, and stopped rebuilding each slice through `SkyCoord.__init__`
(0.138 s to 0.015 s per 100 slices in its own timing). The skill arm re-profiled sorted by self
time and stopped:

> "The profile is now flat, with no remaining single dominant cost. I'll run the relevant tests."
>
> "After the fix the profile has no single dominant cost left. I stopped there rather than chase
> small gains."

That profile still showed `BaseFrame.__init__` at 0.662 s cumulative out of 2.966 s (22 percent),
which is the constructor work the expert patch removes. The skill told the agent to target "the
largest time fraction" without saying inclusive or self time, and it had stop rules (noise floor,
Amdahl, Knuth's "small efficiencies") but no rule to keep going after a win. Commit `a3c46a5` adds:

- re-profile after each kept change, sorted by inclusive time; "flat" is a claim about inclusive
  time
- keep climbing while one call tree on the measured path holds about 20 percent or more, preferring
  rungs 1 to 3 (skip repeated setup, construct directly, change the algorithm)
- stop on a named condition: small or irreducible remaining share, a fix below the noise floor,
  failing tests, or the timebox
- for a supplied benchmark workload: profile it as given, take numbers from it with its own data,
  and treat its sizes as the n that counts
- the `/perf-loop` step picks the largest consumer by inclusive time

The revision was tuned on the round 1 tasks, so round 2 uses two different tasks: the two smallest
remaining images from repositories round 1 did not use (numpy-19608, 1.55 GB, and xarray-9808,
1.78 GB). Testing on new tasks keeps the revision from being fitted to the tasks it was made from.

### Round 2: revised skill, numpy-19608 and xarray-9808

The agent runs behaved as the revision intends. On numpy the skill arm profiled the given workload
by inclusive time, kept two rounds of changes, and re-profiled between them (22 turns against the
baseline's 12). On xarray it fixed three chunk-count hotspots, one more than the
baseline.

The scores do not support a comparison:

- **xarray is not scorable on this host.** The workload opens a public cloud Zarr store with about
  1.3 million chunks per variable, and the official scorer's pre-edit run was killed for running
  out of memory in all three scoring runs (gold included) on the 15 GB host. There is no expert
  timing, so neither arm has a score. The official report would show these runs as incorrect with
  speedup 1.0; `run.py` and `analyze.py` mark them not scorable instead.
- **numpy fails correctness for both arms, and for the expert patch.** The required tests
  `test_large_zip` and `test_dot_big_stride` report no status under the expert patch on this host.
  The baseline patch fails the same two, the skill patch fails one of them. Under the official rule
  both arms score 0.996 (no speedup, divided by the expert's 1.004). The expert speedup itself does
  not reproduce here (1.137 s before, 1.133 s after).
- **The host slept and ran on battery.** The laptop's lid closed at 11:08Z and it slept until
  17:01Z, inside the numpy baseline's scoring step (22,314 s wall). It then ran on battery with
  repeated Modern Standby. The unmodified numpy code measured 1.14 s, 7.11 s and 2.12 s in the
  three scoring runs, so the raw speedups (1.63 and 1.58) are not comparable.

### Why a 4,261-second run counts as inside the 60-minute cap

The xarray skill run took 4,261 s of wall time but 1,864 s of CLI time, and it ended on its own
(exit 0). Windows put the host in Modern Standby from 18:37 to 19:06Z and from 19:16 to 19:26Z, and
asleep from 19:38 to 19:39Z, about 2,390 s in all, which matches the gap. Both the in-container
`timeout` and the host-side subprocess timeout count monotonic time, which stops while the host
sleeps, so neither fired. The cap held for running time and was not enforced on wall time. The
xarray baseline run shows the same effect on a smaller scale (3,635 s wall, 3,402 s CLI).

`run.py` now guards against this:

- a wall-clock watchdog stops any agent run at 60 minutes of wall time
- agent runs and timing runs start only on AC power (`run.py` waits while the host is on battery)
- a Windows keep-awake request is held for the life of the study (effective only from commit
  `84fe1ce`; see round 3)
- every agent run and scoring step records the seconds the host was paused (wall minus monotonic);
  a scoring step that spans a pause of more than 60 s, or ends on battery, is rerun (up to 3 tries)
- a task whose expert patch yields no timing is marked not scorable and its predictions are not
  scored
- each report also records the required tests that fail for the prediction but pass for the
  expert patch on this host (host-adjusted correctness, a diagnostic next to the official verdict)

Lid-close and critical-battery sleep still override a keep-awake request, so run on AC power with
the lid open.

### Round 3: revised skill, sympy-20384 and astropy-7924, 2 runs per arm

Round 3 used `run.py run --gold-gate --need 2 --runs 2` over five candidates in image-size order,
none used before and none with a large-memory workload (dask and xarray tasks were skipped):
astropy-7924, sympy-20384, sympy-23696, astropy-13898, scikit-learn-22235. The gold gate scores
the expert patch first and accepts a task only if it produces a timing, shows at least 1.2x, and
passes every required test on this host. The first two candidates passed (expert speedup 8.82x
for astropy-7924 and 72.68x for sympy-20384), so no swap was needed.

All 8 agent runs ended on their own (68 to 214 s, 5 to 25 turns), and all 10 scoring runs finished
on the first attempt with no host pause and on AC power. The unmodified code timed consistently
across scoring runs: 0.067 to 0.086 s for astropy-7924 and 17.3 to 18.8 s for sympy-20384. Every
run passes the official correctness check.

| Task | Arm | Run | Speedup | Expert | vs expert | Turns | Wall (s) |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| sympy-20384 | baseline | 1 | 107.27x | 72.68x | 1.48 | 5 | 122 |
| sympy-20384 | baseline | 2 | 129.95x | 72.68x | 1.79 | 5 | 69 |
| sympy-20384 | skill | 1 | 448.51x | 72.68x | 6.17 | 23 | 214 |
| sympy-20384 | skill | 2 | 139.25x | 72.68x | 1.92 | 8 | 128 |
| astropy-7924 | baseline | 1 | 4.61x | 8.82x | 0.52 | 7 | 141 |
| astropy-7924 | baseline | 2 | 5.10x | 8.82x | 0.58 | 7 | 96 |
| astropy-7924 | skill | 1 | 6.01x | 8.82x | 0.68 | 25 | 131 |
| astropy-7924 | skill | 2 | 3.55x | 8.82x | 0.40 | 10 | 124 |

Per task (geometric mean over the two runs), the skill arm wins sympy-20384 (3.44 against 1.62
times the expert) and ties astropy-7924 (0.52 against 0.55, within 5 percent). All runs on a task
found the same first fix (an ASCII fast path in `stringPict.line_width`; a cache for
`_get_deriv_key`). The sympy win comes from one run that kept going after it: "While that runs,
I'll look at the remaining hotspot. `PolyElement.str` accounts for about 97% of the time now." It
then cached the printed generator names in `sympy/polys/rings.py`. The other sympy skill run
stopped after the first fix. Both astropy skill runs re-profiled and named a stop condition ("no
single tree above about 25%", "no call tree above about 20%"), although the first stopped above
the skill's 20 percent line.

The revised skill costs more per run in round 3: 16.5 turns against 6, 4,915 output tokens against
1,986, and a cost-equivalent of $0.60 against $0.21 (means over 4 runs per arm).

**Keep-awake correction.** The keep-awake request added after round 2 never took effect: PowerShell
read `0x80000001` as a negative Int32, the `SetThreadExecutionState` call failed, and the helper
kept running without holding anything. Round 3 was covered by a separately started helper that
passed the value correctly, from 23:13Z (about a minute into the first agent run) to the end of
scoring. The gold scoring run before that recorded no host pause. Commit
`84fe1ce` fixes `run.py`, exits the helper when the call fails, and restarts it before each step.
The AC-power wait and the pause checks were in effect for all of round 3.

### Across all rounds

| Round | Skill | Task | Runs per arm | Baseline vs expert | Skill vs expert | Result |
| --- | --- | --- | ---: | ---: | ---: | --- |
| 1 | original | sympy-12640 | 1 | 2.94 | 2.09 | loss |
| 1 | original | astropy-6941 | 1 | 0.35 | 0.07 | loss |
| 2 | revised | numpy-19608 | 1 | 0.996 | 0.996 | no usable score |
| 2 | revised | xarray-9808 | 1 | not scorable | not scorable | no usable score |
| 3 | revised | sympy-20384 | 2 | 1.62 | 3.44 | win |
| 3 | revised | astropy-7924 | 2 | 0.55 | 0.52 | tie |

The original skill lost both of its scored tasks, the revised skill won one and tied one, and two
tasks produced no usable score on this host. That is 4 scored tasks, 2 per skill version, with 1
or 2 runs per arm. The spread between runs of one arm on one task (1.92 to 6.17 for the skill on
sympy-20384) is as large as the gaps between arms, so none of this establishes a difference.
`results/combined/` pools all three rounds for reference; it mixes skill versions.

## Disk

Only one instance image is on disk at a time. Compressed images are 1.4 to 3.5 GB; the 1.39 GB
sympy image took 4.6 GB of Docker image storage once pulled. `run.py` refuses to pull when free
space on the drive holding the WSL disk is under about 3.5 times the compressed size plus 8 GB. The
WSL virtual disk grows to its high-water mark and does not shrink when images are deleted;
reclaiming that space on C: needs `wsl --shutdown` and a compaction (`Optimize-VHD`, or `diskpart`
with `compact vdisk`) on the Windows side.
