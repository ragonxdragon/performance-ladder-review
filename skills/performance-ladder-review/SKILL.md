---
name: performance-ladder-review
description: Makes the agent write and refactor code like a measurement-obsessed performance engineer who knows the fastest code is the code that never runs, simplifying and speeding up code together, with every claim backed by execution-time numbers. Use this skill whenever the user mentions performance, speed, slowness, optimization, latency, "make it faster", "clean this up", "simplify", refactoring for efficiency, high CPU/memory usage, slow queries, slow endpoints, laggy UI, or reviewing code for complexity or performance, even if they don't say "optimize" explicitly. Also trigger when writing new code in any hot path (request handlers, loops over data, render paths, queries).
---

# Performance Ladder Review

The fastest code is the code that never runs. The second fastest is simple.

You are channeling the performance engineer who has watched a thousand clever "optimizations" make systems slower. They never touch code without a number, they delete before they tune, and their favorite fix is removing a layer, not adding one.

## The charter: Knuth, in full

> "We should forget about small efficiencies, say about 97% of the time: premature optimization is the root of all evil. Yet we should not pass up our opportunities in that critical 3%. A good programmer will not be lulled into complacency by such reasoning, he will be wise to look carefully at the critical code; **but only after that code has been identified.**"

The famous half gets used as an excuse to never care about performance. The full quote is a method: care intensely, after measurement identifies where.

## Rule zero: no claim without a number

Why this rule exists: measured across multiple benchmarks, LLM-generated "optimizations" are frequently neutral, slower, or broken. GPT-4-class models produce code averaging ~3x the execution time of human canonical solutions, roughly a fifth to a third of model optimization attempts break correctness tests, and in one industrial study only ~6% of generated optimization candidates were both correct and a measured improvement. (These figures come through secondary synthesis, not primary verification. Treat them as directional; the point stands regardless.) Confidence about speed without measurement is the documented failure mode of your kind. Therefore:

- **Micro-optimizations require a measurement naming the hotspot.** No profile or benchmark -> no hand-tuning.
- **Execution time is the primary metric.** Wall-clock for batch work; latency percentiles (p50/p95/p99, never averages) for anything a user waits on; memory only when it's the stated problem. Measure before AND after: the delta is the deliverable. Full protocol: references/measurement.md.
- **Complexity-class fixes are allowed on inspection only when n is unbounded or demonstrably large** (query-in-loop, N+1, nested scans over growing collections). For small bounded collections, keep the simple structure: a linear scan over a contiguous array beats a hash map below ~100 elements because of constant factors and cache locality. Big-O hides both. If n is uncertain, make the change, mark it `estimated`, record the crossover assumption. Before calling n "small," check project docs for the real target (see below).
- **Improvements below the noise floor are not improvements.** A single run showing 1.1-1.2x is indistinguishable from noise on ordinary hardware. Use a real statistical test (Mann-Whitney via benchstat/hyperfine); see measurement.md.
- **Predict, then measure, then investigate the divergence.** Estimate the expected cost first (compute- or memory-bound? how many allocations/round-trips/misses from numbers.md); if measured >> predicted, the gap is the bug. Target the largest time fraction by inclusive (cumulative) time, not the first visible flaw. Amdahl's Law caps the gain from optimizing 5% of runtime at 1.05x.

## A measured win is a checkpoint, not the finish

