# SWE-fficiency A/B: performance-ladder-review (PILOT, study `pilot + pilot2`)

This view combines 2 studies (pilot, pilot2). They may use different skill versions and different tasks; read the per-study reports first.

**PILOT numbers.** 3 paired task(s). These numbers show the harness works; they are not evidence for or against the skill.

## Per run

| Study | Task | Arm | Run | Outcome | Correct (official) | Correct (host-adjusted) | Raw speedup | Expert speedup | Speedup vs expert | Turns | Wall (s) | CLI (s) | Output tokens | Skill fired | Timed before first edit |
| --- | --- | --- | ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| pilot | sympy__sympy-12640 | baseline | 1 | success | 1 | True | 5.273 | 1.795 | 2.938 | 9 | 92 | 89 | 2648 | False | True |
| pilot | sympy__sympy-12640 | skill | 1 | success | 1 | True | 3.758 | 1.795 | 2.094 | 12 | 130 | 128 | 3714 | True | True |
| pilot | astropy__astropy-6941 | baseline | 1 | success | 1 | True | 9.104 | 26.275 | 0.346 | 15 | 102 | 95 | 7124 | False | True |
| pilot | astropy__astropy-6941 | skill | 1 | success | 1 | True | 1.944 | 26.275 | 0.074 | 11 | 122 | 120 | 3869 | True | True |
| pilot2 | numpy__numpy-19608 | baseline | 1 | success | 0 | True | 1.635 | 1.004 | 0.996 | 12 | 177 | 176 | 7392 | False | True |
| pilot2 | numpy__numpy-19608 | skill | 1 | success | 0 | True | 1.583 | 1.004 | 0.996 | 22 | 570 | 567 | 18494 | True | True |
| pilot2 | pydata__xarray-9808 | baseline | 1 | success | not scorable | not scorable | n/a | n/a | n/a | 57 | 3635 | 3402 | 21143 | False | True |
| pilot2 | pydata__xarray-9808 | skill | 1 | success | not scorable | not scorable | n/a | n/a | n/a | 46 | 4261 | 1864 | 33038 | True | True |

## Paired by task

| Task | Baseline SR | Skill SR | Skill / baseline | Result |
| --- | ---: | ---: | ---: | --- |
| sympy__sympy-12640 | 2.938 | 2.094 | 0.713 | loss |
| astropy__astropy-6941 | 0.346 | 0.074 | 0.214 | loss |
| numpy__numpy-19608 | 0.996 | 0.996 | 1.000 | tie |
| pydata__xarray-9808 | n/a | n/a | n/a | not scorable |

## Aggregates

| Metric | Baseline | Skill | Skill minus baseline | 95% CI | n |
| --- | ---: | ---: | ---: | --- | ---: |
| mean_log_speedup_vs_expert | 0.005 | -0.623 | -0.628 | n/a | 3 |
| geometric_mean_speedup_vs_expert | 1.005 | 0.536 | 0.534 | n/a | 3 |
| mean_paired_speedup_difference | 1.427 | 1.055 | -0.372 | n/a | 3 |
| median_speedup_vs_expert | 0.996 | 0.996 | -0.272 | n/a | 3 |
| harmonic_mean_speedup_vs_expert | 0.709 | 0.200 | -0.509 | n/a | 3 |
| win_tie_loss | n/a | n/a | 0/1/2 | n/a | 3 |
| runs | 4 | 4 | n/a | n/a | n/a |
| correct_rate | 0.667 | 0.667 | n/a | n/a | n/a |
| correct_rate_host_adjusted | 1.000 | 1.000 | n/a | n/a | n/a |
| mean_input_tokens | 45.000 | 39.500 | -5.500 | n/a | n/a |
| median_input_tokens | 25.000 | 29.000 | n/a | n/a | n/a |
| mean_output_tokens | 9576.750 | 14778.750 | 5202.000 | n/a | n/a |
| median_output_tokens | 7258.000 | 11181.500 | n/a | n/a | n/a |
| mean_cache_creation_input_tokens | 60143.000 | 75798.750 | 15655.750 | n/a | n/a |
| median_cache_creation_input_tokens | 50034.000 | 74568.000 | n/a | n/a | n/a |
| mean_cache_read_input_tokens | 1258607.500 | 1329024.250 | 70416.750 | n/a | n/a |
| median_cache_read_input_tokens | 570947.500 | 760367.500 | n/a | n/a | n/a |
| mean_num_turns | 23.250 | 22.750 | -0.500 | n/a | n/a |
| median_num_turns | 13.500 | 17.000 | n/a | n/a | n/a |
| mean_wall_sec | 1001.400 | 1270.850 | 269.450 | n/a | n/a |
| median_wall_sec | 139.300 | 350.100 | n/a | n/a | n/a |
| mean_tool_calls | 22.250 | 20.750 | -1.500 | n/a | n/a |
| median_tool_calls | 12.500 | 15.000 | n/a | n/a | n/a |
| mean_total_cost_usd_equiv | 0.882 | 1.075 | 0.193 | n/a | n/a |
| median_total_cost_usd_equiv | 0.533 | 0.843 | n/a | n/a | n/a |
| rate_skill_fired | 0.000 | 1.000 | n/a | n/a | n/a |
| rate_timing_before_first_edit | 1.000 | 1.000 | n/a | n/a | n/a |
| rate_profiler_before_first_edit | 0.750 | 1.000 | n/a | n/a | n/a |

## Notes

- SR is the official speedup ratio versus the expert patch. Failed correctness counts as no speedup.
- Per-task values are geometric means over runs. Ties are within 5 percent.
- Host-adjusted correctness ignores required tests that also fail under the expert patch on this host. It is a diagnostic; the official verdict drives the score.
- Wall time includes any time the host spent asleep; CLI time is the CLI's own duration and excludes it.
- Bootstrap: 10000 resamples of tasks with replacement, seed 12345; no CI is reported with fewer than 5 paired tasks.
- Token counts come from the CLI result event and cover the whole run.
- 'Timed before first edit' is a transcript heuristic: a Bash call that runs timing or profiling code before the first edit to a tracked repository file.
- pydata__xarray-9808 is not scorable: the workload was killed (out of memory) on this host. Its runs are left out of the speedup statistics.
