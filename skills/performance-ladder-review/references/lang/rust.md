# Rust performance rules

Source: The Rust Performance Book (nnethercote.github.io/perf-book), the Rust Book, Rust std docs. Read when the hot path is Rust.

## Rules

1. **Benchmark with Criterion, in `--release`.** [safe] Debug builds prioritize compile speed; debug benchmarks are meaningless. `cargo bench` uses release by default; `cargo run` does not.
2. **Set the max-speed build profile.** [safe, config rung] `lto = "fat"`, `codegen-units = 1`, `panic = "abort"`, `target-cpu=native`, consider an alternative allocator. The Performance Book: LTO "can improve runtime speed by 10-20% or more"; codegen-units=1 misses fewer optimizations. (panic="abort" and target-cpu=native are trade-offs: no unwinding; won't run on older CPUs.)
3. **Prefer iterator chains over manual indexed loops.** [safe] Zero-cost abstraction: "in many cases, Rust code using iterators compiles to the same assembly you'd write by hand" (Rust Book). Iterators also elide the bounds checks that `data[i]` incurs.
4. **Avoid unnecessary `.clone()` and needless heap allocations; borrow instead.** [safe] Cloning to satisfy the borrow checker is the most common avoidable cost; accept `&str`/`&[T]` for read-only params. Cheap Copy/Rc clones are fine.
5. **`with_capacity` when the final size is known; reuse Vecs.** [safe] Turns many growth-reallocations into one.
6. **Don't `.collect()` mid-chain or when you'll re-iterate; return `impl Iterator`.** [safe] collect allocates a collection; keep the chain lazy. Implement size_hint/ExactSizeIterator::len to cut downstream collect allocations.
7. **On hot paths prefer static dispatch (generics/monomorphization) over `dyn Trait`.** [measurement-gated] `dyn` blocks inlining and adds a vtable lookup. Measured: static 64ms vs dynamic 216ms (3.375x) when the type decision is inside a 20M-iteration loop; only ~1.2x when hoisted out. Hoist the dispatch decision out of tight loops.
8. **Watch `Rc`/`RefCell`/`Arc<Mutex>` overhead; don't reach for `Arc<Mutex>` prematurely.** [measurement-gated] Arc uses atomic refcounting (costlier than Rc); Mutex "rapidly loses performance when in active use by multiple threads." Restructure to avoid shared mutable state; measure contention before adding locks.
9. **Get bounds-check elision through iterators/slicing, not by fighting the optimizer.** [measurement-gated]
10. **`unsafe` only as a measured last resort with sign-off.** [never-without-signoff] `get_unchecked` etc. justified by profiling and reviewed, never speculative.

Reversals: collecting iterators unnecessarily, and cloning to appease the borrow checker instead of restructuring, are the two most common self-inflicted Rust slowdowns.
