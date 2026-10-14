# C++ performance idioms

Sources: Effective C++ / Effective Modern C++ (Meyers); ISO C++ Core Guidelines; cppreference. Read when the hot path is C++. Flags: [safe] apply by default, [gated] measure first, [!] classic advice superseded by move semantics.

## Top idioms
1. **[safe] "in" params:** cheap-to-copy types (< ~3*sizeof(void*), ~24B) by value; larger by const ref. (Core Guidelines F.16)
2. **[gated] Pass-by-value + `std::move`** when a parameter is *always copied* and cheap to move (EMC++ Item 41): one extra move vs the two-overload approach, half the code.
3. **[safe] Return by value; rely on (N)RVO / guaranteed copy elision (C++17). Never `std::move` a return value**: it disables (N)RVO and can force a copy. *(Supersedes the classic "return by const ref for speed.")*
4. **[safe] Move semantics for resource-owning types:** `std::move` on rvalue refs, `std::forward` on universal refs (EMC++ Items 23-25).
5. **[safe] Don't assume moves exist or are cheap** for unknown/legacy types. They may silently be copies (EMC++ Item 29).
6. **[safe] `reserve()` before bulk `push_back`**: avoids repeated geometric reallocation + element moves.
7. **[gated] Prefer prefix `++` for heavyweight iterators/types**: postfix creates a temporary (More Effective C++ Item 6). Irrelevant for cheap iterators.
8. **[gated] Make small hot functions non-virtual**: the win is enabling inlining; a small function can cost more to call than to run. Negligible if per-call work is thousands of cycles.
9. **[gated] Limit inlining to small, frequently-called functions.**
10. **[gated] `emplace_back` over `push_back(T(...))`**; avoid unnecessary temporaries.

## Superseded: do NOT emit
Classic pre-C++11 "return objects via output parameters" / "return by reference for speed" is superseded by move semantics + guaranteed copy elision. Modern idiom: return by value (Core Guidelines F.20). A vector/string move is O(1) (~3-pointer transfer); returning by value is not a deep copy.

## Cache-oblivious recursion (sharpens blocking/tiling, rung 3)
For large-array numeric work (matmul, transpose, FFT, stencils, sorts), **prefer recursive divide-and-conquer over flat nested loops**. It is asymptotically cache-optimal across every cache level with no machine-specific tuning (Frigo et al., FOCS 1999: transpose Θ(1+mn/B); FFT/sort Θ(1+(n/B)(1+log_M n)); holds under the tall-cache assumption M=Ω(B²)). Reach for hand-tuned cache-aware **blocking** only when you have one target machine and need the last constant factor: well-tuned blocking can beat cache-oblivious code (Yotov et al.), but you must measure per machine. Combine: start cache-oblivious for portability, then tune constants. This is [measurement-gated] and mostly relevant to numeric kernels.
