# C# / .NET performance rules

Source: Microsoft .NET performance docs, the .NET blog, EF Core docs. Read when the hot path is C#/.NET.

## Rules
1. **Eliminate boxing/unboxing on hot paths.** [safe] Boxing wraps a value type in a heap object (alloc + copy + GC). Happens implicitly with `object`/interface assignment, non-generic collections (ArrayList), value types to object params. Use generics (`List<int>` not ArrayList).
2. **Use `Span<T>`/`ReadOnlySpan<T>`/`stackalloc` for zero-copy slicing.** [safe] Measured (endjin): a LINQ hot path at 80.57µs / 126.43 KB became 45.77µs (~43% faster) with **32 bytes allocated, a 4,000x reduction**, via span-based string splitting. Constraint: Span is stack-only (no fields, no boxing, limited in async/yield).
3. **Reduce Gen0 pressure; pool with ArrayPool/ObjectPool.** [measurement-gated] Pooling adds complexity and can backfire (one case was 226x slower before tuning). Measure.
4. **Be cautious with LINQ on hot paths, but don't cargo-cult "LINQ is always slow."** [measurement-gated] LINQ allocates iterators/closures; on zero-allocation hot paths it hurts; elsewhere readability wins. Rewrite to loops/Span only where profiling shows it.
5. **`StringBuilder` for repeated concatenation** (`+` in loops is O(n²) allocation). [safe]
6. **async/await correctly.** [safe/measurement-gated] `ValueTask` for hot frequently-synchronous paths (avoids Task allocation); `ConfigureAwait(false)` in library code; never block on async (`.Result`/`.Wait()` -> deadlock risk).
7. **Prefer struct enumerators; avoid closure allocations in tight loops.** [measurement-gated] `foreach` over a concrete collection uses a no-alloc struct enumerator; over IEnumerable<T> it boxes.
8. **Let tiered compilation + Dynamic PGO work; add ReadyToRun/AOT by deployment shape, not reflex.** [config/measurement-gated] Plain JIT gives best steady-state throughput; R2R for faster startup (~2 to 3x binary size); Native AOT only when startup/footprint dominates and no reflection.

## EF Core data-access (see also data-access.md)
- **Filter before you materialize.** Keep it IQueryable so filtering translates to SQL; never `ToList()` then `Where()` (that pulls all rows and filters in memory, the "40ms in dev, 11s in prod" bug). EF Core 3.0+ throws on untranslatable Where; use `.ToQueryString()` to inspect.
- **Project with `Select` into a DTO** to fetch only needed columns; use `AsNoTracking()` for read-only.
- **Kill N+1 with `Include`/`ThenInclude`; use `AsSplitQuery()`** to avoid Cartesian explosion on multiple sibling collections. Avoid lazy loading (EF docs: it "makes it extremely easy to inadvertently trigger the N+1 problem").

## Debunked
- "struct is always faster than class": FALSE; large structs copy on every pass/return and can be slower. Microsoft: "If an object is typically going to get boxed, it would be better off being an Object in the first place."
- "`sealed` for perf": rarely a measurable win alone; apply for design reasons.
