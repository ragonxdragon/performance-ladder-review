# SWE-fficiency A/B: performance-ladder-review (study `pilot + pilot2 + round3`)

This view combines 3 studies (pilot, pilot2, round3). They may use different skill versions and different tasks; read the per-study reports first.

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
| round3 | sympy__sympy-20384 | baseline | 1 | success | 1 | True | 107.265 | 72.685 | 1.476 | 5 | 122 | 121 | 2218 | False | True |
| round3 | sympy__sympy-20384 | baseline | 2 | success | 1 | True | 129.949 | 72.685 | 1.788 | 5 | 69 | 68 | 1451 | False | True |
| round3 | sympy__sympy-20384 | skill | 1 | success | 1 | True | 448.510 | 72.685 | 6.171 | 23 | 214 | 213 | 7656 | True | True |
| round3 | sympy__sympy-20384 | skill | 2 | success | 1 | True | 139.245 | 72.685 | 1.916 | 8 | 128 | 127 | 2497 | True | True |
| round3 | astropy__astropy-7924 | baseline | 1 | success | 1 | True | 4.613 | 8.822 | 0.523 | 7 | 141 | 138 | 2253 | False | True |
| round3 | astropy__astropy-7924 | baseline | 2 | success | 1 | True | 5.097 | 8.822 | 0.578 | 7 | 96 | 94 | 2023 | False | True |
| round3 | astropy__astropy-7924 | skill | 1 | success | 1 | True | 6.008 | 8.822 | 0.681 | 25 | 131 | 129 | 5937 | True | True |
| round3 | astropy__astropy-7924 | skill | 2 | success | 1 | True | 3.554 | 8.822 | 0.403 | 10 | 124 | 122 | 3569 | True | True |

## Paired by task

| Task | Baseline SR | Skill SR | Skill / baseline | Result |
| --- | ---: | ---: | ---: | --- |
| sympy__sympy-12640 | 2.938 | 2.094 | 0.713 | loss |
| astropy__astropy-6941 | 0.346 | 0.074 | 0.214 | loss |
| sympy__sympy-20384 | 1.624 | 3.438 | 2.117 | win |
| numpy__numpy-19608 | 0.996 | 0.996 | 1.000 | tie |
| astropy__astropy-7924 | 0.550 | 0.524 | 0.953 | tie |
| pydata__xarray-9808 | n/a | n/a | n/a | not scorable |

## Aggregates

| Metric | Baseline | Skill | Skill minus baseline | 95% CI | n |
| --- | ---: | ---: | ---: | --- | ---: |
| mean_log_speedup_vs_expert | -0.020 | -0.256 | -0.236 | -0.946 to 0.382 | 5 |
| geometric_mean_speedup_vs_expert | 0.980 | 0.774 | 0.790 | 0.388 to 1.465 | 5 |
| mean_paired_speedup_difference | 1.291 | 1.425 | 0.134 | -0.512 to 1.034 | 5 |
| median_speedup_vs_expert | 0.996 | 0.996 | -0.026 | n/a | 5 |
| harmonic_mean_speedup_vs_expert | 0.750 | 0.291 | -0.459 | -0.649 to 0.262 | 5 |
| win_tie_loss | n/a | n/a | 1/2/2 | n/a | 5 |
| runs | 8 | 8 | n/a | n/a | n/a |
| correct_rate | 0.857 | 0.857 | n/a | n/a | n/a |
| correct_rate_host_adjusted | 1.000 | 1.000 | n/a | n/a | n/a |
| mean_input_tokens | 28.250 | 34.250 | 6.000 | n/a | n/a |
| median_input_tokens | 16.000 | 29.000 | n/a | n/a | n/a |
| mean_output_tokens | 5781.500 | 9846.750 | 4065.250 | n/a | n/a |
| median_output_tokens | 2450.500 | 4903.000 | n/a | n/a | n/a |
| mean_cache_creation_input_tokens | 40282.375 | 63181.375 | 22899.000 | n/a | n/a |
| median_cache_creation_input_tokens | 33454.500 | 51519.000 | n/a | n/a | n/a |
| mean_cache_read_input_tokens | 729848.875 | 1038087.875 | 308239.000 | n/a | n/a |
| median_cache_read_input_tokens | 289629.000 | 760367.500 | n/a | n/a | n/a |
| mean_num_turns | 14.625 | 19.625 | 5.000 | n/a | n/a |
| median_num_turns | 8.000 | 17.000 | n/a | n/a | n/a |
| mean_wall_sec | 554.087 | 710.112 | 156.025 | n/a | n/a |
| median_wall_sec | 111.650 | 130.800 | n/a | n/a | n/a |
| mean_tool_calls | 13.625 | 17.625 | 4.000 | n/a | n/a |
| median_tool_calls | 7.000 | 15.000 | n/a | n/a | n/a |
| mean_total_cost_usd_equiv | 0.547 | 0.838 | 0.291 | n/a | n/a |
| median_total_cost_usd_equiv | 0.369 | 0.653 | n/a | n/a | n/a |
| rate_skill_fired | 0.000 | 1.000 | n/a | n/a | n/a |
| rate_timing_before_first_edit | 1.000 | 1.000 | n/a | n/a | n/a |
| rate_profiler_before_first_edit | 0.875 | 1.000 | n/a | n/a | n/a |

## Notes

- SR is the official speedup ratio versus the expert patch. Failed correctness counts as no speedup.
- Per-task values are geometric means over runs. Ties are within 5 percent.
- Host-adjusted correctness ignores required tests that also fail under the expert patch on this host. It is a diagnostic; the official verdict drives the score.
- Wall time includes any time the host spent asleep; CLI time is the CLI's own duration and excludes it.
- Bootstrap: 10000 resamples of tasks with replacement, seed 12345; no CI is reported with fewer than 5 paired tasks.
- Token counts come from the CLI result event and cover the whole run.
- 'Timed before first edit' is a transcript heuristic: a Bash call that runs timing or profiling code before the first edit to a tracked repository file.
- pydata__xarray-9808 is not scorable: the workload was killed (out of memory) on this host. Its runs are left out of the speedup statistics.
