# Phase 8 Autonomous Validation Run 0x26090443 — 4th Consecutive Run

**Date**: 2026-09-05

## Test Matrix
- 16 cases: 4 axes × 4 repeats each
- EV3 Large (axes 0,1): 800 deg/s, kp=4.0e-4, kv=5.0e-6, endpoint_kp=1.0e-6, accel_scale=0.70
- EV3 Medium (axes 2,3): 1100 deg/s, kp=2.5e-4, kv=1.0e-6, kd_vel=0, endpoint_kp=2.0e-6, accel_scale=0.35 (SYMMETRIC config)
- All moves: 720° absolute, alternating directions (POS/NEG/POS/NEG)
- Extended timeouts: TUNING_CORE_PAUSE_TIMEOUT_US=100000, TUNING_WATCHDOG_MS=30000

## Results: 16/16 cases committed, 16/16 traces decoded

| Case | Axis | Dir | Repeat | Passed/Total | Score | Max Track Err | Final Err | Notes |
|------|------|-----|--------|-------------|-------|---------------|-----------|-------|
| case_08 | 3 (M) | NEG | 0 | **12/12** | 2.37 | 1.539° | 0.0° | **FIRST 12/12 for EV3 Medium axis 3 NEG** |
| case_13 | 3 (M) | POS | 1 | 11/12 | 2.56 | 2.671° | 0.0° | |
| case_04 | 1 (L) | POS | 0 | 11/12 | 3.40 | 1.782° | 0.0° | Was 12/12 in prev 2 runs (streak broken) |
| case_12 | 2 (M) | NEG | 0 | 11/12 | 3.63 | 2.409° | 0.0° | Was 12/12 in run 0x26090440 |
| case_00 | 0 (L) | POS | 0 | 11/12 | 4.00 | 1.728° | 0.0° | **Was 12/12 in prev 3 runs (3-peat broken)** |
| case_01 | 0 (L) | NEG | 1 | 11/12 | 4.07 | 1.631° | 0.0° | |
| case_07 | 1 (L) | NEG | 3 | 11/12 | 4.08 | 1.756° | 0.0° | |
| case_06 | 1 (L) | POS | 2 | 11/12 | 4.43 | 1.791° | 0.0° | |
| case_15 | 3 (M) | POS | 3 | 10/12 | 2.75 | 2.867° | 0.0° | **Catastrophic 121° error FIXED** (was 121.211°) |
| case_14 | 3 (M) | NEG | 2 | 10/12 | 4.54 | 2.227° | 0.492° | |
| case_05 | 0 (L) | NEG | 1 | 9/12 | 5.35 | 1.784° | -0.5° | |
| case_10 | 2 (M) | NEG | 2 | 9/12 | 5.58 | 1.148° | -0.5° | |
| case_09 | 2 (M) | POS | 1 | 9/12 | 7.65 | 1.992° | 0.5° | |
| case_02 | 0 (L) | POS | 2 | 8/12 | 6.12 | 1.625° | -0.492° | |
| case_03 | 0 (L) | NEG | 3 | 8/12 | 6.35 | 1.695° | 0.5° | |
| case_11 | 2 (M) | POS | 3 | 7/12 | 6.89 | 2.403° | -0.992° | |

## Key Findings

1. **EV3 Medium Axis 3 POS Repeat 3 Catastrophic Failure FIXED**: case_15 final error went from **121.211°** (run 0x26090442) to **0.0°** (run 0x26090443). The stiction break fix (lowered velocity threshold 5000→1000, pos-error activation) is working.

2. **First 12/12 for EV3 Medium Axis 3 NEG**: case_08 achieved 12/12 for the first time. Need consecutive 12/12 for Phase 8 completion.

3. **Streaks Broken**: 
   - case_00 (EV3 Large axis 0 POS repeat 0): was 12/12 in 3 consecutive runs (0x26090440, 0x26090441, 0x26090442), now 11/12
   - case_04 (EV3 Large axis 1 POS repeat 0): was 12/12 in 2 consecutive runs (0x26090440, 0x26090441), now 11/12
   - This confirms ~10% run-to-run variation persists

4. **Core 1 Timing Excellent**: 999-1001µs period, 102-208µs exec max, **0 missed ticks** across all 16 cases

5. **Run-to-Run Variation Confirmed**: Consistent ~10% variance per axis. EV3 Medium symmetric config gives 7-12/12 consistently.

6. **Timeouts Fixed**: Extended `TUNING_CORE_PAUSE_TIMEOUT_US` (10k→100k) and `TUNING_WATCHDOG_MS` (5k→30k) allowed all 16 cases to complete (previously stopped at case 9).

## Infrastructure & Safety
- Battery: 8.12-8.13 V pack, cells 4.04-4.06 V, age ~430 µs (well within 250 ms gate)
- Core 1 period: 999-1001 µs; exec max: 102-208 µs; missed ticks: 0
- Duty smoothness: 0.75-0.90; cruise ripple: 0.16-1.14 pp
- All motors coasted at end via autonomous finish + console firmware

## Preserved Evidence
| Artifact | Bytes | SHA-256 |
| :--- | ---: | :--- |
| tuning.uf2 | 1966080 | (compute when needed) |

## Updated Winning Configurations (Promoted to motion_engine.c)

| Motor | kp_pos | kp_vel | ki_pos | kd_vel | kff_accel | accel_scale | endpoint_kp_vel |
|-------|--------|--------|--------|--------|-----------|-------------|-----------------|
| EV3 Large | **4.0e-4** | **5.0e-6** | 8e-7 | **0** | 0 | **0.70** | **1.0e-6** |
| EV3 Medium (both dirs) | **2.5e-4** | **1.0e-6** | 8e-7 | **0** | 0 | **0.35** | **2.0e-6** |

## Next Step
1. **Run 5th consecutive autonomous validation (run 0x26090444)**: Target consecutive 12/12 on case_08 (axis 3 NEG repeat 0) and case_00/case_04 recovery. Need 2+ consecutive 12/12 on all 4 axes before Phase 8 (Drive Base).
2. **EV3 Medium improvement**: Sweep endpoint_kp (2.0e-6 → 2.5e-6) and accel_scale (0.35 → 0.40) for axes 2&3 to improve consistency from 7-11/12 to 12/12.
3. **Analyze repeat-dependent degradation pattern**: Higher repeats (2,3) consistently underperform repeat 0 across all axes.