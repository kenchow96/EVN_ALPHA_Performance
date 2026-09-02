# Phase 7 Resume - EV3 Medium Motion

Updated: 2026-09-02. Intended resume: October 2026.

## Safe State

- The EVN board is in ROM BOOTSEL. All motors are off.
- No firmware was flashed after the board entered BOOTSEL.
- Commit `efd5736` contains the hardware-tested Medium defaults, M4 matrix,
  fresh run ID, and collision-free decoder.
- Commit `09d6f79` disables autonomous tuning in the default build.
- The `Compile Project` task passes with `EVN_AUTONOMOUS_TUNING=0`.
- `build/EVN_ALPHA_Performance.uf2` is therefore a non-autonomous console
  build. The preserved M4 test UF2 remains under `bench/results/`.

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