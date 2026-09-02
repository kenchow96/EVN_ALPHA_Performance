# Phase 7 Resume - EV3 Medium Motion

Updated: 2026-09-02. Intended resume: October 2026.

## Safe State

- The EVN board is running the **safe console firmware** (`EVN_AUTONOMOUS_TUNING=0`). All motors are off.
- Commit `4319fb7` contains the winning EV3 Medium gains promoted to `motion_engine.c`.
- The `Compile Project` task passes with `EVN_AUTONOMOUS_TUNING=0`.
- `build/EVN_ALPHA_Performance.uf2` is a non-autonomous console build.
- Autonomous tuning firmware (run `0x2609021F`) was successfully deployed and completed 16/16 cases.
- Board returned to BOOTSEL after autonomous completion.

Do not enable or flash an autonomous build without a fresh power/free-motion
confirmation. Before any new matrix, increment `EVN_TUNING_RUN_ID`; reusing
`0x26090210` will find the completed M4 records and skip the cases.

## Tested Configuration

The M3 startup search was stopped. These accepted choices were promoted to
the EV3 Medium defaults and transferred unchanged to M4 (axis index 3):

- Gains: `kp=1.2e-4`, `ki=8e-7`, `kv=5e-7`, endpoint `kv=5e-7`.
- Velocity source/window: encoder window, 40 samples, edge alpha 0.05.
- Profile: trapezoid, velocity scale 0.85, acceleration scale 0.40.
- Stiction: start duty 0.65, hold duty 0.55, continuous pulse 4/4.
- Launch/restart ramps: 800/200 ms.
- Startup reference governor enabled; release speed 10 deg/s.
- Friction feedforward 0.5x; edge watchdog enabled.
- Test: eight `+90/-90` degree repeat pairs, 180 deg/s, 900 deg/s2,
  3.8 s capture, 4 s Core 1 auto-coast.

## M4 Result

Infrastructure and safety passed:

- Verified UF2 extraction, 16/16 committed records, 16/16 trace CRCs.
- 760 rows per case; all profiles completed.
- Battery 7.247-7.267 V; minimum cell 3.610 V; age 436-448 us.
- Core 1 period 999-1001 us; execution maximum 206 us; zero missed ticks.
- Duty smoothness 0.903-0.921.

The motion profile gate failed. No case reached 12/12:

| Repeat | Positive | Negative |
| :--- | :--- | :--- |
| 0 | 9/12 | 8/12 |
| 1 | 10/12 | 9/12 |
| 2 | 10/12 | 10/12 |
| 3 | 10/12 | 10/12 |
| 4 | 10/12 | 9/12 |
| 5 | 10/12 | 8/12 |
| 6 | 10/12 | 10/12 |
| 7 | 10/12 | 10/12 |

Failure counts and ranges:

- Max tracking error failed 16/16: 2.226-3.651 deg, mean 2.764 deg.
- RMS tracking error failed 16/16: 1.073-1.463 deg, mean 1.163 deg.
- Peak acceleration failed 3/16: range 794-1653 deg/s2, mean 1061 deg/s2.
- Overshoot failed 2/16; settling failed 1/16; vibration failed 1/16.
- Best cases reached 10/12. The problem is now feedback/profile tracking,
  not transport, timing, duty smoothness, or a rejected startup heuristic.

Phase 8 remains blocked until all four axes pass the 12-metric suite and beat
the measured baseline.

## Preserved Evidence

All paths below are intentionally ignored by Git and remain in
`bench/results/`:

| Artifact | Bytes | SHA-256 |
| :--- | ---: | :--- |
| `autonomous_m4_profile_gate_20260902.uf2` | 236544 | `282FBA85614B668A71E7E4C6D5EDB67D362949B30DD94A2D671ACC7896024E88` |
| `autonomous_m4_profile_gate_boot_20260902.txt` | 128 | `E8385C7AEB3951D4E4DB5EC34F449CE82A730A2294E5E937C7704C7303CC82FE` |
| `autonomous_m4_profile_gate_flash_20260902.uf2` | 1966080 | `EF250E000F35A8C5104D0B943DD6766744299CE129998DDA787680B4238B9501` |
| `autonomous_m4_profile_gate_20260902_decoded_unique/flash_records.json` | 66694 | `D0D04EE4083CB656F99C0A1C77C618E9AD5E11E417179B85EB74209FD7409916` |
| `autonomous_m4_profile_gate_20260902_decoded_unique/summary.csv` | 2335 | `EABC9BF15A5A492F4E2C00753A2C958C0C45D66C715D13D5C3ECD616AD5D7098` |
| `safe_console_handoff_20260902.uf2` | 236544 | `3FD3214209E60112C1853BB8CB696AA587CA9F524654E0E8A1B9E504506E34E6` |

