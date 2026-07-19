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

Updates: users pick up new versions with `/plugin update ccpm-scheduler` — see [Releasing](#releasing) for the maintainer side.

### Via the skills CLI (Claude Code and other agents)

The [skills CLI](https://www.npmjs.com/package/skills) installs skills from
any repo containing `SKILL.md` folders — no plugin/marketplace setup needed:

```bash
# Add to the current project
npx skills add https://github.com/rnwolf/ccpm-single-project-skill

# Add globally (user-level, not project-level)
npx skills add https://github.com/rnwolf/ccpm-single-project-skill -g

# Update to the latest version later
npx skills update ccpm-scheduler -y

# List installed skills
npx skills list
npx skills ls -g           # global skills
```

(Note: use this repo's URL — the
[ccpm-scheduler](https://github.com/rnwolf/ccpm-scheduler) repo is the
Python scheduling engine, not the skill.)

### Manual (any agent that reads skill folders)

Copy `skills/ccpm-scheduler/` into your skills directory:

- one project: `<project>/.claude/skills/ccpm-scheduler/`
- everywhere: `~/.claude/skills/ccpm-scheduler/`

## Requirements

- [uv](https://docs.astral.sh/uv/) — the skill runs the scheduling engine as `uvx ccpm-scheduler@<pinned version> ...`, which fetches and caches the [PyPI package](https://pypi.org/project/ccpm-scheduler/) automatically. (No uv? `pip install ccpm-scheduler==<pinned version>` works too — SKILL.md states the current pin.)

## Releasing

Two things version independently — the **skill** (this repo, the instructions
Claude follows) and the **engine** ([ccpm-scheduler](https://github.com/rnwolf/ccpm-scheduler)
on PyPI, the code that computes schedules). They update through different
channels:

**Releasing the skill** (after changing anything under `skills/` or the
plugin manifest):

1. Make the changes on `master` and verify them — at minimum run the
   documented pipeline on `skills/ccpm-scheduler/examples/` end to end
   (`uvx ccpm-scheduler validate` → `build` → `check` → `plot`).
2. Bump `version` in `.claude-plugin/plugin.json` (semver: patch = wording
   fixes, minor = workflow/contract changes, major = breaking input-format
   changes). This field is what `/plugin update` compares — without the bump,
   downstream users never see the change.
3. Add a `CHANGELOG.md` entry; note which engine version the release was
   verified against.
4. Push `master`, then tag and publish the human-facing record:
   `git tag vX.Y.Z && git push origin vX.Y.Z`, and create a GitHub release
   with the changelog notes (`gh release create vX.Y.Z ...`).

Steps 2 + push are what actually deliver the update; the tag/release give
each version a diffable, documented identity. Manual folder-copy installs
have no update channel — those users re-copy.

**Releasing the engine** happens in the
[ccpm-scheduler repo](https://github.com/rnwolf/ccpm-scheduler) (its GitHub
release workflow publishes to PyPI). SKILL.md invokes the engine **pinned to
an exact version** (`uvx ccpm-scheduler@X.Y.Z`), so engine releases do NOT
reach skill users automatically — deliberately: the skill's algorithm notes
and worked-example numbers are verified against the pinned version, and
engine defaults have changed before (v0.9.0 switched the default buffer
sizing from the 50% rule to CAP, which would have silently contradicted the
skill's docs under an unpinned invocation). Adopting a new engine version is
therefore a skill release: re-run the pipeline on `examples/`, re-baseline
any numbers that changed, bump the pin in SKILL.md (and the version
mentions in both READMEs), then follow the skill-release steps above.

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
