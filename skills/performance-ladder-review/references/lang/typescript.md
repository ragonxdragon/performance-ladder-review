# TypeScript performance rules

Source: TS Handbook, microsoft/TypeScript wiki Performance page, TS release blog, tslib. **Anchoring fact: type annotations are ERASED at compile time and have ZERO runtime cost.** "TypeScript is slower than JS at runtime" and "adding types makes code faster" are both FALSE. Two distinct areas: (A) runtime of the emitted JS, (B) compile-time / build speed. Read alongside javascript.md: all V8 runtime rules are inherited.

## Area A: runtime (emitted-JS) rules
1. **Target modern ES (ES2017+ / ESNext).** [safe, config rung] Emits native async/await, classes, spread; low targets (ES5) emit slow helper state machines (`__awaiter`/`__generator`/`__spreadArray`) that add runtime cost and bloat. If you must downlevel, set `importHelpers: true` + `tslib` to dedupe helpers.
2. **Prefer union-of-literals or `as const` objects over `enum`.** [safe] Regular `enum` emits a runtime IIFE object with property-access indirection and resists tree-shaking; unions emit nothing, `as const` a plain tree-shakeable object, both with identical type safety.
3. **`const enum` only in whole-program-compiled internal code.** [measurement-gated] Inlines values (no runtime object) but breaks under isolatedModules/Babel/esbuild/swc and is unsafe to publish.
4. **Keep decorators off hot method-wrapping paths.** [measurement-gated] Decorator functions run once per class at definition time (cheap); only a decorator that *wraps* a method costs per-call. Prefer standard (TC39) decorators for new code; legacy needed for Angular/NestJS.
5. **Prefer ES modules over namespaces** (namespaces emit non-tree-shakeable IIFEs). [safe]
6. **Everything else at runtime = the inherited V8 rules.** Types are erased; nothing TS-specific remains. [myth-debunked]

## Area B: compile-time / build speed (the real TS-specific lever)
7. **Split type-checking from transpilation.** [safe] Use esbuild (~45x) or swc (~20x faster than tsc for emit) for the build; run `tsc --noEmit` in CI/editor for type errors. Biggest build-speed win.
8. **Write checker-friendly types.** [safe] Interfaces over large intersections (interface relationships are cached); annotate function return types (saves inference); base types over big unions (a >12-member union hurts compile speed, per the official wiki); name complex conditional/mapped types so they cache.
9. **Configure for scale.** [measurement-gated] Project references (5 to 20 per workspace), `incremental`, `skipLibCheck` (masks .d.ts conflicts; speed only), tight include/exclude, scoped `types: []`.
10. **Measure and adopt the native compiler.** [measurement-gated] `tsc --extendedDiagnostics` (watch Check time), `tsc --generateTrace`. TypeScript 7.0 (Go native port, GA July 2026) is ~8 to 12x faster with identical output: a pure DX win, zero runtime effect.