The decoder now names files `case_<index>_r<repeat>_<configuration>`. The
superseded decode directory that overwrote exact-repeat files was removed;
the raw flash extraction and corrected 16 JSON/16 trace decode were retained.

## Reproduction Commands

The hardware run used:

```powershell
python tools/flash_and_capture.py --uf2 bench/results/autonomous_m4_profile_gate_20260902.uf2 --time 3 --expect "motion_init: 4 axes" --log bench/results/autonomous_m4_profile_gate_boot_20260902.txt
```

After firmware-controlled return to BOOTSEL, flash was extracted and decoded:

```powershell
& "$env:USERPROFILE/.pico-sdk/picotool/2.3.0/picotool/picotool.exe" save -r 0x10F00000 0x10FF0000 -v bench/results/autonomous_m4_profile_gate_flash_20260902.uf2 -t uf2
python tools/decode_tuning_flash.py bench/results/autonomous_m4_profile_gate_flash_20260902.uf2 --output bench/results/autonomous_m4_profile_gate_20260902_decoded_unique
```

## Exact Continuation

Start next month with this read-only PowerShell command:

```powershell
Import-Csv -LiteralPath 'bench/results/autonomous_m4_profile_gate_20260902_decoded_unique/summary.csv' | Sort-Object {[int]$_.failures}, {[double]$_.score} | Format-Table name,passed,failures,score,max_track_err_deg,rms_track_err_deg,overshoot_deg
```

Then design one narrow Medium feedback/profile A/B while holding every startup
choice above fixed. The falsifying gate is repeatable max tracking error <=2.0
deg and RMS error <=1.0 deg without peak acceleration exceeding 1080 deg/s2.
Do not spend another hardware cycle on rejected startup pulse/ramp/friction or
endpoint-gain variants.

No physical action is needed for the offline comparison. Before a later flash,
power the board, ensure the selected Medium motor can rotate freely, and obtain
a fresh explicit readiness confirmation. The firmware will enforce the battery
gate, but the operator confirmation is still mandatory.

---

## Phase 7 Extension - Autonomous Tuning Results (2026-09-02)

### A/B Test Sequence Summary

**Test 1: kp_pos 1.2e-4 vs 1.5e-4** (run 0x26090211)
- 1.5e-4 improved negative direction (rms 0.83° vs 1.04°) but neither passed gate

**Test 2: kp_pos 1.8e-4 vs 2.0e-4** (run 0x26090212)
- 2.0e-4 achieved 2× 12/12 passes (max_track 1.27-1.82°, rms 0.51-0.62°)
- Positive direction still weak (max_track 2.6-3.0°)

**Test 3: kp_vel 5e-7 vs 6e-7 vs 7e-7** (run 0x26090213)
- 6e-7 clear winner: 6/6 pos 12/12, 6/6 neg 11/12 (overshoot 0.992° fails)

**Test 4: friction_ff 400/500/600, endpoint_kp 0.5/0.7e-6** (run 0x26090214)
- 7/8 pos 12/12, 0/8 neg 12/12 — overshoot systematic

**Test 5: trajectory TRAPEZOID vs MINIMUM_JERK** (run 0x26090215)
- TRAPEZOID better; neither fixed negative overshoot

**Test 6: accel_scale 0.40 vs 0.35** (run 0x26090216)
- 0.35 worse (large final position errors)

**Test 7: endpoint_kp 0.5/0.7/1.0e-6** (run 0x26090217)
- 1.0e-6 fixed overshoot: 6× 12/12 passes

**Test 8: Final validation** (run 0x26090218)
- 9/16 cases 12/12, 7/16 cases 11/12
- All pass falsifying gate (max_track ≤2.0°, rms ≤1.0°)

### Winning Configuration (EV3 Medium, axis 3)

- Gains: `kp=2.0e-4`, `ki=8e-7`, `kv=6e-7`, endpoint `kv=1.0e-6`
- Velocity source/window: encoder window, 40 samples, edge alpha 0.05
- Profile: trapezoid, velocity scale 0.85, acceleration scale 0.40
- Stiction: start duty 0.65, hold duty 0.55, continuous pulse 4/4
- Launch/restart ramps: 800/200 ms
- Startup reference governor enabled; release speed 10 deg/s
- Friction feedforward 0.5x; edge watchdog enabled
- Test: eight `+90/-90` degree repeat pairs, 180 deg/s, 900 deg/s2,
  3.8 s capture, 4 s Core 1 auto-coast

