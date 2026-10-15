# SWE-fficiency A/B: performance-ladder-review (study `round3`)

## Per run

| Study | Task | Arm | Run | Outcome | Correct (official) | Correct (host-adjusted) | Raw speedup | Expert speedup | Speedup vs expert | Turns | Wall (s) | CLI (s) | Output tokens | Skill fired | Timed before first edit |
| --- | --- | --- | ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
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
| sympy__sympy-20384 | 1.624 | 3.438 | 2.117 | win |
| astropy__astropy-7924 | 0.550 | 0.524 | 0.953 | tie |

## Aggregates

| Metric | Baseline | Skill | Skill minus baseline | 95% CI | n |
| --- | ---: | ---: | ---: | --- | ---: |
| mean_log_speedup_vs_expert | -0.057 | 0.294 | 0.351 | n/a | 2 |
| geometric_mean_speedup_vs_expert | 0.945 | 1.342 | 1.420 | n/a | 2 |
| mean_paired_speedup_difference | 1.087 | 1.981 | 0.894 | n/a | 2 |
| median_speedup_vs_expert | 1.087 | 1.981 | 0.894 | n/a | 2 |
| harmonic_mean_speedup_vs_expert | 0.821 | 0.909 | 0.088 | n/a | 2 |
| win_tie_loss | n/a | n/a | 1/1/0 | n/a | 2 |
| runs | 4 | 4 | n/a | n/a | n/a |
| correct_rate | 1.000 | 1.000 | n/a | n/a | n/a |
| correct_rate_host_adjusted | 1.000 | 1.000 | n/a | n/a | n/a |
| mean_input_tokens | 11.500 | 29.000 | 17.500 | n/a | n/a |
| median_input_tokens | 12.000 | 29.000 | n/a | n/a | n/a |
| mean_output_tokens | 1986.250 | 4914.750 | 2928.500 | n/a | n/a |
| median_output_tokens | 2120.500 | 4753.000 | n/a | n/a | n/a |
| mean_cache_creation_input_tokens | 20421.750 | 50564.000 | 30142.250 | n/a | n/a |
| median_cache_creation_input_tokens | 20628.000 | 44396.500 | n/a | n/a | n/a |
| mean_cache_read_input_tokens | 201090.250 | 747151.500 | 546061.250 | n/a | n/a |
| median_cache_read_input_tokens | 211129.500 | 738411.500 | n/a | n/a | n/a |
| mean_num_turns | 6.000 | 16.500 | 10.500 | n/a | n/a |
| median_num_turns | 6.000 | 16.500 | n/a | n/a | n/a |
| mean_wall_sec | 106.775 | 149.375 | 42.600 | n/a | n/a |
| median_wall_sec | 108.800 | 129.600 | n/a | n/a | n/a |
| mean_tool_calls | 5.000 | 14.500 | 9.500 | n/a | n/a |
| median_tool_calls | 5.000 | 14.500 | n/a | n/a | n/a |
| mean_total_cost_usd_equiv | 0.213 | 0.601 | 0.389 | n/a | n/a |
| median_total_cost_usd_equiv | 0.214 | 0.592 | n/a | n/a | n/a |
| rate_skill_fired | 0.000 | 1.000 | n/a | n/a | n/a |
| rate_timing_before_first_edit | 1.000 | 1.000 | n/a | n/a | n/a |
| rate_profiler_before_first_edit | 1.000 | 1.000 | n/a | n/a | n/a |

## Notes

- SR is the official speedup ratio versus the expert patch. Failed correctness counts as no speedup.
- Per-task values are geometric means over runs. Ties are within 5 percent.
- Host-adjusted correctness ignores required tests that also fail under the expert patch on this host. It is a diagnostic; the official verdict drives the score.
- Wall time includes any time the host spent asleep; CLI time is the CLI's own duration and excludes it.
- Bootstrap: 10000 resamples of tasks with replacement, seed 12345; no CI is reported with fewer than 5 paired tasks.
- Token counts come from the CLI result event and cover the whole run.
- 'Timed before first edit' is a transcript heuristic: a Bash call that runs timing or profiling code before the first edit to a tracked repository file.
