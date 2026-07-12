# CCPM Scheduling Algorithm — deterministic specification

This is the normative spec. Every rule here exists so that the same input always produces the same schedule — that property is what lets users trust reruns. `scripts/build_schedule.py` is the reference implementation (a stdlib-only CLI); when implementing independently, follow the steps and tie-breaks literally and expect byte-identical output.

All times are integer working-day offsets. A task occupies the half-open interval `[start, finish)` with `finish = start + duration`. Two tasks overlap iff `start_a < finish_b and start_b < finish_a`.

Column names: task inputs use `predecessor_ids` and `resource_ids` (accept the legacy names `predecessors`/`resources` on input and normalize).

## Resource calendars (optional input)

`calendar.csv` rows `resource_id, from, to, capacity` override that resource's capacity on the half-open range `[from, to)`; `capacity = 0` means unavailable. **Effective capacity** `cap(res, day)` = the matching override's capacity, else the resource's default. Validate: resource ids must exist, `from < to`, and ranges for the same resource must not overlap (fail on violations).

**Contiguous execution rule:** a task never splits. Every day in `[start, finish)` must have `cap(res, day) >= 1` for each of the task's resources, and total concurrent demand must fit `cap(res, day)`. A position is *feasible* for a task iff its whole span satisfies this. Wherever a step below moves a task (backward pass, leveling shift, feeding-chain shift), take the nearest position in the required direction that is feasible — zero-capacity days are hard walls the span must clear entirely.

## Dependency link types

Links are written `predid[:TYPE][lag]`, e.g. `A`, `A:SS+2`, `A:FF`, `A:SF-1`. Default type is FS, default lag 0. Each type imposes one inequality:

| Type | Constraint | Meaning |
|------|------------|---------|
| FS | `pred.finish + lag <= succ.start` | normal sequencing (default) |
| SS | `pred.start + lag <= succ.start` | successor may start once pred has started |
| FF | `pred.finish + lag <= succ.finish` | successor may not finish before pred finishes |
| SF | `pred.start + lag <= succ.finish` | rare; successor must run until pred has started |
| PB | buffer anchored to commitment date | CCPM-specific: attaches the project buffer to the last critical-chain task |
| FB | buffer anchored to protected CC task | CCPM-specific: attaches a feeding buffer to the chain it protects |

PB and FB are deliberately NOT plain FS links, because buffers are not work driven by their predecessors. At plan time they place like FS (`pred.finish <= buffer.start`), but their execution semantics are inverted: the buffer's END is the anchor. If a critical-chain task finishes late, the project buffer's end (the commitment date) does not move — the buffer shrinks from the left, and only when remaining buffer < 0 does the commitment slip. Likewise a feeding buffer's end stays glued to the start of the critical-chain task it protects; feeder slippage consumes the buffer before it may move the protected task. A scheduling or charting engine that treats these links as FS will wrongly push buffers (and the promise date) when predecessors slip. Encode the type explicitly in the data so execution-phase logic and visuals can do the right thing.

