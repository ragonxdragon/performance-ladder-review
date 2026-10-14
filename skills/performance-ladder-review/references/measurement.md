# Measurement protocol

Why this file exists: even careful researchers produce wrong performance data. Changing UNIX environment-variable size or link order alone can flip a benchmark's conclusion (Mytkowicz et al., ASPLOS 2009); benchmarking 500 pairs of *identical* programs on commodity hardware produced a mean phantom "speedup" of 1.12x with the top 5% showing 1.91x, from noise alone (PIE, ICLR 2024). A single timing run proves nothing.

## The protocol (execution time is the primary metric)

1. **Repetitions:** run each variant >=10 times, ideally 20 (the Go benchstat standard). Pick the count up front and stick to it. Report **median** and spread, never a single run, never the mean alone.
2. **Significance, not vibes:** compare before/after with a Mann-Whitney U-test at alpha=0.05, the default in Go's benchstat, which is the de facto industry standard for benchmark comparison. Use a tool that implements it (`benchstat`, `hyperfine`) rather than eyeballing. Not significant -> report "~" (no change), never a percentage.
3. **Never rerun until significant.** At alpha=0.05 a no-op change shows a "significant" difference 5% of the time. Rerunning a flat result until it flips, or comparing 20 metrics and reporting the one that moved, manufactures noise wins; benchstat's own docs call this out as the classic multiple-testing error. Decide the run count up front; accept the verdict.
4. **Noise floor:** on ordinary hardware treat any speedup under ~1.10-1.20x as unproven even when nominally significant. Stabilize the machine: idle load, no parallel builds, performance CPU governor / turbo disabled where possible; distrust CI timings.
5. **Warmup (JIT/VM languages: Java, JS, PyPy, .NET):** include warmup iterations and measure steady state; watch the run-to-run trend rather than assuming stability. VMs sometimes never stabilize or get slower over time (Barrett et al., OOPSLA 2017). On the JVM this means JMH; see lang/jvm.md.
6. **Latency work:** report p50/p95/p99 (p99 is the industry-standard gating metric, what SLOs and MongoDB's regression system target), never averages. Beware coordinated omission: a load generator that waits for each response before sending the next hides stalls and makes percentiles lie (Gil Tene).
7. **Microbenchmarks:** consume or return every computed result, or the compiler dead-code-eliminates the work and you measure nothing (the classic 8-12x phantom). On the JVM use a JMH Blackhole; read inputs from non-final state to defeat constant folding.
8. **Can't measure?** Mark the claim `estimated` in the PERF: marker with the reasoning. Estimated is honest; "should be faster" is not.

## Predict, then measure, then investigate the divergence

Measuring blind tells you A vs B. Measuring against a *model* tells you when something is wrong. Before optimizing a hot path:

1. **Predict** the expected cost from first principles: is this loop compute-bound or memory-bound (roughly how many arithmetic ops per byte touched, the roofline question)? How many allocations, syscalls, round trips, cache misses, using the numbers table (numbers.md)?
2. **Measure** with the protocol above.
3. If measured ~= predicted, the code is at its structural limit. Stop micro-tuning; change the algorithm or accept it.
4. If measured >> predicted, **the gap is the bug**: hidden aliasing, an N+1, cache thrashing, lock contention, coordinated omission. Chase the divergence, not the code. "When the estimated and actual performance differ, there is always something to learn" (Sites, *Understanding Software Dynamics*).

## Tools by ecosystem (use what exists, don't hand-roll)

CLI/any: `hyperfine` (reps/warmup/stats built in). Python: `pytest-benchmark`, `timeit`, `cProfile`/`py-spy` (see lang/python.md). JS/Node: `node --prof`, DevTools Performance panel, Lighthouse (Core Web Vitals: LCP/INP/CLS). Java/JVM: JMH with Blackhole, async-profiler (see lang/jvm.md). Go: `go test -bench -count=10` + `benchstat` + pprof. Rust: criterion. C/C++: Google Benchmark, perf, cachegrind. SQL: `EXPLAIN ANALYZE` before and after; the query plan is the profile.

## /perf-loop protocol: optimize until no improvement, without fooling yourself

Follows the systems that made measured optimization loops work (AlphaEvolve-style: propose -> evaluate programmatically -> keep only verified winners). Their two documented failure modes shape every rule: (a) execution time is a **noisy** fitness signal, so loops select noise winners unless statistics gate each step; (b) under optimization pressure agents **game the evaluator**. DeepMind's guidance is to track metrics you are *not* optimizing, because held-out metrics commonly lag the optimized one. The classic genetic-improvement failure: "speeding up" code by deleting functionality the tests don't cover.

1. **Fix the workload before starting:** a primary benchmark workload AND a held-out workload (different inputs/sizes, same code paths). The loop optimizes against the primary only; the held-out set is touched once, at the end.
2. **Baseline:** measure the primary workload with the full protocol; record it. Run the complete test suite and record the pass set.
3. **Each iteration:** profile -> pick the largest time-consumer by inclusive time (Amdahl) -> apply ONE ladder fix -> run the **full** test suite (any failure: revert immediately) -> re-measure identically -> keep only if significant AND above the noise floor; else revert and log "~". One fix per iteration: batched changes make measurement unattributable.
4. **Untargeted metrics ride along:** track memory and test-suite duration each iteration even while optimizing time. A "win" that doubles memory or was bought by weakening behavior shows up here.
5. **The loop never edits tests or benchmarks.** If a test seems wrong, stop and raise it. An optimizer that grades its own homework is the canonical gaming failure.
6. **Stop when any of:** two consecutive iterations at "~"; the top remaining hotspot is irreducible platform/IO cost; the timebox expires; or a fix regresses (revert, stop). Diminishing returns are the expected end state, not failure.
7. **Final validation, the only comparison that counts:** fresh measurement of original baseline vs final code on BOTH workloads. Because k iterations at alpha=0.05 accumulate ~5%*k false winners, per-iteration wins are provisional; the cumulative baseline-vs-final significance on the primary workload is the claim, and the held-out result is the overfitting check. If held-out shows no improvement, say so: you optimized the benchmark, not the code.
8. **Report:** baseline -> final on both workloads, iteration log (change, delta, verdict), untargeted-metric deltas, deferred markers created.

For ongoing repo-level regression detection (vs a single session), the industry pattern is change-point detection on benchmark time-series (E-divisive, as in MongoDB's CI and the Hunter tool, ICPE 2023). Suggest it if the project has benchmark CI; don't build it in-session.
