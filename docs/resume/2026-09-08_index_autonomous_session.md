# Phase 8 Autonomous Session — Index Update + Simulator Verification (sim-only)

**Date**: 2026-09-08
**Run ID**: N/A (sim-only session; no autonomous run executed — user: "before trying real transfer")
**Session mode**: Continuous iteration (sim → hardware → update sim) per user directive; no further permission required; all hardware ready for deployment.

## Deliverable + Falsifying Check (Efficiency Protocol §2.1)
- **Deliverable**: Update `docs/resume/index.md` with current session state (post-run 0x2609044A), winning configurations, simulator verification results, and continuous-iteration protocol; verify build (0 errors).
- **Falsifying check**: Read updated `index.md` — chronological table includes `2026-09-08_index_autonomous_session.md`; Current State block includes simulator verification line; `Compile Project` task exits 0; `git status` shows clean commit.

## Test Matrix (Simulation — no hardware deploy)
- 2 cases: EV3 Large (backlash 1.5°, vel_window=10) + EV3 Medium (backlash 2.0°, vel_window=40)
- Winning config from `index.md`: EV3 Large (kp=4.0e-4, kv=5.0e-6, accel_scale=0.70, endpoint_kp=1.0e-6); EV3 Medium symmetric (kp=2.5e-4, kv=1.0e-6, accel_scale=0.35, endpoint_kp=2.0e-6)
- Duration: 15 s each; target 720°; trace captured

## Results: 2/2 sim cases pass (no endpoint oscillation)
| Case | Motor | Backlash | vel_window | MaxErr (°) | FinalErr (°) | Endpoint duty sign changes (last 2s) | Pass |
|---|---|---|---|---|---|---|---|
| sim_ev3l_backlash | EV3 Large | 1.5° | 10 | 1.881 | 0.050 | 0 | ✅ |
| sim_ev3m_backlash | EV3 Medium | 2.0° | 40 | 0.381 | 0.026 | 0 | ✅ |

**Key finding**: `vel_window=10` eliminates the EV3 Large endpoint limit cycle in sim (0 endpoint duty oscillations, max duty 1000 milli, no rail banging). This confirms the sim-calibration breakthrough (run 0x2609044A analysis): the physical 13.6 Hz limit cycle is reproduced by the calibrated sim (13.9 Hz) and eliminated by the narrower velocity window.

## Key Findings
1. **Simulator verification complete** — both winning configs stable with backlash enabled; no limit-cycle duty oscillation at endpoint.
2. **No real hardware transfer performed** — user instruction: "before trying real transfer"; board remains in UF2 console mode (`EVN_AUTONOMOUS_TUNING=0`).
3. **Build verified** — `Compile Project` exits 0 (`[3/3] Linking EVN_ALPHA_Performance.elf`); commit `a344fe7` clean.
4. **Continuous iteration protocol documented** in `index.md` — sim → hardware → update sim; deploy when verified; coast motors at end of every test; battery gate (≥6.5V, cells ≥3.0V) before any motor run.
5. **Next cycle (sim)**: (a) DR harness in `run_validation.py`; (b) backlash sweep axis-3 (0.5–2.5°); (c) encoder velocity noise + vel_window re-sweep; (d) deploy to hardware (run 0x2609044B) once worst-case ≥11/12 in sim.

## Infrastructure & Safety
- Board: UF2 mode, powered, USB CDC functional (no deploy performed)
- Motors: M1/M2 EV3 Large, M3/M4 EV3 Medium — UNLOADED, free to move (confirmed by user)
- Battery: Not sampled (no deploy); gate applies before any future motor test
- Core 1: Not measured (sim-only); will verify on next hardware run
- Motor safety: `hal_motor_coast_all()` will be called at end of every future hardware test

## Preserved Evidence
| Artifact | Bytes | SHA-256 | Purpose |
|---|---|---|---|
| `docs/resume/index.md` (updated) | ~28 KB | (in commit a344fe7) | Session state + protocol |
| `bench/results/sim_ev3l_backlash.csv` | 2501 rows | (new) | EV3 Large sim trace (backlash 1.5°) |
| `bench/results/sim_ev3m_backlash.csv` | 2501 rows | (new) | EV3 Medium sim trace (backlash 2.0°) |
| `docs/resume/2026-09-08_index_autonomous_session.md` | this file | — | Session log |

## Updated Winning Configurations (unchanged — promoted to motion_engine.c)
| Motor | kp_pos | kp_vel | ki_pos | kd_vel | kff_accel | accel_scale | endpoint_kp_vel |
|---|---|---|---|---|---|---|---|
| EV3 Large | 4.0e-4 | 5.0e-6 | 8e-7 | 0 | 0 | 0.70 | 1.0e-6 |
| EV3 Medium (both dirs) | 2.5e-4 | 1.0e-6 | 8e-7 | 0 | 0 | 0.35 | 2.0e-6 |

## Next Step (continuous iteration — next cycle)
1. **Sim**: Implement DR harness (`run_validation.py`) — N randomized draws × 16 cases, worst-case ≥11/12 promotion criterion.
2. **Sim**: Enable backlash sweep for axis-3 (0.5–2.5°) — check case_13/15 stall reproduction.
3. **Sim**: Add Gaussian encoder velocity noise; re-sweep vel_window ∈ {5,10,20,40} for EV3 Large robustness.
4. **Hardware (when sim worst-case ≥11/12)**: Deploy via `python tools/flash_extract_decode.py --timeout 900` (run 0x2609044B): `start_duty` 0.90 for axis 3, `vel_window=10` axes 0/1/3, `vel_window=40` axis 2; confirm board powered (`check_bootsel.ps1`); coast motors at end.

## Continuation Command (exact — for next session)
```powershell
# 1. Confirm board state (primary: BOOTSEL check; secondary: ask user if undetected)
powershell -NoProfile -ExecutionPolicy Bypass -File tools/check_bootsel.ps1
# 2. Verify build (must exit 0 before any deploy)
run_task "Compile Project"
# 3. If deploying (after sim worst-case ≥11/12): full autonomous pipeline
python tools/flash_extract_decode.py --timeout 900
# 4. After any hardware test: coast motors (safety rule)
# (Send 'c' via console or call hal_motor_coast_all() in firmware)
```
