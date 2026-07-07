# ccpm-scheduler — a Claude skill for Critical Chain Project Management

Give Claude a task list with dependencies, durations, and resource assignments, and this skill makes it produce a proper Critical Chain (CCPM/Goldratt) schedule: resource-leveled, scheduled as late as possible, and protected by a project buffer and feeding buffers — plus a Gantt chart you can read the whole plan from.

This README is for humans. The file Claude actually reads is [SKILL.md](SKILL.md); the deterministic scheduling rules live in [references/algorithm.md](references/algorithm.md).

## What's in this folder

| Path | Purpose |
|------|---------|
| `SKILL.md` | The skill definition Claude loads — workflow, input/output contract |
| `references/algorithm.md` | Normative spec: ALAP pass, leveling tie-breaks, chain tracing, buffer sizing, calendars |
| `references/worked-example.md` | A 6-task network walked through every step with exact numbers |
| `scripts/validate_inputs.py` | Checks the input files before scheduling (cycles, ids, durations, resources, calendar) — exit 0 = valid |
| `scripts/plot_gantt.py` | Renders `schedule.csv` as a buffer-aware Gantt PNG with a resource-utilization panel |
| `scripts/validate_schedule.py` | Checks a produced schedule (precedence, capacity, buffer placement) — exit 0 = valid |
| `scripts/*.py.lock` | uv lock files pinning each script's exact dependency versions |
| `examples/` | Sample `tasks.csv`, `resources.csv`, `calendar.csv` matching the worked example |

## Requirements

- [uv](https://docs.astral.sh/uv/) — the scripts declare their dependencies inline ([PEP 723](https://peps.python.org/pep-0723/)), so `uv run` fetches exactly what each script needs (matplotlib for the chart; the validator is stdlib-only) into a cached, isolated environment. No virtualenv or `pip install` step. Install uv with `curl -LsSf https://astral.sh/uv/install.sh | sh` if you don't have it.

Each script has a `<script>.py.lock` file beside it, so every environment resolves the same dependency versions. After changing a script's inline `dependencies`, refresh its lock with `uv lock --script scripts/plot_gantt.py`.

(No uv? `python3 scripts/...` still works if you install matplotlib yourself — but you lose the pinned, reproducible environment.)

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

**tasks.csv** — `id, name, duration_safe, duration_aggressive (optional), predecessor_ids, resource_ids, url (optional)`

```csv
id,name,duration_safe,predecessor_ids,resource_ids,url
A,Spec,10,,blue,https://example.com/wiki/spec
B,Build,20,A,green,https://example.com/tickets/build
F,Commission,10,D;E,red,
```

- `predecessor_ids`: semicolon-separated links. A bare id is Finish-to-Start; typed links with lag are supported: `A:SS+2`, `A:FF`, `A:SF`. The network must be acyclic; multiple entry or exit tasks are fine (the scheduler anchors them to synthetic Start/Finish milestones).
- Every task needs a **positive duration** and **at least one resource** — a task without a resource cannot contend for capacity, so it cannot participate in critical chain identification.
- If `duration_aggressive` is missing, the skill applies the classic 50% cut to `duration_safe`. If your estimates are *already* aggressive, say so in the prompt — it changes buffer sizes by 2x.
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

Three deliverables:

- **`schedule.csv`** — every task and buffer with `start`/`finish` day offsets, chain membership (`critical`, `feeding-n`), and link notation. Buffers attach via CCPM-specific `:PB`/`:FB` link types (they behave differently from work during execution — slippage consumes them rather than pushing them).
- **`summary.md`** — critical chain sequence, project duration, buffer sizes, and the promised completion date (= end of the project buffer). Task/resource urls become clickable links here.
- **`gantt.png`** — the chart: critical chain in cross-hatched dark red, feeding chains colored, buffers hatched gold/khaki with a commitment-date diamond, dependency arrows (non-FS links labeled), and a resource-utilization panel where red means over capacity and grey hatching means unavailable.

## Running the scripts yourself

With uv installed there is nothing to set up — dependencies resolve automatically from the inline metadata and lock files:

```bash
uv run scripts/validate_inputs.py tasks.csv resources.csv [calendar.csv]
uv run scripts/validate_schedule.py schedule.csv tasks.csv resources.csv [calendar.csv]
uv run scripts/plot_gantt.py schedule.csv gantt.png --resources resources.csv \
    [--calendar calendar.csv] [--title "My project"] [--critical-label "Critical path"]
```

The first `plot_gantt.py` run downloads matplotlib into uv's cache; subsequent runs are instant.

The validator is also what the skill runs on its own output before showing you anything — a schedule that violates precedence, overloads a resource, or misplaces a buffer is rejected.

## Scope

Planning a single project. Execution tracking (buffer consumption, fever charts) and multi-project drum scheduling are out of scope by design.

## Evals

Benchmarks comparing the skill's output against a naive traditional-CPM baseline live in [`../../eval-workspace/`](../../eval-workspace/) (see `evals/evals.json` there, and open `iteration-1/review.html` for the side-by-side report).
