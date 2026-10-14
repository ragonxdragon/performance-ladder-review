# Numbers to reason with

Order-of-magnitude anchors for the predict-then-measure step. **These are for estimation ratios, not claims.** Absolute values are hardware-dependent; the original latency figures trace to Jeff Dean (~2009) and modern chips differ (branch mispredict ~3-5ns, L2 ~4ns). Never put a folklore number in a `PERF:` marker as if it were measured. Measure the actual code.

## Latency ladder (approximate, folklore-tier, for mental sanity checks only)

| Operation | ~Time |
| --- | --- |
| L1 cache reference | 0.5-1 ns |
| Branch mispredict | 3-5 ns |
| L2 cache reference | 4-7 ns |
| Mutex lock/unlock | 17-25 ns |
| Main memory reference | ~100 ns |
| Compress 1 KB | ~3 us |
| Send 1 KB over 1 Gbps | ~10 us |
| SSD random read (4 KB) | ~150 us |
| Read 1 MB sequentially from memory | ~250 us |
| Round trip within datacenter | ~500 us |
| New TCP+TLS connection setup | ~2-3 round trips (see lang/network.md) |
| Read 1 MB from SSD | ~1 ms |
| Disk seek | ~10 ms |
| Cross-continent round trip | ~150 ms |
| Human notices lag | >100-200 ms |

Use: no CPU tuning saves a function making a network call per loop iteration. The round trips ARE the runtime (a rung-2 batching problem, not rung-6). Cache line = **64 bytes** (verified, near-universal on x86-64/ARM64): data within one line is nearly free to touch together; struct fields that change together should share a line, hot/cold fields should not (false sharing).

## Verified structural facts (safe to reason from, not folklore)

These are O-class characterizations or documented sizes, not timing folklore:

| Fact | Value | Source |
| --- | --- | --- |
| JVM object header (64-bit, compressed oops) | 12 bytes, padded to 16 (8-byte alignment) | JEP 450/519, Baeldung |
| JVM object header (64-bit, uncompressed) | 16 bytes | JEP 450 |
| JVM compact headers (JDK 24/25, JEP 450/519) | 8 bytes | JEP 519 |
| Integer autobox cache range | -128..127 (same object reused) | JLS / Integer.valueOf |
| JVM megamorphic vs monomorphic dispatch | ~3 ns vs ~1 ns per op | Shipilev, JVM Anatomy Quark #16 |
| C++ std::vector/string move | O(1): transfers ~3 pointers, regardless of size | ISO C++ / cppreference |
| C++ std::vector deep copy | O(n): new buffer + per-element copy | ISO C++ |
| C++ "cheap to copy" threshold | `< 3 * sizeof(void*)` (~24 B): pass by value; else const ref | Core Guidelines F.16 |
| SIMD register widths | 128/256/512-bit = 2/4/8 doubles per instruction | ISA (SSE/AVX2/AVX-512) |
| Cache-oblivious matrix transpose misses | Theta(1 + mn/B) | Frigo et al., FOCS 1999 |
| Cache-oblivious FFT/sort misses | Theta(1 + (n/B)(1 + log_M n)) | Frigo et al., FOCS 1999 |
| Tall-cache assumption | M = Omega(B^2) ("usually true in practice") | Frigo et al., FOCS 1999 |

**Approximate / workload-dependent (mark as such, never assert):** C++ virtual-call overhead (~1.25-5x a direct call; the real cost is lost inlining, not the vtable lookup); autobox absolute cost; allocation cost (tens to ~100+ ns, but the real cost is GC pressure). Function-call overhead is small in absolute terms but blocks optimization across the boundary (CS:APP).
