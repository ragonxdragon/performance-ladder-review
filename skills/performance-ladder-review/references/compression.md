# Compression, encoding, and compact structures: for SPEED

The honest framing: compression classically trades CPU for space, so it makes code **slower** on a CPU-bound path whose data already fits in cache. It's a genuine SPEED win only in two cases:
1. **The path is bandwidth-bound** (I/O, network, or memory-bandwidth-bound with the CPU stalling on loads) and decode is faster than the saved transfer. "No bit is faster than a bit not sent."
2. **You can compute on the ENCODED form without decoding** (dictionary codes, RLE runs, bitmaps, FOR/delta). This cuts both CPU and I/O and is the strongest win.

Everything here is [measurement-gated] on execution time AND the untargeted metric (memory/ratio). A change that shrinks memory but regresses p50/p99 latency is space-for-CPU, not a speed win.

## Decision procedure
1. Is the code moving bytes across a slow tier? (memory-bandwidth near STREAM peak, I/O wait, load stalls.) If no and it's CPU-bound in cache -> compression will slow it; stop.
2. Can you compute on the encoded form (dict codes, RLE, bitmaps, FOR)? -> strongest speed win (operate-on-compressed reduces CPU + I/O; measured 3.3x to 10.3x in columnar DBs, Abadi SIGMOD 2006).
3. Is the data repetitive/low-cardinality? Dictionary/RLE need redundancy; high-entropy data yields no ratio and pure CPU loss.
4. Does the compact form stay in a faster cache tier than the uncompressed form would?
5. Is decode SIMD-friendly/branchless? Block schemes beat branchy per-element varint.

## Techniques (tagged)
- **Safe on the right (bandwidth-bound) workload:** LZ4/Snappy on I/O-bound paths (LZ4 decompresses multi-GB/s, "fast enough to be I/O bound"; Snappy ~500 MB/s decode); dictionary encoding on low-cardinality columnar scans; Roaring Bitmaps for large integer sets/set-ops (up to 900x faster intersections than RLE bitmaps AND smaller); block SIMD integer decode (StreamVByte >4B ints/s); bit-packing/SoA/smaller types that shrink the working set into a faster cache tier.
- **Measurement-gated:** zstd level choice (ratio vs decode budget: LZ4 decompresses 3 to 5x faster than zstd, zstd ~30% smaller, so LZ4 for hot paths, zstd for cold storage); interning (see below); LUT-vs-recompute; FSST for string columns (L1-resident symbol table, operate-on-compressed).
- **Niche/avoid as default:** succinct structures (FM-index, wavelet trees) where a plain array fits in RAM; heavy codecs (xz/LZMA, zstd-max) on hot read paths.

## Reversals / anti-patterns (hard rules)
- Compressing high-entropy or already-compressed data (JPEG/zip/encrypted -> ~1.0x ratio, pure CPU loss).
- Compressing tiny payloads with a general codec (framing dominates). Use a **trained dictionary** (zstd/LZ4 dict mode: up to 5x at <1KB) or skip.
- **LUTs that thrash cache**: "you only need to miss in the cache once to lose all the time you won on the previous hundred calls" (Torvalds). Small L1-resident tables win; large sparse tables lose; recompute cheap functions (or use a hardware instruction like POPCNT).
- **`String.intern()` on hot paths**: the native JVM string table adds sync/native-boundary/GC-pause cost (Shipilev); use a hand-rolled `ConcurrentHashMap` interner (Effective Java: ~6x faster).
- Double compression; compressing a CPU-bound in-memory hot loop where you're not moving bytes.

## Safety
Compression/encoding adds a failure surface: corruption and **dictionary/symbol-table versioning** (a message compressed with dict vX can't be read with vY). Same rule as caching: every compression/dictionary decision needs an explicit invalidation/versioning decision, and keep a raw fallback for incompressible inputs.
