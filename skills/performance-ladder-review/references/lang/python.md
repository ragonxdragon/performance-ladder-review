# Python performance rules

Sources: High-Performance Python (Gorelick & Ozsvald). Read when the hot path is Python.

## Profile in this order (never guess)

cProfile (which function) -> line_profiler / `%lprun` (which line) -> memory_profiler (if RAM is suspect) -> py-spy (low-overhead, production, no code change). Re-profile after every change.

## Top rules

1. **Vectorize with NumPy** for numeric array work: contiguous memory, arithmetic in chunks without Python-level looping. Typical wins are large. **Trap:** calling NumPy element functions *inside a Python for-loop* does NOT help; the win is whole-array operations. Python bytecode does not auto-vectorize.
2. **Sets/dicts for membership**, O(1) average, not lists (O(n)).
3. **Generators for large sequences** to avoid materializing everything in memory.
4. **Prefer built-in / stdlib functions** (C-implemented) over hand-rolled Python loops (`sum`, `any`, `sorted`, `str.join`).
5. **CPU-bound -> multiprocessing** (separate processes bypass the GIL, at IPC/memory cost); **I/O-bound -> asyncio/threading**. The GIL means threads don't run CPU-bound bytecode in parallel.
6. **Assume you're I/O-bound or memory-bandwidth-bound** until profiling proves otherwise (von Neumann bottleneck).
7. **Reach for Numba/Cython only after** profiling + vectorization fail to hit the target, not first.
8. **Hoist attribute lookups and method bindings out of hot loops** (`append = lst.append` before a tight loop); each `.` is a dict lookup.
9. **Contiguous typed arrays** (NumPy / `array`) over lists-of-objects for numeric data: locality plus far less memory.
10. **`str.join` over `+=` in loops**; string concatenation in a loop is repeated reallocation.

## Free-threading note (3.13/3.14, experimental)

3.13's free-threaded build (PEP 703) disables the GIL: CPU-bound threads can run in parallel (reported ~8x on some workloads), but single-thread code ran ~40% slower in 3.13t (~5-10% in 3.14). I/O-bound/asyncio apps see little change. Benchmark against the free-threaded build only for CPU-bound new work; don't assume.

## ORM / data-access (see also data-access.md)

- **Kill N+1 with eager loading.** Django `select_related` (FK/1-1 -> JOIN) and `prefetch_related` (reverse FK / M2M -> batched `IN`). SQLAlchemy `joinedload` (JOIN) vs `selectinload` (batched IN, usually best for collections) vs default lazy; `raiseload` guards accidental lazy loads.
- **Project only needed columns:** Django `.only()`/`.defer()`/`.values()`; SQLAlchemy `load_only()`. Accessing a deferred field triggers another query.
- **Bulk DML:** `bulk_create()`, `bulk_update()`, `QuerySet.update()`/`delete()` instead of saving in a loop.
- **Stream large result sets:** `QuerySet.iterator(chunk_size=...)` (note: historically disabled prefetch_related; check your version).
- **Push work into the DB, or vectorize** in pandas/NumPy. Django docs: "Do database work in the database rather than in Python."
- **Generator/comprehension pipelines filter early:** `[f(x) for x in xs if pred(x)]` never builds a large intermediate you immediately shrink.
