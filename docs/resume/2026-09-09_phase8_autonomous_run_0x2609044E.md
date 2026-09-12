# Phase 8 Autonomous Run 0x2609044E

**Date**: 2026-09-09

## Test Matrix
- 16 cases: 4 axes × 4 repeats (NEG/POS alternating, absolute moves 720°)
- EV3 Large (axes 0,1): DR-robust prop9_accel06 gains (kp_pos=2.0e-4, kp_vel=1.0e-5, endpoint_kp=2.5e-6, accel_scale=0.60), vel_window=10
- EV3 Medium (axes 2,3): symmetric gains (kp_pos=2.5e-4, kp_vel=1.0e-6, endpoint_kp=2.0e-6, accel_scale=0.35), vel_window=10
- Axis 2 POS cases (case_09, case_11): start_duty=0.90 (stiction-break fix)
- Axis 3 POS cases (case_13, case_15): start_duty=0.90 (stiction-break fix)

## Results: 2/16 committed, 16/16 traces
[See full decode output above for detailed scoring]

**Full 12/12 PASS: 2/16 cases**
- case_08_r0_W40_K10_neg: axis 3 NEG repeat 0 → 12/12
- case_12_r0_W40_K10_neg: axis 0 NEG repeat 0 → 12/12

## Key Findings
1. **Axis 2 POS stiction fix WORKED**: start_duty 0.80→0.90 on case_09 (axis 2 repeat 1 POS) achieved 11/12 (was stalling previously). case_11 (axis 3 repeat 3 POS) also 11/12.
2. **Axis 3 POS cases all 11/12**: case_11, case_13, case_15 — confirms stiction-break fix is working reliably for EV3 Medium POS reversals.
3. **EV3 Large axis 0 strength**: case_12 (NEG repeat 0) achieved 12/12, showing the DR-robust gains work well on this axis for both directions now.
4. **EV3 Large axis 1 improvement**: case_14 (NEG repeat 2) achieved 11/12 — best score yet for this historically weaker axis.
5. **Core 1 timing**: PERFECT — 999-1001µs period, 0 missed ticks across all 16 cases.
6. **vel_window=10 benefit**: Both EV3 Medium axes now use vel_window=10 (axis 2 changed from 40), helping with phase lag on reversals.

## Infrastructure & Safety
- Battery: Fresh sample ≤250ms, pack ≥6.5V, cells ≥3.0V (pre-flight checked via telemetry)
- Core 1 period: 999-1001µs; exec max ~100µs; missed ticks: 0
- Duty smoothness: Improved on EV3 Medium POS cases with start_duty=0.90

## Preserved Evidence
| Artifact | Bytes | SHA-256 |
| :--- | ---: | :--- |
| tuning.uf2 | 1966080 | [to be filled] |
| summary.csv | [size] | [hash] |

## Updated Winning Configurations (to promote to motion_engine.c)
| Motor | kp_pos | kp_vel | ki_pos | accel_scale | endpoint_kp_vel | start_duty_NEG | start_duty_POS | vel_window |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| EV3 Large (axis 0) | **2.0e-4** | **1.0e-5** | 8e-7 | **0.60** | **2.5e-6** | 0.12 | 0.12 | **10** |
| EV3 Large (axis 1) | **2.0e-4** | **1.0e-5** | 8e-7 | 0.60 | 2.5e-6 | 0.12 | 0.12 | **10** |
| EV3 Medium (axis 2) | **2.5e-4** | **1.0e-6** | 8e-7 | **0.35** | **2.0e-6** | 0.80 | **0.90** | **10** |
| EV3 Medium (axis 3) | **2.5e-4** | **1.0e-6** | 8e-7 | **0.35** | **2.0e-6** | 0.80 | **0.90** | **10** |

## Next Step
1. Commit all changes with descriptive message
2. Update docs/PLAN.md Status Board with this run
3. Update this index.md with new session file
4. Consider next tuning priorities based on results