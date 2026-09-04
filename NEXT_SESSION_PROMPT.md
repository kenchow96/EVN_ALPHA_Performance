# NEXT SESSION PROMPT — EVN ALPHA Performance

## 📋 SESSION STATE SUMMARY (as of 2026-09-04 end)

### Hardware Setup
- **Board**: EVN ALPHA (RP2040, 200 MHz, Pico SDK 2.3.0)
- **Motors**: M1/M2 = EV3 Large (no load), M3/M4 = EV3 Medium **UNLOADED** (new motors, no wheels — changed from previous light load)
- **Battery**: 8.37V multimeter reading, ~8.21V on board
- **Firmware**: Console build (`EVN_AUTONOMOUS_TUNING=0`) with v26 winning configs

### Key Results (144 cases across 9 autonomous runs)
| Motor | Config | Best Pass Rate | Status |
|-------|--------|----------------|--------|
| EV3 Large (M1,M2) | kp=4.0e-4, kv=5.0e-6, kd=0, kff=0, ep_kp=1.0e-6, accel=0.70 | 9-11/12 | Run-to-run variation |
| EV3 Medium NEG (M3) | kp=2.5e-4, kv=1.0e-6, kd=0, ep_kp=2.0e-6, accel=0.35 | 10/12 | Run-to-run variation |
| EV3 Medium POS (M4) | kp=2.5e-4, kv=1.0e-6, kd=1.0e-6, ep_kp=2.5e-6, accel=0.35 | 10/12 | Run-to-run variation |

### Critical Blockers
1. **Run-to-run variation** prevents 2+ consecutive 12/12 on any axis
2. **Motor models don't match unloaded hardware** — sim-to-real gap is root cause
3. **Phase 8 (Drive Base) BLOCKED** until 2+ consecutive 12/12 on all 4 axes

---

## 🎯 NEXT SESSION GOALS

### Priority 1: Motor Model Calibration (HIGHEST PRIORITY)
```bash
# Run system identification on hardware
python tools/simulate_motor.py --motor EV3_Large --sysid ...
python tools/simulate_motor.py --motor EV3_Medium --sysid ...
# Update tools/motor_models.json with HW-identified parameters
```

### Priority 2: Verify Sim-HW Alignment
```bash
# Re-run digital twin with calibrated models
python tools/simulate_motor.py --motor EV3_Large --kp-pos 4.0e-4 --kp-vel 5.0e-6 ...
python tools/simulate_motor.py --motor EV3_Medium --kp-pos 2.5e-4 --kp-vel 1.0e-6 --kd-vel 1.0e-6 ...
# Compare sim predictions vs hardware traces
```

### Priority 3: Only After Calibration → Re-run Autonomous
```bash
# If calibration improves sim-hw alignment, re-run validation
python tools/flash_extract_decode.py  # Run 0x26090439
```

---

## 📁 KEY FILES & LOCATIONS

| Purpose | File |
|---------|------|
| Winning configs | `motion/motion_engine.c` (init function) |
| Test matrix | `bench/autonomous_tuning.c` (`s_cases` array) |
| Motor models | `tools/motor_models.json` |
| Autonomous pipeline | `tools/flash_extract_decode.py` |
| Simulator | `tools/simulate_motor.py` |
| Decoder | `tools/decode_tuning_flash.py` |
| Session logs | `docs/resume/*.md` |
| Master plan | `docs/PLAN.md` |

---

## ⚡ QUICK COMMANDS

```bash
# Build
ninja -C build

# Full autonomous pipeline (build + flash + wait BOOTSEL + extract + decode)
python tools/flash_extract_decode.py

# Quick simulation
python tools/simulate_motor.py --motor EV3_Large --kp-pos 4.0e-4 --kp-vel 5.0e-6 --target 720 --max-vel 800 --max-accel 1600 --battery 8370 --ff --trace

# Decode flash
python tools/decode_tuning_flash.py bench/results/autonomous_auto_*/tuning.uf2 --output bench/results/autonomous_auto_*/

# Check board state
picotool info
```

---

## 🛑 IMPORTANT NOTES

- **Board powered**: Verify with multimeter (8.37V) before flashing
- **USB CDC**: If console doesn't appear, power cycle board
- **Run ID**: Next is `0x26090439` (in `hal/hal_tuning_log.h`)
- **Autonomous tuning**: Currently disabled in `CMakeLists.txt` (`EVN_AUTONOMOUS_TUNING=0`)
- **Motor safety**: Always coast at end of tests (`hal_motor_coast_all()`)

---

## 📝 SESSION HANDOFF CHECKLIST

- [x] All 9 autonomous runs committed with descriptive messages
- [x] Documentation updated: `docs/resume/index.md`, `docs/resume/2026-09-04_phase8_final_validation.md`
- [x] Winning configs in `motion/motion_engine.c`
- [x] Next run ID set: `0x26090439`
- [x] `EVN_AUTONOMOUS_TUNING=0` in CMakeLists.txt
- [x] Board in console mode, USB CDC functional
- [x] Motors coasted

---

**Next session should start with: `python tools/simulate_motor.py --help` then proceed to motor model calibration.**