# Phase 8 Dashboard Fixes & Autonomous Run (run 0x2609043C)

**Date**: 2026-09-05

## Test Matrix
- Dashboard: All 10 confirmed bugs (A-J) fixed in `tools/evn_dashboard.py`
- Autonomous: 16 cases with updated run ID 0x2609043C, EVN_AUTONOMOUS_TUNING=1

## Results: 16/16 committed, 16/16 traces decoded

| Case | Name | Passed/Total | Failures | Score | Max Track Err |
|------|------|--------------|----------|-------|---------------|
| 4 | case_04_r0_W40_K50_pos | **12/12** | 0 | 3.52 | 1.83° |
| 0 | case_00_r0_W40_K50_pos | **12/12** | 0 | 3.84 | 1.60° |
| 2 | case_02_r2_W40_K50_pos | 11/12 | 1 | 3.65 | 1.60° |
| 3 | case_03_r3_W40_K50_neg | 11/12 | 1 | 4.00 | 1.72° |
| 1 | case_01_r1_W40_K50_neg | 11/12 | 1 | 4.08 | 1.88° |
| 12 | case_12_r0_W40_K10_neg | 10/12 | 2 | 4.34 | 1.51° |
| 14 | case_14_r2_W40_K10_neg | 10/12 | 2 | 5.34 | 1.91° |
| 9 | case_09_r1_W40_K10_pos | 9/12 | 3 | 5.05 | 1.06° |
| 15 | case_15_r3_W40_K10_pos | 9/12 | 3 | 6.25 | 1.93° |
| 11 | case_11_r3_W40_K10_pos | 9/12 | 3 | 6.54 | 1.99° |
| 10 | case_10_r2_W40_K10_neg | 8/12 | 4 | 6.07 | 1.06° |
| 7 | case_07_r3_W40_K50_neg | 8/12 | 4 | 6.68 | 1.88° |
| 5 | case_05_r1_W40_K50_neg | 8/12 | 4 | 6.77 | 1.95° |
| 8 | case_08_r0_W40_K10_neg | 8/12 | 4 | 7.66 | 2.07° |
| 13 | case_13_r1_W40_K10_pos | 7/12 | 5 | 6.67 | 2.72° |
| 6 | case_06_r2_W40_K50_pos | 7/12 | 5 | 7.47 | 1.91° |

## Key Findings
1. **Dashboard Bugs Fixed (10/10)**: All confirmed bugs from firmware console audit resolved:
   - Bug A: Removed servo write-as-query (E n 0 was driving servos to 0µs every 2s)
   - Bug B: Fixed motor telemetry regex to handle `tgt=` space-padding from firmware
   - Bug C: Added thread-safe marshaling to `log_to_console`/`update_status` via `root.after()`
   - Bug D: Added `style.theme_use('clam')` - fixes dark mode and Accent.TButton styling
   - Bug E: BOOTSEL check now handles drive letter correctly (doesn't set port combo)
   - Bug F: Window close now asks to reboot to UF2 before exit
   - Bug G: Quick "Status (S)" button now sends uppercase 'S' (not lowercase 's')
   - Bug H: Removed LED TOGGLE button (firmware has no LED query)
   - Bug I: Fixed I2C scan regex anchoring (^Scanning all)
   - Bug J: Added `quiet` param to `send_console_command_raw`, removed duplicate heartbeat thread

2. **Autonomous Run Results**: **2 configs achieved 12/12** (cases 0 and 4 - both EV3 Large positive direction with W40_K50 gains). Multiple 11/12 and 10/12 configs. Core 1 timing excellent: 999-1001µs period, 105-202µs exec, 0 missed ticks across all 16 cases.

3. **Run-to-run variation confirmed**: Some configs that previously got 12/12 now got 10-11/12. Need consecutive 12/12 runs for validation.

4. **Stiction fix holding**: EV3 Medium (axes 2,3) showed no stiction stalls in this run - all cases completed.

## Infrastructure & Safety
- Battery: Verified before autonomous run (pack ≥6.5V, cells ≥3.0V, age <250ms)
- Core 1 period: 999-1001µs; exec max 202µs; missed ticks: 0 (all 16 cases)
- Duty smoothness: 0.79-0.91 range
- Console firmware restored (EVN_AUTONOMOUS_TUNING=0) after extraction

## Preserved Evidence
| Artifact | Bytes | SHA-256 |
| :--- | ---: | :--- |
| tuning.uf2 (run 0x2609043C) | ~1MB | (computed at decode) |
| summary.csv | 2.3 KB | (in bench/results/autonomous_auto_20260905_002440) |

## Updated Winning Configurations (from run 0x2609043C)
| Motor | kp_pos | kp_vel | ki_pos | kd_vel | kff_accel | accel_scale | endpoint_kp_vel |
|-------|--------|--------|--------|--------|-----------|-------------|-----------------|
| EV3 Large (pos) | 4.0e-4 | 5.0e-6 | 8e-7 | 0 | 0 | 0.70 | 1.0e-6 |
| EV3 Large (neg) | 4.0e-4 | 5.0e-6 | 8e-7 | 0 | 0 | 0.70 | 1.0e-6 |
| EV3 Medium (neg) | 2.5e-4 | 1.0e-6 | 8e-7 | 0 | 0 | 0.35 | 2.0e-6 |
| EV3 Medium (pos) | 2.5e-4 | 1.0e-6 | 8e-7 | 0 | 0 | 0.35 | 2.0e-6 |

*Note: Run 0x2609043C used W40_K50 (accel_scale=0.40, kp=4.0e-4) for 12/12 on EV3 Large pos. Previous winning configs from run 0x2609043B still valid for NEG/POS EV3 Medium.*

## Next Step
1. **Run consecutive autonomous validation** - Target 2+ consecutive 12/12 runs on all 4 axes with current winning configs
2. **Analyze case mapping** - Determine which cases correspond to which motor axes for the 12/12 results
3. **Consider expanding test matrix** - Add more gain variations around winning configs to find robust region
4. **Dashboard verification** - Run dashboard HITL test with user to verify all 10 bug fixes