# ccpm-scheduler — a Claude skill for Critical Chain Project Management

Give Claude a task list with dependencies, durations, and resource assignments, and this skill makes it produce a proper Critical Chain (CCPM/Goldratt) schedule: resource-leveled, scheduled as late as possible, and protected by a project buffer and feeding buffers — plus a Gantt chart you can read the whole plan from.

This README is for humans. The file Claude actually reads is [SKILL.md](SKILL.md); the deterministic scheduling rules live in [references/algorithm.md](references/algorithm.md); the computation itself lives in the [ccpm-scheduler](https://github.com/rnwolf/ccpm-scheduler) Python package, whose CLI the skill drives.

## What's in this folder

| Path | Purpose |
|------|---------|
| `SKILL.md` | The skill definition Claude loads — workflow, input/output contract |
| `references/algorithm.md` | Normative spec: ALAP pass, leveling tie-breaks, chain tracing, buffer sizing, calendars |
| `references/worked-example.md` | A 6-task network walked through every step with exact numbers |
| `examples/` | Sample `tasks.csv`, `resources.csv`, `calendar.csv` matching the worked example |

The scheduler scripts that used to be bundled here became the
[ccpm-scheduler](https://github.com/rnwolf/ccpm-scheduler) package — a proper
library + CLI with a typed model, coded validation issues, and a JSON
exchange format, so the same engine serves this skill, other tools (e.g.
[our-planner](https://github.com/rnwolf/our-planner)), and direct human use.

## Requirements

- [uv](https://docs.astral.sh/uv/) — the skill runs the CLI as `uvx ccpm-scheduler@0.10.0 ...`, which fetches and caches the [PyPI package](https://pypi.org/project/ccpm-scheduler/) automatically. The version is **pinned** to the engine release the skill's docs and worked example are verified against; the pin is bumped deliberately when the skill is re-verified against a newer engine. Install uv with `curl -LsSf https://astral.sh/uv/install.sh | sh` if you don't have it.

(No uv? `pip install ccpm-scheduler==0.10.0` puts the `ccpm-scheduler` command on your PATH.)

## Installing the skill

Skills are folders that Claude Code discovers by location. Pick one:

- **Just for this repo**: copy (or symlink) this folder to `.claude/skills/ccpm-scheduler/` in the project root.
- **For all your projects**: copy it to `~/.claude/skills/ccpm-scheduler/`.

Verify it's picked up by asking Claude Code: *"what skills do you have for scheduling?"* — or just make a request that matches the skill description (below) and watch it trigger.

## Using it

You don't invoke the skill by name (though `/ccpm-scheduler` works too where user-invocable skills are enabled) — you ask for the work. The skill triggers on requests like:

> Build a CCPM schedule for this project — tasks are in tasks.csv, resources in resources.csv.

> Schedule my project with critical chain: here are the tasks, dependencies and who does what. The estimates already include safety.

Mention of CCPM, critical chain, Goldratt, project/feeding buffers, or resource-leveled scheduling all trigger it.

### Input files

**tasks.csv** — `id, name, realistic_duration, optimal_duration (optional), predecessor_ids, resource_ids, url (optional)`

`realistic_duration` is the estimate with safety baked in; `optimal_duration` is the padding-free estimate. (The classic CCPM literature calls these "safe" and "aggressive"; the legacy column names `duration_safe`/`duration_aggressive` are still accepted.)

```csv
id,name,realistic_duration,predecessor_ids,resource_ids,url
A,Spec,10,,blue,https://example.com/wiki/spec
B,Build,20,A,green,https://example.com/tickets/build
F,Commission,10,D;E,red,
```

- `predecessor_ids`: semicolon-separated links. A bare id is Finish-to-Start; typed links with lag are supported: `A:SS+2`, `A:FF`, `A:SF`. The network must be acyclic; multiple entry or exit tasks are fine (the scheduler anchors them to synthetic Start/Finish milestones).
- Every task needs a **positive duration** and **at least one resource** — a task without a resource cannot contend for capacity, so it cannot participate in critical chain identification.
- If `optimal_duration` is missing, the skill applies the classic 50% cut to `realistic_duration`. If your estimates are *already* optimal (padding-free), say so in the prompt — it changes buffer sizes by 2x.
- **Buffer sizing method**: `cap` (default — buffers equal the safety removed from the chain, the most explainable rule), `hchain` (classic 50%-of-chain, shorter promise dates), or `rsem` (root-squared error, statistical pooling for two-point estimates). Say e.g. *"use the 50% rule"* to pick one; unsure means the skill asks, or gathers two-point estimates and uses `cap`. On the same plan the promise date can differ by weeks between methods — see `references/algorithm.md`.
- `url`: optional link to a ticket/wiki page; it is carried into the outputs.

**resources.csv** — `id, name, capacity, url (optional)`; capacity defaults to 1.

**calendar.csv** (optional) — availability overrides:

```csv
resource_id,from,to,capacity
green,2,4,0
red,0,10,0
```

Overrides a resource's capacity on the day range `[from, to)`. The bracket notation is deliberate — it is the mathematical convention for a **half-open interval**: the square bracket `[` means `from` is **included**, the round bracket `)` means `to` is **excluded**. So `green,2,4,0` means green is unavailable on days 2 and 3, and back at work on day 4 — the range covers `to − from` days, never `to` itself.

Why half-open? It matches how the schedule itself works: a task with `start=2, finish=4` occupies days 2 and 3 too, so a calendar row and a task span with the same numbers cover exactly the same days, and adjacent ranges like `[0,5)` and `[5,10)` butt together without overlapping or leaving a gap.

Days are working-day offsets from day 0 (the same axis as the Gantt chart). `capacity 0` = unavailable (holiday, another project); a higher value models temporary extra capacity (e.g. a contractor). Outside the listed ranges, the resource's default capacity from `resources.csv` applies. Ranges for the same resource must not overlap.

Tasks run **contiguously** — they never pause across an outage, so a task is scheduled entirely before or entirely after it.

### Outputs

Four deliverables:

- **`schedule.csv`** — every task and buffer with `start`/`finish` day offsets, chain membership (`critical`, `feeding-n`), and link notation. Buffers attach via CCPM-specific `:PB`/`:FB` link types (they behave differently from work during execution — slippage consumes them rather than pushing them), and each feeding buffer also *merges*: the critical-chain task it protects lists it back as `FBn:FB` *instead of* the direct feeder link (rerouted through the buffer, so nothing bypasses it). Feeding chains that run to the project end merge into a zero-duration `FINISH` milestone; the project buffer's only predecessor is the terminal critical-chain task (or that milestone).
- **`summary.md`** — critical chain sequence, project duration, buffer sizes, and the promised completion date (= end of the project buffer). Task/resource urls become clickable links here.
- **`gantt.png`** — the chart: critical chain in cross-hatched dark red, feeding chains colored, buffers hatched gold/khaki with a commitment-date diamond, dependency arrows (non-FS links labeled), and a resource-utilization panel where red means over capacity and grey hatching means unavailable.
- **`project-network.html`** — a standalone interactive dependency graph of the same schedule (vis-network via CDN, data embedded — no server needed): zoom, pan, drag nodes, toggle hierarchical/free layout, filter by resource (All / Unassigned / each named resource — everything else fades so each person sees their part in context), click a task to inspect its details, including its realistic vs optimal duration estimates (and how much safety was pooled into buffers). The Gantt shows *when*; this shows *why*.

## Running the scheduler yourself

With uv installed there is nothing to set up (the first run fetches the package into uv's cache; subsequent runs are instant):

```bash
alias ccpm-scheduler="uvx ccpm-scheduler@0.10.0"

ccpm-scheduler validate tasks.csv resources.csv [calendar.csv]
ccpm-scheduler build tasks.csv resources.csv [--calendar calendar.csv] \
    [--buffer-method cap|hchain|rsem] [--out-dir DIR] [--title "My project"]
ccpm-scheduler check schedule.csv tasks.csv resources.csv [calendar.csv]
ccpm-scheduler plot schedule.csv gantt.png --resources resources.csv \
    [--calendar calendar.csv] [--title "My project"] [--critical-label "Critical path"]
ccpm-scheduler graph schedule.csv project-network.html [--title "My project"]
```

The CLI is deterministic — the same input always yields byte-identical output — and works standalone, independent of Claude: exit codes are a contract (0 = ok, 1 = problems found, 2 = usage error), every subcommand takes `--json` for machine-readable output, and `ccpm-scheduler schema network` prints the JSON input format. Claude's role in the skill is normalizing messy input into the input contract, choosing assumptions (realistic vs optimal estimates), and explaining the result.

`check` is also what the skill runs on its own output before showing you anything — a schedule that violates precedence, overloads a resource, or misplaces a buffer is rejected.

## Scope

Planning a single project. Execution tracking (buffer consumption, fever charts) and multi-project drum scheduling are out of scope by design.

## Evals

Benchmarks comparing the skill's output against a naive traditional-CPM baseline live in [`../../eval-workspace/`](../../eval-workspace/) (see `evals/evals.json` there, and open `iteration-1/review.html` for the side-by-side report).