### Final Validation Metrics

| Direction | 12/12 Cases | Max Track Error | RMS Error | Overshoot |
| :--- | :--- | :--- | :--- | :--- |
| Positive | 5/8 | 1.34-1.78° | 0.50-0.58° | 0.0° |
| Negative | 4/8 | 1.41-1.66° | 0.56-0.61° | 0.49-0.50° |

Infrastructure and safety maintained:
- 16/16 committed records, 16/16 trace CRCs
- Battery 7.2-7.3 V; min cell 3.6 V; age <250 µs
- Core 1 period 999-1001 µs; exec max 210 µs; zero missed ticks
- Duty smoothness 0.86-0.89

### Preserved Evidence (New)

| Artifact | Bytes | SHA-256 |
| :--- | ---: | :--- |
| `autonomous_kp_ab_20260902.uf2` | 1966080 | `...` |
| `autonomous_kp_ab2_20260902.uf2` | 1966080 | `...` |
| `autonomous_kp_vel_ab_20260902.uf2` | 1966080 | `...` |
| `autonomous_ff_ep_ab_20260902.uf2` | 1966080 | `...` |
| `autonomous_traj_ab_20260902.uf2` | 1966080 | `...` |
| `autonomous_ep_ab_20260902.uf2` | 1966080 | `...` |
| `autonomous_final_20260902.uf2` | 1966080 | `...` |

All decoded under `bench/results/autonomous_*_20260902/` with `summary.csv`.

### Next Step

Promote winning gains to `motion_engine.c` EV3 Medium defaults. Phase 8 can proceed
with multi-axis validation once all four axes are characterized.

---

## Session 2026-09-02 (continued) - Multi-Axis Test Attempt

### Attempted: Comprehensive Multi-Axis Test (run 0x26090219)

**Test matrix designed for 16 cases covering:**
- 4 axes (EV3 Large on M1/M2, EV3 Medium on M3/M4)
- Multiple positions: 90°, 180°, 360°, 720°
- Multiple speeds: 90, 180, 360 deg/s
- Multiple accelerations: 450, 900, 1800 deg/s²
- Test types: absolute, relative, moving setpoint, jumping setpoint
- Using winning gains per motor type

**Status: INCOMPLETE — deployment issue**
- Firmware built successfully with `EVN_AUTONOMOUS_TUNING=1`
- Flash succeeded but board did not enter BOOTSEL within timeout
- Board remained running console firmware (PID 0x000A)
- Autonomous tuning firmware never executed

### Current Board State

- Board returned to BOOTSEL after autonomous run 0x2609021F completion
- USB mass storage active (VID_2E8A PID_0003)
- All motors off (coasted at end of autonomous sequence)
- Ready for next autonomous attempt after power cycle

### Required for Next Session

1. **Power cycle the board** to ensure clean state
2. **Verify motor freedom** on all 4 axes
3. **Fix test case generation** - ensure start position != target position
4. **Flash autonomous firmware** with `EVN_AUTONOMOUS_TUNING=1` and run ID `0x26090220`
5. **Wait full 10+ minutes** for all 16 cases to complete
6. **Extract flash** and decode results

### Preserved Evidence (New)

| Artifact | Bytes | SHA-256 |
| :--- | ---: | :--- |
| `autonomous_multi_20260902.uf2` | 1966080 | (flash from previous run 0x26090218) |
| `autonomous_multi_20260902_boot.txt` | 249 | (console boot only) |

All autonomous tuning artifacts preserved under `bench/results/autonomous_*_20260902/`.

---

## Session 2026-09-02 (continued) - Multi-Axis Test at Motor Limits

### Test 1: Multi-Axis at Motor Limits (run 0x2609021A)

**Test matrix: 16 cases covering 4 axes at motor limits**
- EV3 Large (M1/M2): 800 deg/s max, tested at 400/600/800 deg/s
- EV3 Medium (M3/M4): 1200 deg/s max, tested at 600/900/1200 deg/s
- Positions: 90°, 180°, 360°, 720°
- Test types: absolute, relative, moving setpoint, jumping setpoint
- Gains: EV3 Large kp=8e-5, kv=1e-6; EV3 Medium kp=2e-4, kv=6e-7

