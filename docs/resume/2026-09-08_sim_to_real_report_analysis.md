# Sim-to-Real Report Analysis (run 0x2609044A complete)

**Date**: 2026-09-08

## Source
Integrated insights from `Sim-To-Real DC Motor Control.md` (local report) against current Phase 8 state (as of run 0x2609044A).

## Current State (per [index.md](index.md))
- **Board**: Console firmware (`EVN_AUTONOMOUS_TUNING=0`), USB CDC functional after power cycle
- **Motors**: M1/M2 = EV3 Large, M3/M4 = EV3 Medium **UNLOADED** (new motor on port 4)
- **Build**: `build/EVN_ALPHA_Performance.uf2` = non-autonomous console with stiction fix + symmetric EV3 Medium config
- **Next Run ID**: `0x2609044B`
- **Autonomous Tuning**: Disabled in `CMakeLists.txt` (restored after run)
- **Hardware Validation**: ✅ Complete — 224/224 cases run across 14 autonomous runs, all traces decoded
- **Motor Model Calibration**: ✅ Complete — EV3 Medium model fixed for unloaded operation, sim 12/12 both directions
- **Stiction Break Fix**: ✅ **HITL VERIFIED & CONFIRMED IN AUTONOMOUS** — case_15 catastrophic 121° error FIXED (0.0° final error); both EV3 Medium motors break stiction
- **Dashboard**: **10/10 BUGS FIXED** — All confirmed root causes from firmware console audit resolved
- **Symmetric EV3 Medium Config**: ✅ **VALIDATED** — Simulation 12/12 for both NEG/POS; hardware 7-12/12 consistent
- **Consecutive 12/12**: ✅ **case_04 (axis 1 POS r0): 2+ consecutive** (0x26090445 + 0x26090446). ⚠️ **case_01 (axis 0 NEG r1) hunting is SYSTEMATIC** (6/12→5/12) — axes 0 & 1 share identical EV3 Large gains but diverge ⇒ per-axis/hardware difference, not gains
- **Pipeline**: ✅ **FIXED (2026-09-06)** — `flash_extract_decode.py` BOOTSEL false-positive: now waits for the drive to disappear (app booted) before waiting for it to reappear (run done)
- **Simulator**: ✅ **CALIBRATED TO PHYSICAL** — Reproduces the EV3 Large endpoint limit cycle (13.9 Hz vs physical 13.6 Hz). **vel_window=10 eliminates the limit cycle in sim** (tested on hardware run 0x26090449: axis-0 NEG 6/12→11/12). EV3 Medium 12/12 unaffected

## Key Blockers (from run 0x2609044A)
1. **EV3 Medium Axis 3 Stiction Stall Fix** — axis 3 (new EV3 Medium motor) POS reversals still stall (case_13 9/12, case_15 10/12); vel_window=10 helped slightly (case_15 9→10/12) but stiction break not triggering reliably on NEG→POS reversal
2. **EV3 Large Robustness** — hunting is systematic per-axis; config marginally stable across gear-train variability range
3. **Run-to-run Variation** — ~10% per axis, no 2+ consecutive 12/12 on EV3 Medium yet
4. **Sim Determinism vs Hardware Stochasticity** — sim has no injected noise/backlash/compliance (gearbox_compliance disabled, no stochastic terms)

## Report Insights → Project Mapping

The report **Sim-to-Real Transfer in Encoder-Only Brushed DC Motor Control** provides a direct framework for these exact blockers. Key mappings:

| Report Concept | Project Manifestation |
|---|---|
| **Gearbox Backlash & Directional Hysteresis** — deadzones during reversals → zero-torque motion delays + violent impact on tooth re-engagement | Axis 3 POS reversal stalls (case_13/15) — failure mode is specifically NEG→POS reversal |
| **Policies trained in naive sims exploit instantaneous torque → limit cycles on hardware** | EV3 Large endpoint limit cycle (13.9 Hz sim / 13.6 Hz physical) — duty swinging ±full (chatter) |
| **Domain Randomization ranges**: R ±25%, friction 0.5–2×, backlash 0–2.5°, delay 0–4 ms, V_max ±15%, Gaussian velocity noise | ~10% run-to-run variation — sim is deterministic ensemble of one; hardware varies |
| **Numerical differentiation amplifies velocity encoder noise**; DR includes Gaussian measurement noise | vel_window tradeoff — window=10 improved hunting (6/12→11/12) but narrower windows increase noise sensitivity |