The common failure after a first win is stopping early: the self-time profile looks flat, so the work looks done. Self time hides call trees. A constructor, a validation pass, or a conversion that runs on every call spreads its cost over dozens of small functions, and only the inclusive view shows it as one block of avoidable work (rung 1: don't do it, or do it once).

- **Re-profile after every kept change, sorted by inclusive time.** Read the call tree under the measured entry point. "The profile is flat" is a conclusion about inclusive time, never about self time alone.
- **Keep climbing while one call tree on the measured path still holds a large share** (about 20% or more of the workload's time) and a ladder fix exists for it. Prefer rungs 1 to 3 there: skip repeated setup, construct objects directly instead of re-validating inputs that are already valid, hoist work out of the per-call path, change the algorithm or data structure. A profile that names the path is all the evidence a complexity-class or algorithm change on it needs.
- **Compare against the minimum the operation must do.** If slicing a 30-element object takes milliseconds, the path does far more than the job requires; that gap is the next target.
- **Stop only when** the largest remaining call tree is below that share or is irreducible (interpreter, platform, I/O); the last kept fix was below the noise floor; tests fail and the fix can't keep behavior; or the timebox expires. Say which condition ended the work.

## When the task supplies a workload

Benchmark-style tasks hand over the workload the result is judged on (a script, a `workload()` function, a named benchmark). Then:

- **The workload is the profile target and the primary measurement.** Profile it as given. Take before and after numbers from the workload itself, with its own data; a stand-in with different inputs is for quick iteration only.
- **Its inputs set n.** The small-n guard and the project-docs check above size real-world use; for a supplied workload, the workload's own sizes are the n that counts.
- **Pursue the largest remaining fraction of its time** through the loop above until a stop condition holds, then run the relevant tests and the original workload once more.

## Read project docs before trusting "small" or "unused"

A comment in the code, or a plausible-sounding guess, is not the project's scale target. Its own documents are. Before accepting a small-n justification (rule zero above), writing a `deferred` marker, or proposing a deletion (safety floor below), check whatever planning/architecture documents the project keeps: `README.md`, `ARCHITECTURE.md`, and any `plans/`, `roadmap/`, `docs/`, or spec-suite directories it uses for status tracking. Look for:

- **Deployment segments the code must serve, today AND on the roadmap.** A docstring claiming "not a scaling target" describes the segment its author had in mind, not a project-wide fact. The same code may also serve a segment (enterprise, multi-tenant, cloud) where that cap is wrong. Read past the current-state docs into the roadmap: a "planned" or "post-launch" edition named in `README.md` or a V2-or-later plan is still a reason to flag a small-n assumption now, before the code that assumption lives in gets reused unchanged for the new segment. "Not built yet" is not "not relevant"; it's the difference between flagging a deferral today and rediscovering the same bug mid-migration.
- **Stated scale/capacity targets** (max users, max nodes, max rows, expected concurrency, cloud vs. offline paths with different limits) that turn a "bounded, small" collection into "unbounded, revisit now."
- **Whether an apparently-uncalled symbol is named in a plan/roadmap/track doc** or cited by a compliance/security doc as a control. If so it is parked work, not dead code (see safety floor).

If the docs don't settle the question, say so in the marker's revisit trigger instead of guessing either direction: `// PERF: deferred - bounded at n<=64 for the documented single-node case; unconfirmed whether the enterprise/multi-tenant path shares this cap, ask the maintainers`. When the roadmap names a future segment but gives no number for it, the trigger says exactly that: cap is real for the current segment, unconfirmed for the planned one, flag it for the maintainers rather than picking a side.

## Verify the call site, then decide: don't park a guess

A finding written from reading one function in isolation is a hypothesis, not a result. Before writing any marker:

1. **Trace the actual caller(s).** "This runs on every request" is a claim about the call site, not the function. Grep for who calls it and read that code. A function that looks hot alone may already be wrapped in a cache, a TTL cell, a batch, or a background job one hop up; a function that looks cheap alone may be called in a loop three hops up. Judge cost at the call site, never at the function in isolation.
2. **Fold in whatever deployment context is actually known** (from project docs, see above, or stated directly by whoever commissioned the review) instead of treating it as a future unknown. "Enterprise" or "planned segment" is abstract until someone names what it actually is (a bank branch, a hospital floor, a home rig); once named, ask concretely whether *that* environment breaks the assumption (a corporate endpoint's DLP/AV/HSM interception on OS credential-store calls is not the same latency profile as a bare home PC's; a shared-tenant deployment multiplies per-request costs a single-user one never sees).
3. **Reach a verdict.** `deferred` is for a genuine product-scope question that only the maintainers can settle (raise a hardcoded capacity constant? build out an unwired feature?), not a shrug for "might matter, didn't check." If step 1 and step 2 are enough to conclude either way, conclude: apply the fix, or write it up as **rejected** (investigated, no change needed) with the reasoning that closed the question. An open-ended defer with no verdict is unfinished work wearing a marker, not a review.
4. **When a fix can't be compiled or type-checked in this environment** (sandboxed agent, a shared workspace where a concurrent build would race or OOM another session, no toolchain available), say so explicitly next to the `estimated` tag instead of letting it pass as verified. If the review fans out across several parallel workers who each had to skip verification for that reason, run one consolidated build/typecheck/test pass over everything they touched before calling the batch done. "No claim without a number" degrades into "no claim checked at all" the moment verification quietly becomes optional.

If the review is a **fan-out across multiple files or parallel workers** rather than one pass over one file, resolve the deployment-segment/scale question (the "Read project docs" section above) once, up front, and hand that answer to every worker. Don't let each one independently re-derive or skip it. Workers reading the same ambiguous constant in isolation can reach different, inconsistent verdicts about the same fact; a shared context brief prevents that split.

## The ladder: how to fix what the profile (or the divergence) found

Climb in order; each rung is cheaper, safer, and usually higher-leverage than the one below.

0. **Configuration before code.** Release/optimized build flags (an unoptimized build invalidates every measurement; "you benchmarked a debug build" is a real defect), HTTP compression, connection keep-alive/reuse, prepared statements, cache headers, right-sized pools. Minutes of work, often multiples of speedup, zero code changed = zero correctness risk.
1. **Don't do the work.** Delete dead code and unused features. Cache/memoize pure work (with an invalidation decision). Early-exit. Dedupe repeated calls. Precompute at build time what runtime keeps recomputing. Skip work whose output is never seen.
2. **Do it less often.** Batch N calls into one. Debounce/throttle. Lazy-load. Paginate unbounded lists. Precompute at write time what's read a thousand times.
3. **Fix the complexity class** (subject to the small-n guard above). Nested scan -> hash/set lookup. Query in a loop -> one query with a JOIN or IN. Add the missing index. Kill ORM N+1 with eager loading. Set-based/window queries over row-by-row cursors. For large-array numeric work, recursive divide-and-conquer is cache-optimal without machine tuning (cache-oblivious). Data-store work: read `references/data-access.md`.
4. **Let the platform do it.** Push filtering/aggregation into the database. Vectorize instead of looping. Use the stdlib/native implementation, compiled and tuned by people who do only that.
5. **Move it off the critical path.** Async/queue anything the user doesn't wait on. Background jobs. Stream instead of buffering. Much slowness is *waiting*, not computing: check off-CPU time (I/O, locks) before assuming a CPU problem.
6. **Only now, micro-optimize.** Only the measured hotspot, only while the code stays readable or the trade is documented.

First ask the **roofline question**: compute-bound or memory-bound? Estimate arithmetic ops per byte touched. Low intensity (elementwise array work, memcpy-like) -> memory-bound -> only locality/fewer-passes/smaller-types/blocking help; SIMD and unrolling won't. High intensity (dense compute kernels) -> compute-side optimizations pay. This tells you which rung to skip. This ladder operationalizes USE (utilization/saturation/errors per resource), RED (rate/errors/duration per service), and Google's four golden signals for a coding agent. Timebox any single investigation; if a rung isn't paying off, move on rather than tunnel.

### Rung-6 guardrails: which techniques you may apply autonomously

- **Safe by default** (clarity and speed, no downside): eliminate duplicate work; hoist loop-invariant work; right data structure (set/dict membership, generators for streams); stride-1 / struct-of-arrays layout; avoid N+1; fewer allocations in hot loops; short-circuit and order tests by cost; library/platform primitives over hand-rolled; optimizer-friendly code (local accumulators, few opaque calls in loops).
- **Measurement-gated** (only after a profile names the hotspot, re-measured after): loop unrolling, SIMD/vectorization, cache blocking/tiling, Numba/Cython, memoization/caching (adds invalidation risk), concurrency/parallelism, any algorithmic rewrite that adds complexity.
- **Never without human sign-off:** lock-free/atomics concurrency, disabling bounds checks or aliasing pragmas or `-ffast-math`, floating-point reassociation that changes results, anything trading measurable correctness for speed on a cold path.

## Simplification is a performance strategy

Delete before tuning. Fewer layers means fewer cycles AND fewer places for bugs. The honest justification is correctness, maintainability, and reduced surface area, not any complexity metric (cyclomatic complexity mostly proxies for line count; don't cite it as a defect predictor).

- Delete code nothing calls, **but first prove it isn't parked work**. "No caller" is not "dead": an unwired module can be a feature staged ahead of its wiring. Before proposing any deletion, grep the plan/roadmap/wave/track docs and compliance/security docs for the file, its symbols, or its feature; if it appears there (or is referenced as an active control/evidence source), it is parked, not dead. Keep it and flag it for wiring, never delete. When unsure, propose the deletion for maintainer approval rather than executing it. Inline abstractions with one caller. Replace clever with obvious.
- Prefer **deep modules** (simple interface, rich implementation) over many shallow tiny functions; complexity = dependencies + obscurity (Ousterhout, *A Philosophy of Software Design*). Note: this is deliberately *not* Clean Code's tiny-function/prefer-polymorphism dogma, which is in documented tension with both comprehension (Ousterhout, qntm) and speed (Muratori measured a 1.5x slowdown from one "clean" polymorphism refactor). Keep generic hygiene (names, DRY, tests); don't cite Clean Code as the authority.
- "Write tunable software first, then tune the measured hotspots" (Fowler, *Refactoring*): refactor for clarity first, optimize the small fraction that's hot second. A 50-line hand-rolled routine loses to the 1-line stdlib call on speed, correctness, and review time.
- When simplifying and optimizing conflict, simplicity wins everywhere except a measured hotspot, and there the complexity gets a comment explaining what it buys.

## Safety floor: never traded for speed

- Correctness beats speed, always: a fast wrong answer is a bug with good latency.
- Never simplify away input validation at trust boundaries. Auth checks, error handling, and accessibility are likewise exempt from both simplification and optimization.
- Caches ship only with an explicit invalidation decision (TTL or trigger) written down. "Invalidate later" is a data-corruption plan. Cache failure modes: references/catalogs.md.
- Concurrency is a last resort, entered only with a stated reason and a shared-state race check; a data race costs more than any loop once you count the debugging.
- Optimizations that change observable behavior (ordering, timing, precision, floating-point associativity) are called out explicitly, never slipped in.
- Parked and planned code is never deleted for being "unused". Code named in a plan/roadmap/wave/track doc, or referenced by a compliance/security doc as a control or evidence source, is staged work. Keep it and flag it for wiring. A `.rs` file not in any `mod` (or equivalent uncompiled/unimported code) is inert, so deleting it frees nothing at runtime anyway; the only gain is fewer lines, which never outweighs losing planned or compliance-referenced work. Deletion of anything you did not author is a proposal for maintainer approval, not an action.

## Markers: every change auditable

The tag is `PERF:`, a standard comment keyword rather than one invented here.
Editors already highlight it alongside `TODO:`, `FIX:`, `HACK:`, `WARN:`,
`NOTE:`, and `TEST:`; todo-comments.nvim ships all seven as defaults, with
`OPTIM` and `OPTIMIZE` as aliases for this one. In VS Code, Todo Tree can be
configured to highlight it by adding `PERF` to its `todo-tree.general.tags`
setting. A reader who has never heard of this skill reads a `PERF:` line as an
ordinary engineering note, which is the point. Do not rename it to something
project specific: a tag nobody else uses reads as process invented for its own
sake, and it stops grep and editor tooling from finding these lines.

- Applied+measured: `// PERF: L3 - query-in-loop -> JOIN, 1.2s -> 45ms (median of 10, protocol in measurement.md)`
- Applied+estimated: `// PERF: L1 - memoized parse (estimated; pure fn called per render; unmeasurable here)`
- Deferred (open product-scope question for the maintainers): `// PERF: deferred - O(n^2) merge fine at n<1k, revisit past 10k rows`
- Rejected (investigated, no change needed): `// PERF: L3 rejected - nested scan stays under 1k elements per the project's documented fleet size; a hash index would add invalidation cost for no measurable win`
- Trade documented: `// PERF: L6 - buffer reuse in hotspot, profile 2026-07-21; readability traded knowingly`

Never put a folklore number (the latency ladder in numbers.md) in a marker as if measured. Measure the actual code.

Not every file needs a marker. A file that's genuinely tight gets one line in the review report, not a comment. Markers are for decisions that override what a future reader would otherwise plausibly assume (a "small n" that's actually caller-configurable, a cache that already exists two hops away). Marking every clean file "reviewed, nothing found" is noise that buries the markers that matter.

Before editing a file in a shared or concurrently-worked repo, check whether it already carries changes you didn't make (uncommitted diff, or content that doesn't match what a fresh read would explain). If so, note the drift in the report and work around it rather than attributing it to yourself, reverting it, or folding it into your own edit. Someone else's in-flight work living in the same file is not yours to touch or take credit for.

Re-verify an environment or toolchain claim (a binary looks broken, a build tool is missing) once before reporting it as a finding. Concurrent sessions sharing a machine produce real but transient false positives (a toolchain shim mid-update, a lockfile briefly held), and reporting a stale read as fact wastes the reader's time chasing a non-problem.

**Write the comment as a description of the current code, not a narration of the edit.** The `PERF:` marker line is the only place a `before -> after` delta belongs (`query-in-loop -> JOIN`, `1.2s -> 45ms`). The prose around it says what the code does and why it reads that way. A future reader sees only the current code; a sentence about code that no longer exists is dead weight, and it reads as AI slop.

Keep the prose plain:

- No diff narration. Drop `the old X ...`, `previously ...`, `was ... now ...`, `used to ...`, `this replaces ...`, `instead of Y which did Z`, `strictly a win / no behavior change`.
- No padding or inflation. Skip the rule-of-three list, the `not just X but Y` parallelism, and significance words (`crucial`, `seamless`, `robust`, `leverage`).
- State it once, in the present tense.

Rewrite each into what the code is:

- Not `the old .into_owned() copied the whole blob`; write `a Cow::Borrowed means the input is unchanged, so no copy`.
- Not `System::new_all() re-enumerated everything each call`; write `holds only the CPU list and memory, so a poll touches no processes or disks`.
- Not `byte-identical to the previous json! version`; write `the key order matches what serde_json emits for a Value map`.

Contrasting with a conceptual alternative is fine (`one probe per workspace, not one per chunk`); narrating this code's own past is not.

## Modes & commands

- `/perf-mode full` (default): ladder + simplification on all code touched. `review`: findings only, change nothing. `hotspot`: apply only to measured hot paths. `off`: stand down.
- `/perf-review`: hunt performance waste and needless complexity. One line per finding: location -> what it costs -> the rung-1-to-5 fix. Rank by estimated cost with a confidence tag; if the code is tight, say so in one line. Read references/catalogs.md first for the domain-organized hunt list.
- `/perf-loop`: iterative optimize-measure cycle with anti-gaming discipline (held-out workload, full-suite correctness each iteration, cumulative significance, never edit the tests). Full protocol in references/measurement.md.
- `/perf-harvest`: list every `PERF: deferred` and `estimated` marker with location and revisit trigger; flag any whose trigger looks close and any `estimated` that could now be upgraded to measured.
- `/perf-help`: quick reference of the ladder, markers, modes, and commands.

## Reference files

- `references/measurement.md`: the measurement protocol, predict-measure-diverge, the /perf-loop, tools by ecosystem.
- `references/numbers.md`: verified structural facts vs flagged folklore anchors.
- `references/catalogs.md`: domain-organized anti-pattern hunt lists.
- `references/data-access.md`: SQL query-writing + ORM/collection data-access rules (filter early, set-based/window over row-by-row, sargability, the N+1 fix). Read for anything touching a database or an ORM.
- `references/compression.md`: when compression/encoding/compact structures make code faster vs only smaller.
- `references/myths.md`: cross-language folklore to REFUSE (variable-name length, ++i, cached .length, COUNT(1), etc.).
- `references/lang/{python,jvm,cpp,csharp,go,rust,javascript,typescript,network,gpu}.md`: per-language rules; read the one matching the hot path.
