# EVN ALPHA Performance — Resume Index

This directory contains per-session resume notes. Each file is a self-contained summary of a work session or major phase.

## Session Files (Chronological)

| Date | File | Phase / Focus |
|------|------|---------------|
| 2026-09-02 | [2026-09-02_phase7_ev3_medium.md](2026-09-02_phase7_ev3_medium.md) | Phase 7 — EV3 Medium Motion (initial resume) |
| 2026-09-02 | [2026-09-02_phase8_multi_axis_v11.md](2026-09-02_phase8_multi_axis_v11.md) | Phase 8 Multi-Axis Validation v11 (run 0x26090224) |
| 2026-09-02 | [2026-09-02_phase8_focused_v12.md](2026-09-02_phase8_focused_v12.md) | Phase 8 Focused Tuning v12 (run 0x26090226) |
| 2026-09-02 | [2026-09-02_phase8_focused_v13.md](2026-09-02_phase8_focused_v13.md) | Phase 8 Focused Tuning v13 — **Breakthrough** (run 0x26090227) |
| 2026-09-02 | [2026-09-02_usb_issues.md](2026-09-02_usb_issues.md) | Safe Console Handoff & USB CDC Issues |
| 2026-09-03 | [2026-09-03_phase8_focused_v14.md](2026-09-03_phase8_focused_v14.md) | Phase 8 Focused Tuning v14 — v13 not reproduced (run 0x26090228) |
| 2026-09-03 | [2026-09-03_phase8_focused_v15.md](2026-09-03_phase8_focused_v15.md) | Phase 8 Focused Tuning v15 — v13 not reproduced 2nd time (run 0x26090229) |
| 2026-09-03 | [2026-09-03_session_end.md](2026-09-03_session_end.md) | Session End State & Autonomous Flash Extraction Protocol |
| 2026-09-04 | [2026-09-04_next_session.md](2026-09-04_next_session.md) | Next Session Priorities (from NEXT_SESSION.md) |

## Quick Reference

### Current State (as of 2026-09-03 end)
- **Board**: Console firmware (`EVN_AUTONOMOUS_TUNING=0`), USB CDC functional after power cycle
- **Motors**: M1/M2 = EV3 Large, M3/M4 = EV3 Medium (gains promoted)
- **Build**: `build/EVN_ALPHA_Performance.uf2` = non-autonomous console with v15 gains
- **Next run ID**: `0x2609022A` (in `hal/hal_tuning_log.h`)
- **Autonomous tuning**: Disabled in `CMakeLists.txt`

### Winning Configurations (Promoted to `motion_engine.c`)

| Motor | kp_pos | kp_vel | ki_pos | accel_scale | endpoint_kp_vel |
|-------|--------|--------|--------|-------------|-----------------|
| EV3 Large | 2.5e-4 | 2.5e-6 | 8e-7 | 0.70 | 1.0e-6 |
| EV3 Medium | 2.0e-4 | 1.0e-6 (all) | 8e-7 | **0.40 (all)** | 1.0e-6 |

### Key Results Summary
- **EV3 Large 800°/s**: 11/12 ceiling (unloaded) — no sweep improved base gains
- **EV3 Medium 1100°/s positive**: 12/12 achieved (both axes)
- **EV3 Medium 1100°/s negative**: 8-10/12 — v13 breakthrough (accel_scale=0.30 → 12/12) **not reproduced** in v14/v15
- **Best EV3 Medium negative**: 10/12 with endpoint_kp=2.0e-6 (v15)

### Next Session Priorities
1. **Fix plumbing**: PowerShell WMI drive detection, timeout reduction, error deduplication, automation script
2. **Console/USB**: Assess console value, UART alternative, USB CDC root cause
3. **Digital twin**: Simulation-first parameter search with logged trace data
4. **Perfect control first**: 12/12 on all 4 axes at max speeds before uneven loading

---

*Generated from monolithic RESUME.md + NEXT_SESSION.md on 2026-09-04*