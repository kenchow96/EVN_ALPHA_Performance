# Phase 8 Torture Excitation Profile Validation — Run 0x26090454

**Date**: 2026-09-12  
**Run ID**: `0x26090454`  
**Pipeline**: `tools/auto_tuner.py --iterations 1` with `use_torture_profiles=True`  
**Result Directory**: `bench/results/autonomous_auto_20260912_221143/`

---

## 1. Excitation Profile Integration Overview
The 16-case tuning matrix was updated to integrate the multi-regime torture profiles from `tools/excitation_profiles.py`:
- **EV3 Large (Axes 0 & 1)**:
  - Cases 00 / 04: Nominal fast forward move ($+720^\circ$ at $800^\circ/\text{s}$, $1600^\circ/\text{s}^2$).
  - Cases 01 / 05: Reversal return move ($-720^\circ$ at $800^\circ/\text{s}$, $1600^\circ/\text{s}^2$).
  - Cases 02 / 06: **Micro-step backlash test** ($+45^\circ$ rapid step at $400^\circ/\text{s}$, $2000^\circ/\text{s}^2$).
  - Cases 03 / 07: **Deadband reversal & lash crossing** ($-90^\circ$ at $600^\circ/\text{s}$, $1800^\circ/\text{s}^2$).
- **EV3 Medium (Axes 2 & 3)**:
  - Cases 08 / 12: Nominal fast move ($-720^\circ$ at $1100^\circ/\text{s}$, $2200^\circ/\text{s}^2$).
  - Cases 09 / 13: Forward breakaway stiction test ($+720^\circ$ at $1100^\circ/\text{s}$, $2200^\circ/\text{s}^2$).
  - Cases 10 / 14: **Rapid step acceleration** ($-360^\circ$ at $1200^\circ/\text{s}$, $2500^\circ/\text{s}^2$).
  - Cases 11 / 15: **Micro-step stiction test** ($+60^\circ$ at $600^\circ/\text{s}$, $2400^\circ/\text{s}^2$).

---

## 2. Hardware Results (16 Cases)

| Case | Motor | Move Description | Physical Result | Max Error | Final Error | Sim Agreement |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `case_14` | M4 (EV3M) | Rapid step ($-360^\circ$) | **12/12** (Pass) | 1.135° | 0.0° | 29.4% |
| `case_12` | M4 (EV3M) | Nominal return ($-720^\circ$) | **12/12** (Pass) | 1.508° | 0.0° | 28.2% |
| `case_11` | M3 (EV3M) | Micro-step stiction ($+60^\circ$) | **12/12** (Pass) | 1.818° | 0.0° | 13.7% |
| `case_15` | M4 (EV3M) | Micro-step stiction ($+60^\circ$) | **12/12** (Pass) | 1.291° | 0.0° | 19.3% |
| `case_09` | M3 (EV3M) | Stiction breakaway ($+720^\circ$) | **11/12** | 1.549° | 0.0° | 27.4% |
| `case_10` | M3 (EV3M) | Rapid step ($-360^\circ$) | **11/12** | 1.481° | 0.0° | 22.6% |
| `case_03` | M1 (EV3L) | Deadband reversal ($-90^\circ$) | **11/12** | 1.134° | 0.0° | 44.1% |
| `case_08` | M3 (EV3M) | Nominal return ($-720^\circ$) | **11/12** | 1.775° | 0.0° | 24.0% |
| `case_04` | M2 (EV3L) | Nominal move ($+720^\circ$) | **11/12** | 2.883° | 0.0° | **94.4%** |
| `case_02` | M1 (EV3L) | Backlash micro-step ($+45^\circ$) | **10/12** | 1.308° | 0.0° | 40.9% |
| `case_06` | M2 (EV3L) | Backlash micro-step ($+45^\circ$) | **10/12** | 1.507° | 0.0° | 47.1% |
| `case_13` | M4 (EV3M) | Stiction breakaway ($+720^\circ$) | **10/12** | 2.464° | 0.0° | 17.2% |
| `case_00` | M1 (EV3L) | Nominal move ($+720^\circ$) | **10/12** | 2.692° | 0.0° | **98.9%** |
| `case_01` | M1 (EV3L) | Reversal return ($-720^\circ$) | **9/12** | 2.690° | 0.0° | **98.3%** |
| `case_07` | M2 (EV3L) | Deadband reversal ($-90^\circ$) | **9/12** | 1.364° | 0.0° | 53.0% |
| `case_05` | M2 (EV3L) | Reversal return ($-720^\circ$) | **5/12** | 2.975° | 0.0° | **88.8%** |

---

## 3. Key Telemetry Insights
1. **Micro-Step & Deadband Reversal Performance**:
   - EV3 Large micro-step moves ($45^\circ$, $90^\circ$) showed very low tracking errors: **1.13°–1.50°** max error with **0.0° final settling error**, confirming backlash compensation stability.
   - EV3 Medium micro-steps ($60^\circ$) achieved **12/12 full passes** on both Axis 2 and Axis 3 (`case_11`, `case_15`).
2. **Breakthrough Pass Rate**:
   - **4 cases achieved 12/12 full passes** (`case_14`, `case_12`, `case_11`, `case_15`).
   - **5 cases achieved 11/12 near-passes** (`case_09`, `case_10`, `case_03`, `case_08`, `case_04`).
3. **Core 1 Determinism**:
   - Period: 999–1001 µs, **0 missed ticks**, max execution time 205 µs across all 16 cases.
