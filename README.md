# Performance Ladder Review

A [Claude Code](https://docs.claude.com/en/docs/claude-code) skill that makes the agent review and
write code like a performance engineer who measures first. It refuses speed claims without a
number, deletes work before tuning it, climbs a fixed ladder of fixes from configuration down to
micro-optimization, and leaves a `PERF:` comment wherever a decision needs to survive the next
reader. Simplifying and speeding up are treated as one job.

## Why

**No claim without a number.** Model-written "optimizations" are often neutral, slower, or broken,
and a single timing run can't tell the difference. The skill asks for a measurement that names the
hotspot before any hand-tuning, a before and an after, medians instead of single runs, and a real
significance test. When a change can't be measured, it is marked `estimated` and says why.

**Delete before you tune.** The fastest code is the code that never runs. Removing a layer, a
copy or a round trip beats making it faster, and it leaves fewer places for bugs.

**Climb the ladder in order.** Each rung is cheaper and safer than the one below it:

| Rung | Move | Examples |
| ------ | ------ | ---------- |
| L0 | Configuration before code | release build flags, compression, connection reuse, pool sizes |
| L1 | Don't do the work | delete dead code, cache pure work, early exit, dedupe calls |
| L2 | Do it less often | batch, debounce, lazy-load, paginate |
| L3 | Fix the complexity class | nested scan to hash lookup, query in a loop to one JOIN, N+1 to eager load |
| L4 | Let the platform do it | push filtering into the database, vectorize, use the stdlib |
| L5 | Move it off the critical path | async, queues, background jobs, streaming |
| L6 | Micro-optimize the measured hotspot | only with a profile, only while it stays readable |

The full rules, including the safety floor (correctness, validation and auth are never traded for
speed) and the guardrails on what the agent may change without sign-off, are in
[`skills/performance-ladder-review/SKILL.md`](skills/performance-ladder-review/SKILL.md).

## The `PERF:` marker

`PERF:` is an existing comment keyword, highlighted by editors next to `TODO:` and `FIX:`
(todo-comments.nvim ships it by default; VS Code's Todo Tree highlights it once `PERF` is added to
`todo-tree.general.tags`). Every decision the skill makes in code reads as one of these:

```text
PERF: <rung> - <what changed>, <before> -> <after> (<method>)      applied, measured
PERF: <rung> - <what changed> (estimated; <why it can't be measured>)  applied, estimated
PERF: deferred - <open question>, <revisit trigger>                deferred to the owner
PERF: <rung> rejected - <why no change is needed>                  investigated, no change
```

```c
// PERF: L3 - query-in-loop -> JOIN, 1.2s -> 45ms (median of 10)
// PERF: L1 - memoized parse (estimated; pure fn called per render; unmeasurable here)
// PERF: deferred - O(n^2) merge fine at n<1k, revisit past 10k rows
// PERF: L3 rejected - nested scan stays under 1k elements per the documented fleet size
```

The marker line is the only place a before and after belongs. The prose around it describes the
current code, never the edit.

## Commands

Inside a session the skill recognizes these mode names:

| Command | What it does |
| --------- | -------------- |
| `/perf-mode full` | ladder and simplification on all code touched (default); `review`, `hotspot`, `off` switch modes |
| `/perf-review` | findings only: location -> cost -> fix, ranked by estimated cost with a confidence tag |
| `/perf-loop` | measure, fix one thing, re-measure, keep only significant wins; never edits tests |
| `/perf-harvest` | lists every `deferred` and `estimated` marker with its revisit trigger |
| `/perf-help` | quick reference |

Claude Code registers the skill itself as `/performance-ladder-review`, and loads it on its own
when a conversation is about speed, slowness or simplification. The short names above are modes
the skill reads from your request, so pass them as text: `/performance-ladder-review perf-review src/`,
or "run a perf-review on the upload path".

## Install

Copy or link `skills/performance-ladder-review` into your personal skills directory, or into a
project's `.claude/skills/` to share it with everyone on that repository.

```sh
# personal, macOS or Linux
git clone https://github.com/ragonxdragon/performance-ladder-review.git
ln -s "$PWD/performance-ladder-review/skills/performance-ladder-review" ~/.claude/skills/performance-ladder-review

# one project
mkdir -p .claude/skills
cp -r performance-ladder-review/skills/performance-ladder-review .claude/skills/
```

```powershell
# personal, Windows
Copy-Item -Recurse performance-ladder-review\skills\performance-ladder-review "$HOME\.claude\skills\"
```

Start a new Claude Code session and run `/performance-ladder-review perf-help` to check it loaded.

## Results in real projects

The skill has run since 2026-07-21 on three of the author's projects: a cellular IoT gateway
firmware (ESP32, client work, private), a desktop AI model manager (Rust and TypeScript, private),
and [twinflow](https://github.com/ragonxdragon/twinflow) (Python, public). Every number below was
written at the time of the change, in a commit message or in the `PERF:` comment on the changed
code. Nothing was re-run or estimated for this page.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="results/charts/before-after-dark.svg">
  <img alt="Dumbbell chart of before and after values for 16 measured changes, grouped into time, size, and counts, each on a log scale" src="results/charts/before-after-light.svg">
</picture>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="results/charts/reduction-factor-dark.svg">
  <img alt="Improvement factor per measured change on a log scale, from 1.04x to 530,771x" src="results/charts/reduction-factor-light.svg">
</picture>

The strongest measured results:

| Project | Change | Before | After | Method |
| --------- | -------- | -------- | ------- | -------- |
| twinflow | [Count repeated sequence numbers in one pass (L3)](https://github.com/ragonxdragon/twinflow/commit/03df49a3540ab08307d3c2377030043f35a6b76c) | 4,903 ms | 2.827 ms | n=16,000, identical output at every size |
| twinflow | [Hold the event-log hash until an append changes it (L1)](https://github.com/ragonxdragon/twinflow/commit/03df49a3540ab08307d3c2377030043f35a6b76c) | 185.77 ms | 0.00035 ms | 8,000 events, repeat lookups |
| twinflow | [Resolve the hook interpreter once (L0)](https://github.com/ragonxdragon/twinflow/commit/3a3a28ee2ccccde51a855b728346dbbd2323cdab) | 2,787 ms | 1,202 ms | pre-commit wall clock, three runs each |
| desktop app | Reparse only the unfinished block of a streaming answer (L1) | 33.3 ms | 1.0 ms | per frame at 16 KB, release build |
| firmware | Skip the LED refresh when the pixel color is unchanged (L1) | 334 | 1 | refreshes per 10 s in the steady state, host bench |
| firmware | Flush emulator notifications without an idle sleep | 56.0 ms | 5.1 ms | median of 100 queued notifications |
| firmware | Batch WebSocket writes (L2) | 28 | 9 | modem send commands per full refresh, on device |
| firmware | Build the upload scan in place (L1) | 2.92 s | 1.85 s | 1,000 tags, on device, median of 10 cycles |
| firmware | Poll device registration every 0.5 s | 18.1 s | 13.8 s | randomized 2x2 factorial, Mann-Whitney p=0.0020 |
| firmware | Read device twins in parallel during batch provisioning (L5) | 1x | 6.5x | throughput vs serial at 8 workers (11.7x at 16) |

The registration row is the measurement protocol doing its job: a single before and after timing earlier
the same day had picked the slower 3 s interval, and the factorial showed that comparison was
noise.

Five more firmware changes were measured going to zero, which a log axis can't show: allocations
for 500 tags re-read 200 times (100,000 to 0, host bench), heap allocations to build a 1,000-tag
scan (2,000 to 0), internal heap held by a per-antenna map at 500 tags (20 KB to 0), bytes copied
per config callback (3.2 KB to 0), and CI cache restore time per job (17-19 s to 0).

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="results/charts/marker-verdicts-dark.svg">
  <img alt="Bar chart of applied, deferred and rejected marker decisions per project" src="results/charts/marker-verdicts-light.svg">
</picture>

| Project | Perf commits | Measured changes | Estimated changes | Perf commits with no number |
| --------- | -------------: | -----------------: | ------------------: | ----------------------------: |
| firmware | 63 | 17 | 29 | 22 |
| desktop app | 41 | 2 | 3 | 36 |
| twinflow | 2 | 3 | 0 | 0 |

Measured points are few outside the firmware: 22 measured changes in all, 16 of them charted.
The full dataset is [`results/results.csv`](results/results.csv) (82 rows) with per-project counts
in [`results/summary.csv`](results/summary.csv).

### How the data was gathered, and its limits

- **Selection.** Commits since 2026-07-21 whose conventional-commit type is `perf`, or that named
  the skill, plus fix commits merged as part of a review pass, across all branches of the three
  repositories. This is one author's work after adopting the skill, chosen by commit type. It is
  not a controlled study, and there is no comparison against what the same work would have
  produced without the skill.
- **Numbers as stated.** Every value comes from a commit message or from the `PERF:` comment on
  the changed code, found by searching every revision of each repository. Methods vary and
  are recorded in the `method` column: on-device bench medians, host benchmarks, build output,
  single-checkout measurements. A row is `measured` only when the commit says it was measured;
  computed, simulated, approximate and by-construction figures are `estimated` and never appear in
  a chart. Where a commit message and its code comment disagree, the CSV keeps the commit message
  and notes the other figure.
- **Noise.** Two charted firmware results (1.04x and 1.06x) are medians without a stated
  significance test and sit below the 1.1x to 1.2x noise floor the skill itself uses, so treat them
  as unproven.
- **Context for single rows.** The 530,771x twinflow figure compares recomputing a hash against
  reading a held value, so it applies to repeat calls. The gzip upload result is opt-in and off by
  default. The parallel twin-read figure is throughput, so higher is better; the factor chart
  inverts it to match the others. The startup JavaScript cut is deterministic, but the same commit found no launch-time
  change above run-to-run noise.
- **Charts** show one headline metric per change, the first row for that change in the CSV.
- **Markers.** Counts come from `git grep` over each project's main branch, excluding vendored and
  dependency directories and docs, and include an earlier marker spelling used before the projects
  settled on `PERF:`. The firmware later moved decision records from code comments into commit
  messages, so its counts come from the last tree that carried markers (2026-09-04).
- **Privacy.** Two of the projects are private. Their commits are not linked, client-identifying
  details are removed, and the desktop app appears only as a metric and a one-line description.

Regenerate the charts with:

```sh
uv run --no-project --with matplotlib python results/make_charts.py
```

## Repository layout

| Path | Contents |
| ------ | ---------- |
| `skills/performance-ladder-review/` | the skill: `SKILL.md` and `references/` |
| `results/results.csv` | one row per measured or estimated metric |
| `results/summary.csv` | per-project commit and marker counts |
| `results/make_charts.py` | renders the light and dark SVGs in `results/charts/` |

## License

[MIT](LICENSE), copyright (c) 2026 John Hall.
