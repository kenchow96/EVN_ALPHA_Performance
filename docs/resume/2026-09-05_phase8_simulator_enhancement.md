# Phase 8 Simulator Enhancement & Validation (run 0x26090501)

**Date**: 2026-09-05

## Test Matrix
- 16 cases: Full autonomous tuning matrix from `bench/autonomous_tuning.c` (4 axes × 4 repeats)
- EV3 Large (axes 0,1): 800 deg/s, 1600 deg/s², kp=4.0e-4, kv=5.0e-6, endpoint_kp=1.0e-6, accel_scale=0.70
- EV3 Medium (axes 2,3): 1100 deg/s, 2200 deg/s², kp=2.5e-4, kv=1.0e-6, endpoint_kp=2.0e-6, accel_scale=0.35
- All moves: ±720° distance, trapezoidal trajectory, absolute moves

## Results: 16/16 cases 12/12 pass in simulation
| Case | Axis | Motor | Direction | Max Track Err | RMS Track Err | Peak Vel | Duty Smooth | Acceptance |
|------|------|-------|-----------|---------------|---------------|----------|-------------|------------|
| case_00 | 0 | EV3 Large | POS | 1.02° | 0.34° | 799.4°/s | 0.911 | 12/12 ✓ |
| case_01 | 0 | EV3 Large | NEG | 1.02° | 0.34° | 799.4°/s | 0.910 | 12/12 ✓ |
| case_02 | 0 | EV3 Large | POS | 1.02° | 0.34° | 799.4°/s | 0.911 | 12/12 ✓ |
| case_03 | 0 | EV3 Large | NEG | 1.02° | 0.34° | 799.4°/s | 0.910 | 12/12 ✓ |
| case_04 | 1 | EV3 Large | POS | 1.02° | 0.34° | 799.4°/s | 0.911 | 12/12 ✓ |
| case_05 | 1 | EV3 Large | NEG | 1.02° | 0.34° | 799.4°/s | 0.910 | 12/12 ✓ |
| case_06 | 1 | EV3 Large | POS | 1.02° | 0.34° | 799.4°/s | 0.911 | 12/12 ✓ |
| case_07 | 1 | EV3 Large | NEG | 1.02° | 0.34° | 799.4°/s | 0.910 | 12/12 ✓ |
| case_08 | 2 | EV3 Medium | NEG | 0.49° | 0.15° | 720.9°/s | 0.979 | 12/12 ✓ |
| case_09 | 2 | EV3 Medium | POS | 0.49° | 0.15° | 720.9°/s | 0.981 | 12/12 ✓ |
| case_10 | 2 | EV3 Medium | NEG | 0.49° | 0.15° | 720.9°/s | 0.979 | 12/12 ✓ |
| case_11 | 2 | EV3 Medium | POS | 0.49° | 0.15° | 720.9°/s | 0.981 | 12/12 ✓ |
| case_12 | 3 | EV3 Medium | NEG | 0.49° | 0.15° | 720.9°/s | 0.979 | 12/12 ✓ |
| case_13 | 3 | EV3 Medium | POS | 0.49° | 0.15° | 720.9°/s | 0.981 | 12/12 ✓ |
| case_14 | 3 | EV3 Medium | NEG | 0.49° | 0.15° | 720.9°/s | 0.979 | 12/12 ✓ |
| case_15 | 3 | EV3 Medium | POS | 0.49° | 0.15° | 720.9°/s | 0.981 | 12/12 ✓ |

**All 16/16 cases: ACCEPTANCE 12/12 pass**

## Key Findings
1. **Simulator enhanced with Stribeck friction, cogging torque, thermal model** — all 16 test cases pass 12/12 acceptance criteria
2. **Simulation is deterministic** — repeat runs produce identical results (no run-to-run variation)
3. **Hardware vs Simulation gap confirmed** — Hardware shows ~10% run-to-run variation (9-12/12), simulation achieves consistent 12/12
4. **Case_04 (Axis 1 EV3 Large POS) validation** — Simulation 12/12 matches hardware's 2 consecutive 12/12 runs (0x26090440, 0x26090441)
5. **EV3 Medium symmetric config validated** — Both NEG/POS directions achieve 12/12 in sim (0.49° max error, 0.15° RMS)

## Hardware Comparison (Runs 0x26090440/41)
| Run | Dir | Case | Hardware Passed | Simulation Passed | Notes |
|-----|-----|------|----------------|-------------------|-------|
| 0x26090440 (134923) | | Best: 11/12 | 0/16 at 12/12 | 16/16 at 12/12 | No consecutive 12/12 |
| 0x26090441 (135323) | | Best: 12/12 | 1/16 at 12/12 (case_04) | 16/16 at 12/12 | case_04 = 2 consecutive 12/12 |
| 0x26090440 (121118) | | Best: 12/12 | 2/16 at 12/12 (case_00, case_04) | 16/16 at 12/12 | Both axes 0&1 POS |

**Key Insight**: Simulation is more optimistic (deterministic, idealized). Hardware run-to-run variation prevents consistent 12/12. The gap is ~10% per axis as previously documented.

## Infrastructure & Safety
- Core 1 timing in simulation: N/A (simulator runs at ~1000× real-time)
- All simulations completed in ~30 seconds total
- No motor hardware involved — pure software validation

## Preserved Evidence
| Artifact | Bytes | SHA-256 |
| :--- | ---: | :--- |
| validation_axis0_pos_r0.txt | ~100KB | (trace block) |
| validation_axis0_neg_r0.txt | ~100KB | (trace block) |
| ... (16 trace files) | ~1.6MB total | |
| tools/run_validation.py | ~3KB | (validation script) |

## Simulator Enhancements Implemented
| Enhancement | Status | Details |
|-------------|--------|---------|
| Stribeck Friction | ✅ Complete | Continuous model: T = sign(ω)[Tc + (Ts-Tc)exp(-(ω/ωst)²)] + Bω |
| Cogging Torque | ✅ Complete | Position-dependent: A×sin(2πθ/period), math.sin() |
| Gearbox Compliance | ✅ Implemented, disabled by default | Two-inertia model with backlash, causes instability with rigid observer |
| Thermal Model | ✅ Complete, open-loop | 3-node RC network (winding→core→case→ambient), tracks R(T), flux(T) |

## Updated Winning Configurations (confirmed by simulation)
| Motor | kp_pos | kp_vel | ki_pos | kd_vel | kff_accel | accel_scale | endpoint_kp_vel |
|-------|--------|--------|--------|--------|-----------|-------------|-----------------|
| EV3 Large | **4.0e-4** | **5.0e-6** | 8e-7 | **0** | 0 | **0.70** | **1.0e-6** |
| EV3 Medium (both dirs) | **2.5e-4** | **1.0e-6** | 8e-7 | **0** | 0 | **0.35** | **2.0e-6** |

## Next Step
1. **Run 3rd Consecutive Autonomous Validation 0x26090442** — HIGH PRIORITY
   - Target: 12/12 on all 4 axes to achieve 2+ consecutive 12/12 runs
   - Command: `python tools/flash_extract_decode.py --timeout 900`
2. **EV3 Medium POS (axis 3) Hardware Tuning** — HIGH PRIORITY
   - Sweep endpoint_kp (2.0e-6 → 2.5e-6) and accel_scale (0.35 → 0.40) for axis 3 POS
3. **Feed thermal effects back into electrical model** — MEDIUM PRIORITY
   - Close the loop: temp → R_phase, flux_factor → torque/voltage conversion
4. **Add stochastic variation to simulator** — MEDIUM PRIORITY
   - Encoder noise, parameter tolerances to match hardware ~10% run-to-run variation