# Engineering Lessons — Phase 7 Motion Tuning (2026-09-01)

Hard-won, non-obvious knowledge from the motion-engine tuning session. Read
**before** touching `motion/` or the serial tuning console. Distilled from
measured behaviour, not theory. Cross-references: [RP2040_GOTCHAS.md](RP2040_GOTCHAS.md),
[ASSUMPTIONS.md](ASSUMPTIONS.md), [../bench/RESULTS.md](../bench/RESULTS.md).

---

## A. Control architecture (the big one)

**A1. Close the loop on the measured state, not the observer estimate.**
The Luenberger observer's θ̂/ω̂ are *model-predictive* estimates that are
**intentionally allowed to diverge from the encoder under load** — that
divergence is precisely what the sensorless stall detector reads. Early on we
fed θ̂/ω̂ into the PID and got a collapsing speed reading (ω̂ ≈ 18 deg/s while
the shaft actually spun at ~180 deg/s) and a velocity loop that was flying
blind. Fix: **position error = ref − encoder (exact); velocity error = ref −
edge-timed encoder speed.** The observer is reserved for feedforward torque and
stall detection only. This matches how Pybricks actually uses it
(`pbio_control` runs on the *measured* tacho state; the observer supplies the
feedforward + stall signal).

**A2. Raw differentiated encoder position is unusable as a velocity source at 1 kHz.**
Encoder resolution at the output is 0.5°/edge (720 edges/rev). One tick of
jitter in the edge count = 0.5° in 1 ms = a phantom **500 deg/s**. Feeding
`(enc_now − enc_prev)/dt` straight into the velocity P term produced a violent
duty bang-bang (±full) limit cycle. Use the HAL's **edge-timed** speed
(`hal_encoder_get_speed_substep`, substeps/s) which interpolates edge timing —
far lower noise. Even that has ripple; see A4.

**A3. A hold deadzone must keep integrating, not freeze.**
First deadzone attempt *decayed* the integrator inside the tolerance band → the
motor settled into stiction 1.75–2.6° off target with no restoring force.
Correct behaviour: inside the deadzone, **keep integrating** (integral action is
what breaks static friction to reach the exact count) but **drop the noisy
velocity-P term** and **cap the integrator** so it can't wind up into a limit
cycle. Deadzone = 0.4°, integrator capped at 15% of `i_limit`.

**A4. Stiction needs an explicit break floor.**
EV3 Large motors in particular sit at a constant ±0.06 duty in hold, unable to
creep the last degree or two. A **minimum-duty floor** (`min_duty = 0.12`) that
guarantees a correcting-direction pulse whenever |error| > deadzone is what let
M1/M2 converge from ~2° down to 0.04–0.12°.

**A5. Gains are genuinely per-model.** EV3 Large (more rotor inertia + stiction)
needs **stronger** integral (`ki=4e-6`) and the same kp as Medium to overcome
stiction; EV3 Medium tracks to 0.000° with `ki=2e-6`. "Softer loop for the
bigger motor" was the wrong initial guess — the larger motor needs more
integral authority to break friction, not less.

**A6. Feedforward carries the move; feedback corrects it.**
Enabling model feedforward (friction + back-EMF + accel → voltage) cut the
cruise duty mean from ~1.0 (saturated) to ~0.15 and halved saturation time.
The velocity feedback term then only has to mop up the residual. This is the
correct division of labour and the path to smooth motion.

---

## B. What "looks bad" actually is (the visual-roughness problem)

**B1. The endpoint error and the smoothness are separate problems.** We reached
0.000–0.12° final error while the motor still *sounded/looked* rough. The
roughness is a **~90-tick limit-cycle ripple** in the duty signal during cruise,
driven by encoder quantization noise feeding the velocity P term. Position is
unaffected; acoustics/vibration are. **Never accept "final error is small" as
proof of good motion — measure the control-effort smoothness explicitly** (see
the metrics harness, `tools/motion_metrics.py`).

**B2. An under-damped hold oscillates.** Setting `kv=0` (to dodge speed noise)
made cruise position track beautifully (0.99°) but the hold oscillated ±2.5°
because there was no velocity damping. There is a **minimum** velocity gain for
stability even when the velocity signal is noisy. M3 sweet spot: `kv≈4e-5`.

---

## C. USB-CDC / tooling (cost the most wall-clock time)

**C1. Blocking `printf` over stdio-USB wedges the Windows port.** When the host
is slow/closed, blocking CDC writes back up the TinyUSB FIFO and the Windows
`usbser.sys` driver enters a state where COM7 enumerates but **won't open**
(`PermissionError 31`). Only a cold physical re-enumeration clears it.
**Fix (permanent): all console output goes through a non-blocking, FIFO-paced
writer** (`tud_cdc_write_available()` → `tud_cdc_write()` → `tud_cdc_write_flush()`,
servicing `tud_task()`), with a hard wall-clock cap so a dump can never hang.
Host side: small reads + short timeouts + `write_timeout=0`.

**C2. A `printf` in a cross-core command path is a deadlock.** `evn_motion_move_to`
had a debug `printf` in the Core-0→Core-1 handover; under load it deadlocked the
console mid-session (commands consumed, zero response). **Rule: no printf inside
any command-handover or RT-adjacent path.** RT core never prints (already true);
command functions that run under the console must not print either.

**C3. Don't `import` the session module from a test probe.** Importing
`tune_session` runs `main()` (no `if __name__ == "__main__"` guard was relied
on) and double-opens the port → wedge. Test ports with a bare
`serial.Serial(...)` open/close, never by importing the session.

**C4. Every reflash costs a port re-enumeration.** Bake gains into firmware
defaults as soon as they're validated (per-model in `evn_motion_init`), so a
reflash doesn't silently revert a motor to untuned gains mid-analysis. We lost
a run to exactly this (analyzed a trace with defaults, not the tuned gains).

---

## D. Process

**D1. Measure the thing you actually care about.** The analyzer originally
compared `vref` to the *observer* speed and reported a scary 164 deg/s "velocity
error" that was really observer divergence — a measurement artifact, not a
tracking defect. Always compute metrics from the **physical feedback** (encoder),
and record *which* signal each metric uses.

**D2. Read the raw trace before trusting the summary metric.** "M3 did not move"
was caught by eye, not by the (green) final-error metric. The summary hid a
bang-bang oscillation. Metrics are for *quantifying*; always also eyeball the
duty/position waveforms.

**D3. Physical coast drift is real.** An unpowered motor shaft settles/relaxes
by a degree or more after coasting. Don't mistake coasted-shaft drift for a
control overshoot — check whether the loop was *engaged* at that moment.

---

## E. Open items carried into the smoothness push
- Cruise duty ripple (B1) — needs observer-speed or a filtered-velocity term
  that damps without amplifying quantization noise. **This is the top priority
  before drivebase.**
- Observer θ̂/ω̂ diverge up to ~60° during moves — by design, but confirms the
  model constants (ported from Pybricks EV3) are only approximate for our
  7.4 V / DRV8833 / 25 kHz drive. If we ever want the observer *accurate*
  (not just stable), the motor model needs re-characterising on our hardware.
