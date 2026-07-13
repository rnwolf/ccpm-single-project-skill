# Changelog

## 0.2.0 — 2026-07-13

The scheduling engine moved out of the skill and onto PyPI.

- The skill now drives the [ccpm-scheduler](https://pypi.org/project/ccpm-scheduler/)
  CLI (`uvx ccpm-scheduler validate|build|check|plot|schema`) instead of
  bundled scripts; `scripts/` and the uv lock files are gone. The engine is
  the same code, extracted behavior-preserving into its own repo
  (https://github.com/rnwolf/ccpm-scheduler) with byte-identical golden
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
