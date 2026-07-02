# Changelog

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
