# SWE-fficiency A/B: performance-ladder-review (PILOT, study `pilot2`)

**PILOT numbers.** 1 paired task(s). These numbers show the harness works; they are not evidence for or against the skill.

## Per run

| Study | Task | Arm | Run | Outcome | Correct (official) | Correct (host-adjusted) | Raw speedup | Expert speedup | Speedup vs expert | Turns | Wall (s) | CLI (s) | Output tokens | Skill fired | Timed before first edit |
| --- | --- | --- | ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| pilot2 | numpy__numpy-19608 | baseline | 1 | success | 0 | True | 1.635 | 1.004 | 0.996 | 12 | 177 | 176 | 7392 | False | True |
| pilot2 | numpy__numpy-19608 | skill | 1 | success | 0 | True | 1.583 | 1.004 | 0.996 | 22 | 570 | 567 | 18494 | True | True |
| pilot2 | pydata__xarray-9808 | baseline | 1 | success | not scorable | not scorable | n/a | n/a | n/a | 57 | 3635 | 3402 | 21143 | False | True |
| pilot2 | pydata__xarray-9808 | skill | 1 | success | not scorable | not scorable | n/a | n/a | n/a | 46 | 4261 | 1864 | 33038 | True | True |

## Paired by task

| Task | Baseline SR | Skill SR | Skill / baseline | Result |
| --- | ---: | ---: | ---: | --- |
| numpy__numpy-19608 | 0.996 | 0.996 | 1.000 | tie |
| pydata__xarray-9808 | n/a | n/a | n/a | not scorable |

## Aggregates

| Metric | Baseline | Skill | Skill minus baseline | 95% CI | n |
| --- | ---: | ---: | ---: | --- | ---: |
| mean_log_speedup_vs_expert | -0.004 | -0.004 | 0.000 | n/a | 1 |
| geometric_mean_speedup_vs_expert | 0.996 | 0.996 | 1.000 | n/a | 1 |
| mean_paired_speedup_difference | 0.996 | 0.996 | 0.000 | n/a | 1 |
| median_speedup_vs_expert | 0.996 | 0.996 | 0.000 | n/a | 1 |
| harmonic_mean_speedup_vs_expert | 0.996 | 0.996 | 0.000 | n/a | 1 |
| win_tie_loss | n/a | n/a | 0/1/0 | n/a | 1 |
| runs | 2 | 2 | n/a | n/a | n/a |
| correct_rate | 0.000 | 0.000 | n/a | n/a | n/a |
| correct_rate_host_adjusted | 1.000 | 1.000 | n/a | n/a | n/a |
| mean_input_tokens | 68.000 | 59.000 | -9.000 | n/a | n/a |
| median_input_tokens | 68.000 | 59.000 | n/a | n/a | n/a |
| mean_output_tokens | 14267.500 | 25766.000 | 11498.500 | n/a | n/a |
| median_output_tokens | 14267.500 | 25766.000 | n/a | n/a | n/a |
| mean_cache_creation_input_tokens | 70252.000 | 110101.500 | 39849.500 | n/a | n/a |
| median_cache_creation_input_tokens | 70252.000 | 110101.500 | n/a | n/a | n/a |
| mean_cache_read_input_tokens | 2050284.000 | 2208628.500 | 158344.500 | n/a | n/a |
| median_cache_read_input_tokens | 2050284.000 | 2208628.500 | n/a | n/a | n/a |
| mean_num_turns | 34.500 | 34.000 | -0.500 | n/a | n/a |
| median_num_turns | 34.500 | 34.000 | n/a | n/a | n/a |
| mean_wall_sec | 1906.100 | 2415.350 | 509.250 | n/a | n/a |
| median_wall_sec | 1906.100 | 2415.350 | n/a | n/a | n/a |
| mean_tool_calls | 33.500 | 32.000 | -1.500 | n/a | n/a |
| median_tool_calls | 33.500 | 32.000 | n/a | n/a | n/a |
| mean_total_cost_usd_equiv | 1.251 | 1.710 | 0.459 | n/a | n/a |
| median_total_cost_usd_equiv | 1.251 | 1.710 | n/a | n/a | n/a |
| rate_skill_fired | 0.000 | 1.000 | n/a | n/a | n/a |
| rate_timing_before_first_edit | 1.000 | 1.000 | n/a | n/a | n/a |
| rate_profiler_before_first_edit | 0.500 | 1.000 | n/a | n/a | n/a |

## Notes

- SR is the official speedup ratio versus the expert patch. Failed correctness counts as no speedup.
- Per-task values are geometric means over runs. Ties are within 5 percent.
- Host-adjusted correctness ignores required tests that also fail under the expert patch on this host. It is a diagnostic; the official verdict drives the score.
- Wall time includes any time the host spent asleep; CLI time is the CLI's own duration and excludes it.
- Bootstrap: 10000 resamples of tasks with replacement, seed 12345; no CI is reported with fewer than 5 paired tasks.
- Token counts come from the CLI result event and cover the whole run.
- 'Timed before first edit' is a transcript heuristic: a Bash call that runs timing or profiling code before the first edit to a tracked repository file.
- pydata__xarray-9808 is not scorable: the workload was killed (out of memory) on this host. Its runs are left out of the speedup statistics.
