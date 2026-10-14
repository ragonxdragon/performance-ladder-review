# Hunt catalogs: read before any /perf-review

One line per finding: location -> what it costs -> the rung-1-to-5 fix. Rank by estimated cost, tag confidence. Only report domains present in the codebase.

## Data / database

N+1 and query-in-loop (-> JOIN, IN, eager loading, dataloader batching) - missing index on filtered/joined/sorted columns (verify with EXPLAIN) - non-sargable predicates forcing full scans (function-wrapped columns, leading-wildcard LIKE) - SELECT * on wide tables - over-eager loading (huge object graphs when a few columns suffice) - missing pagination on large result sets - unbounded IN-lists - missing connection pooling.

## Backend / general

Sync IO on a hot path - repeated parse/serialize of the same data - string building in tight loops - allocation in tight loops - nested scans over the same collection (subject to the small-n guard) - work computed then discarded - hand-rolled versions of stdlib/platform features - speculative abstraction and dead flexibility - single-caller indirection layers.

## API / distributed

Chatty APIs (N round trips for one screen -> batch endpoint; see lang/network.md) - over-fetching and under-fetching - missing timeouts on outbound calls - retries without backoff/jitter (retry storms) - tail-latency amplification in fanout: at 1-in-100 slow servers a request touching 100 servers is slow ~63% of the time, so p99 of the slowest dependency becomes your median; mitigate with hedged requests (paired with a circuit breaker) and reduced fanout (Dean & Barroso, The Tail at Scale) - missing circuit breakers on flaky dependencies.

## Caching

Cache without an invalidation decision (TTL or trigger) - **stampede/thundering herd**: mass concurrent misses recompute the same key -> coalesce requests, lock-and-wait, or refresh early - **penetration**: repeated misses for keys that don't exist -> negative-cache or bloom filter - **avalanche**: simultaneous mass expiry -> jitter the TTLs - caching non-deterministic or per-user data under a shared key.

## Frontend

Unnecessary re-renders (state too high in the tree, unstable props/identities) - missing memoization on measured-expensive renders (don't memo everything; measure) - bundle bloat and missing code-splitting (a component library for what a native `<input>` does) - layout thrash (interleaved reads/writes of layout properties) - main-thread blocking work (-> workers, chunking) - Core Web Vitals regressions: LCP (largest contentful paint), INP (interaction latency), CLS (layout shift), the industry-standard user-facing metrics; measure with Lighthouse/DevTools.

## Memory / GC

Leaks (listeners never removed, unbounded caches, accumulating globals) - GC pressure from allocation churn in hot loops (reuse buffers only in measured hotspots, L6 with a marker; on the JVM see lang/jvm.md) - unbounded in-memory collections that should stream or paginate.

## Data layout / mechanical sympathy

Pointer-chasing structures where a contiguous array would do - array-of-structs where struct-of-arrays would vectorize (hot numeric loops) - iterating data in non-memory order (respect stride-1) - false sharing: unrelated hot fields sharing a 64-byte cache line across threads. For large-array numeric work, recursive divide-and-conquer is cache-optimal across all cache levels without per-machine tuning (cache-oblivious; Frigo et al.). It is a good default before hand-tuned cache-aware blocking, which can beat it once tuned for one machine.
