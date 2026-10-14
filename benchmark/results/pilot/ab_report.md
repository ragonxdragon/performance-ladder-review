# SWE-fficiency A/B: performance-ladder-review (PILOT, study `pilot`)

**PILOT numbers.** 2 paired task(s). These numbers show the harness works; they are not evidence for or against the skill.

## Per run

| Study | Task | Arm | Run | Outcome | Correct (official) | Correct (host-adjusted) | Raw speedup | Expert speedup | Speedup vs expert | Turns | Wall (s) | CLI (s) | Output tokens | Skill fired | Timed before first edit |
| --- | --- | --- | ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| pilot | sympy__sympy-12640 | baseline | 1 | success | 1 | True | 5.273 | 1.795 | 2.938 | 9 | 92 | 89 | 2648 | False | True |
| pilot | sympy__sympy-12640 | skill | 1 | success | 1 | True | 3.758 | 1.795 | 2.094 | 12 | 130 | 128 | 3714 | True | True |
| pilot | astropy__astropy-6941 | baseline | 1 | success | 1 | True | 9.104 | 26.275 | 0.346 | 15 | 102 | 95 | 7124 | False | True |
| pilot | astropy__astropy-6941 | skill | 1 | success | 1 | True | 1.944 | 26.275 | 0.074 | 11 | 122 | 120 | 3869 | True | True |

## Paired by task

| Task | Baseline SR | Skill SR | Skill / baseline | Result |
| --- | ---: | ---: | ---: | --- |
| sympy__sympy-12640 | 2.938 | 2.094 | 0.713 | loss |
| astropy__astropy-6941 | 0.346 | 0.074 | 0.214 | loss |

## Aggregates

| Metric | Baseline | Skill | Skill minus baseline | 95% CI | n |
| --- | ---: | ---: | ---: | --- | ---: |
| mean_log_speedup_vs_expert | 0.009 | -0.932 | -0.941 | n/a | 2 |
| geometric_mean_speedup_vs_expert | 1.009 | 0.394 | 0.390 | n/a | 2 |
| mean_paired_speedup_difference | 1.642 | 1.084 | -0.559 | n/a | 2 |
| median_speedup_vs_expert | 1.642 | 1.084 | -0.559 | n/a | 2 |
| harmonic_mean_speedup_vs_expert | 0.620 | 0.143 | -0.477 | n/a | 2 |
| win_tie_loss | n/a | n/a | 0/0/2 | n/a | 2 |
| runs | 2 | 2 | n/a | n/a | n/a |
| correct_rate | 1.000 | 1.000 | n/a | n/a | n/a |
| correct_rate_host_adjusted | 1.000 | 1.000 | n/a | n/a | n/a |
| mean_input_tokens | 22.000 | 20.000 | -2.000 | n/a | n/a |
| median_input_tokens | 22.000 | 20.000 | n/a | n/a | n/a |
| mean_output_tokens | 4886.000 | 3791.500 | -1094.500 | n/a | n/a |
| median_output_tokens | 4886.000 | 3791.500 | n/a | n/a | n/a |
| mean_cache_creation_input_tokens | 50034.000 | 41496.000 | -8538.000 | n/a | n/a |
| median_cache_creation_input_tokens | 50034.000 | 41496.000 | n/a | n/a | n/a |
| mean_cache_read_input_tokens | 466931.000 | 449420.000 | -17511.000 | n/a | n/a |
| median_cache_read_input_tokens | 466931.000 | 449420.000 | n/a | n/a | n/a |
| mean_num_turns | 12.000 | 11.500 | -0.500 | n/a | n/a |
| median_num_turns | 12.000 | 11.500 | n/a | n/a | n/a |
| mean_wall_sec | 96.700 | 126.350 | 29.650 | n/a | n/a |
| median_wall_sec | 96.700 | 126.350 | n/a | n/a | n/a |
| mean_tool_calls | 11.000 | 9.500 | -1.500 | n/a | n/a |
| median_tool_calls | 11.000 | 9.500 | n/a | n/a | n/a |
| mean_total_cost_usd_equiv | 0.514 | 0.441 | -0.073 | n/a | n/a |
| median_total_cost_usd_equiv | 0.514 | 0.441 | n/a | n/a | n/a |
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
