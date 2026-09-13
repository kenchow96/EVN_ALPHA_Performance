#!/usr/bin/env python3
"""
EVN ALPHA Digital Twin — Cycle-Accurate Motor Simulator

Replicates the Core 1 firmware tick-for-tick:
- Luenberger observer (5 ms discrete, integer math)
- Cascaded PID controller (1 ms, float math with windowed speed)
- Trapezoidal / quintic trajectory profiler (1 ms)
- Model-based feedforward (torque → voltage → duty)
- Encoder quantization + simple motor plant model
- Battery voltage compensation

Output: evn_trace_row_t compatible CSV for motion_metrics.py analysis
"""

import json
import argparse
import csv
import sys
import math
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# Constants (must match firmware exactly)
# ─────────────────────────────────────────────────────────────────────────────

MOTION_DT = 1.0 / 1000.0                    # 1 kHz control loop
OBSERVER_PERIOD_TICKS = 5                   # Observer runs every 5 ms
EVN_TRACE_SAMPLE_DIV = 5                    # Trace captured every 5th tick (200 Hz)

# Observer prescale constants (from observer.h — do not change)
EVN_OBS_PRESCALE_SPEED     = 858
EVN_OBS_PRESCALE_ACCEL     = 85
EVN_OBS_PRESCALE_CURRENT   = 71582
EVN_OBS_PRESCALE_VOLTAGE   = 178956
EVN_OBS_PRESCALE_TORQUE    = 2147

EVN_OBS_MAX_SPEED_MDEPS    = 2_500_000
EVN_OBS_MAX_ACCEL          = 25_000_000
EVN_OBS_MAX_CURRENT        = 30_000
EVN_OBS_MAX_VOLTAGE_MV     = 12_000
EVN_OBS_MAX_TORQUE_UNM     = 1_000_000

# PID speed window (from pid.h)
PID_SPEED_WINDOW = 60

# ─────────────────────────────────────────────────────────────────────────────
# Helper functions (match firmware integer math)
# ─────────────────────────────────────────────────────────────────────────────

def iabs32(x: int) -> int:
    return -x if x < 0 else x

def isign32(x: int) -> int:
    return (1 if x > 0 else 0) - (1 if x < 0 else 0)

def iclamp(v: int, lim: int) -> int:
    if v > lim: return lim
    if v < -lim: return -lim
    return v

def fsign(x: float) -> float:
    return 1.0 if x > 0 else (-1.0 if x < 0 else 0.0)

def fabs_f(x: float) -> float:
    return -x if x < 0 else x

def fclamp(v: float, lo: float, hi: float) -> float:
    if v > hi: return hi
    if v < lo: return lo
    return v

# ─────────────────────────────────────────────────────────────────────────────
# Motor Model & Observer Settings
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class MotorModel:
    """evn_motor_model_t — 17 integer coefficients for 5 ms discrete observer"""
    d_angle_d_speed: int
    d_speed_d_speed: int
    d_current_d_speed: int
    d_angle_d_current: int
    d_speed_d_current: int
    d_current_d_current: int
    d_angle_d_voltage: int
    d_speed_d_voltage: int
    d_current_d_voltage: int
    d_angle_d_torque: int
    d_speed_d_torque: int
    d_current_d_torque: int
    d_voltage_d_torque: int
    d_torque_d_voltage: int
    d_torque_d_speed: int
    d_torque_d_acceleration: int
    torque_friction: int

    # Metadata for simulation
    cpr: int = 2880
    counts_per_rev: float = 720.0
    rated_max_speed_deg_s: int = 800

    # Stribeck friction parameters (for enhanced PlantModel)
    # torque_friction is the Coulomb friction level (at high speed)
    # static_friction: static friction torque (stiction) at zero speed
    # stribeck_vel_mdegs: Stribeck transition velocity (mdeg/s)
    # viscous_friction: viscous friction coefficient (torque per mdeg/s)
    static_friction: int = 0          # If 0, defaults to 2x torque_friction
    stribeck_vel_mdegs: int = 50000   # Transition speed (mdeg/s) ~ 50 deg/s
    viscous_friction: int = 0         # Viscous coefficient (unm per mdeg/s)

    @property
    def substeps_per_rev(self) -> float:
        return (self.counts_per_rev / 4.0) * 256.0

    @property
    def mdeg_per_substep(self) -> float:
        return 360000.0 / self.substeps_per_rev
    
    def get_static_friction(self) -> int:
        """Get static friction torque (stiction). Defaults to 2x Coulomb if not set."""
        return self.static_friction if self.static_friction > 0 else self.torque_friction * 2
    
    def get_stribeck_vel(self) -> int:
        """Get Stribeck transition velocity."""
        return self.stribeck_vel_mdegs
    
    def get_viscous_friction(self) -> int:
        """Get viscous friction coefficient."""
        return self.viscous_friction


@dataclass
class ObserverSettings:
    """evn_observer_settings_t"""
    stall_speed_limit: int = 50000
    stall_time_ms: int = 50
    feedback_voltage_negligible: int = 500
    feedback_voltage_stall_ratio: int = 50
    feedback_gain_low: int = 45
    feedback_gain_high: int = 200
    feedback_gain_threshold: int = 5000
    coulomb_friction_speed_cutoff: int = 20000


@dataclass
class ObserverState:
    """evn_observer_t runtime state"""
    angle_mdeg: int = 0
    speed_mdegs: int = 0
    current: int = 0
    stalled: bool = False
    stall_start_ms: int = 0


# ─────────────────────────────────────────────────────────────────────────────
# Observer (exact port of firmware evn_observer_update)
# ─────────────────────────────────────────────────────────────────────────────

