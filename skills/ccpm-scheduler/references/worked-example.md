# Worked example — 6-task network, one resource conflict

Input (`examples/tasks.csv`, `examples/resources.csv`):

| id | name      | realistic_duration | predecessor_ids | resource_ids |
|----|-----------|--------------------|-----------------|--------------|
| A  | Spec      | 10            |                 | blue         |
| B  | Build     | 20            | A               | green        |
| C  | Design    | 10            | A               | blue         |
| D  | Integrate | 20            | B               | blue         |
| E  | Test rig  | 10            | C               | green        |
| F  | Commission| 10            | D;E             | red          |

Resources: blue, green, red — capacity 1 each.

(The example CSVs also carry an optional `url` column on tasks and resources — a link to each item's detail page. It plays no part in the computation and is omitted from the tables below; it simply passes through to `schedule.csv` and becomes markdown links in the summary. There is also an `examples/calendar.csv` with availability overrides — green in training days 2–4, red on another project days 0–10. Both outages fall where those resources have no work in this schedule, so every step below is unchanged; they exist to show the format and to render as grey "unavailable" blocks on the chart.)

## Step 0 — Optimal durations (50% cut)

A=5, B=10, C=5, D=10, E=5, F=5.

## Step 2 — ALAP baseline

Forward pass: longest path A→B→D→F = 5+10+10+5 = 30 = T.
Backward pass (late starts): F 25–30, D 15–25, B 5–15, A 0–5, E 20–25, C 15–20.

## Step 3 — Resource leveling

Conflict: C (blue, 15–20) overlaps D (blue, 15–25). Total path through D (A→B→D→F) = 30; through C (A→C→E→F) = 20. D is more critical and stays; C shifts earlier so it finishes at D's start: **C 10–15**. C's predecessor A finishes at 5 ≤ 10, no ripple. No further conflicts (blue: A 0–5, C 10–15, D 15–25; green: B 5–15, E 20–25).

## Step 4 — Critical chain

Latest finish: F (30). F.start = 25 → who finishes at 25? D (precedence pred) and E (precedence pred). Both precedence: pick longer path back — D (A→B→D = 25) over E (A→C→E = 15). D.start = 15 → B finishes 15 → B. B.start = 5 → A finishes 5 → A.

**Critical chain: A → B → D → F** (length 30).

## Step 5 — Feeding chain

C and E are non-critical; they reach the chain at F. **Feeding chain: C → E**, join point F (start 25).

## Step 6 — Buffers (CAP, the default method)

Per-task safety Δ = realistic − optimal = 5, 10, 5, 10, 5, 5 for A…F — all *derived*, since the input gives single-point (realistic-only) estimates that Step 0 cut by 50%. CAP sizes each buffer as the sum of the protected chain's Δs.

- Project buffer: Δ(A)+Δ(B)+Δ(D)+Δ(F) = 5+10+10+5 = **30**. Placed 30–60. Promised completion: **day 60**. (With single-point estimates, CAP's promise lands exactly where the traditional realistic plan would — 10+20+20+10 = 60 — but with all the protection pooled and visible instead of hidden inside tasks.)
- Feeding buffer (C→E): Δ(C)+Δ(E) = **10 wanted**. E must then finish by 25 − 10 = 15, so the whole chain shifts earlier by 10 — but a shifted task may only land where its resources are free: E cannot take 10–15 (green is booked by B, 5–15) and stays at **15–20**; C shifts as far as its predecessor allows, pinned by A's finish at 5: **C 5–10**. The achieved gap to the join (F starts 25) is 5, so **FB1 = 5, occupying 20–25**, and the summary reports `5 (method wanted 10)`. The shortfall is information, not an error: this merge carries half the protection CAP wanted, so it deserves critical-chain-level attention during execution.

No negative starts; nothing else moved.

## Final schedule

| id  | name       | type           | chain     | start | finish | duration | resource_ids | predecessor_ids |
|-----|------------|----------------|-----------|-------|--------|----------|--------------|-----------------|
| A   | Spec       | task           | critical  | 0     | 5      | 5        | blue         |                 |
| B   | Build      | task           | critical  | 5     | 15     | 10       | green        | A               |
| C   | Design     | task           | feeding-1 | 5     | 10     | 5        | blue         | A               |
| D   | Integrate  | task           | critical  | 15    | 25     | 10       | blue         | B               |
| E   | Test rig   | task           | feeding-1 | 15    | 20     | 5        | green        | C               |
| FB1 | Feed buffer| feeding_buffer | feeding-1 | 20    | 25     | 5        |              | E:FB            |
| F   | Commission | task           | critical  | 25    | 30     | 5        | red          | D;FB1:FB        |
| PB  | Proj buffer| project_buffer | critical  | 30    | 60     | 30       |              | F:PB            |

Task-to-task links here are plain FS; the buffers attach with the CCPM-specific `:FB` / `:PB` types, drawn as dashed arrows. Note the merge on the protected side: F lists `FB1:FB` among its predecessors, and the input's direct `E` link was REROUTED through the buffer (E → FB1 → F) — keeping `E` alongside `FB1:FB` would be a bypass that lets E's slippage push F directly, absorbing nothing. PB's end (60) is the commitment date and has no successor. If the input used typed links (`A:SS+2` etc.) they would appear unchanged in this column and as labeled arrows on the Gantt.

Project duration without buffer: 30 days. Promised completion: day 60.

## The other sizing methods

Same network with `--buffer-method hchain` or `rsem` — every task lands on identical days; only the buffer arithmetic changes:

| Method | PB | Promise | FB1 |
|--------|----|---------|-----|
| `cap` (default) | Σ Δ = 30 | day 60 | 5 (wanted 10) |
| `hchain` | ⌈0.5 × 30⌉ = 15 | day 45 | 5 (wanted ⌈0.5 × 10⌉ = 5 — exact) |
| `rsem` | ⌈√(5²+10²+10²+5²)⌉ = 16 | day 46 | 5 (wanted ⌈√50⌉ = 8) |

`hchain` reproduces the engine's pre-v0.9 default output (and this document's previous baseline). The spread — promise day 45 vs 60 on the same plan — is why the method is worth a deliberate choice with the user rather than a silent default. All numbers above verified against `ccpm-scheduler` 0.10.0 on `examples/`.
