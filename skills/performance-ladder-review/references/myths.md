# Cross-language folklore: do NOT "optimize" these

This skill should REFUSE these changes and cite the debunk, because they cost nothing at runtime and often hurt readability (against the simplification thesis). Modern compilers/JITs/optimizers already handle them.

- **Variable/identifier name length affects runtime speed**: FALSE in every compiled/JIT language. Names resolve to offsets/registers at compile time and don't exist in optimized machine code. Zero runtime effect in Rust, C#, Go, JIT'd JS/TS. Never shorten names for "speed."
- **`++i` is faster than `i++`**: folklore for primitive loop counters; compilers emit identical code when the result is unused (C-family, Rust, Go, JS). (Only matters for heavyweight C++ iterators.)
- **Caching `array.length` / manual loop-index tricks**: folklore on modern engines; V8 measured zero effect; Go/Rust compilers hoist invariants and elide bounds checks on idiomatic patterns.
- **Manual strength reduction / constant folding / hoisting invariants**: the compiler already does these (LLVM, RyuJIT, gc, TurboFan). Hand-doing them adds no speed and hurts readability.
- **"Fewer/shorter source lines = faster"**: FALSE; post-compilation the source layout is gone.
- **`for` vs `forEach` vs `map`/functional style as a major perf lever**: mostly folklore; real cost is allocation (map builds a new array), not the loop construct.
- **SQL:** COUNT(1) vs COUNT(*) (identical), WHERE-predicate order (optimizer reorders), EXISTS-always-beats-IN (usually same plan), subquery-always-slower-than-join (often same plan). See data-access.md.

"Myth" means "no measurable runtime effect on the modern optimizer," not "never true on any historical engine." The author's job is mostly to NOT DEFEAT the optimizer (preserve sargability, keep it IQueryable, filter-before-map) rather than to hand-optimize.