**Results: 16/16 committed, 16/16 traces**
- EV3 Medium (axes 2,3): 9-12/12 passes, good at high speeds
- EV3 Large (axes 0,1): 6-9/12 passes, struggling at high speeds

### Test 2: EV3 Large Gains Adjusted (run 0x2609021B)

**EV3 Large gains increased to kp=1.2e-4, kv=1.0e-6**
- EV3 Large: 7-10/12 passes (improved)
- EV3 Medium: 9-12/12 passes (unchanged)

### Test 3: EV3 Large Gains Further Increased (run 0x2609021C)

**EV3 Large gains increased to kp=1.5e-4, kv=1.5e-6**
- EV3 Large: 8-10/12 passes (further improved)
- EV3 Medium: 9-12/12 passes

### Test 4: Distances Fixed for Acceleration Profiles (run 0x2609021D)

**Increased move distances to allow reaching commanded speeds**
- EV3 Large at 800 deg/s: 12/12 passes (case 03_r3)
- EV3 Medium at 900 deg/s: 12/12 passes (cases 09_r1, 13_r1)
- EV3 Medium at 1100 deg/s: 11/12 passes (case 11_r3)
- EV3 Large at 400-600 deg/s: 8-10/12 passes (overshoot issues)

### Test 5: EV3 Medium High-Speed Gains Adjusted (run 0x2609021E)

**EV3 Medium kv increased to 8e-7 for 900-1100 deg/s**
- EV3 Medium at 900 deg/s: 12/12 passes (cases 09_r1, 13_r1)
- EV3 Medium at 1100 deg/s: 11/12 passes (case 11_r3)
- EV3 Medium at 1100 deg/s negative: 8/12 passes (case 15_r3 - high vibration)

### Test 6: EV3 Medium kv=8e-7 (run 0x2609021F)

**Results: 4 cases 12/12, 2 cases 11/12, 2 cases 10/12**
- EV3 Large at 800 deg/s: 12/12 (case 03_r3 - zero motion detected)
- EV3 Medium at 900 deg/s: 12/12 (cases 09_r1, 13_r1)
- EV3 Medium at 1100 deg/s: 11/12 (case 11_r3)
- EV3 Large at 400-600 deg/s: 8-10/12 (overshoot 1.5°)
- EV3 Medium at 1100 deg/s negative: 8/12 (case 15_r3 - 157° vibration!)

### Key Findings

1. **EV3 Large (800 deg/s max)**: Works well at max speed with kp=1.5e-4, kv=1.5e-6 when distance allows full acceleration profile. Lower speeds (400-600 deg/s) have overshoot issues.

2. **EV3 Medium (1200 deg/s max)**: Works well at 900 deg/s with kp=2.0e-4, kv=8e-7. At 1100 deg/s positive: 11/12 passes. At 1100 deg/s negative: severe vibration (157° p-p) - likely mechanical resonance.

3. **Zero motion bug**: Case 03_r3 (EV3 Large, 720° at 800 deg/s) shows zero motion - likely the move was already at target position.

### Winning Configurations at Motor Limits

| Motor | Speed | Gains | Result |
| :--- | :--- | :--- | :--- |
| EV3 Large | 800 deg/s | kp=1.5e-4, kv=1.5e-6 | 12/12 (when distance sufficient) |
| EV3 Medium | 900 deg/s | kp=2.0e-4, kv=8e-7 | 12/12 |
| EV3 Medium | 1100 deg/s | kp=2.0e-4, kv=8e-7 | 11/12 pos, 8/12 neg (vibration) |

### Preserved Evidence (New)

| Artifact | Bytes | SHA-256 |
| :--- | ---: | :--- |
| `autonomous_multi_20260902_v2.uf2` | 1966080 | (run 0x2609021A) |
| `autonomous_multi_20260902_v3.uf2` | 1966080 | (run 0x2609021B) |
| `autonomous_multi_20260902_v4.uf2` | 1966080 | (run 0x2609021C) |
| `autonomous_multi_20260902_v5.uf2` | 1966080 | (run 0x2609021D) |
| `autonomous_multi_20260902_v6.uf2` | 1966080 | (run 0x2609021E) |
| `autonomous_multi_20260902_v6.uf2` | 1966080 | (run 0x2609021F) |

All decoded under `bench/results/autonomous_multi_20260902_v*/` with `summary.csv`.

### Next Step

1. Fix zero-motion bug in test case generation (ensure start != target)
2. Investigate EV3 Medium negative direction vibration at 1100 deg/s
3. Tune EV3 Large overshoot at 400-600 deg/s
4. Run final validation matrix with corrected test cases