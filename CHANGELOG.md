# Changelog

## 0.6.0 — 2026-07-18

- **Engine invocation is now pinned**: `uvx ccpm-scheduler@0.10.0`. The skill's
  algorithm notes and worked-example numbers are verified against exactly this
  engine version; adopting a newer engine is a deliberate skill release
  (re-verify, re-baseline, bump the pin). Motivated by engine v0.9.0 changing
  the default buffer sizing under the previously-unpinned invocation, which
  made the engine's real output contradict the skill's own reference docs.
- **Buffer-sizing methods** (engine v0.9.0): `--buffer-method cap|hchain|rsem`
  documented throughout — CAP (Σ safety removed, the new engine default, most
  explainable), HCHAIN (classic 50%-of-chain, the old hard-coded behavior),
  RSEM (root-squared error). The skill asks the user which method to use;
  when unsure it gathers two-point estimates and uses the CAP default.
  algorithm.md Step 6 rewritten (normalization triple, three formulas,
  achieved-gap shortfall reporting); the separate "SSQ variant" note is
  subsumed by RSEM.
- **Worked example re-baselined against engine 0.10.0** with the CAP default:
  PB 30, promise day 60, and FB1 comes up short — `5 (method wanted 10)` —
  because the feeding chain is blocked by a resource booking, which the
  example now teaches as information rather than an error. A new comparison
  table shows cap/hchain/rsem side by side (promise day 60 / 45 / 46 on the
  same plan); hchain reproduces the previous baseline. Also corrects C's
  final placement (5–10, the uniform whole-chain buffer shift) which the
  previous text had wrong even for the old default.
- **Engine v0.10.0 diagnostics documented**: the calendar-aware scheduling
  horizon (long outages/positive lags no longer misreport "no feasible
  schedule") and the named infeasibility error (task + blocking resources
  when base capacity is 0), plus guidance on feeding-buffer shortfalls and
  the summary's derived-estimate counts.

## 0.5.3 - 2026-07-15

- Skill zip file included to much information. Fix zip file contents.

## 0.5.1 - 2026-07-15

- Workflow was to publish a mcp service. Not correct for a skill. Deleted.
- Added workflow to create a zip file of just the key files required for skill zip.

## 0.5.1 - 2026-07-14

- Add github worlflow to publish skill in zip file format that can be
  downloaded and installed in Claude desktop.

## 0.5.0 — 2026-07-13

- `schedule.csv` now includes `realistic_duration` per task (engine 0.7.0):
  filter by chain to audit how much safety left the tasks versus what
  landed in that chain's buffer — the reassurance conversation of CCPM
  adoption. The graph step no longer needs `--tasks`; the schedule carries
  the estimates.
- `project-network.html` gains a resource filter (All / Unassigned / each
  named resource) — everything but the selected resource's tasks fades, so
  each team member can see their part in the context of the whole plan.
- Gantt: task labels no longer clip at the left edge; dotted horizontal
  guides per task row and per resource row make label-to-bar alignment easy
  on long schedules.
- README: installation via the skills CLI (`npx skills add ...`) documented
  alongside the plugin and manual installs.
- Verified against engine ccpm-scheduler 0.7.0 (build byte-identical to the
  regenerated goldens).

## 0.4.0 — 2026-07-13

- `project-network.html` now shows each task's **realistic estimate** next
  to its scheduled optimal duration — in the hover tooltip
  ("5d optimal, 10d realistic") and in the inspector's new Estimates row,
  including the % of safety pooled into buffers. The graph step passes
  `--tasks tasks.csv`, so reviewing the optimal/realistic balance happens
  right on the network view.
- Verified against engine ccpm-scheduler 0.6.0.

## 0.3.0 — 2026-07-13

- New fourth deliverable: `project-network.html`, an interactive dependency
  graph of the schedule (`ccpm-scheduler graph`) — a standalone HTML file
  (vis-network via CDN, data embedded, no server or build step) for
  exploring the network structure the Gantt can't show: zoom, pan, drag
  nodes, toggle hierarchical/free layout, click a task to inspect its
  schedule, resources, and links. Colors match the Gantt.
- Verified against engine ccpm-scheduler 0.5.0 (build output byte-identical
  to the reference goldens).

## 0.2.0 — 2026-07-13

The scheduling engine moved out of the skill and onto PyPI.

- The skill now drives the [ccpm-scheduler](https://pypi.org/project/ccpm-scheduler/)
  CLI (`uvx ccpm-scheduler validate|build|check|plot|schema`) instead of
  bundled scripts; `scripts/` and the uv lock files are gone. The engine is
  the same code, extracted behavior-preserving into its own repo
  (<https://github.com/rnwolf/ccpm-scheduler>) with byte-identical golden
  tests, a typed library API, machine-readable validation issue codes, a
  JSON exchange format, and an agent-friendly CLI contract (exit codes
  0/1/2, `--json`, `schema` subcommand).
- Duration columns renamed to `realistic_duration` (safety included) /
  `optimal_duration` (padding-free), matching our-planner's terminology;
  the legacy `duration_safe`/`duration_aggressive` names are still accepted.
- Deterministic builder shipped and buffer topology hardened (pre-extraction):
  every merge edge into the critical chain gets its own feeding buffer, the
  direct feeder edge is rerouted through the buffer, end-running chains merge
  into a zero-duration FINISH milestone, and feeding buffers must merge into
  the critical chain (no dangling successors).

## 0.1.0 — 2026-07-02

First packaged release, extracted from the ccpm-proof-of-concept repo.

- CCPM scheduling skill: ALAP baseline, deterministic resource leveling,
  critical chain identification (precedence + resource links), 50%-rule
  project and feeding buffers attached via explicit `:PB`/`:FB` link types.
- Resource calendars (`calendar.csv`): per-day capacity overrides with
  contiguous task execution (tasks never split across an outage).
- Optional `url` columns on tasks and resources, passed through to
  `schedule.csv` and rendered as links in `summary.md`.
- `validate_inputs.py`: rejects cycles, duplicate/unknown ids, non-positive
  durations, resource-less tasks, and calendar problems before scheduling.
- `validate_schedule.py`: 10 deterministic checks including calendar-aware
  capacity and a ban on zero-length buffers.
- `plot_gantt.py`: cross-hatched critical chain, dynamic legend with
  `--critical-label`, dependency arrows, resource-utilization panel with
  within/overload/unavailable legend.
- Scripts carry PEP 723 inline metadata with committed uv lock files.
- Eval harness comparing CCPM output against a traditional-CPM baseline,
  with a single-page self-contained review report.
