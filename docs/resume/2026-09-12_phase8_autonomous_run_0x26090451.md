# Phase 8 Autonomous Validation — Run 0x26090451

**Date**: 2026-09-12  
**Run ID**: `0x26090451`  
**Pipeline Output**: `bench/results/autonomous_auto_20260912_214227`  
**Status**: Real physical execution completed (16/16 test cases executed, decoded, and verified).

---

## 1. Audit Remediation Applied Before Run
1. **Root Directory Cleared**: 269 stale test trace files untracked and removed from git; `.gitignore` updated.
2. **Decoder Motor & Axis Labeling Fixed**: `decode_tuning_flash.py` now explicitly outputs motor and axis identifiers (`M1_EV3L`, `M2_EV3L`, `M3_EV3M`, `M4_EV3M`) eliminating case-to-axis confusion.
3. **Stale Flash & Run ID Verification Added**: `flash_extract_decode.py` now enforces that extracted flash matches the expected `EVN_TUNING_RUN_ID` and trace CRC.
4. **Autonomous Loop Controller Upgraded**: `autonomous_loop.py` automatically bumps `EVN_TUNING_RUN_ID` before each iteration and checks convergence criteria.

---

## 2. Hardware Execution & Verification
- **Flash Command**: `python tools/flash_extract_decode.py --timeout 900`
- **Execution Time**: ~102 seconds across 16 test cases (3,820 control ticks per case).
- **Core 1 Real-Time Scheduler**: **PERFECT**
  - Period: 999–1,001 µs across all 16 cases.
  - Maximum execution time: 208 µs (< 21% of 1,000 µs budget).
  - Missed ticks: **0**.
- **Battery Gate**: Pre-run pack 8.21 V, cell 1 = 4.10 V, cell 2 = 4.10 V.

---

## 3. Results Summary (16 Cases)

| Case | Motor | Axis | Dir | Repeat | Score | Passed | MaxErr | FinalErr | Ripple | Core 1 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `case_13` | M4 (EV3M) | 3 | POS | r1 | 3.625 | 10/12 | 1.493° | 0.0° | 0.309 | 999-1001 µs, 0 miss |
| `case_11` | M3 (EV3M) | 2 | POS | r3 | 5.412 | 10/12 | 1.967° | 1.5° | 0.211 | 999-1001 µs, 0 miss |
| `case_09` | M3 (EV3M) | 2 | POS | r1 | 5.415 | 10/12 | 1.846° | 1.5° | 0.181 | 999-1001 µs, 0 miss |
| `case_04` | M2 (EV3L) | 1 | POS | r0 | 5.896 | 10/12 | 2.905° | 0.0° | 0.961 | 999-1001 µs, 0 miss |
| `case_00` | M1 (EV3L) | 0 | POS | r0 | 6.048 | 10/12 | 2.567° | 0.0° | 1.277 | 999-1001 µs, 0 miss |
| `case_08` | M3 (EV3M) | 2 | NEG | r0 | 4.973 | 9/12 | 1.977° | -1.0° | 0.184 | 999-1001 µs, 0 miss |
| `case_15` | M4 (EV3M) | 3 | POS | r3 | 5.214 | 9/12 | 1.056° | 1.0° | 0.272 | 999-1001 µs, 0 miss |
| `case_01` | M1 (EV3L) | 0 | NEG | r1 | 5.858 | 9/12 | 2.683° | 0.0° | 1.012 | 999-1001 µs, 0 miss |
| `case_06` | M2 (EV3L) | 1 | POS | r2 | 5.868 | 9/12 | 2.947° | 0.0° | 1.260 | 999-1001 µs, 0 miss |
| `case_03` | M1 (EV3L) | 0 | NEG | r3 | 7.256 | 9/12 | 2.599° | 0.0° | 1.191 | 999-1001 µs, 0 miss |
| `case_10` | M3 (EV3M) | 2 | NEG | r2 | 7.511 | 9/12 | 1.554° | -2.0° | 0.187 | 999-1001 µs, 0 miss |
| `case_02` | M1 (EV3L) | 0 | POS | r2 | 5.442 | 8/12 | 2.656° | 0.0° | 1.348 | 999-1001 µs, 0 miss |
| `case_12` | M4 (EV3M) | 3 | NEG | r0 | 6.203 | 8/12 | 2.011° | 0.0° | 0.265 | 999-1001 µs, 0 miss |
| `case_14` | M4 (EV3M) | 3 | NEG | r2 | 7.528 | 8/12 | 1.492° | 1.0° | 0.306 | 999-1001 µs, 0 miss |
| `case_05` | M2 (EV3L) | 1 | NEG | r1 | 6.808 | 6/12 | 2.974° | 0.0° | 0.950 | 999-1001 µs, 0 miss |
| `case_07` | M2 (EV3L) | 1 | NEG | r3 | 8.729 | 5/12 | 2.960° | -0.5° | 1.209 | 999-1001 µs, 0 miss |

---

## 4. Key Physical Findings & Controller Insights

1. **M1 (EV3 Large, Axis 0)**:
   - Consistent 8–10/12 passes. Final errors are consistently 0.0°.
   - Max tracking error is ~2.5–2.6°, with cruise ripple ~1.0–1.3 pp.

2. **M2 (EV3 Large, Axis 1)**:
   - POS cases perform well (`case_04` achieves 10/12, `case_06` achieves 9/12).
   - NEG cases show lower scores (5–6/12) with higher ripple. The endpoint damping gain $kp_{vel}=3.0\times 10^{-6}$ stabilizes POS but needs tuning for NEG direction asymmetry.

3. **M3 & M4 (EV3 Medium, Axes 2 & 3)**:
   - Very low max tracking error (1.0–2.0° across all cases).
   - Cruise ripple is extremely low (0.18–0.31 pp), demonstrating smooth trajectory tracking.
   - Stiction break fix ($start\_duty=0.90$) allows both motors to break breakaway friction smoothly without stalls.

4. **Flash Pipeline Stability**:
   - Firmware automatically coasted all motors at completion and rebooted cleanly to BOOTSEL.
   - The tooling verified fresh flash extraction, decoded records with unambiguous labels, and restored `CMakeLists.txt` to interactive console mode (`EVN_AUTONOMOUS_TUNING=0`).
