---
name: ccpm-scheduler
description: Build Critical Chain Project Management (CCPM) schedules from a project network and resource availability. Use this skill whenever the user mentions CCPM, critical chain, Goldratt, project buffers, feeding buffers, resource-leveled scheduling, or wants to schedule/reschedule a project network with constrained resources — even if they just say "schedule my project" and provide a task list with dependencies and resources. Produces a deterministic schedule table and a buffer-aware Gantt chart.
---

# CCPM Scheduler

Convert a project network (tasks, dependencies, durations, resource assignments) plus resource availability into a Critical Chain schedule: resource-leveled, as-late-as-possible, protected by a project buffer and feeding buffers.

## Why CCPM differs from ordinary CPM

Classic critical path scheduling ignores resources and embeds safety inside every task estimate, where Parkinson's Law and student syndrome consume it. CCPM instead:

1. Strips padding from individual tasks (uses **optimal** durations — the classic CCPM literature calls these "aggressive").
2. Levels resources first — the **critical chain** is the longest path through the network considering BOTH precedence and resource dependencies. It may jump between precedence-unrelated tasks that share a resource.
3. Pools the removed safety into a **project buffer** at the end and **feeding buffers** where non-critical chains merge into the critical chain.

Never skip resource leveling. A "critical chain" computed without resolving resource contention is just a critical path and defeats the purpose.

## Inputs

Expect two tables (CSV or YAML — normalize anything reasonable into this shape):

**tasks**: `id, name, realistic_duration, optimal_duration (optional), predecessor_ids, resource_ids, url (optional)` — `realistic_duration` is the estimate with safety included; `optimal_duration` is the padding-free estimate
- `predecessor_ids`: semicolon- or space-separated dependency links (empty for start tasks). A bare id means Finish-to-Start, the normal case. Other link types use `id:TYPE` with an optional integer lag: `A` (FS), `A:SS+2` (start 2 days after A starts), `A:FF` (finish no earlier than A finishes), `A:SF` (rare). Carry this notation through unchanged into the output schedule so the chart can draw the links. Two additional CCPM-specific types exist for buffer rows in the output: `:PB` and `:FB` (see below) — never attach buffers with plain FS.
- `resource_ids`: semicolon-separated resource ids — **required, at least one per task**: a task without a resource cannot contend for capacity and breaks critical chain identification
- If `optimal_duration` is missing, derive it as `ceil(realistic_duration / 2)` (the classic "50% cut")
- `url`: optional link to more detail about the task (ticket, wiki page, spec). Pass it through untouched.

**resources**: `id, name, capacity, url (optional)` — capacity defaults to 1 (one task at a time); `url` is an optional link to more detail about the resource (team page, calendar). Durations are in working days; the schedule uses integer day offsets from day 0 (convert to calendar dates only if the user asks).

**calendar** (optional): `resource_id, from, to, capacity` — overrides a resource's capacity on the half-open day range `[from, to)`. `capacity = 0` means unavailable (vacation, maintenance, another project); a higher value models a temporary contractor. Outside listed ranges the resource's default capacity applies. Tasks execute **contiguously** — they never pause and resume around an unavailability window, so a task must fit entirely into a span where each of its resources has capacity every day. Legacy column names `predecessors`/`resources`/`duration_safe`/`duration_aggressive` in user-supplied files are fine — normalize them to `predecessor_ids`/`resource_ids`/`realistic_duration`/`optimal_duration`.

If the user gives only one duration per task, ask (or state the assumption) whether it is realistic (safety included) or already optimal — this changes buffer sizes by 2x.

## Workflow

Work through these steps in order. **Do the computation with the bundled deterministic builder** — `uv run scripts/build_schedule.py tasks.csv resources.csv [--calendar calendar.csv] --out-dir <dir> --title "..."` implements steps 2-5 of `references/algorithm.md` exactly and writes `schedule.csv` + `summary.md`. Never do the arithmetic in your head: schedules have too many interacting constraints. Only write custom code when the input genuinely exceeds the builder (then follow `references/algorithm.md` literally, including tie-breaks, and still validate the result); steps 2-5 below describe what the builder does so you can sanity-check its output and explain it to the user.

Run the bundled scripts with `uv run` — they carry PEP 723 inline dependency metadata plus a `.lock` file, so uv provisions the right environment (matplotlib for the chart) automatically. If uv is unavailable, fall back to `python3` with matplotlib installed.

