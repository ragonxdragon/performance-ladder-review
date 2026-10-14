# JavaScript / Node / V8 performance rules

Source: V8 blog (v8.dev), web.dev "Performance tips for JavaScript in V8", Node.js docs. TypeScript inherits ALL of these: it compiles to JS on the same engine (see typescript.md for TS-only concerns). Read when the hot path is JS/TS/Node.

## Runtime rules
1. **Keep object shapes stable.** Initialize all properties in the constructor, in the same order; never add/delete properties later. V8 assigns a hidden class per shape; stable shapes let it use monomorphic inline caches. Adding a property later forks the hidden class and can deoptimize methods. [safe]
2. **Keep property-access sites monomorphic.** One shape = fast; up to ~4 = polymorphic; beyond = megamorphic (V8 abandons site-specific optimization). [safe]
3. **Don't mix element kinds in arrays; keep them packed.** V8 tracks a one-way lattice PACKED_SMI -> PACKED_DOUBLE -> PACKED (each with a HOLEY variant); transitions only go downward and are permanent. "Operations on packed arrays are more efficient than on holey arrays" (V8 blog). [safe]
4. **Avoid holey/sparse arrays.** `new Array(n)` is immediately HOLEY and stays holey forever; grow from `[]` via push, or use array literals. [safe]
5. **Don't block the event loop.** V8 is fast except regexes and JSON ops. Move CPU-bound work (large JSON.parse/stringify, sync fs, hashing) off the hot path: worker_threads for CPU-bound (stable since Node 12), streams for large I/O, cluster for multiple cores. Pool workers; transfer ArrayBuffers instead of copying. [safe; this is the ladder's off-critical-path rung]
6. **Reduce allocation in hot loops; reuse buffers; avoid closures capturing large scopes.** Pre-allocate arrays of known length. [safe]

## Debunked folklore (do NOT "optimize" these; modern V8 handles them)
- Caching `array.length` or hoisting an element into a temp: measured **zero effect** on V8 (leanylabs). V8 already does it.
- `++i` vs `i++`: identical after compilation.
- `for` vs `forEach` vs `map` as a speed lever: mostly folklore; real cost is allocation (`map` builds a new array; don't use it just to iterate) and that `forEach` can't `break`.
- `try/catch` deopt: real under old Crankshaft (~90% slowdown), fixed under TurboFan (V8 5.6+). Don't contort code to avoid it on modern Node.
- `delete obj.prop`: this one IS real. It triggers a hidden-class change; use `obj.prop = undefined` or a Map on hot objects.
