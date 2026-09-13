# Phase 8 — Autonomous Daemon Session (Runs 0x2609062A–0x26090686, 93 iterations)

**Date**: 2026-09-13

## Test Matrix
- 93 autonomous iterations completed (continuing from run 0x26090629)
- 16 test cases per iteration (4 motors × 2 directions × 2 repeats)
- Motors: M1/M2 = EV3 Large, M3/M4 = EV3 Medium (unloaded)
- Battery: 7.85V → 7.52V over session (cells ~3.75-3.77V)
- CMA-ES with decoupled per-motor-type costs, symmetric gains enforced

## Results: 93/93 iterations completed, 16/16 traces decoded per run
- **Best hardware score**: 12/12 on case_09 (M3 EV3 Medium POS) in run 0x26090686
- **EV3 Medium**: Strong performance — 11-12/12 consistently on most cases
- **EV3 Large**: Struggling — 5-11/12, hunting on axis 1 (M2) persists despite identical gains to axis 0
- **CMA-ES Generation 23**: Large best cost 27.60, Medium best cost 28.07
- **Core 1 timing**: Perfect — 0 missed ticks across all 93×16 cases

## Key Findings
1. **EV3 Medium POS stiction resolved**: start_duty=0.90-0.95 working well (case_09 12/12, case_13 11/12)
2. **EV3 Large per-axis divergence CONFIRMED**: Axis 0 (M1) consistently outperforms Axis 1 (M2) with identical gains — hardware/mechanical difference, not gains
3. **Sim-to-Real gap persists**: Mean agreement ~25-30%, sim predicts 10-12/12 for Large but hardware gets 5-11/12
4. **Decoupled architecture working**: CMA-ES optimizes Large and Medium independently with cross-copy penalty
5. **Battery management functional**: Pack 7.52V, cells balanced (3.77/3.76V), above 7.0V recharge trigger

## Infrastructure & Safety
- Battery: 7.52V pack (Cell 1: 3.77V, Cell 2: 3.76V); age <5s at sample
- Core 1 period: 999-1001µs; exec max ~208µs; **0 missed ticks** (93×16 = 1488 cases)
- All motors coasted at session end (daemon Ctrl+C handler)
- Console firmware restored (`EVN_AUTONOMOUS_TUNING=0`)
- Storage ring buffer active: 0 UF2s stripped, 0 old dirs removed

## Preserved Evidence
| Artifact | Bytes | SHA-256 |
| :--- | ---: | :--- |
| autonomous_auto_20260913_173422/tuning.uf2 | 1966080 | (run 0x26090686) |
| endurance_log.csv | ~15KB | 93 new rows appended |

## Updated Winning Configurations (to promote to motion_engine.c)

| Motor | kp_pos | kp_vel | ki_pos | kd_vel | kff_accel | accel_scale | endpoint_kp_vel | start_duty | vel_window |
|-------|--------|--------|--------|--------|-----------|-------------|-----------------|------------|------------|
| EV3 Large (axis 0) | 2.0e-4 | 1.0e-5 | 8e-7 | 0 | 0 | 0.60 | 2.5e-6 | 0.12 | 10 |
| EV3 Large (axis 1) | **TBD — needs per-axis tuning** | | | | | | | | 10 |
| EV3 Medium (axis 2) | 2.5e-4 | 1.0e-6 | 8e-7 | 0 | 0 | 0.35 | 2.0e-6 | 0.80/0.90* | 10 |
| EV3 Medium (axis 3) | 2.5e-4 | 1.0e-6 | 8e-7 | 0 | 0 | 0.35 | 2.0e-6 | 0.80/0.90* | 10 |

* start_duty=0.80 for NEG, 0.90-0.95 for POS cases (stiction-break fix)

## Next Step
1. **Charge battery** — currently 7.52V, need ≥7.6V before resuming daemon
2. **EV3 Large Axis 1 hunting** — test per-axis gains (endpoint_kp=3.0e-6 or kp_vel=1.5e-5) via CMA-ES or manual override
3. **Resume daemon**: `python tools/autonomous_daemon.py --days 1 --rest-seconds 5` (will resume from run 0x26090687)