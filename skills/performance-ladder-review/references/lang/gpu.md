# GPU / CUDA performance rules

Source: Programming Massively Parallel Processors (Kirk & Hwu). Read ONLY when code targets CUDA/GPU. Rung-6, measurement-gated. The unifying idea: this is the same memory-hierarchy and locality reasoning as CPU code (roofline: coalescing and tiling are memory-bound fixes; occupancy is latency-hiding), expressed in warps and shared memory.

## The book's optimization checklist, in order

1. **Maximize occupancy**: enough active threads/warps to hide memory latency; tune threads-per-block, shared memory, registers. Block size a multiple of 32 (warp size).
2. **Coalesce global memory access**: adjacent threads in a warp touch adjacent addresses (the GPU form of stride-1). Non-coalesced access multiplies memory traffic.
3. **Minimize control divergence**: threads in a warp taking different branches serialize; pack active threads, avoid data-dependent branching within a warp.
4. **Tile reused data into shared memory**: load once into on-chip memory, reuse (the GPU form of cache blocking).
5. **Privatization**: threads accumulate into private copies, combine with a final atomic, to cut contention.
6. **Thread coarsening**: assign more work per thread to cut redundant loads/sync, but not so far it hurts occupancy.

Avoid shared-memory bank conflicts. Profile memory-bound vs compute-bound before choosing which of these to apply: same roofline question as the CPU.