1. **Parse and validate.** Run `uv run scripts/validate_inputs.py tasks.csv resources.csv [calendar.csv]` first — it rejects cycles, duplicate/unknown ids, non-positive durations, resource-less tasks, and calendar problems, and reports the network's entry/exit points. Fix or ask about errors before attempting to schedule. Multiple start or terminal tasks are fine: anchor them to a single synthetic Start / Finish milestone (zero duration, no resources, removed from outputs).
2. **ALAP baseline.** Compute a classic CPM backward pass with optimal durations: every task at its late start. CCPM schedules as late as possible so work starts when it can flow continuously, not early "because we can".
3. **Level resources.** Resolve overlapping demands on the same resource by shifting tasks **earlier** (never later — the ALAP pass already has everything as late as precedence allows). With a calendar, capacity is per-day: a conflict is demand exceeding the effective capacity on any day, and a shifted task must land where its whole span is available (contiguous execution). Follow the deterministic rules in `references/algorithm.md` exactly, including tie-breaks, so the same input always yields the same schedule.
4. **Identify the critical chain.** Trace back from the task that finishes last, at each step following the precedence-or-resource predecessor that directly bounds the current task's start. Mark every other maximal path feeding into the chain as a feeding chain.
5. **Size and insert buffers.** Default method — 50% rule: buffer = half the sum of optimal durations along the protected chain, rounded up. Project buffer goes after the final critical-chain task; each feeding buffer is inserted where its feeding chain joins the critical chain, shifting the feeding chain earlier to make room. Details and edge cases (negative starts, chains joining mid-network) are in `references/algorithm.md`.
6. **Verify.** Run `uv run scripts/validate_schedule.py schedule.csv tasks.csv resources.csv [calendar.csv]` against the produced schedule. It checks precedence, resource capacity (calendar-aware when given), buffer placement, and chain continuity. Fix any violation before presenting results — do not hand the user a schedule that fails its own validator.
7. **Present.** Produce:
   - `schedule.csv` — columns: `id, name, type, chain, start, finish, duration, resource_ids, predecessor_ids, url` where `type` ∈ {`task`, `project_buffer`, `feeding_buffer`} and `chain` ∈ {`critical`, `feeding-<n>`, `none`}. `predecessor_ids` keeps the link notation (`B`, `B:SS+2`, …). Buffers attach via dedicated link types: the project buffer as `<last CC task>:PB`, each feeding buffer as `<last chain task>:FB`. This matters because buffers are not work — in execution, a buffer's end stays anchored (commitment date for PB, protected task start for FB) and predecessor slippage consumes the buffer rather than pushing it; plain FS links would encode the wrong behavior. Buffers must also MERGE back into the network: the critical-chain task where the feeding chain joins lists the buffer among its predecessors as `<FBid>:FB`, and the buffer REPLACES the direct feeder→join edge (a plain edge kept alongside would bypass the buffer — feeder slippage would push the critical chain immediately; the validator rejects bypasses, dangling buffers, and unbuffered merges). Every edge from non-critical work into the critical chain gets its own buffer, and chains that run to the project end merge into a zero-duration `FINISH` milestone from which the project buffer hangs as its single `:PB` predecessor. `url` passes through the input task's url (empty for buffers)
   - A markdown summary (`summary.md`): critical chain sequence, project duration, promised completion (end of project buffer), buffer sizes. Where tasks or resources have a `url`, render their mentions as markdown links so the reader can jump to the detail page
   - A Gantt chart PNG via `uv run scripts/plot_gantt.py schedule.csv gantt.png --resources resources.csv` (add `--calendar calendar.csv` if one was provided — unavailable days show as grey hatched blocks in the utilization panel) — this renders the schedule with dependency-link arrows (non-FS links labeled SS/FF/SF) plus a resource-utilization sub-chart on the same time axis, so the user can read the dependencies at a glance and visually confirm the load leveling is correct (any red block = a resource over capacity = a leveling bug)

   The deliverables are exactly these three files: `schedule.csv`, `summary.md`, `gantt.png`. Keep working files — the scheduling script you wrote, intermediate CSVs, debug output — OUT of the folder where deliverables go (use a scratch/temp directory). The reader is a project manager, not a programmer; they should never have to scroll past code to find their schedule.

## Worked example

`references/worked-example.md` walks a 6-task network through every step with exact numbers, including a resource conflict that the leveling pass must resolve. Read it the first time you apply this skill, and consult it whenever a step's expected output is unclear. Sample input files matching it are in `examples/`.

## Things that commonly go wrong

- **Buffers are not slack, and not FS successors.** They are scheduled blocks that consume calendar time, attached with `:PB`/`:FB` link types. The promised completion date is the end of the project buffer, not the last task — and that date is the fixed anchor: slippage consumes buffer, it must not push the buffer.
- **Feeding buffer insertion can ripple.** Shifting a feeding chain earlier can create a new resource conflict or push a start negative. The shifting chain drags its non-critical external predecessors along (critical-chain tasks never move). Re-run leveling on affected tasks; if any start goes below 0, shift the entire schedule right so the earliest start is 0.
- **Never emit a zero-length buffer.** A 0-day buffer protects nothing. If a feeding chain has no room for its buffer (gap 0 and nowhere to shift), omit the buffer and flag the chain in the summary as effectively critical — the validator rejects zero-length buffer rows.
- **Resource links belong in the chain.** If task X waits for task Y only because they share a welder, Y is X's critical-chain predecessor even with no arrow between them in the network diagram.
- **Don't re-add safety.** Resist padding optimal durations back toward "realistic" — that's what the buffers are for. If the user's estimates already include safety, cut them; if they say estimates are already optimal, buffer from those without cutting.
- **Multiple sinks.** If several tasks have no successors, treat them as predecessors of a virtual zero-duration end milestone and proceed normally.
- **Tasks don't straddle unavailability.** With a resource calendar, a task cannot pause over an unavailable window and resume — place it entirely before or entirely after the window (contiguous execution). A leveling shift that parks a task on a zero-capacity day is a bug the validator will catch.

## Scope

This skill covers **planning** a single project. Execution tracking (buffer consumption, fever charts) and multi-project pipelining (drum scheduling) are out of scope — say so if asked, and schedule the single-project plan as the foundation.
