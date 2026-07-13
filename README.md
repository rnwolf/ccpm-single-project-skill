# ccpm-single-project-skill

A [Claude Code](https://claude.com/claude-code) plugin providing the **ccpm-scheduler** skill: give Claude a task list with dependencies, durations, resource assignments, and (optionally) resource availability, and it produces a proper Critical Chain (CCPM / Goldratt) schedule — resource-leveled, as-late-as-possible, protected by a project buffer and feeding buffers — plus a Gantt chart and a validated `schedule.csv`.

The skill itself (what Claude reads, plus its references and examples) lives in [`skills/ccpm-scheduler/`](skills/ccpm-scheduler/) — see its [README](skills/ccpm-scheduler/README.md) for input formats, outputs, and how to run the scheduler yourself. The scheduling engine is the [ccpm-scheduler](https://pypi.org/project/ccpm-scheduler/) Python package ([source](https://github.com/rnwolf/ccpm-scheduler)) — a deterministic library + CLI that the skill drives via `uvx ccpm-scheduler`, and that other tools (like [our-planner](https://github.com/rnwolf/our-planner)) embed directly.

## Installation

### As a Claude Code plugin (recommended)

This repo is both a plugin and its own marketplace. In Claude Code:

```
/plugin marketplace add rnwolf/ccpm-single-project-skill
/plugin install ccpm-scheduler@ccpm-single-project-skill
```

To try a local checkout during development:

```
/plugin marketplace add /path/to/ccpm-single-project-skill
```

Updates: bump the `version` in `.claude-plugin/plugin.json`, tag a release, and users pick it up with `/plugin update ccpm-scheduler`.

### Manual (any agent that reads skill folders)

Copy `skills/ccpm-scheduler/` into your skills directory:

- one project: `<project>/.claude/skills/ccpm-scheduler/`
- everywhere: `~/.claude/skills/ccpm-scheduler/`

## Requirements

- [uv](https://docs.astral.sh/uv/) — the skill runs the scheduling engine as `uvx ccpm-scheduler ...`, which fetches and caches the [PyPI package](https://pypi.org/project/ccpm-scheduler/) automatically. (No uv? `pip install ccpm-scheduler` works too.)

## Using it

Ask for the work — the skill triggers on requests like:

> Build a CCPM schedule for this project — tasks are in tasks.csv, resources in resources.csv, availability in calendar.csv.

Mentions of CCPM, critical chain, Goldratt, project/feeding buffers, or resource-leveled scheduling all trigger it.

## Evals

[`eval-workspace/`](eval-workspace/) contains the benchmark harness used to develop the skill: four project networks (`inputs/`), a deliberately naive traditional-CPM baseline (`cpm_baseline.py`), a grader (`grader.py`), and a single-page report generator (`make_review.py`). `iteration-1/` holds the current results — open `iteration-1/review.html` in a browser to compare CCPM vs CPM per eval, inputs included.

To re-run after changing the skill:

```bash
cd eval-workspace
# (re)build with_skill outputs per inputs/<eval>/, then:
python3 grader.py iteration-N inputs
python3 make_review.py iteration-N inputs evals/evals.json
```

## Scope

Planning a single project. Execution tracking (buffer consumption, fever charts) and multi-project drum scheduling are out of scope by design — this repo's name reserves the space for siblings.

## License

[MIT](LICENSE)
