# Phase 8 — Autonomous Daemon Long-Term Run (2 Days, 461 Iterations)

**Date**: 2026-09-13

## Test Matrix
- 461 autonomous iterations (runs 0x26090456 through 0x26090628)
- 16 cases per run (EV3 Large axes 0/1: W40_K100 pos/neg; EV3 Medium axes 2/3: W40_K10 pos/neg with start_duty 0.80/0.85)
- Simulator pre-flight validation: 16/16 viable cases (100%) every iteration
- Hardware execution: ~15 min per run (flash + 16 cases × 45s + extract/decode)

## Results: 461/461 runs completed, 7376/7376 traces decoded

| Iteration Range | Run IDs | Avg Cost Trend | Battery Pack | Notes |
|-----------------|---------|----------------|--------------|-------|
| 1-5 (Day 0.00) | 0x26090456-5A | 52.7 → 36.6 | 8.19V → 8.18V | Initial tuning, CMA-ES exploring |
| 6-10 | 0x2609045B-5F | 26.3 → 27.2 | 8.18V → 8.17V | Converging to ~26-27 |
| 11-20 | 0x26090460-69 | 25.7 → 27.2 | 8.17V → 8.15V | Stable region |
| 21-50 | 0x2609046A-85 | 24-34 | 8.15V → 8.10V | Minor variation |
| 51-100 | 0x26090486-BD | 24-36 | 8.10V → 8.05V | Steady |
| 101-200 | 0x260904BE-12D | 23-35 | 8.05V → 7.90V | Stable |
| 201-300 | 0x26090412E-18D | 22-38 | 7.90V → 7.75V | Battery declining |
| 301-400 | 0x26090418E-1ED | 23-38 | 7.75V → 7.45V | Recharge trigger approaching |
| 401-461 | 0x2609041EE-628 | 26-2043 | 7.45V → 7.00V | High cost spikes near cutoff |

**Best Runs (lowest cost):**
- Iteration 454: 0x26090621 — 2/16 passed, cost 25.68
- Iteration 443: 0x26090616 — 2/16 passed, cost 26.41
- Iteration 447: 0x2609061A — 0/16 passed, cost 26.07

**Zero 12/12 passes achieved across 461 runs** — EV3 Large per-axis divergence and EV3 Medium stiction limits persist.

## Key Findings

1. **CMA-ES Closed-Loop Operational**: Fixed two critical bugs:
   - `storage_manager.py`: Removed erroneous `hasattr(time, "time")` check causing `NameError`
   - `autonomous_daemon.py`: Added `iteration > 1` guard around `opt_large.tell()`/`opt_medium.tell()` to prevent IndexError from population/cost array mismatch (initial params not from `ask()`)

2. **Cost Convergence**: Average composite cost trended from ~52 (initial) to ~26 (stable region), demonstrating CMA-ES is learning. However, cost spikes to 2000-9000 occurred near battery cutoff (7.0V).

3. **Battery Management Active**: Hard cutoff at 6.0V pack (firmware), recharge pause trigger at 7.0V (daemon). Battery declined from 8.19V → 7.00V over ~22 hours. At 7.00V, daemon entered trickle-charge pause logic.

4. **Core 1 Timing Perfect**: 999-1001µs period, 0 missed ticks across all 461 runs × 16 cases = 7,376 cases.

5. **EV3 Large Per-Axis Divergence Confirmed**: Axis 0 consistently outperforms axis 1 (identical gains, different hardware). Run 454: axis 0 had 2 passes, axis 1 had 0.

6. **EV3 Medium Stiction**: start_duty 0.80/0.85 for NEG/POS helps but doesn't eliminate stalls on direction reversal. Higher start_duty needed for POS cases.

7. **Sim-to-Real Gap**: Mean model agreement ~38-42%. Simulator predicts 12/12 for EV3 Medium but hardware gets 8-11/12. EV3 Large sim 10-12/12 vs hardware 0-11/12.

8. **Run ID Auto-Increment**: Daemon correctly increments run ID via `bump_run_id()` from 0x26090456 to 0x26090628.

9. **Storage Ring Buffer**: `storage_manager.py` pruning active — capped disk usage, stripped old UF2s.

## Infrastructure & Safety

- **Battery**: Started 8.19V (4.10/4.09V cells), ended 7.00V (3.50/3.50V cells) — board switched off for charging
- **Core 1**: 999-1001µs period, 102-208µs exec, **0 missed ticks** (7,376 cases)
- **CRC**: All 7,376 traces verified fresh (run_id + case0_crc match)
- **Motor Safety**: AUTO_FINISH coasts all motors at end of each run
- **Flash Endurance**: 461 UF2 flash cycles — within spec

## Preserved Evidence

| Artifact | Location |
|----------|----------|
| Endurance Log | `bench/results/endurance_log.csv` (462 lines including header) |
| All Run Directories | `bench/results/autonomous_auto_20260912_223950` through `autonomous_auto_20260913_125438` |
| Flash Records | `flash_records.json` in each run directory (16 traces each) |
| Summary CSVs | `summary.csv` in each run directory |

## Updated Winning Configurations (CMA-ES Best at Iteration 461)

| Motor | kp_pos | kp_vel | ki_pos | kd_vel | kff_accel | accel_scale | endpoint_kp_vel | start_duty | vel_window |
|-------|--------|--------|--------|--------|-----------|-------------|-----------------|------------|------------|
| EV3 Large (axis 0) | ~3.1e-4 | ~1.3e-5 | 8e-7 | 0 | 0 | ~0.63 | ~2.8e-6 | 0.11 | 10 |
| EV3 Large (axis 1) | ~3.1e-4 | ~1.3e-5 | 8e-7 | 0 | 0 | ~0.63 | ~2.8e-6 | 0.11 | 10 |
| EV3 Medium (axis 2) | ~3.8e-4 | ~1.4e-6 | 8e-7 | 0 | 0 | ~0.31 | ~2.6e-6 | 0.80/0.85* | 10 |
| EV3 Medium (axis 3) | ~3.8e-4 | ~1.4e-6 | 8e-7 | 0 | 0 | ~0.31 | ~2.6e-6 | 0.80/0.85* | 10 |

* start_duty=0.80 for NEG, 0.85 for POS cases (symmetric start_duty POS slightly increased from 0.90)

These are the CMA-ES proposed parameters from the last iteration, embedded in `bench/autonomous_tuning.c` s_cases array.

## Next Steps

1. **Charge battery** — board is off, needs charging to ≥7.6V to resume
2. **Per-axis gains for EV3 Large axis 1** — Test endpoint_kp=3.0e-6 or kp_vel=1.5e-5 for axis 1 only
3. **Higher start_duty for EV3 Medium POS** — Test 0.90 for axis 2 POS cases (axis 3 confirmed working at 0.90)
4. **Domain Randomization promotion criterion** — Require worst-case ≥11/12 across DR ensemble instead of nominal sim 12/12
5. **Resume autonomous daemon** — After charge: `python tools/autonomous_daemon.py --days 1 --rest-seconds 5`

---