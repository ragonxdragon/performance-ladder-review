# Data-access performance: SQL and application code

The unifying rule across SQL and every language: **filter/reduce as early as possible, and prefer one bulk/set-based/single-pass operation over per-item processing.** Read before touching a query, an ORM call, or a collection pipeline that hits a data store. For a slow DB query, **EXPLAIN ANALYZE is the profile**: read it before and after (Seek vs Scan, Sort operators, estimated-vs-actual rows).

## SQL query-writing rules

### Filter early (logical order: FROM/JOIN -> WHERE -> GROUP BY -> HAVING -> SELECT -> ORDER BY -> LIMIT)
- **Filter in WHERE, not HAVING,** for any predicate not depending on an aggregate. WHERE runs before grouping. Use both: WHERE to shrink rows early, HAVING for aggregate-only conditions. [safe]
- **Project only needed columns; never SELECT * in production.** Enables covering-index-only scans, less I/O/network, smaller sort/hash memory; breaks silently on schema change. [safe]
- **Predicate pushdown:** put filters as close to base tables as possible; filter before joining/aggregating. Modern optimizers push many down automatically; explicit early filtering never hurts. [safe]
- **Keyset/seek pagination over large OFFSET.** OFFSET reads and discards all preceding rows (O(offset)); `WHERE (sort_cols) < (last_seen) ORDER BY ... FETCH FIRST n` seeks directly and is stable under concurrent inserts (Winand). Needs a deterministic ORDER BY; can't jump to arbitrary page. [safe]
- **Push aggregation into SQL** rather than pulling rows to the app and looping. [safe]

### Set-based / window functions over row-by-row
- **One set-based statement beats cursors/loops (RBAR, "row by agonizing row," Jeff Moden).** Replace cursors with a single UPDATE / INSERT...SELECT / DELETE / MERGE. Per-row loops add overhead, hold locks, and hide the work from the optimizer. [safe]
- **Window functions (OVER/PARTITION BY) over correlated subqueries/self-joins** for running totals, rankings, top-N-per-group, moving averages: one pass over sorted data vs per-row re-execution or rescan. Ben-Gan's **POC index** (Partition, Order, Covering) removes the Sort. [safe] Sometimes `LATERAL`/`CROSS APPLY ... LIMIT` beats ROW_NUMBER() for top-1-per-group (early stop). [engine-dependent]
- **Batch DML** (multi-row INSERT, set-based UPDATE...FROM) over row-at-a-time round trips. [safe]

### Sargability (keep the indexed column bare on one side)
- **No functions on indexed columns in WHERE/JOIN.** `WHERE YEAR(d)=2014` -> scan; rewrite as range `d >= '2014-01-01' AND d < '2015-01-01'`. Measured: 3 pages vs 512, 10 rows vs 121,320. Move functions to the constant side. [safe]
- **Avoid leading-wildcard `LIKE '%x'`** (non-sargable); `LIKE 'x%'` is sargable. For infix search use a trigram/full-text index. [safe]
- **Avoid implicit type conversions and collation mismatches** in predicates/joins. They wrap the column in a CAST and force a scan. Fix types at source, cast the parameter not the column. [safe]

### Joins
- **Explicit ANSI JOINs, never comma joins** (comma joins invite accidental cross joins). [safe]
- **Join fan-out bug: pre-aggregate or COUNT(DISTINCT).** A one-to-many join repeats parent rows, so `SUM(parent.total)` double-counts (Looker's example: correct $124.84 -> inflated $223.44). Aggregate the child to the parent grain before joining. Silent wrong-number bug. [safe, correctness]
- **Let the optimizer reorder joins; hints only as a last resort**, gated on a measured before/after (they freeze the plan and hurt after data changes). [engine-dependent]
- Nested-loop vs hash vs merge: provide indexes + fresh stats, then read the plan. You don't choose directly. [measurement-gated]

### Predicates & set membership
- **NOT IN with a NULL is a correctness trap; prefer NOT EXISTS.** One NULL in the subquery makes NOT IN return no rows (three-valued logic). NOT EXISTS is null-safe. [safe, correctness]
- **EXISTS / IN / JOIN are usually equivalent** on modern optimizers (semijoin transformation). Real differences only with asymmetric sizes (EXISTS early-exits) or a correlated re-execution; check the plan. [myth-debunked / engine-dependent]
- **OR across different columns can defeat indexes; rewrite as UNION ALL** so each branch seeks its own index (verify; some engines do index-merge already). [measurement-gated]
- **DISTINCT is often a crutch masking a fan-out join.** Fix the join grain instead of paying for a dedup sort. [safe]

### Aggregation, DML, misc
- **UNION ALL by default; UNION only when you need dedup** (UNION does a costly sort/hash DISTINCT). One pipeline dropped 11 min -> 40 sec swapping UNION over already-unique shards for UNION ALL. [safe]
- **Chunk large DELETE/UPDATE into batches** to avoid log bloat and lock escalation (SQL Server escalates at ~5,000 locks/statement; keep batches below). Batching is about lock duration and log growth, not raw speed. [engine-dependent]
- **Keep statistics fresh** (ANALYZE / UPDATE STATISTICS). Stale stats cause bad plans; the tell is estimated-vs-actual row divergence. [measurement-gated]

### SQL myths: do NOT "fix" these (require a plan diff first)
- **COUNT(1) vs COUNT(\*):** identical in modern engines; COUNT(col) differs by skipping NULLs. Prefer COUNT(*).
- **Predicate order in WHERE:** the optimizer reorders; hand-ordering makes zero difference (Postgres). (Oracle-without-stats is an edge case.)
- **EXISTS always beats IN:** usually the same plan.
- **A subquery is always slower than a join:** often the identical plan after unnesting.
- **SELECT \* is harmless:** real costs (above).
- **Most-selective column leftmost in an index:** falsified by Winand.

## Application-code data-access, per language
The same two ideas (filter early; prefer bulk/single-pass); see each lang file for detail:
- **The universal ORM N+1 fix is batch/eager-load:** Django select_related/prefetch_related · Hibernate JOIN FETCH/@EntityGraph · EF Core Include/AsSplitQuery · SQLAlchemy joinedload/selectinload · Prisma DataLoader/relationLoadStrategy. Same idea everywhere: replace "1 query for the list + 1 per item" with "1 + 1 batched WHERE id IN (...)".
- **C# LINQ:** keep it IQueryable so filtering translates to SQL; never ToList() then Where() (client-eval bug). Project with Select; AsNoTracking for reads.
- **Java Streams:** filter before map, short-circuit, single fused pass; IntStream to avoid boxing.
- **Rust/JS lazy iterators:** filter before map, no intermediate collect/array, single pass, early exit.
- **Go/Rust SQL drivers:** query only needed columns, prepared statements, batch DML (mind Postgres' 65,535 param cap), stream large results.

## Ladder mapping (no new rungs)
Projection + filter-early = "do less work". Batch DML + fewer round trips = "do it less often". Set-based/window/eager-load = "fix complexity class" (O(n) pass vs O(n^2) per-row), with the small-n guard (a cursor/N+1 over a handful of rows is imperceptible). Push aggregation/filtering into the DB and trust the optimizer = "let the platform do it". EXPLAIN ANALYZE / benchmark = the measurement rung.
