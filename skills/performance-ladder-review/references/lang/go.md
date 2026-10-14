# Go performance rules

Source: Dave Cheney's High Performance Go, the Go blog, Efficient Go (Płotka), go-database-sql.org. Read when the hot path is Go.

## Rules
1. **Preallocate slices/maps with known capacity: `make([]T, 0, n)`.** [safe] Avoids repeated grow-reallocations; measured ~8 extra allocs and ~40% of runtime in an append-in-loop benchmark without it.
2. **Cut allocations to cut GC; verify escape with `go build -gcflags=-m`.** [safe] Values that escape to the heap drive GC cost. "The cost of memory allocation can far exceed that of business logic."
3. **`strings.Builder` (with Grow) for concatenation; prefer `[]byte` to avoid conversions.** [safe] Measured (freshman.tech): `+` operator = 24.8M ns/op, 1009 allocs/op; `strings.Builder` = 40K ns/op, 1 alloc/op. `fmt.Sprint` is slowest (reflection). Minimize string↔[]byte conversions (they allocate).
4. **Reuse objects with `sync.Pool` for high-churn temporaries.** [measurement-gated] Best for short-lived buffers; objects can be GC'd out of the pool; reset before reuse.
5. **Avoid `interface{}`/`any` boxing on hot paths.** [measurement-gated] Can allocate and defeats inlining; prefer concrete types or generics.
6. **Choose value vs pointer receivers deliberately.** [measurement-gated] Pointer receivers avoid copying large structs; value receivers copy (cheap for small, costly for large). Stdlib convention: pointer receivers for mutation types (sync.Mutex, bytes.Buffer).
7. **Measure with pprof + benchstat; test with `-race`.** [safe] Cheney: benchmark first, then CPU/mem profile; "Do not enable more than one kind of profile at a time."

## database/sql data-access (see also data-access.md)
- **Query only needed columns; avoid row-by-row round trips.** `db.Query()` "actually prepares, executes, and closes a prepared statement: three round-trips" (go-database-sql.org); careless looping triples DB interactions.
- **Prepared statements for repeated queries** reuse the plan, but keep them alive for the app lifetime; don't re-prepare per call.
- **Batch DML** (multi-row INSERT in a transaction). Mind PostgreSQL's **65,535 bind-parameter cap** per statement: chunk large inserts (~21,845 rows x 3 cols).

## Debunked
- "Goroutines are free": cheap, not free; each starts with a **2 KB** stack (runtime/stack.go `_StackMin = 2048`); ~1M goroutines ≈ 2 GB of stacks.
- "defer is slow": real pre-1.13, negligible now. Go 1.14 made a deferred mutex unlock "~0.7 of a nanosecond slower" (Cheney). Keep defer for correctness.
- "channels for everything": a `sync.Mutex` is often simpler and faster for protecting simple shared state.