The CPM passes, leveling shifts, and chain tracing all use these inequalities instead of assuming FS. When shifting a task earlier during leveling, drag its predecessors by the minimum amount that keeps every link inequality satisfied. Non-FS links are unusual in CCPM networks — warn (don't fail) if they appear on the critical chain, since buffer sizing along chains with SS/FF overlaps can double-count overlapped duration; size such a chain's buffer from the chain's elapsed span instead of the simple sum of durations.

## Step 0 — Normalize

- For each task, `duration = optimal_duration` if given, else `ceil(realistic_duration / 2)`. (Accept the legacy column names `duration_aggressive`/`duration_safe` as aliases.)
- `safety_removed = realistic_duration - duration` (used for nothing in the 50% buffer rule, but compute it anyway — the SSQ variant needs it).
- If several tasks have no successors, add a virtual milestone `END` (duration 0, no resources) whose predecessors are all sink tasks. Likewise, if several tasks have no predecessors, add a virtual `START` milestone (duration 0, no resources) that all entry tasks succeed — the network always flows from one source to one sink. Both virtual nodes are removed from outputs.

## Step 1 — Validate

Run `uv run scripts/validate_inputs.py tasks.csv resources.csv [calendar.csv]` before scheduling. Fail with a clear message (do not schedule) on: dependency cycles, duplicate ids, predecessor ids that don't exist, resource ids not in the resource table, non-positive durations, and **tasks with no resources assigned** — a task without a resource cannot contend for capacity, so it cannot participate properly in critical chain identification or leveling. Warn (but proceed) on: resource capacity > 1 (supported, but unusual in CCPM), non-FS links.

## Step 2 — ALAP baseline (backward pass)

1. Forward pass with optimal durations → early start/finish; project length `T` = max early finish. Apply each link's inequality (see Dependency link types) when propagating.
2. Backward pass from `T` → late start/finish, again per link type.
3. Set every task's scheduled `start = late_start`.

With a calendar: both passes ignore *contention* (that is Step 3's job) but respect *unavailability* — when a pass would place a task across a zero-capacity day of one of its resources, move it in the pass's direction (later in the forward pass, earlier in the backward pass) to the nearest position whose whole span avoids the outage. If the forward pass pushes tasks later, `T` grows accordingly.

## Step 3 — Resource leveling

Resolve conflicts by moving tasks **earlier only**. Iterate to a fixed point:

1. Find the conflict to resolve: among all (resource, overlapping task pair) conflicts, pick the one whose overlap region has the **latest end**; tie-break by resource id ascending, then task ids ascending. (Resolving from the project end backward mirrors the ALAP logic and prevents churn.)
2. Decide which task moves: keep in place the task with the **longer total path through it** (longest precedence path from any start task to END that passes through the task, in optimal durations) — the more critical task stays put; the other shifts earlier so its `finish = stay_task.start`. Tie-break: keep the task with the later current finish; if still tied, keep the lexicographically smaller id.
3. A shifted task drags its predecessors: if the shift violates a precedence constraint (`pred.finish > task.start`), shift those predecessors earlier too, recursively, by the minimum amount needed.
4. Recheck everything (a shift can create new conflicts) and repeat until no conflicts remain.

If any start would go below 0, allow it during leveling; fix in Step 6 by shifting the whole schedule right.

Capacity > 1 generalization: a conflict exists when concurrent demand on a resource exceeds its capacity; shift the lowest-priority overlapping task (same priority rule) until demand fits. With a calendar this reads: demand on any day exceeds `cap(res, day)` — and a shifted task must land on a feasible position (whole span available, contiguous execution), skipping past outage windows entirely rather than pausing over them.

## Step 4 — Critical chain identification

1. Start at the task with the latest finish (the END milestone's bounding task).
2. Walk backward: the current task's chain predecessor candidates are tasks whose `finish == current.start` AND which are either (a) precedence predecessors, or (b) share a resource with the current task. Among candidates, pick the one whose own backward chain (computed recursively by this same rule) extends earliest in time — the chain should reach as far back as possible, because the critical chain is the sequence that actually bounds the project from day 0. Tie-break: precedence link over resource link, then smaller id. Do not blindly prefer precedence links — after leveling, a resource link is often the true bound, and picking a precedence candidate whose chain dead-ends in a gap understates the chain and undersizes the project buffer.
3. Stop when no such predecessor exists. The visited sequence (reversed) is the **critical chain**.

If a gap exists (no task finishes exactly at `current.start`), the chain ends there — this can happen after leveling and is acceptable; the chain is the bounded sequence from the gap forward.

## Step 5 — Feeding chains

For every non-critical task, find its chain: follow successors until reaching a critical-chain task (the **join point**) or END. Group tasks by join point; within a group, each maximal precedence path is a feeding chain. A task belongs to exactly one feeding chain — if paths share tasks, the shared prefix belongs to the longest chain (tie-break: smaller chain-head id).

**Merges are per edge, not per chain.** EVERY edge from a non-critical task into a critical-chain task is a merge that needs its own feeding buffer — including edges from a task that belongs to another chain (a shared prefix feeding a second join point, like a protocol task that feeds both trial arms). A chain's tail edge is sized on the chain's tasks; an extra edge from task X is sized on X's backward non-critical closure (X plus every non-critical task reachable through X's predecessors). Yes, a shared task's duration then contributes to more than one buffer — conservative double protection beats an unbuffered merge.

## Step 6 — Buffers (50% rule, default)

- **Project buffer** `PB = ceil(0.5 × sum of optimal durations of critical-chain tasks)`. Insert at `start = finish of last CC task`, `duration = PB`. Promised completion = end of PB.
- **Feeding buffer** per feeding chain: `FB = ceil(0.5 × sum of optimal durations of that chain's tasks)`. The feeding chain must finish `FB` days before its join point's start: shift the entire feeding chain earlier by the overlap amount, then place the buffer in the gap `[chain_finish, join.start)`.
- A shifting feeding chain **drags its non-critical external predecessors** along (same semantics as a leveling shift) — an ALAP-placed feeder of a feeder must not pin the chain against its join point. Critical-chain tasks never move; they cap the shift instead.
- **Buffers are at least 1 day.** If a chain cannot shift at all (blocked by a critical-chain predecessor, the calendar, or day 0) and the gap to its join point is zero, do NOT emit a zero-length buffer — omit it and flag the chain in the summary as effectively critical, to be watched as closely as the critical chain. The validator rejects zero-length buffer rows.
- Feeding-chain shifts can create new resource conflicts → re-run Step 3 restricted to moved tasks (they may only move earlier).
- After all insertions, if min start < 0, shift **every** task and buffer right uniformly so min start = 0.

SSQ variant (use only if the user asks): buffer = `ceil(sqrt(sum(safety_removed_i²)))` over the chain. Requires real realistic AND optimal estimates per task; mention that it yields smaller buffers on long chains.

Buffers never consume resources and never participate in leveling as demand. Calendars therefore never constrain buffer placement — a buffer is calendar time, and may freely span days on which resources are unavailable.

## Step 7 — Outputs

`schedule.csv` columns: `id, name, type, chain, start, finish, duration, resource_ids, predecessor_ids, url`. The `predecessor_ids` column repeats the input link notation; buffers get their protected chain's last task (FS) so charts can draw arrows into them. `url` is copied through from the input task, empty for buffers and tasks without one.
- `type`: `task` | `project_buffer` | `feeding_buffer`
- `chain`: `critical` | `feeding-1`, `feeding-2`, … (numbered by join-point start ascending) | `none`
- Buffers get ids `PB`, `FB1`, `FB2`, … and empty `resources`.
- Buffer rows attach with the buffer link types: feeding buffers get `<last chain task>:FB`, the project buffer gets `<last CC task>:PB`. Never attach a buffer with a plain FS link — the validator rejects it.
- **Buffers must also merge** — a buffer with no successor dangles outside the network. Encode the merge on the protected side: the critical-chain task where a feeding chain joins lists `<FBid>:FB` among its predecessors. Every feeding buffer has exactly one successor (the validator enforces this).
- **The buffer REPLACES the direct edge.** When a feeding buffer covers the merge X→J, the direct `X` token is removed from J's `predecessor_ids` — the dependency now routes X → FB → J and is transitively preserved. Keeping the plain edge alongside the buffer is a **bypass**: any FS-semantics reader would push J the moment X slips, and the buffer would absorb nothing. The validator rejects bypasses, and also rejects unbuffered merges when there is room (>= 1 day) for a buffer; a direct edge is tolerated only in the zero-gap no-room case, which the summary flags as effectively critical.
- **Chains that run to the project end merge into a `FINISH` milestone**, not into the project buffer. When any end-running feeding buffer exists, emit a zero-duration critical-chain task `FINISH` at the last critical task's finish, with the terminal critical task and those buffers as predecessors; the project buffer then attaches as `FINISH:PB`. The project buffer always has exactly ONE predecessor (`<terminal CC task or FINISH>:PB`) and no successor — its end IS the commitment date.
- Keep link-type notation intact in `predecessor_ids` — the Gantt script reads it to draw FS/SS/FF/SF arrows and dashed PB/FB buffer attachments with a commitment-date marker.

Then run `uv run scripts/validate_schedule.py schedule.csv tasks.csv resources.csv [calendar.csv]` and resolve any reported violation before presenting.