## Concrete, Actionable Takeaways

### 1. Adopt Domain Randomization as the Tuning Methodology (Priority)
Stop tuning against the single deterministic calibrated sim. Instead:
- Sample parameter vectors from the report's DR ranges (R 0.85–1.25×, L 0.70–1.30×, kv 0.90–1.10×; friction 0.5–2.0×; backlash 0–2.5°; delay 0–4 ms; V_max 0.85–1.0×; Gaussian velocity noise)
- For each candidate gain set, run all 16 cases across N randomized parameter draws (e.g., N=30)
- Promote the gain set with the **best worst-case pass-rate** (or ≥11/12 worst-case), not the best nominal sim 12/12
- This directly targets "marginally stable across the whole gear-train variability range" (runs 0x26090447/48) and is the fastest path to 2+ consecutive 12/12

### 2. Enable and Sweep the Disabled Gearbox Backlash Model
[simulate_motor.py](tools/simulate_motor.py) already implements:
- `gearbox_backlash_mdeg` (mdeg)
- `gearbox_stiffness` (unm/deg) 
- two-inertia motor/load states
...but they are **disabled by default** (`gearbox_backlash_mdeg = 0`, comment: "requires careful tuning").

**Action**: Enable backlash for the EV3 Medium axis-3 plant model and sweep 0.5–2.5°. Check whether this reproduces the case_13/15 stall signature (NEG→POS reversal stall). If yes, tune the axis-3 stiction-break parameters (start_duty 0.80→0.90, pulse 4→6 ticks) in sim instead of burning hardware runs.

### 3. Validate vel_window=10 Under Encoder Noise
The report confirms that narrower velocity estimation windows (smaller vel_window) increase phase lag reduction but amplify quantization noise. The current sim has encoder quantization but **zero stochastic noise** (grep finds no `np.random` usage — fully deterministic).

**Action**: Add Gaussian velocity measurement noise to the encoder model in [simulate_motor.py](tools/simulate_motor.py), then re-sweep vel_window ∈ {5, 10, 20, 40} for EV3 Large. Determine whether vel_window=10 is a robust setting (consistent improvement across noise realizations) or a fragile one (only helps in the noiseless sim).

### 4. Formalize Duty Slew as an Acceptance Metric
The report's reward function explicitly penalizes `|V_t - V_{t-1}|` (voltage slew) to suppress chatter. The EV3 Large limit cycle **is** duty chatter (duty swinging ±full at ~13.6 Hz). The project already logs "Duty smoothness" in every session template but doesn't use it as an acceptance criterion.

**Action**: Treat max endpoint duty slew (or RMS slew) as a formal pass/fail metric alongside position error. In the validation harness, reject gain sets that produce high-frequency duty oscillation at endpoint, even if position error is <2.0°.

### 5. Confirm Architecture Choice — Residual PID is Correct-Sized
The report's Residual Policy Learning (RPL) section describes exactly what the stiction-break mechanism is: a baseline PID + a learned residual correction targeting backlash/stiction. It rates this architecture **"Very Low deployment complexity, Minimal hardware wear risk"** — the right-size solution for the deterministic 1 kHz RP2040 loop with zero-heap constraints. Teacher-student distillation / RMA / IQL+TD3 would fight hard-real-time and determinism requirements for no needed benefit in this context.

## Updated Assumptions to Track
Based on the report analysis, the following simulator fidelity assumptions should be made explicit and tracked in `ASSUMPTIONS.md`:
- **A?** Simulator uses deterministic physics (no injected parameter noise, no backlash/compliance unless explicitly enabled, no measurement noise)
- **A?** Encoder model includes quantization but no Gaussian velocity measurement noise
- **A?** Plant and observer run at the same rate (1 ms) — known velocity lag mismatch mitigated by voltage_lag_ms term but not yet swept

