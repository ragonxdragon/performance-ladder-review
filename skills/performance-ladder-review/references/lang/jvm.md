# JVM performance rules

Source: Optimizing Java (Evans/Gough/Newland), Shipilev's JVM Anatomy Quarks, OpenJDK JMH samples, Effective Java. Read when the hot path is JVM (Java/Kotlin/Scala).

## Rules
1. **Reduce allocation rate before tuning GC.** GC cost is downstream of allocation. Cutting MB/s of garbage beats tuning collector flags. ("Don't do the work" for the JVM.) [safe]
2. **Pick the collector by workload:** Parallel = throughput/batch; G1 = balanced default, large heaps; ZGC = sub-ms pauses, huge heaps (Generational ZGC is default from JDK 23, JEP 474); Shenandoah = low-latency + compressed-oops memory savings. Verify with GC logs. [measurement-gated]
3. **Avoid autoboxing in hot loops / large collections**: prefer primitives, `int[]`, `IntStream`. Boxed Integers outside the cache range **-128..127** allocate. [safe]
4. **`StringBuilder` for concatenation in loops** (straight-line concat is already lowered by javac; loops are the case that matters). [measurement-gated]
5. **Avoid finalizers; use try-with-resources.** [safe]
6. **Keep hot call sites monomorphic/bimorphic** to preserve inlining; ≥3 receiver types ("megamorphic") generally can't inline. The cost is lost inlining, not the vtable lookup: **~3 ns/op megamorphic vs ~1 ns/op monomorphic** (Shipilev, Anatomy Quark #16). `final`/`sealed` help. [measurement-gated]
7. **Let escape analysis / scalar replacement remove short-lived allocations** (default-on since JDK 7), but don't rely on it across inlining boundaries; storing a reference in a field/array disables it. [measurement-gated]
8. **Warm up to steady state (C2) before measuring**; account for warmup in serverless/CLI where C2 may never engage. [safe]

## Stream API data-access
- **Filter before map, and short-circuit.** filter is cheap/stateless; doing it before an expensive map runs the map on fewer elements. Use findFirst/anyMatch/limit.
- **Avoid boxing: use IntStream/LongStream/DoubleStream** for numeric aggregation (a Stream<Integer> boxes per element).
- **Parallel streams help only for large, CPU-bound, splittable work.** Goetz's NQ rule: for trivial per-element work, N should exceed ~10,000. They hurt on small or I/O-bound workloads; use virtual threads for I/O.

## JPA/Hibernate (see also data-access.md)
- **Kill N+1** with `JOIN FETCH`, `@EntityGraph`, or `@BatchSize` (turns N per-row selects into `WHERE id IN (...)` batches). "101 JDBC statements" for one list is the N+1 signature. Keep FetchType.LAZY default, fetch explicitly where you traverse.
- **DTO/constructor projections** (`SELECT new ...Summary(...)`) for read-only screens: no entity hydration.
- **Batch writes:** StatelessSession, JDBC batching (rewriteBatchedStatements, hibernate.jdbc.batch_size); tune JDBC fetch size (Oracle defaults to 10 rows/round trip).

## Benchmark on the JVM without fooling yourself
1. Use JMH; never a hand-rolled `System.nanoTime()` loop.
2. Enough warmup iterations to reach C2 steady state.
3. **Return every result or feed it to a `Blackhole`**: defeats dead-code elimination (the classic 8-12x phantom).
4. **Read inputs from non-`final` `@State` fields**: defeats constant folding.
5. Pad/isolate shared state to avoid false sharing.
6. Report percentiles + error bars; JVM timings are non-normal.
7. Validate under production-like load, data, and warmup, not on your laptop.

## Verified numbers
JVM object header: **12 bytes** (compressed oops, padded to 16) or **16 bytes** (uncompressed); **8 bytes** with compact headers (JDK 24/25, JEP 519). Autobox cache: **-128..127**. Megamorphic vs mono dispatch: **~3 ns vs ~1 ns/op**.