class Observer:
    def __init__(self, model: MotorModel, settings: ObserverSettings, start_angle_mdeg: int = 0):
        self.model = model
        self.settings = settings
        self.state = ObserverState(angle_mdeg=start_angle_mdeg)

    def feedback_voltage(self, angle_mdeg: int) -> int:
        """evn_observer_feedback_voltage"""
        error = angle_mdeg - self.state.angle_mdeg
        error_abs = iabs32(error)
        
        if error_abs <= self.settings.feedback_gain_threshold:
            fb_abs = error_abs * self.settings.feedback_gain_low // 1000
        else:
            fb_abs = (self.settings.feedback_gain_threshold * self.settings.feedback_gain_low +
                      (error_abs - self.settings.feedback_gain_threshold) * self.settings.feedback_gain_high) // 1000
        
        return iclamp(fb_abs * isign32(error), EVN_OBS_MAX_VOLTAGE_MV)

    def update(self, time_ms: int, angle_mdeg: int, voltage_mv: int):
        """evn_observer_update — exact firmware logic"""
        m = self.model
        s = self.state
        obs_s = self.settings

        fb_voltage = self.feedback_voltage(angle_mdeg)
        
        # Stall detection (mirrors firmware update_stall)
        speed = s.speed_mdegs
        if voltage_mv < 0:
            speed = -speed
            fb_voltage = -fb_voltage
        
        if (speed < obs_s.stall_speed_limit and
            fb_voltage < 0 and
            -fb_voltage * 100 > voltage_mv * obs_s.feedback_voltage_stall_ratio and
            voltage_mv > obs_s.feedback_voltage_negligible):
            if not s.stalled:
                s.stall_start_ms = time_ms
            s.stalled = True
        else:
            s.stalled = False

        # Model input = applied voltage + observer feedback
        model_voltage = iclamp(voltage_mv + fb_voltage, EVN_OBS_MAX_VOLTAGE_MV)

        # Coulomb friction, linearised near zero speed
        coulomb = isign32(s.speed_mdegs) * (
            m.torque_friction if iabs32(s.speed_mdegs) > obs_s.coulomb_friction_speed_cutoff
            else iabs32(s.speed_mdegs) * m.torque_friction // obs_s.coulomb_friction_speed_cutoff
        )
        torque = coulomb  # (+ external load torque, currently none)

        # x(k+1) = A x(k) + B u(k) — discrete Luenberger state update
        angle_next = (s.angle_mdeg +
            EVN_OBS_PRESCALE_SPEED   * s.speed_mdegs // m.d_angle_d_speed +
            EVN_OBS_PRESCALE_CURRENT * s.current     // m.d_angle_d_current +
            EVN_OBS_PRESCALE_VOLTAGE * model_voltage // m.d_angle_d_voltage +
            EVN_OBS_PRESCALE_TORQUE  * torque        // m.d_angle_d_torque)

        speed_next = iclamp(
            EVN_OBS_PRESCALE_SPEED   * s.speed_mdegs // m.d_speed_d_speed +
            EVN_OBS_PRESCALE_CURRENT * s.current     // m.d_speed_d_current +
            EVN_OBS_PRESCALE_VOLTAGE * model_voltage // m.d_speed_d_voltage +
            EVN_OBS_PRESCALE_TORQUE  * torque        // m.d_speed_d_torque,
            EVN_OBS_MAX_SPEED_MDEPS)

        current_next = iclamp(
            EVN_OBS_PRESCALE_SPEED   * s.speed_mdegs // m.d_current_d_speed +
            EVN_OBS_PRESCALE_CURRENT * s.current     // m.d_current_d_current +
            EVN_OBS_PRESCALE_VOLTAGE * model_voltage // m.d_current_d_voltage +
            EVN_OBS_PRESCALE_TORQUE  * torque        // m.d_current_d_torque,
            EVN_OBS_MAX_CURRENT)

        # Undo friction through zero-speed crossing
        if (s.speed_mdegs < 0) != (speed_next < 0):
            speed_next -= EVN_OBS_PRESCALE_TORQUE * coulomb // m.d_speed_d_torque

        s.angle_mdeg = angle_next
        s.speed_mdegs = speed_next
        s.current = current_next

    def get_state(self):
        return self.state.angle_mdeg, self.state.speed_mdegs, self.state.current

    def is_stalled(self, time_ms: int) -> tuple[bool, int]:
        s = self.state
        if s.stalled and (time_ms - s.stall_start_ms) > self.settings.stall_time_ms:
            return True, time_ms - s.stall_start_ms
        return False, 0

    def torque_to_voltage(self, torque_unm: int) -> int:
        """evn_observer_torque_to_voltage"""
        return EVN_OBS_PRESCALE_TORQUE * iclamp(torque_unm, EVN_OBS_MAX_TORQUE_UNM) // self.model.d_voltage_d_torque

    def voltage_to_torque(self, voltage_mv: int) -> int:
        """evn_observer_voltage_to_torque"""
        return EVN_OBS_PRESCALE_VOLTAGE * iclamp(voltage_mv, EVN_OBS_MAX_VOLTAGE_MV) // self.model.d_torque_d_voltage

    def feedforward_torque(self, rate_ref_mdegs: int, accel_ref: int, friction_permille: int = 500) -> int:
        """evn_observer_feedforward_torque_scaled"""
        m = self.model
        friction = (m.torque_friction * friction_permille // 1000) * isign32(rate_ref_mdegs)
        backemf  = EVN_OBS_PRESCALE_SPEED * iclamp(rate_ref_mdegs, EVN_OBS_MAX_SPEED_MDEPS) // m.d_torque_d_speed
        accel    = EVN_OBS_PRESCALE_ACCEL * iclamp(accel_ref, EVN_OBS_MAX_ACCEL) // m.d_torque_d_acceleration
        return iclamp(friction + backemf + accel, EVN_OBS_MAX_TORQUE_UNM)


# ─────────────────────────────────────────────────────────────────────────────
# PID Controller (exact port of firmware evn_pid)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PIDController:
    """evn_pid_t — cascaded position/velocity PID with anti-windup, stiction break, deadzone"""
    # Gains
    kp_pos: float = 8.0e-5
    ki_pos: float = 1.0e-6
    kp_vel: float = 1.0e-6
    endpoint_kp_vel: float = 0.0
    kd_vel: float = 0.0
    kff_accel: float = 0.0

    # Limits
    out_min: float = -1.0
    out_max: float = 1.0
    i_limit: float = 0.20

    # Battery compensation
    vbus_comp: float = 7400.0

    # Speed source
    use_enc_speed: int = 1

    # Deadzone & stiction
    deadzone_mdeg: float = 400.0
    min_duty: float = 0.12
    start_duty: float = 0.12
    startup_release_speed_mdegs: float = 0.0
    startup_ramp_ticks: int = 200
    restart_ramp_ticks: int = 200
    startup_pulse_on_ticks: int = 4
    motion_stuck: bool = False

    # State
    integrator: float = 0.0
    prev_vel_meas: float = 0.0
    first: bool = True
    motion_start_position: float = 0.0
    pos_hist: list = field(default_factory=lambda: [0.0] * PID_SPEED_WINDOW)
    pos_hist_idx: int = 0
    vel_window: int = PID_SPEED_WINDOW
    last_vel_smooth: float = 0.0
    stick_ticks: int = 0

    def reset(self, initial_position: float):
        self.integrator = 0.0
        self.prev_vel_meas = 0.0
        self.first = True
        self.motion_start_position = initial_position
        self.pos_hist_idx = 0
        self.stick_ticks = 0
        self.last_vel_smooth = 0.0
        for i in range(self.vel_window):
            self.pos_hist[i] = initial_position

    def speed_of(self, pos_meas: float, dt: float) -> float:
        """evn_pid_speed_of — windowed speed estimate"""
        W = self.vel_window
        if W < 2: W = 2
        if W > PID_SPEED_WINDOW: W = PID_SPEED_WINDOW
        self.pos_hist[self.pos_hist_idx] = pos_meas
        self.pos_hist_idx = (self.pos_hist_idx + 1) % PID_SPEED_WINDOW
        if dt <= 0.0: return 0.0
        back = (self.pos_hist_idx - W + PID_SPEED_WINDOW) % PID_SPEED_WINDOW
        oldest_pos = self.pos_hist[back]
        return (pos_meas - oldest_pos) / ((W - 1) * dt)

    def update(self, pos_ref: float, vel_ref: float, accel_ref: float,
               pos_meas: float, vel_meas: float, dt: float,
               feedforward_duty: float, vbus_mv: int) -> float:
        """evn_pid_update — exact firmware logic"""
        if dt <= 0.0: return 0.0

        pos_err = pos_ref - pos_meas
        ae = fabs_f(pos_err)
        in_deadzone = self.deadzone_mdeg > 0.0 and ae < self.deadzone_mdeg

        # Velocity D on measured speed (no derivative kick)
        d_vel = 0.0
        if not self.first:
            d_vel = -(vel_meas - self.prev_vel_meas) / dt
        self.prev_vel_meas = vel_meas
        self.first = False

        # Velocity P uses windowed speed
        vel_err_smooth = vel_ref - vel_meas
        if in_deadzone:
            vel_err_smooth = 0.0
        self.last_vel_smooth = vel_meas
        abs_vel_ref = fabs_f(vel_ref)

        kp_vel = self.kp_vel
        if self.endpoint_kp_vel > kp_vel and abs_vel_ref < 5000.0 and ae < 5000.0:
            kp_vel = self.endpoint_kp_vel

        feedback_no_i = (self.kp_pos * pos_err +
                         kp_vel * vel_err_smooth +
                         self.kd_vel * d_vel +
                         self.kff_accel * accel_ref)

        integral_limit = 0.15 * self.i_limit if in_deadzone else self.i_limit
        integral_delta = self.ki_pos * pos_err * dt
        candidate_integral = self.integrator + integral_delta
        if candidate_integral > integral_limit: candidate_integral = integral_limit
        if candidate_integral < -integral_limit: candidate_integral = -integral_limit

        # Battery voltage compensation
        voltage_scale = 1.0
        if self.vbus_comp > 0.0 and vbus_mv > 0:
            voltage_scale = self.vbus_comp / float(vbus_mv)

        candidate_duty = (feedback_no_i + candidate_integral) * voltage_scale + feedforward_duty
        winds_up_high = candidate_duty > self.out_max and integral_delta > 0.0
        winds_up_low  = candidate_duty < self.out_min and integral_delta < 0.0
        if not winds_up_high and not winds_up_low:
            self.integrator = candidate_integral

        duty = (feedback_no_i + self.integrator) * voltage_scale + feedforward_duty

        # Stiction break (matching firmware update)
        abs_speed = fabs_f(vel_meas)
        displacement = pos_meas - self.motion_start_position
        if displacement < 0.0: displacement = -displacement
        initial_starting = (abs_vel_ref > 1000.0 and
                           (displacement < 100.0 or
                            (self.startup_release_speed_mdegs > 0.0 and
                             displacement < 5000.0 and
                             abs_speed < self.startup_release_speed_mdegs)))
        pos_err_starting = (ae > self.deadzone_mdeg and
                           abs_vel_ref < 1000.0 and
                           abs_speed < 1000.0 and
                           displacement < 100.0)
        restarting = abs_vel_ref > 1000.0 and self.motion_stuck
        starting = initial_starting or pos_err_starting or restarting
        approaching = ae > self.deadzone_mdeg and abs_vel_ref < 1000.0 and abs_speed < 1000.0

        if starting or approaching:
            self.stick_ticks += 1
        else:
            self.stick_ticks = 0

        threshold = 5 if starting else 30
        if self.stick_ticks >= threshold:
            ramp_ticks = self.stick_ticks - threshold + 1
            ramp_duration = (self.startup_ramp_ticks if initial_starting
                           else (self.restart_ramp_ticks if restarting else 100))
            ramp = ramp_ticks / float(ramp_duration)
            if ramp > 1.0: ramp = 1.0
            floor_d = (self.start_duty if starting else self.min_duty) * ramp
            abs_duty = fabs_f(duty)
            direction = vel_ref if starting else pos_err
            apply_floor = True
            if initial_starting and self.startup_pulse_on_ticks < 4:
                apply_floor = ((ramp_ticks - 1) & 3) < self.startup_pulse_on_ticks
            if apply_floor and floor_d > 0.0 and abs_duty < floor_d:
                duty = -floor_d if direction < 0.0 else floor_d

        # Output saturation
        if duty > self.out_max: duty = self.out_max
        if duty < self.out_min: duty = self.out_min
        return duty


# ─────────────────────────────────────────────────────────────────────────────
# Trajectory Profiler (exact port of firmware evn_trajectory)
# ─────────────────────────────────────────────────────────────────────────────

class TrajectoryType:
    TRAPEZOID = 0
    MINIMUM_JERK = 1


@dataclass
class Trajectory:
    """evn_trajectory_t"""
    max_vel: float = 0.0
    max_accel: float = 0.0
    start_pos: float = 0.0
    target_pos: float = 0.0
    accel_time: float = 0.0
    coast_time: float = 0.0
    total_time: float = 0.0
    peak_vel: float = 0.0
    dir: float = 1.0
    t: float = 0.0
    type: int = TrajectoryType.TRAPEZOID
    active: bool = False
    done: bool = True

    def start(self, start: float, target: float, max_vel: float, max_accel: float,
              traj_type: int = TrajectoryType.TRAPEZOID):
        self.max_vel = max_vel
        self.max_accel = max_accel
        self.start_pos = start
        self.target_pos = target
        self.type = traj_type

        dist = target - start
        self.dir = 1.0 if dist >= 0.0 else -1.0
        d = fabs_f(dist)

        if d < 1e-6 or max_vel <= 0.0 or max_accel <= 0.0:
            self.active = False
            self.done = True
            self.t = 0.0
            self.accel_time = self.coast_time = self.total_time = 0.0
            self.peak_vel = 0.0
            return

        if traj_type == TrajectoryType.MINIMUM_JERK:
            velocity_time = 1.875 * d / max_vel
            accel_time = math.sqrt(5.773502692 * d / max_accel)
            self.total_time = velocity_time if velocity_time > accel_time else accel_time
            self.accel_time = 0.5 * self.total_time
            self.coast_time = self.accel_time
            self.peak_vel = 1.875 * d / self.total_time
            self.t = 0.0
            self.active = True
            self.done = False
            return

        # Trapezoidal
        t_acc = max_vel / max_accel
        d_acc = max_accel * t_acc * t_acc

        if d >= d_acc:
            d_coast = d - d_acc
            self.accel_time = t_acc
            self.coast_time = t_acc + d_coast / max_vel
            self.total_time = self.coast_time + t_acc
            self.peak_vel = max_vel
        else:
            t_pk = math.sqrt(d / max_accel)
            self.accel_time = t_pk
            self.coast_time = t_pk
            self.total_time = 2.0 * t_pk
            self.peak_vel = max_accel * t_pk

        self.t = 0.0
        self.active = True
        self.done = False

    def advance_to_position(self, position: float):
        """evn_trajectory_advance_to_position — startup reference governor"""
        if not self.active or self.type != TrajectoryType.TRAPEZOID or \
           self.max_accel <= 0.0 or self.peak_vel <= 0.0:
            return
        distance = (self.target_pos - self.start_pos) * self.dir
        progress = (position - self.start_pos) * self.dir
        if progress <= 0.0 or progress >= distance: return

        accel_distance = 0.5 * self.max_accel * self.accel_time * self.accel_time
        coast_end_distance = accel_distance + self.peak_vel * (self.coast_time - self.accel_time)
        
        if progress < accel_distance:
            candidate_time = math.sqrt(2.0 * progress / self.max_accel)
        elif progress < coast_end_distance:
            candidate_time = self.accel_time + (progress - accel_distance) / self.peak_vel
        else:
            remaining = distance - progress
            candidate_time = self.total_time - math.sqrt(2.0 * remaining / self.max_accel)
        
        if candidate_time > self.t:
            self.t = candidate_time

    def update(self, dt: float) -> tuple[float, float, float]:
        """evn_trajectory_update — returns (pos_ref, vel_ref, accel_ref)"""
        if not self.active:
            return self.target_pos, 0.0, 0.0

        t = self.t
        a = self.max_accel * self.dir
        v_pk = self.peak_vel * self.dir
        d = self.target_pos - self.start_pos

        if self.type == TrajectoryType.MINIMUM_JERK and t < self.total_time:
            u = t / self.total_time
            u2 = u * u
            u3 = u2 * u
            u4 = u3 * u
            u5 = u4 * u
            inv_time = 1.0 / self.total_time
            p = self.start_pos + d * (10.0 * u3 - 15.0 * u4 + 6.0 * u5)
            v = d * inv_time * (30.0 * u2 - 60.0 * u3 + 30.0 * u4)
            acc = d * inv_time * inv_time * (60.0 * u - 180.0 * u2 + 120.0 * u3)
        elif self.type == TrajectoryType.MINIMUM_JERK:
            acc = 0.0; v = 0.0; p = self.target_pos
            self.active = False; self.done = True
        elif t < self.accel_time:
            acc = a
            v = a * t
            p = self.start_pos + 0.5 * a * t * t
        elif t < self.coast_time:
            acc = 0.0
            v = v_pk
            t1 = self.accel_time
            p = self.start_pos + 0.5 * a * t1 * t1 + v_pk * (t - t1)
        elif t < self.total_time:
            td = t - self.coast_time
            acc = -a
            v = v_pk - a * td
            t1 = self.accel_time
            p_coast_start = self.start_pos + 0.5 * a * t1 * t1 + v_pk * (self.coast_time - t1)
            p = p_coast_start + v_pk * td - 0.5 * a * td * td
        else:
            acc = 0.0; v = 0.0; p = self.target_pos
            self.active = False; self.done = True

        # Clamp position to not overshoot target
        if (self.dir > 0.0 and p > self.target_pos) or (self.dir < 0.0 and p < self.target_pos):
            p = self.target_pos

        self.t += dt
        return p, v, acc


# ─────────────────────────────────────────────────────────────────────────────
# Encoder & Motor Plant Model
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class EncoderModel:
    """Simulates encoder quantization and speed measurement"""
    cpr: int = 2880
    counts_per_rev: float = 720.0
    position_substep: int = 0
    position_edge: int = 0
    last_transition_us: int = 0
    
    @property
    def substeps_per_rev(self) -> float:
        return (self.counts_per_rev / 4.0) * 256.0
    
    @property
    def mdeg_per_substep(self) -> float:
        return 360000.0 / self.substeps_per_rev
    
    @property
    def mdeg_per_edge(self) -> float:
        return 360000.0 / self.counts_per_rev

    def update(self, true_angle_mdeg: float, dt_s: float, time_us: int):
        """Update encoder state from true motor angle"""
        # Convert true angle to substeps (quantized)
        substeps = int(round(true_angle_mdeg / self.mdeg_per_substep))
        self.position_substep = substeps
        
        # Edge count for speed measurement
        edges = int(round(true_angle_mdeg / self.mdeg_per_edge))
        self.position_edge = edges
        
        # Simulate edge timing (for edge watchdog)
        # This is simplified - just track when we'd get edges
        if dt_s > 0 and abs(true_angle_mdeg) > 0:
            # Approximate: edges per second = speed / mdeg_per_edge
            pass  # Not fully implemented for now

    def get_position_substep(self) -> int:
        return self.position_substep

    def get_speed_substep(self) -> float:
        """Simulated edge-timed speed (substeps/s) - simplified"""
        return 0.0  # Not used when use_enc_speed != 2,3

    def get_transition_age_us(self) -> int:
        """Time since last encoder edge"""
        return 0  # Not implemented for now


@dataclass
class PlantModel:
    """Discrete-time plant model matching observer state-space (no feedback)
    
    Uses the exact same A/B matrices as the observer for perfect consistency.
    Enhanced with Stribeck friction, cogging torque, and gearbox compliance.
    State: [angle_mdeg, speed_mdeg/s, current_0.1mA]
    Input: [voltage_mv, torque_unm]
    """
    # State (matching observer)
    angle_mdeg: int = 0
    speed_mdegs: int = 0
    current: int = 0
    
    # Model coefficients (from motor_model)
    d_angle_d_speed: int = 88290
    d_speed_d_speed: int = 921
    d_current_d_speed: int = -61626
    d_angle_d_current: int = 5755278
    d_speed_d_current: int = 44574
    d_current_d_current: int = 21338185
    d_angle_d_voltage: int = 5240040
    d_speed_d_voltage: int = 21582
    d_current_d_voltage: int = 106130
    d_angle_d_torque: int = -1887437
    d_speed_d_torque: int = -9555
    d_current_d_torque: int = 861143
    torque_friction: int = 16476      # Coulomb friction level (high speed)
    
    # Stribeck friction parameters
    static_friction: int = 0          # Static friction (stiction) at zero speed
    stribeck_vel_mdegs: int = 50000   # Stribeck transition velocity (mdeg/s)
    viscous_friction: int = 0         # Viscous friction coefficient
    
    # Cogging torque parameters
    cogging_amplitude: int = 0        # Cogging torque amplitude (unm)
    cogging_period_mdeg: int = 45000  # Cogging period (mdeg) = 45 deg = 360/8 for 8-pole
    
    # Gearbox compliance parameters
    gearbox_stiffness: int = 0        # Gearbox torsional stiffness (unm/deg)
    gearbox_backlash_mdeg: int = 0    # Gearbox backlash (mdeg)
    motor_inertia_ratio: float = 1.0  # Ratio of motor inertia to load inertia
    
    # Gearbox state
    gearbox_twist_mdeg: int = 0       # Torsional twist between motor and load
    load_speed_mdegs: int = 0         # Load side speed

    # Plant voltage lag (first-order low-pass on applied voltage, models the
    # physical motor's electrical + electromechanical delay that the 5 ms
    # observer matrices don't capture when the plant is stepped at 1 ms)
    voltage_lag_ms: float = 0.0       # Time constant (ms); 0 = no lag
    voltage_filtered_mv: float = 0.0  # Filtered voltage state

    # Plant transport delay (pure delay on applied voltage, models the
    # physical PWM->current->torque->motion pipeline delay)
    voltage_delay_ms: int = 0         # Delay (ms); 0 = no delay
    voltage_delay_buf: list = None    # Ring buffer for delayed voltage
    voltage_delay_idx: int = 0        # Ring buffer write index

    # Observer prescales
    EVN_OBS_PRESCALE_SPEED: int = 858
    EVN_OBS_PRESCALE_ACCEL: int = 85
    EVN_OBS_PRESCALE_CURRENT: int = 71582
    EVN_OBS_PRESCALE_VOLTAGE: int = 178956
    EVN_OBS_PRESCALE_TORQUE: int = 2147
    EVN_OBS_MAX_SPEED_MDEPS: int = 2500000
    EVN_OBS_MAX_CURRENT: int = 30000
    EVN_OBS_MAX_VOLTAGE_MV: int = 12000
    EVN_OBS_MAX_TORQUE_UNM: int = 1000000
    
    def __init__(self, motor_model=None):
        if motor_model:
            self.d_angle_d_speed = motor_model.d_angle_d_speed
            self.d_speed_d_speed = motor_model.d_speed_d_speed
            self.d_current_d_speed = motor_model.d_current_d_speed
            self.d_angle_d_current = motor_model.d_angle_d_current
            self.d_speed_d_current = motor_model.d_speed_d_current
            self.d_current_d_current = motor_model.d_current_d_current
            self.d_angle_d_voltage = motor_model.d_angle_d_voltage
            self.d_speed_d_voltage = motor_model.d_speed_d_voltage
            self.d_current_d_voltage = motor_model.d_current_d_voltage
            self.d_angle_d_torque = motor_model.d_angle_d_torque
            self.d_speed_d_torque = motor_model.d_speed_d_torque
            self.d_current_d_torque = motor_model.d_current_d_torque
            self.torque_friction = motor_model.torque_friction
            
            # Stribeck parameters (with defaults if not in model)
            self.static_friction = motor_model.get_static_friction()
            self.stribeck_vel_mdegs = motor_model.get_stribeck_vel()
            self.viscous_friction = motor_model.get_viscous_friction()
            
            # Cogging defaults based on motor type
            if motor_model.counts_per_rev == 720:  # EV3 Large / NXT (8-pole?)
                self.cogging_period_mdeg = 45000  # 45 deg per cog
                self.cogging_amplitude = motor_model.torque_friction // 10  # ~10% of Coulomb
            elif motor_model.counts_per_rev == 360:  # EV3 Medium (different pole count?)
                self.cogging_period_mdeg = 90000  # 90 deg per cog
                self.cogging_amplitude = motor_model.torque_friction // 10
            
            # Gearbox defaults (DISABLED by default - enable explicitly for compliance studies)
            # The observer model assumes rigid body; adding compliance requires careful tuning
            self.gearbox_backlash_mdeg = 0     # 5 deg backlash typical for EV3 (set >0 to enable)
            self.gearbox_stiffness = 0         # Gearbox torsional stiffness (unm/deg) (set >0 to enable)
            self.motor_inertia_ratio = 1.0     # Load inertia / motor inertia (set >1 for compliance)
            
            # Thermal model parameters (DISABLED by default - enable explicitly for thermal studies)
            # Copper resistance: R = R0 * (1 + alpha_cu * (T - T0))
            # alpha_cu = 0.00393 /°C for copper
            self.temp_ambient: float = 25.0           # Ambient temperature (°C)
            self.temp_initial: float = 25.0           # Initial temperature (°C)
            self.alpha_cu: float = 0.00393            # Copper temp coefficient (/°C)
            self.r_phase_ohm_25c: float = 1.0         # Phase resistance at 25°C (ohm)
            self.magnet_temp_coeff: float = -0.0012   # Magnet flux temp coefficient (/°C) ~ -0.12%/°C
            
            # Lumped thermal network (Cauer/R-C ladder)
            # Winding -> Core -> Case -> Ambient
            self.c_th_winding: float = 10.0           # Winding thermal capacitance (J/°C)
            self.c_th_core: float = 50.0              # Core thermal capacitance (J/°C)
            self.c_th_case: float = 200.0             # Case thermal capacitance (J/°C)
            self.r_th_wc: float = 0.5                 # Winding-to-core thermal resistance (°C/W)
            self.r_th_cc: float = 1.0                 # Core-to-case thermal resistance (°C/W)
            self.r_th_ca: float = 2.0                 # Case-to-ambient thermal resistance (°C/W)
            
            # Thermal states
            self.temp_winding: float = 25.0           # Winding temperature (°C)
            self.temp_core: float = 25.0              # Core temperature (°C)
            self.temp_case: float = 25.0              # Case temperature (°C)
            
            # Thermal update rate (every N ms, since thermal time constants are long)
            self.thermal_update_divider: int = 1000   # Update thermal every 1000ms (1s)
            self.thermal_counter: int = 0

    @staticmethod
    def iclamp(x: int, limit: int) -> int:
        if x > limit: return limit
        if x < -limit: return -limit
        return x

    @staticmethod
    def isign32(x: int) -> int:
        return (x > 0) - (x < 0)

    @staticmethod
    def iabs32(x: int) -> int:
        return x if x >= 0 else -x

    def _compute_stribeck_friction(self, speed_mdegs: int) -> int:
        """Compute Stribeck friction torque.
        
        Model: T = sign(ω) * [T_c + (T_s - T_c) * exp(-(ω/ω_st)^2)] + B*ω
        
        Where:
        - T_s = static_friction (stiction)
        - T_c = torque_friction (Coulomb)
        - ω_st = stribeck_vel_mdegs
        - B = viscous_friction
        """
        if speed_mdegs == 0:
            return 0
        
        sign = 1 if speed_mdegs > 0 else -1
        abs_speed = abs(speed_mdegs)
        
        T_c = self.torque_friction
        T_s = self.static_friction
        omega_st = self.stribeck_vel_mdegs
        B = self.viscous_friction
        
        if omega_st <= 0:
            # Fallback to linear transition if no Stribeck velocity set
            if abs_speed > 20000:
                coulomb = sign * T_c
            else:
                coulomb = sign * (abs_speed * T_c // 20000)
            return coulomb + (B * speed_mdegs // 1000)  # B is per mdeg/s, scale
        
        # Stribeck curve: exponential transition from static to Coulomb
        ratio = abs_speed / omega_st
        # exp(-ratio^2) - use integer approximation
        # For small ratio, exp(-ratio^2) ≈ 1 - ratio^2
        # For large ratio, exp(-ratio^2) ≈ 0
        if ratio >= 3:
            stribeck_factor = 0
        else:
            # Approximate exp(-x^2) using polynomial
            r2 = ratio * ratio
            stribeck_factor = max(0, 10000 - int(r2 * 10000)) / 10000.0
        
        # T = T_c + (T_s - T_c) * exp(-(ω/ω_st)^2)
        friction_magnitude = T_c + int((T_s - T_c) * stribeck_factor)
        
        # Add viscous component
        viscous = B * abs_speed // 1000  # B in unm per mdeg/s
        
        return sign * (friction_magnitude + viscous)

    def _compute_cogging_torque(self, angle_mdeg: int) -> int:
        """Compute cogging torque (position-dependent disturbance).
        
        Model: T_cog = A * sin(2π * θ / period)
        
        Uses math.sin() for accurate sine (Python simulator, not firmware).
        """
        if self.cogging_amplitude == 0 or self.cogging_period_mdeg == 0:
            return 0
        
        # Normalize angle to [0, period)
        period = self.cogging_period_mdeg
        norm_angle = angle_mdeg % period
        if norm_angle < 0:
            norm_angle += period
        
        # Proper sine using math.sin
        # sin(2π * angle / period)
        angle_rad = 2.0 * math.pi * norm_angle / period
        sine_val = math.sin(angle_rad)
        
        # Scale by amplitude
        return int(self.cogging_amplitude * sine_val)

    def _update_gearbox(self, motor_torque_unm: int, load_torque_unm: int = 0) -> int:
        """Stable dead-zone backlash model (replaces the unstable two-inertia model).

        Physics: the encoder sits on the MOTOR shaft. With gear-train slack, the
        motor shaft can move within the backlash band WITHOUT the load (and its
        disturbance/load torque) following. Only when the twist exceeds the band
        does the load engage and its torque react back on the motor.

        - twist = motor_angle - load_angle (mdeg), integrated from speed difference
        - |twist| <= backlash/2  -> dead zone: no spring torque, load torque decoupled
        - |twist| >  backlash/2  -> engaged: spring torque (stiffness) + load torque

        This is unconditionally stable (no free-running load-inertia integration,
        which was the source of the runaway in the old two-inertia model) and
        reproduces the sustained endpoint limit cycle seen on the physical EV3
        Large: the controller overshoots into the dead zone, the load doesn't
        follow, the error sign flips, and the motor bangs back and forth.

        Returns the torque acting on the MOTOR side (spring + engaged load).
        """
        if self.gearbox_stiffness == 0 and self.gearbox_backlash_mdeg == 0:
            return 0  # rigid gearbox

        backlash_half = self.gearbox_backlash_mdeg // 2

        # Integrate twist from the motor/load speed difference (1 ms step).
        # Load speed: in the dead zone the load coasts (decays toward 0); when
        # engaged it tracks the motor. This avoids the unstable separate
        # load-inertia integration of the old model.
        if abs(self.gearbox_twist_mdeg) <= backlash_half:
            # Dead zone: load not driven, its speed decays (friction at rest)
            self.load_speed_mdegs = (self.load_speed_mdegs * 7) // 8
        else:
            # Engaged: load tracks the motor shaft
            self.load_speed_mdegs = self.speed_mdegs

        speed_diff = self.speed_mdegs - self.load_speed_mdegs  # mdeg/s
        self.gearbox_twist_mdeg += speed_diff // 1000          # 1 ms step

        # Spring/load torque on the motor side
        if abs(self.gearbox_twist_mdeg) <= backlash_half:
            return 0  # dead zone: motor feels no load

        effective_twist = self.gearbox_twist_mdeg
        if effective_twist > 0:
            effective_twist -= backlash_half
        else:
            effective_twist += backlash_half
        # Spring torque opposes the twist; stiffness in unm/deg, twist in mdeg
        spring_torque = -(self.gearbox_stiffness * effective_twist // 1000)
        # When engaged, the external load torque also reacts on the motor
        return spring_torque + load_torque_unm

    def _update_thermal(self, current_01ma: int, speed_mdegs: int, voltage_mv: int):
        """Update lumped thermal network (winding -> core -> case -> ambient).
        
        Called at slower rate (thermal_update_divider ms) since thermal time constants
        are much longer than electrical/mechanical time constants.
        
        Heat sources:
        - Copper losses: I²R (current_01ma is in 0.1mA units)
        - Core losses: hysteresis + eddy current (speed-dependent)
        """
        if self.thermal_update_divider <= 0:
            return
            
        self.thermal_counter += 1
        if self.thermal_counter < self.thermal_update_divider:
            return
        self.thermal_counter = 0
        
        dt_s = self.thermal_update_divider / 1000.0  # seconds
        
        # Current in Amps (current_01ma is 0.1mA units)
        current_a = abs(current_01ma) / 10000.0
        
        # Copper resistance at current winding temperature
        # R = R0 * (1 + alpha * (T - T0))
        r_phase = self.r_phase_ohm_25c * (1.0 + self.alpha_cu * (self.temp_winding - 25.0))
        
        # Copper losses (3-phase): P_cu = 3 * I_rms² * R
        # Assuming current_a is peak, I_rms = I_peak / sqrt(2) for sinusoidal
        # But motor current is more complex. Use P_cu = 1.5 * I² * R for 3-phase (conservative)
        p_cu = 1.5 * current_a * current_a * r_phase  # Watts
        
        # Core losses (simplified): P_core = k_h * f * B^2 + k_e * f^2 * B^2
        # Speed in electrical rad/s: omega_e = speed_mdegs * pi/180000 * pole_pairs
        # Pole pairs: assume 4 for EV3 (8 poles)
        pole_pairs = 4
        omega_e = abs(speed_mdegs) * math.pi / 180000.0 * pole_pairs
        # Flux linkage proportional to magnet flux (decreases with temperature)
        # Simplified: P_core = k_h * omega_e + k_e * omega_e^2
        # These coefficients would need to be identified per motor
        k_h = 0.001  # Hysteresis loss coefficient
        k_e = 0.00001  # Eddy current loss coefficient
        p_core = k_h * omega_e + k_e * omega_e * omega_e
        
        # Scale core losses to be reasonable (few watts max)
        p_core = min(p_core, 5.0)
        
        # Total heat generated in winding and core
        p_winding = p_cu + 0.3 * p_core  # 30% of core losses in winding
        p_core_total = 0.7 * p_core      # 70% of core losses in core
        
        # Thermal network: Winding -> Core -> Case -> Ambient
        # Using forward Euler integration
        
        # Heat flow from winding to core
        q_wc = (self.temp_winding - self.temp_core) / self.r_th_wc
        
        # Heat flow from core to case
        q_cc = (self.temp_core - self.temp_case) / self.r_th_cc
        
        # Heat flow from case to ambient
        q_ca = (self.temp_case - self.temp_ambient) / self.r_th_ca
        
        # Temperature derivatives
        dT_winding = (p_winding - q_wc) / self.c_th_winding
        dT_core = (p_core_total + q_wc - q_cc) / self.c_th_core
        dT_case = (q_cc - q_ca) / self.c_th_case
        
        # Update temperatures
        self.temp_winding += dT_winding * dt_s
        self.temp_core += dT_core * dt_s
        self.temp_case += dT_case * dt_s

    def set_mechanical_tau_ms(self, tau_ms: float):
        """Set the plant's mechanical time constant while preserving steady-state gain.

        The plant is stepped at 1 ms but uses the observer's 5 ms discrete matrices,
        which makes the effective mechanical time constant ~5x too fast. This method
        adjusts d_speed_d_speed and d_speed_d_voltage to match the physical motor's
        true mechanical time constant.

        For the first-order speed dynamics:
            speed_next = a * speed + b * V
            a = PRESCALE_SPEED / d_speed_d_speed
            b = PRESCALE_VOLTAGE / d_speed_d_voltage
            tau = -dt / ln(a)  (dt = 1 ms step)
            K_ss = b / (1 - a)  (steady-state gain, preserved)
        """
        import math
        dt = 1.0  # plant step is 1 ms
        a_old = self.EVN_OBS_PRESCALE_SPEED / self.d_speed_d_speed
        b_old = self.EVN_OBS_PRESCALE_VOLTAGE / self.d_speed_d_voltage
        K_ss = b_old / (1.0 - a_old)

        a_new = math.exp(-dt / tau_ms)
        b_new = K_ss * (1.0 - a_new)

        self.d_speed_d_speed = int(round(self.EVN_OBS_PRESCALE_SPEED / a_new))
        self.d_speed_d_voltage = int(round(self.EVN_OBS_PRESCALE_VOLTAGE / b_new))

    def get_phase_resistance(self) -> float:
        """Get phase resistance at current winding temperature (ohm)."""
        return self.r_phase_ohm_25c * (1.0 + self.alpha_cu * (self.temp_winding - 25.0))

    def get_magnet_flux_factor(self) -> float:
        """Get magnet flux factor at current core temperature (1.0 at 25°C)."""
        return 1.0 + self.magnet_temp_coeff * (self.temp_core - 25.0)

    def step(self, voltage_mv: int, load_torque_unm: int = 0):
        """Discrete-time step matching observer (no feedback correction)"""

        # Apply transport delay (pure delay on voltage)
        if self.voltage_delay_ms > 0:
            if self.voltage_delay_buf is None:
                self.voltage_delay_buf = [0] * self.voltage_delay_ms
            self.voltage_delay_buf[self.voltage_delay_idx] = voltage_mv
            self.voltage_delay_idx = (self.voltage_delay_idx + 1) % self.voltage_delay_ms
            voltage_mv = self.voltage_delay_buf[self.voltage_delay_idx]

        # Apply first-order voltage lag (models electrical/electromechanical delay)
        if self.voltage_lag_ms > 0.0:
            alpha = 1.0 - math.exp(-1.0 / self.voltage_lag_ms)  # 1 ms step
            self.voltage_filtered_mv += alpha * (voltage_mv - self.voltage_filtered_mv)
            voltage_mv = int(round(self.voltage_filtered_mv))

        # Compute Stribeck friction (motor side)
        friction = self._compute_stribeck_friction(self.speed_mdegs)
        
        # Compute cogging torque
        cogging = self._compute_cogging_torque(self.angle_mdeg)
        
        # Compute gearbox spring torque
        spring_torque = self._update_gearbox(0, load_torque_unm)  # spring torque on motor side
        
        # Total disturbance torque on motor side
        # Includes friction, cogging, spring, and external load
        # The load_torque_unm is applied to the load side, so it affects motor via spring
        motor_disturbance = self.iclamp(friction + cogging + spring_torque, self.EVN_OBS_MAX_TORQUE_UNM)
        
        # Clamp voltage
        voltage_mv = self.iclamp(voltage_mv, self.EVN_OBS_MAX_VOLTAGE_MV)
        
        # x(k+1) = A x(k) + B u(k) — exact observer update without feedback
        # Use motor_disturbance (friction + cogging + spring) as torque input
        angle_next = (self.angle_mdeg +
            self.EVN_OBS_PRESCALE_SPEED   * self.speed_mdegs // self.d_angle_d_speed +
            self.EVN_OBS_PRESCALE_CURRENT * self.current     // self.d_angle_d_current +
            self.EVN_OBS_PRESCALE_VOLTAGE * voltage_mv       // self.d_angle_d_voltage +
            self.EVN_OBS_PRESCALE_TORQUE  * motor_disturbance // self.d_angle_d_torque)

        speed_next = self.iclamp(
            self.EVN_OBS_PRESCALE_SPEED   * self.speed_mdegs // self.d_speed_d_speed +
            self.EVN_OBS_PRESCALE_CURRENT * self.current     // self.d_speed_d_current +
            self.EVN_OBS_PRESCALE_VOLTAGE * voltage_mv       // self.d_speed_d_voltage +
            self.EVN_OBS_PRESCALE_TORQUE  * motor_disturbance // self.d_speed_d_torque,
            self.EVN_OBS_MAX_SPEED_MDEPS)

        current_next = self.iclamp(
            self.EVN_OBS_PRESCALE_SPEED   * self.speed_mdegs // self.d_current_d_speed +
            self.EVN_OBS_PRESCALE_CURRENT * self.current     // self.d_current_d_current +
            self.EVN_OBS_PRESCALE_VOLTAGE * voltage_mv       // self.d_current_d_voltage +
            self.EVN_OBS_PRESCALE_TORQUE  * motor_disturbance // self.d_current_d_torque,
            self.EVN_OBS_MAX_CURRENT)

        # Undo friction through zero-speed crossing (same as observer)
        # Use the friction value computed for this step
        if (self.speed_mdegs < 0) != (speed_next < 0):
            speed_next -= self.EVN_OBS_PRESCALE_TORQUE * friction // self.d_speed_d_torque

        self.angle_mdeg = angle_next
        self.speed_mdegs = speed_next
        self.current = current_next
        
        # Update thermal model (runs at slower rate internally)
        self._update_thermal(self.current, self.speed_mdegs, voltage_mv)
        
        return self.angle_mdeg, self.speed_mdegs, self.current


# Keep MotorPlant for backward compatibility (deprecated)
@dataclass
class MotorPlant:
    """Simple first-order motor plant model (deprecated - use PlantModel)"""
    # Motor parameters (approximate)
    Kv: float = 1.0          # Speed constant (rad/s/V) - will scale
    R: float = 1.0           # Resistance (ohm)
    J: float = 0.001         # Inertia (kg·m²)
    B: float = 0.001         # Viscous friction
    tau_mech: float = 0.01   # Mechanical time constant
    
    # State
    angle_rad: float = 0.0
    speed_rad_s: float = 0.0
    
    def __post_init__(self):
        self.tau_mech = self.J / self.B if self.B > 0 else 0.01

    def step(self, voltage: float, dt: float, load_torque: float = 0.0):
        """First-order electrical + mechanical model"""
        # Electrical: V = I*R + Kv*ω  →  I = (V - Kv*ω)/R
        # Torque = Kt * I  (Kt ≈ Kv in SI)
        current = (voltage - self.Kv * self.speed_rad_s) / self.R if self.R > 0 else 0
        torque = current  # Kt = Kv ≈ 1
        
        # Mechanical: J*α = torque - B*ω - load_torque
        accel = (torque - self.B * self.speed_rad_s - load_torque) / self.J if self.J > 0 else 0
        
        self.speed_rad_s += accel * dt
        self.angle_rad += self.speed_rad_s * dt
        
        return self.angle_rad, self.speed_rad_s, current


# ─────────────────────────────────────────────────────────────────────────────
# Main Simulation Loop
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TraceRow:
    """evn_trace_row_t — matches firmware exactly"""
    t_ms: int = 0
    ref_mdeg: int = 0
    enc_mdeg: int = 0
    hat_mdeg: int = 0
    vref_mdegs: int = 0
    what_mdegs: int = 0
    duty_milli: int = 0
    cur_01ma: int = 0


class Simulator:
    def __init__(self, motor_name: str, models_json_path: str = "tools/motor_models.json"):
        with open(models_json_path) as f:
            data = json.load(f)
        
        m = data[motor_name]
        self.motor_model = MotorModel(
            d_angle_d_speed=m["d_angle_d_speed"],
            d_speed_d_speed=m["d_speed_d_speed"],
            d_current_d_speed=m["d_current_d_speed"],
            d_angle_d_current=m["d_angle_d_current"],
            d_speed_d_current=m["d_speed_d_current"],
            d_current_d_current=m["d_current_d_current"],
            d_angle_d_voltage=m["d_angle_d_voltage"],
            d_speed_d_voltage=m["d_speed_d_voltage"],
            d_current_d_voltage=m["d_current_d_voltage"],
            d_angle_d_torque=m["d_angle_d_torque"],
            d_speed_d_torque=m["d_speed_d_torque"],
            d_current_d_torque=m["d_current_d_torque"],
            d_voltage_d_torque=m["d_voltage_d_torque"],
            d_torque_d_voltage=m["d_torque_d_voltage"],
            d_torque_d_speed=m["d_torque_d_speed"],
            d_torque_d_acceleration=m["d_torque_d_acceleration"],
            torque_friction=m["torque_friction"],
            cpr=m.get("cpr", 2880),
            counts_per_rev=m.get("counts_per_rev", 720.0),
            rated_max_speed_deg_s=m.get("rated_max_speed_deg_s", 800)
        )
        
        self.obs_settings = ObserverSettings(**data["default_observer_settings"])
        self.observer_constants = data["observer_constants"]
        self.trace_constants = data["trace_constants"]
        
        # Motor plant (uses observer's discrete state-space for perfect consistency)
        self.plant = PlantModel(self.motor_model)
        # Apply per-motor plant calibration (from motor_models.json)
        # These correct for the fact that the plant is stepped at 1 ms but uses
        # the observer's 5 ms discrete matrices, making it ~5x too fast.
        if "plant_tau_ms" in m:
            self.plant.set_mechanical_tau_ms(m["plant_tau_ms"])
        if "plant_lag_ms" in m:
            self.plant.voltage_lag_ms = m["plant_lag_ms"]
        if "plant_friction_scale" in m:
            fs = m["plant_friction_scale"]
            self.plant.torque_friction = int(self.plant.torque_friction * fs)
            self.plant.static_friction = int(self.plant.static_friction * fs)
            self.plant.viscous_friction = int(self.plant.viscous_friction * fs)
        self.encoder = EncoderModel(
            cpr=self.motor_model.cpr,
            counts_per_rev=self.motor_model.counts_per_rev
        )
        
        # Controller components
        self.observer = Observer(self.motor_model, self.obs_settings)
        self.pid = PIDController()
        self.trajectory = Trajectory()
        
        # Trace
        self.trace: list[TraceRow] = []
        self.trace_armed = False
        self.trace_divider = 0
        self.time_ms = 0
        
        # Battery
        self.vbus_mv = 7400
        self.vbus_profile = None  # Optional: list of (time_ms, voltage_mv)
        
        # Feedforward
        self.ff_on = True
        self.friction_feedforward_permille = 500
        
        # Startup reference governor
        self.startup_reference_governor = True
        
        # Auto coast
        self.auto_coast_deadline_ms = 0
        self.holding = False
        
        # For PID speed measurement
        self.use_enc_speed = 1  # 0=observer, 1=windowed, 2=raw edge, 3=filtered edge

        # Velocity measurement noise (for Domain Randomization)
        self.vel_noise_std = 0.0  # Standard deviation of Gaussian noise (mdeg/s)

        # Disturbance Observer (DOB) matching firmware Core 1
        self.dob_enabled = True
        self.dob_gain = 0.40
        self.dob_dist_voltage_mv = 0.0

        # External load torque applied to the load side (unm); set via --load-torque
        self.load_torque_unm = 0

    def set_gains(self, kp_pos, ki_pos, kp_vel, kd_vel=0.0, kff_accel=0.0,
                  endpoint_kp_vel=0.0, vbus_comp=7400.0, i_limit=0.20,
                  deadzone_mdeg=400.0, min_duty=0.12, start_duty=0.12,
                  startup_release_speed_mdegs=0.0, startup_ramp_ticks=200,
                  restart_ramp_ticks=200, startup_pulse_on_ticks=4,
                  vel_window=40):
        self.pid.kp_pos = kp_pos
        self.pid.ki_pos = ki_pos
        self.pid.kp_vel = kp_vel
        self.pid.kd_vel = kd_vel
        self.pid.kff_accel = kff_accel
        self.pid.endpoint_kp_vel = endpoint_kp_vel
        self.pid.vbus_comp = vbus_comp
        self.pid.i_limit = i_limit
        self.pid.deadzone_mdeg = deadzone_mdeg
        self.pid.min_duty = min_duty
        self.pid.start_duty = start_duty
        self.pid.startup_release_speed_mdegs = startup_release_speed_mdegs
        self.pid.startup_ramp_ticks = startup_ramp_ticks
        self.pid.restart_ramp_ticks = restart_ramp_ticks
        self.pid.startup_pulse_on_ticks = startup_pulse_on_ticks
        self.pid.vel_window = vel_window
        self.pid.use_enc_speed = self.use_enc_speed

    def set_trajectory(self, target_deg: float, max_vel_degs: float, max_accel_degs2: float,
                       trajectory_type: int = TrajectoryType.TRAPEZOID,
                       vel_scale: float = 1.0, accel_scale: float = 1.0,
                       auto_coast_ms: int = 0):
        """Start a new move"""
        target_mdeg = target_deg * 1000.0
        max_vel_mdegs = max_vel_degs * 1000.0 * vel_scale
        max_accel_mdegs2 = max_accel_degs2 * 1000.0 * accel_scale
        
        # Get current position from plant (PlantModel uses mdeg)
        cur_mdeg = self.plant.angle_mdeg
        
        # Re-sync observer
        self.observer = Observer(self.motor_model, self.obs_settings, int(round(cur_mdeg)))
        
        # Start trajectory
        self.trajectory.start(cur_mdeg, target_mdeg, max_vel_mdegs, max_accel_mdegs2, trajectory_type)
        
        # Reset PID
        self.pid.reset(cur_mdeg)
        
        # State
        self.holding = True
        self.auto_coast_deadline_ms = self.time_ms + auto_coast_ms if auto_coast_ms > 0 else 0
        self.trace = []
        self.trace_divider = 0
        
        print(f"Started move: target={target_deg:.1f}°, max_vel={max_vel_degs:.0f}°/s, "
              f"max_accel={max_accel_degs2:.0f}°/s², type={'jerk' if trajectory_type==1 else 'trap'}")

    def arm_trace(self):
        self.trace_armed = True
        self.trace = []
        self.trace_divider = 0

    def set_battery_profile(self, profile: list[tuple[int, int]]):
        """Set battery voltage profile as list of (time_ms, voltage_mv)"""
        self.vbus_profile = profile

    def _get_vbus(self) -> int:
        if self.vbus_profile:
            # Interpolate or step
            for t, v in self.vbus_profile:
                if self.time_ms <= t:
                    return v
            return self.vbus_profile[-1][1]
        return self.vbus_mv

    def step(self) -> bool:
        """Run one 1 ms tick. Returns True if move is still active."""
        if not self.holding:
            return False
            
        # Check auto coast
        if self.auto_coast_deadline_ms != 0 and self.time_ms >= self.auto_coast_deadline_ms:
            self.holding = False
            return False
        
        # Battery
        vbus_mv = self._get_vbus()
        
        # --- Sense: encoder ---
        true_angle_mdeg = self.plant.angle_mdeg
        self.encoder.update(true_angle_mdeg, MOTION_DT, self.time_ms * 1000)
        angle_mdeg = self.encoder.get_position_substep()  # Quantized position
        
        # --- Startup reference governor ---
        startup_displacement = fabs_f(angle_mdeg - self.pid.motion_start_position)
        if (self.startup_reference_governor and self.trajectory.active and
            startup_displacement >= 100.0 and startup_displacement <= 5000.0):
            self.trajectory.advance_to_position(angle_mdeg)
        
        # --- Trajectory reference ---
        trajectory_time = self.trajectory.t
        pos_ref, vel_ref, accel_ref = self.trajectory.update(MOTION_DT)
        
        # --- Observer update (every 5 ms) ---
        # Average applied voltage over 5 ticks
        if not hasattr(self, 'obs_voltage_sum'):
            self.obs_voltage_sum = 0
            self.obs_divider = 0
        
        self.obs_voltage_sum += getattr(self, 'last_applied_mv', 0)
        self.obs_divider += 1
        
        if self.obs_divider >= OBSERVER_PERIOD_TICKS:
            avg_mv = self.obs_voltage_sum // OBSERVER_PERIOD_TICKS
            self.observer.update(self.time_ms, angle_mdeg, avg_mv)
            self.obs_voltage_sum = 0
            self.obs_divider = 0
        
        th_hat, w_hat, i_hat = self.observer.get_state()
        
        # --- Velocity feedback ---
        if self.pid.use_enc_speed == 3:
            vel_for_pid = self.encoder.get_speed_substep()  # Not implemented
        elif self.pid.use_enc_speed == 2:
            vel_for_pid = self.encoder.get_speed_substep()  # Not implemented
        elif self.pid.use_enc_speed == 1:
            vel_for_pid = self.pid.speed_of(float(angle_mdeg), MOTION_DT)
            # Add Gaussian noise to windowed speed estimate (encoder quantization noise)
            if self.vel_noise_std > 0.0:
                import random
                vel_for_pid += random.gauss(0.0, self.vel_noise_std)
        else:
            vel_for_pid = float(w_hat)
        
        # --- Feedforward ---
        feedforward_duty = 0.0
        if self.ff_on and vbus_mv > 0:
            t_ff = self.observer.feedforward_torque(
                int(round(vel_ref)), int(round(accel_ref)),
                self.friction_feedforward_permille)
            v_ff = self.observer.torque_to_voltage(t_ff)
            feedforward_duty = float(v_ff) / float(vbus_mv)

        # --- Disturbance Observer (DOB) active payload / friction compensation ---
        if getattr(self, 'dob_enabled', False) and vbus_mv > 0:
            raw_fb_mv = self.observer.feedback_voltage(angle_mdeg)
            self.dob_dist_voltage_mv += (raw_fb_mv - self.dob_dist_voltage_mv) / 10.0
            dob_duty = (self.dob_dist_voltage_mv * getattr(self, 'dob_gain', 0.40)) / float(vbus_mv)
            feedforward_duty += float(dob_duty)
        
        # --- PID update ---
        duty = self.pid.update(pos_ref, vel_ref, accel_ref,
                               float(angle_mdeg), vel_for_pid, MOTION_DT,
                               feedforward_duty, vbus_mv)
        
        # --- Plant step ---
        applied_mv = duty * vbus_mv
        self.last_applied_mv = int(round(applied_mv))
        self.plant.step(self.last_applied_mv, getattr(self, 'load_torque_unm', 0))  # PlantModel uses mV directly
        
        # --- Trace capture ---
        if self.trace_armed:
            capture = self.trace_divider == 0
            self.trace_divider += 1
            if self.trace_divider >= EVN_TRACE_SAMPLE_DIV:
                self.trace_divider = 0
            if capture and len(self.trace) < self.trace_constants["EVN_TRACE_MAX"]:
                self.trace.append(TraceRow(
                    t_ms=self.time_ms,
                    ref_mdeg=int(round(pos_ref)),
                    enc_mdeg=angle_mdeg,
                    hat_mdeg=th_hat,
                    vref_mdegs=int(round(vel_ref)),
                    what_mdegs=int(round(self.pid.last_vel_smooth)),
                    duty_milli=int(round(duty * 1000.0)),
                    cur_01ma=i_hat
                ))
        
        # Stall check
        stalled, _ = self.observer.is_stalled(self.time_ms)
        
        # Done check - only coast if auto_coast is set or trajectory fully done
        if self.trajectory.done and not self.trajectory.active:
            if self.auto_coast_deadline_ms != 0:
                # Wait for auto_coast deadline
                pass
            else:
                # Keep holding at target (position control)
                pass
        
        self.time_ms += 1
        return self.holding or self.time_ms < self.max_time_ms

    def run(self, duration_s: float) -> list[TraceRow]:
        """Run simulation for duration seconds"""
        self.max_time_ms = int(duration_s * 1000)
        print(f"Simulating {self.max_time_ms} ticks ({duration_s:.2f}s)...")
        
        for _ in range(self.max_time_ms):
            if not self.step():
                if not self.trajectory.active and not self.holding:
                    break
        
        print(f"Completed {self.time_ms} ms, captured {len(self.trace)} trace rows")
        return self.trace

    def save_trace_csv(self, filepath: str):
        """Save trace in evn_trace_row_t CSV format (raw)"""
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['t_ms', 'ref_mdeg', 'enc_mdeg', 'hat_mdeg',
                           'vref_mdegs', 'what_mdegs', 'duty_milli', 'cur_01ma'])
            for r in self.trace:
                writer.writerow([r.t_ms, r.ref_mdeg, r.enc_mdeg, r.hat_mdeg,
                               r.vref_mdegs, r.what_mdegs, r.duty_milli, r.cur_01ma])
        print(f"Saved trace to {filepath} ({len(self.trace)} rows)")

    def save_trace_block(self, filepath: str, axis: int = 0,
                         kp_pos: float = 0.0, ki_pos: float = 0.0, kp_vel: float = 0.0,
                         kd_vel: float = 0.0, kff_accel: float = 0.0,
                         target_deg: float = 0.0, duration_s: float = 0.0,
                         max_vel_degs: float = 0.0, max_accel_degs2: float = 0.0,
                         vel_scale: float = 1.0, accel_scale: float = 1.0,
                         use_enc_speed: int = 1, vel_window: int = 60,
                         edge_alpha: float = 0.05):
        """Save trace in firmware TRACE block format for motion_metrics.py"""
        if not self.trace:
            print("No trace data to save")
            return
        
        n = len(self.trace)
        t0 = self.trace[0].t_ms
        
        with open(filepath, 'w') as f:
            # TRACE BEGIN header
            f.write(f"TRACE BEGIN axis={axis+1} rows={n} "
                   f"kp={kp_pos:.6g} ki={ki_pos:.6g} kv={kp_vel:.6g} "
                   f"kd={kd_vel:.6g} kff={kff_accel:.6g} ff={1 if self.ff_on else 0} "
                   f"pwm=25000 target={target_deg:.6g} duration={duration_s:.6g} "
                   f"vmax={max_vel_degs:.6g} accel={max_accel_degs2:.6g} "
                   f"vscale={vel_scale:.6g} ascale={accel_scale:.6g} "
                   f"vsrc={use_enc_speed} vwin={vel_window} valpha={edge_alpha:.6g}\n")
            
            # Column header
            f.write("t_ms,ref_mdeg,enc_mdeg,hat_mdeg,vref_mdegs,what_mdegs,duty_milli,cur_01ma\n")
            
            # Data rows (relative time from first sample)
            for r in self.trace:
                f.write(f"{r.t_ms - t0},{r.ref_mdeg},{r.enc_mdeg},{r.hat_mdeg},"
                       f"{r.vref_mdegs},{r.what_mdegs},{r.duty_milli},{r.cur_01ma}\n")
            
            # TRACE END
            f.write("TRACE END\n")
        
        print(f"Saved trace block to {filepath} ({n} rows)")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='EVN ALPHA Motor Digital Twin Simulator')
    parser.add_argument('--motor', choices=['EV3_Large', 'EV3_Medium', 'NXT'],
                        default='EV3_Medium', help='Motor model to simulate')
    parser.add_argument('--models', default='tools/motor_models.json',
                        help='Path to motor models JSON')
    
    # Gains
    parser.add_argument('--kp-pos', type=float, default=2.0e-4)
    parser.add_argument('--ki-pos', type=float, default=8.0e-7)
    parser.add_argument('--kp-vel', type=float, default=1.0e-6)
    parser.add_argument('--kd-vel', type=float, default=0.0)
    parser.add_argument('--kff-accel', type=float, default=0.0)
    parser.add_argument('--endpoint-kp-vel', type=float, default=1.0e-6)
    parser.add_argument('--vbus-comp', type=float, default=7400.0)
    parser.add_argument('--i-limit', type=float, default=0.20)
    parser.add_argument('--deadzone', type=float, default=400.0)
    parser.add_argument('--min-duty', type=float, default=0.12)
    parser.add_argument('--start-duty', type=float, default=0.12)
    parser.add_argument('--startup-release-speed', type=float, default=0.0)
    parser.add_argument('--startup-ramp-ticks', type=int, default=200)
    parser.add_argument('--restart-ramp-ticks', type=int, default=200)
    parser.add_argument('--startup-pulse-on-ticks', type=int, default=4)
    parser.add_argument('--vel-window', type=int, default=40)
    
    # Trajectory
    parser.add_argument('--target', type=float, default=360.0, help='Target position (deg)')
    parser.add_argument('--max-vel', type=float, default=800.0, help='Max velocity (deg/s)')
    parser.add_argument('--max-accel', type=float, default=2000.0, help='Max acceleration (deg/s²)')
    parser.add_argument('--trajectory', choices=['trapezoid', 'quintic'], default='trapezoid')
    parser.add_argument('--vel-scale', type=float, default=1.0)
    parser.add_argument('--accel-scale', type=float, default=1.0)
    parser.add_argument('--auto-coast', type=int, default=0, help='Auto coast after ms')
    
    # Feedforward
    parser.add_argument('--ff', action='store_true', default=True, help='Enable feedforward')
    parser.add_argument('--no-ff', dest='ff', action='store_false', help='Disable feedforward')
    parser.add_argument('--friction-permille', type=int, default=500)
    
    # Battery
    parser.add_argument('--battery', type=int, default=7400, help='Battery voltage (mV)')
    parser.add_argument('--battery-sag', action='store_true', help='Simulate battery sag')

    # Physical gear-train / load (to reproduce hardware variability)
    parser.add_argument('--backlash-deg', type=float, default=0.0,
                        help='Gearbox backlash (deg). EV3 Large has significant slack; >0 enables the two-inertia model')
    parser.add_argument('--gearbox-stiffness', type=int, default=0,
                        help='Gearbox torsional stiffness (unm/deg). >0 enables the two-inertia model')
    parser.add_argument('--inertia-ratio', type=float, default=1.0,
                        help='Load inertia / motor inertia (>1 adds compliance)')
    parser.add_argument('--friction-scale', type=float, default=1.0,
                        help='Scale Coulomb/static/viscous friction to model unit-to-unit variability')
    parser.add_argument('--static-friction', type=int, default=0,
                        help='Override static friction (stiction) torque (unm). 0 = use model default')
    parser.add_argument('--load-torque', type=int, default=0,
                        help='Constant external load torque (unm) applied to the load side')
    parser.add_argument('--plant-lag-ms', type=float, default=0.0,
                        help='First-order voltage lag time constant (ms) applied to the plant input; '
                             'models the physical motor electrical/electromechanical delay')
    parser.add_argument('--plant-delay-ms', type=int, default=0,
                        help='Pure transport delay (ms) applied to the plant voltage input; '
                             'models the physical PWM->current->torque pipeline delay')
    parser.add_argument('--plant-tau-ms', type=float, default=0.0,
                        help='Set the plant mechanical time constant (ms), preserving steady-state gain. '
                             'The default plant uses 5 ms observer matrices at 1 ms steps, making it ~5x too fast. '
                             'Set to the physical motor time constant (e.g. 70-110 ms) to match hardware.')

    # Output
    parser.add_argument('--duration', type=float, default=5.0, help='Simulation duration (s)')
    parser.add_argument('--output', type=str, default='trace.csv', help='Output CSV file')
    parser.add_argument('--trace', action='store_true', default=True, help='Enable trace capture')
    parser.add_argument('--no-trace', dest='trace', action='store_false')
    
    # Encoder noise for Domain Randomization
    parser.add_argument('--vel-noise-std', type=float, default=0.0,
                        help='Standard deviation of Gaussian velocity measurement noise (mdeg/s). '
                             'Added to windowed speed estimate to model encoder quantization noise.')
    
    args = parser.parse_args()
    
    # Create simulator
    sim = Simulator(args.motor, args.models)

    # Velocity measurement noise (for Domain Randomization)
    sim.vel_noise_std = args.vel_noise_std

    # Physical gear-train / load variability (EV3 Large has slack + high/variable friction)
    if args.backlash_deg > 0.0:
        sim.plant.gearbox_backlash_mdeg = int(args.backlash_deg * 1000.0)
    if args.gearbox_stiffness > 0:
        sim.plant.gearbox_stiffness = args.gearbox_stiffness
    if args.inertia_ratio != 1.0:
        sim.plant.motor_inertia_ratio = args.inertia_ratio
    if args.friction_scale != 1.0:
        sim.plant.torque_friction = int(sim.plant.torque_friction * args.friction_scale)
        sim.plant.static_friction = int(sim.plant.static_friction * args.friction_scale)
        sim.plant.viscous_friction = int(sim.plant.viscous_friction * args.friction_scale)
    if args.static_friction > 0:
        sim.plant.static_friction = args.static_friction
    sim.load_torque_unm = args.load_torque
    if args.plant_lag_ms > 0.0:
        sim.plant.voltage_lag_ms = args.plant_lag_ms
    if args.plant_delay_ms > 0:
        sim.plant.voltage_delay_ms = args.plant_delay_ms
    if args.plant_tau_ms > 0.0:
        sim.plant.set_mechanical_tau_ms(args.plant_tau_ms)

    # Configure gains
    sim.set_gains(
        kp_pos=args.kp_pos,
        ki_pos=args.ki_pos,
        kp_vel=args.kp_vel,
        kd_vel=args.kd_vel,
        kff_accel=args.kff_accel,
        endpoint_kp_vel=args.endpoint_kp_vel,
        vbus_comp=args.vbus_comp,
        i_limit=args.i_limit,
        deadzone_mdeg=args.deadzone,
        min_duty=args.min_duty,
        start_duty=args.start_duty,
        startup_release_speed_mdegs=args.startup_release_speed * 1000.0,
        startup_ramp_ticks=args.startup_ramp_ticks,
        restart_ramp_ticks=args.restart_ramp_ticks,
        startup_pulse_on_ticks=args.startup_pulse_on_ticks,
        vel_window=args.vel_window
    )
    
    # Configure feedforward
    sim.ff_on = args.ff
    sim.friction_feedforward_permille = args.friction_permille
    
    # Battery profile
    if args.battery_sag:
        # Simple sag profile: start at nominal, drop under load
        sim.set_battery_profile([
            (0, args.battery),
            (500, args.battery - 200),
            (2000, args.battery - 400),
            (5000, args.battery - 300),
        ])
    else:
        sim.vbus_mv = args.battery
    
    # Trajectory type
    traj_type = TrajectoryType.TRAPEZOID if args.trajectory == 'trapezoid' else TrajectoryType.MINIMUM_JERK
    
    # Start move
    sim.set_trajectory(
        target_deg=args.target,
        max_vel_degs=args.max_vel,
        max_accel_degs2=args.max_accel,
        trajectory_type=traj_type,
        vel_scale=args.vel_scale,
        accel_scale=args.accel_scale,
        auto_coast_ms=args.auto_coast
    )
    
    # Arm trace
    if args.trace:
        sim.arm_trace()
    
    # Run
    sim.run(args.duration)
    
    # Save
    if args.trace:
        # Determine trajectory type string
        traj_type_str = 'trapezoid' if args.trajectory == 'trapezoid' else 'quintic'
        # For motion_metrics.py compatibility, use trace block format
        if args.output.endswith('.txt') or args.output.endswith('.log'):
            sim.save_trace_block(args.output,
                                axis=0,
                                kp_pos=args.kp_pos,
                                ki_pos=args.ki_pos,
                                kp_vel=args.kp_vel,
                                kd_vel=args.kd_vel,
                                kff_accel=args.kff_accel,
                                target_deg=args.target,
                                duration_s=args.duration,
                                max_vel_degs=args.max_vel,
                                max_accel_degs2=args.max_accel,
                                vel_scale=args.vel_scale,
                                accel_scale=args.accel_scale,
                                use_enc_speed=1,
                                vel_window=args.vel_window,
                                edge_alpha=0.05)
        else:
            # Also save raw CSV
            sim.save_trace_csv(args.output)
    
    print(f"Simulation complete. Output: {args.output}")

if __name__ == '__main__':
    main()