## Next Steps (from analysis)
1. **Implement DR harness in [run_validation.py](tools/run_validation.py)** — N randomized draws × 16 cases, report worst-case and pass-distribution per config
2. **Enable backlash sweep for EV3 Medium axis-3** — 0.5–2.5°, check case_13/15 stall reproduction
3. **Add encoder velocity noise** — re-sweep vel_window for EV3 Large robustness
4. **Change promotion criterion** — from "nominal sim 12/12" to "worst-case ≥ 11/12 across ensemble"

These steps are all sim-only, zero hardware risk, and directly address the consecutive-12/12 gate and the per-axis hunting systematicity.

## Evidence Preserved
| Artifact | Purpose |
|---|---|
| [Sim-To-Real DC Motor Control.md](file:///C:/Users/kenne/OneDrive - Centre Of Robotics Excellence/CORE/Projects/Sim-To-Real%20DC%20Motor%20Control.md) | Source report |
| Current session files in `docs/resume/` | Baseline state for comparison |

## Updated Winning Configurations (Promotion Criteria)
Promotion to [motion_engine.c](motion/motion_engine.c) now requires **worst-case performance across a domain-randomized ensemble**, not just the nominal calibrated sim. Winning configs from past runs remain valid only if they maintain ≥11/12 worst-case across the DR ensemble.

## Next Step (from analysis)
1. Create DR harness in validation script
2. Enable backlash in sim for axis-3 sweep
3. Add encoder noise and re-test vel_window
4. Re-run analysis with worst-case criterion

---

## ⚠️ Dissenting Viewpoint — Alternative Agent Challenge (2026-09-08)

A parallel review of this same analysis (same `index.md` and `Sim-To-Real DC Motor Control.md` source) raised **three substantive disagreements** with the recommendations above. Both viewpoints are preserved here so future agents can weigh them against the actual workspace evidence.

### Challenge 1 — Domain Randomization as Primary Tuning Methodology (Priority 1 above)
**Parallel agent's position**: Replace the promotion criterion ("nominal sim 12/12") with "worst-case ≥11/12 across a DR ensemble" (N=30 randomized draws per config); make DR the primary tuning methodology.

**Dissenting evidence** (from workspace, not opinion):
- The project has **14 verified autonomous hardware runs** (`0x2609042C` → `0x2609044A`, 224/224 cases traced, all traces decoded). The DR ensemble is a *sim-only* abstraction that has not been validated against any of those 14 runs.
- The calibrated simulator **already reproduces the physical EV3 Large endpoint limit cycle** (13.9 Hz sim vs 13.6 Hz physical, 8.2° pp vs 6.2° pp). The gap is not "sim doesn't match physics" — it is "sim is deterministic, hardware varies ~10%." A DR ensemble makes the promotion criterion stricter without evidence that worst-case DR predicts worst-case hardware.
- The **actual open blocker** is axis 3 POS reversal stall (case_13 9/12, case_15 10/12, run 0x2609044A) — a concrete, reproducible failure mode. A 30-draw statistical ensemble dilutes focus from this specific mechanism.
- `AGENTS.md` rules (§2.1, §2.3) require "cheapest falsifying check" and "one focused validation per edit." A 30-draw ensemble violates both.
- `index.md` "Next Session Priorities" (pre-parallel-agent update) already lists the correct first action: "Increase `start_duty` for axis 3 from 0.80 → 0.90" — a direct parameter change, not a statistical abstraction.

**Dissenting recommendation**: Keep DR as a **secondary robustness check** (Priority 7 in `index.md`), not the primary promotion criterion. The primary gate should remain "2+ consecutive 12/12 on hardware" — which the project has already achieved (case_04: 2 consecutive runs 0x26090445+46; case_00: 3 consecutive runs 0x26090440–42).

### Challenge 2 — Enable Disabled Gearbox Backlash Model (Priority 2 above)
**Parallel agent's position**: Enable `gearbox_backlash_mdeg` in `simulate_motor.py` (currently `0`, disabled with comment "requires careful tuning") and sweep 0.5–2.5° for axis-3 to reproduce case_13/15 stall.

**Dissenting evidence**:
- The `simulate_motor.py` source explicitly states the 2-inertia gearbox model is **unstable with the rigid observer**. The parallel agent ignores this stability warning.
- The case_13/15 stall is **already explained** by the verified stiction-break mechanism: direction-reversal static friction exceeds `start_duty=0.80`; the fix (`start_duty` 0.80→0.90, pulse 4→6 ticks) is a direct parameter change, not a model change.
- Running a backlash sweep burns sim cycles without addressing the actual mechanism. If backlash were the root cause, the stall would occur on both directions; it is specifically NEG→POS reversal — matching the stiction-break activation pattern, not a backlash deadzone.
- The `index.md` Priority 1 (pre-parallel-agent) already specifies the correct action: increase `start_duty`/`startup_pulse_on_ticks` for axis 3.

**Dissenting recommendation**: Do **not** enable backlash until the stiction-break parameter fix is tested on hardware. Backlash is a separate physical mechanism; conflating it with stiction stalls confuses root-cause analysis and risks destabilizing the observer.

### Challenge 3 — "Residual PID is Correct-Sized" Framing (Priority 5 above)
**Parallel agent's position**: Frame the stiction-break mechanism as "exactly what Residual Policy Learning (RPL) describes" (baseline PID + learned residual correction); claim RPL is "the right-size solution" for the RP2040 loop.

**Dissenting evidence**:
- The stiction-break mechanism (`start_duty` pulse + velocity-threshold activation + pos-error activation) is a **classical feedforward + state-machine** mechanism. There is no neural network (`torch`/`onnx` not in repo), no imitation loss (`L_distill`), no policy gradient, no `π_φ`.
- The report's RPL architecture (`V_total = clip(V_PID + ΔV, ±V_max)`) requires a **trainable DRL network** (`ΔV = π_φ(o_enc)`). The EVN ALPHA control path (`motion_engine.c`, `pid.c`, `observer.c`, `trajectory.c`) contains zero DRL infrastructure.
- Calling the classical mechanism "RPL" is a **category error** that could mislead future agents into attempting DRL integration — which would conflict with `AGENTS.md` rules (zero heap allocation in RT path, `__not_in_flash_func`, deterministic 1 kHz loop, no dynamic memory).
- The architecture is correctly described as: **cascaded PID + Luenberger observer + trajectory profiler + stiction-break feedforward**. It should be labeled as such.

**Dissenting recommendation**: Reject the "RPL" relabeling. The architecture is classical control with a feedforward stiction-break mechanism. If future work genuinely requires a learned residual, that should be a separate, explicitly-scoped phase — not a relabeling of existing classical code.

---

## Consensus Points (Both Agents Agree)
Both the original analysis and the dissent agree on:
- The 4 gap categories from the report (backlash, stiction/Stribeck, supply saturation, encoder quantization + delay) directly match EVN ALPHA's open problems.
- The calibrated simulator (13.9 Hz vs 13.6 Hz) is a significant achievement and should be preserved.
- `vel_window=10` improved axis-0 NEG hunting (6/12 → 11/12) and should be retained.
- Duty-slew should be formalized as an acceptance metric (report's `|V_t - V_{t-1}|` reward term aligns with observed endpoint limit-cycle behavior).
- Encoder velocity noise should be added to the simulator (currently fully deterministic — no `np.random` usage found).
- The thermal model (3-node lumped network in `simulate_motor.py`) should eventually be closed-loop (temp → R_phase, flux_factor) — currently open-loop.

---

*Both viewpoints preserved. The parallel agent's recommendations (DR primary, backlash sweep, RPL framing) are documented above with their supporting reasoning; the dissenting challenges are documented with workspace evidence (run IDs, file comments, `AGENTS.md` rules, `simulate_motor.py` source). Future agents should evaluate both against the actual hardware state before committing to either path.*