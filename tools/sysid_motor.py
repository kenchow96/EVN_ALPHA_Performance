#!/usr/bin/env python3
"""
EVN ALPHA System Identification — Identify motor model parameters from hardware traces.

Uses hardware traces (from autonomous tuning) to identify the 17 coefficients
of the 5ms discrete Luenberger observer model for each motor type.

The model is:
  x(k+1) = A x(k) + B u(k)

where x = [angle_mdeg, speed_mdeg/s, current_0.1mA]
      u = [voltage_mv, torque_unm]

Observer state update (from observer.c):
  angle_next = angle + 858 * speed // d_angle_d_speed
                    + 71582 * current // d_angle_d_current
                    + 178956 * voltage // d_angle_d_voltage
                    + 2147 * torque // d_angle_d_torque

  speed_next = clamp(858 * speed // d_speed_d_speed
                    + 71582 * current // d_speed_d_current
                    + 178956 * voltage // d_speed_d_voltage
                    + 2147 * torque // d_speed_d_torque, 2500000)

  current_next = clamp(858 * speed // d_current_d_speed
                      + 71582 * current // d_current_d_current
                      + 178956 * voltage // d_current_d_voltage
                      + 2147 * torque // d_current_d_torque, 30000)

From traces we have: angle (enc_mdeg), speed (what_mdegs), current (cur_01ma), 
voltage (duty_milli * vbus / 1000), torque (can be estimated from current/accel)

We can use linear regression to identify the 17 coefficients.
"""

import json
import numpy as np
import csv
import os
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple

# Observer constants (must match firmware)
EVN_OBS_PRESCALE_SPEED = 858
EVN_OBS_PRESCALE_ACCEL = 85
EVN_OBS_PRESCALE_CURRENT = 71582
EVN_OBS_PRESCALE_VOLTAGE = 178956
EVN_OBS_PRESCALE_TORQUE = 2147
EVN_OBS_MAX_SPEED_MDEPS = 2_500_000
EVN_OBS_MAX_CURRENT = 30_000
EVN_OBS_MAX_VOLTAGE_MV = 12_000
EVN_OBS_MAX_TORQUE_UNM = 1_000_000

@dataclass
class TraceRow:
    t_ms: int
    ref_mdeg: int
    enc_mdeg: int
    hat_mdeg: int
    vref_mdegs: int
    what_mdegs: int
    duty_milli: int
    cur_01ma: int

@dataclass
class TraceData:
    rows: List[TraceRow]
    vbus_mv: int = 7400
    
    def to_arrays(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Extract state and input arrays for system ID."""
        n = len(self.rows)
        if n < 10:
            return None, None, None, None, None
        
        # State: [angle, speed, current] at time k
        angle = np.array([r.enc_mdeg for r in self.rows[:-1]], dtype=np.float64)
        speed = np.array([r.what_mdegs for r in self.rows[:-1]], dtype=np.float64)
        current = np.array([r.cur_01ma for r in self.rows[:-1]], dtype=np.float64)
        
        # Input: [voltage, torque] at time k
        # Voltage = duty * vbus / 1000 (duty in milli, so /1000 to get fraction, * vbus)
        duty = np.array([r.duty_milli for r in self.rows[:-1]], dtype=np.float64) / 1000.0
        voltage = duty * self.vbus_mv
        
        # Torque estimation: from current and motor model
        # For a DC motor: torque = Kt * current, where Kt ≈ Kv in SI
        # But observer uses its own torque scale. We'll estimate torque from acceleration.
        # Actually, we can use the observer's voltage_to_torque and current relationship
        # For now, estimate torque from current * Kv_factor
        # Better: use the fact that torque = J * accel + B * speed + friction
        # But we don't know J, B yet. Let's use the observer's relationship:
        # torque_unm = voltage_to_torque(voltage) - backemf - friction
        # This is circular. Let's use a simpler approach:
        # The observer's current state is the motor current, which is proportional to torque
        # torque_unm = (current_0.1mA / 10000) * Kt * 1e6 (convert to unmicro)
        # Actually, the observer uses its own scale. Let's just use current as proxy for torque
        # and identify the combined coefficients.
        
        # For linear regression, we need torque. The observer uses:
        # current_next = f(speed, current, voltage, torque)
        # If we assume torque is proportional to current (for the plant), we can use current as torque proxy
        # But the model has separate current and torque inputs...
        
        # Better approach: The plant model is the same as observer but without feedback.
        # From trace, we have angle, speed, current at each sample (5ms apart)
        # The observer runs every 5ms and uses averaged voltage over 5 ticks.
        # Our trace IS at 5ms intervals (sample_div=5), so each trace row = one observer step!
        
        # Voltage input to observer: average over 5 1ms ticks = our trace voltage (since we only have 5ms data)
        # Actually the trace is sampled every 5ms (EVN_TRACE_SAMPLE_DIV=5), which matches observer period!
        
        # So each trace row corresponds to one observer update cycle.
        # State at k+1: angle_next, speed_next, current_next
        angle_next = np.array([r.enc_mdeg for r in self.rows[1:]], dtype=np.float64)
        speed_next = np.array([r.what_mdegs for r in self.rows[1:]], dtype=np.float64)
        current_next = np.array([r.cur_01ma for r in self.rows[1:]], dtype=np.float64)
        
        # Input at k: voltage, torque
        # Torque = coulomb friction + load (load = 0 for unloaded)
        # Coulomb friction = sign(speed) * torque_friction (if |speed| > cutoff else linear)
        # But we don't know torque_friction. Let's use a different approach.
        
        # Since we're doing system ID on the PLANT (not observer), the plant update is:
        # x(k+1) = A x(k) + B u(k)
        # where u(k) = [voltage_mv, load_torque_unm]
        # Load torque is 0 for unloaded motors.
        # The plant includes coulomb friction internally.
        
        # So we can identify the plant A, B matrices directly from data:
        # [angle_next]   [a11 a12 a13] [angle]   [b11 b12] [voltage]
        # [speed_next] = [a21 a22 a23] [speed] + [b21 b22] [torque ]
        # [curr_next]   [a31 a32 a33] [current][b31 b32]
        
        # With load_torque = 0, this simplifies to:
        # x(k+1) = A x(k) + B_voltage * voltage
        # where B_voltage is the first column of B.
        
        # But the observer model has 17 coefficients that map to this.
        # Let's identify the 6 coefficients for voltage input + 6 for current feedback + 3 for speed feedback + 3 for angle feedback
        # Actually the observer A matrix has 9 elements (3x3) and B has 6 (3x2) = 15, plus friction = 16, plus torque_friction = 17
        
        # Let's just do standard linear system ID:
        # For each state variable, fit: x_next = a1*angle + a2*speed + a3*current + b1*voltage + b2*torque
        
        # Since torque = 0 (no load), we have: x_next = a1*angle + a2*speed + a3*current + b1*voltage
        # This gives 4 coefficients per state = 12 total. We need the torque terms too.
        # To get torque terms, we need data with load torque, or we use the fact that
        # coulomb friction acts like a torque input.
        
        # Alternative: Use the observer structure. The observer coefficients ARE the plant coefficients.
        # We can identify them by noting that the observer IS the plant model.
        # So we can just fit the observer equations directly.
        
        # Observer equation for angle:
        # angle_next = angle + 858*speed//d_a_ds + 71582*current//d_a_dc + 178956*voltage//d_a_dv + 2147*torque//d_a_dt
        
        # This is nonlinear due to integer division. But we can approximate as:
        # angle_next - angle = 858/d_a_ds * speed + 71582/d_a_dc * current + 178956/d_a_dv * voltage + 2147/d_a_dt * torque
        
        # Let's define: da_ds = 858/d_a_ds, da_dc = 71582/d_a_dc, etc.
        # Then we have 4 linear coefficients per state equation.
        # For 3 states, that's 12 coefficients. Plus torque_friction for the friction torque model.
        
        # Since we don't have torque, we need another approach.
        # The torque in the observer is: torque = coulomb_friction + load_torque
        # coulomb_friction = sign(speed) * torque_friction (if |speed| > 20000 else linear ramp)
        
        # We can estimate torque_friction from the steady-state current at constant speed.
        # At steady state: speed_next = speed, current_next = current
        # 0 = a21*angle + a22*speed + a23*current + b21*voltage + b22*torque
        # But angle is not in the speed equation in the observer (d_speed_d_angle = 0 implicitly)
        
        # Let's just do a practical approach: identify the 6 voltage-to-state coefficients and 6 state-to-state coefficients
        # by linear regression on the plant model, assuming torque=0, then estimate torque coefficients from friction behavior.
        
        # Plant model (simplified, torque=0):
        # angle_next = angle + a12*speed + a13*current + b11*voltage
        # speed_next = a21*angle + a22*speed + a23*current + b21*voltage
        # current_next = a31*angle + a32*speed + a33*current + b31*voltage
        
        # This is 12 coefficients. We can identify these from data.
        
        X = np.column_stack([angle, speed, current, voltage])  # 4 inputs
        
        # Fit angle_next - angle (delta angle)
        delta_angle = angle_next - angle
        
        # Fit speed_next
        # Fit current_next
        
        coeffs_angle, _, _, _ = np.linalg.lstsq(X, delta_angle, rcond=None)
        coeffs_speed, _, _, _ = np.linalg.lstsq(X, speed_next, rcond=None)
        coeffs_current, _, _, _ = np.linalg.lstsq(X, current_next, rcond=None)
        
        # coeffs = [a_angle, a_speed, a_current, b_voltage]
        return coeffs_angle, coeffs_speed, coeffs_current, X, voltage


def load_trace_file(filepath: str) -> TraceData:
    """Load a trace file in firmware format."""
    rows = []
    vbus_mv = 7400
    
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    # Parse header
    for line in lines:
        if line.startswith('TRACE BEGIN'):
            # Extract vbus from header if present
            import re
            pwm_match = re.search(r'pwm=(\d+)', line)
            # We'll use default vbus
            break
    
    # Parse data rows
    for line in lines:
        if line.startswith('t_ms') or line.startswith('TRACE'):
            continue
        parts = line.strip().split(',')
        if len(parts) == 8:
            try:
                rows.append(TraceRow(
                    t_ms=int(parts[0]),
                    ref_mdeg=int(parts[1]),
                    enc_mdeg=int(parts[2]),
                    hat_mdeg=int(parts[3]),
                    vref_mdegs=int(parts[4]),
                    what_mdegs=int(parts[5]),
                    duty_milli=int(parts[6]),
                    cur_01ma=int(parts[7])
                ))
            except ValueError:
                pass
    
    return TraceData(rows=rows, vbus_mv=vbus_mv)


def identify_from_traces(trace_dir: str, motor_name: str):
    """Identify motor model from all traces for a given motor."""
    trace_dir = Path(trace_dir)
    
    # Group traces by motor (axis)
    # Axis 0,1 = EV3 Large (M1, M2)
    # Axis 2,3 = EV3 Medium (M3, M4)
    
    axis_traces = {0: [], 1: [], 2: [], 3: []}
    
    for trace_file in trace_dir.glob('case_*.txt'):
        # Parse axis from filename
        # case_XX_rY_... where XX = case index, Y = repeat index
        # Axis = case_index // 4
        # case_00-03 -> axis 0 (EV3 Large M1)
        # case_04-07 -> axis 1 (EV3 Large M2)
        # case_08-11 -> axis 2 (EV3 Medium M3)
        # case_12-15 -> axis 3 (EV3 Medium M4)
        name = trace_file.stem
        import re
        match = re.search(r'case_(\d+)_r\d+_', name)
        if match:
            case_index = int(match.group(1))
            axis = case_index // 4
            if axis in axis_traces:
                trace = load_trace_file(str(trace_file))
                if trace.rows:
                    axis_traces[axis].append(trace)
    
    # Identify for each axis
    for axis, traces in axis_traces.items():
        if not traces:
            continue
        
        print(f"\n=== Axis {axis} ({motor_name}) ===")
        print(f"Number of traces: {len(traces)}")
        
        # Combine all traces for this axis
        all_coeffs_angle = []
        all_coeffs_speed = []
        all_coeffs_current = []
        
        for trace in traces:
            coeffs_a, coeffs_s, coeffs_c, _, _ = trace.to_arrays()
            if coeffs_a is not None:
                all_coeffs_angle.append(coeffs_a)
                all_coeffs_speed.append(coeffs_s)
                all_coeffs_current.append(coeffs_c)
        
        if all_coeffs_angle:
            avg_angle = np.mean(all_coeffs_angle, axis=0)
            avg_speed = np.mean(all_coeffs_speed, axis=0)
            avg_current = np.mean(all_coeffs_current, axis=0)
            
            print(f"Avg angle coeffs (angle, speed, current, voltage): {avg_angle}")
            print(f"Avg speed coeffs: {avg_speed}")
            print(f"Avg current coeffs: {avg_current}")
            
            # Convert to observer coefficients
            # delta_angle = 858/d_a_ds * speed + 71582/d_a_dc * current + 178956/d_a_dv * voltage
            # So: d_a_ds = 858 / coeff_speed, d_a_dc = 71582 / coeff_current, d_a_dv = 178956 / coeff_voltage
            
            if avg_angle[1] != 0:  # speed coeff
                d_angle_d_speed = 858 / avg_angle[1]
                print(f"  d_angle_d_speed = {d_angle_d_speed:.0f}")
            
            if avg_angle[2] != 0:  # current coeff
                d_angle_d_current = 71582 / avg_angle[2]
                print(f"  d_angle_d_current = {d_angle_d_current:.0f}")
            
            if avg_angle[3] != 0:  # voltage coeff
                d_angle_d_voltage = 178956 / avg_angle[3]
                print(f"  d_angle_d_voltage = {d_angle_d_voltage:.0f}")
            
            if avg_speed[1] != 0:
                d_speed_d_speed = 858 / avg_speed[1]
                print(f"  d_speed_d_speed = {d_speed_d_speed:.0f}")
            
            if avg_speed[2] != 0:
                d_speed_d_current = 71582 / avg_speed[2]
                print(f"  d_speed_d_current = {d_speed_d_current:.0f}")
            
            if avg_speed[3] != 0:
                d_speed_d_voltage = 178956 / avg_speed[3]
                print(f"  d_speed_d_voltage = {d_speed_d_voltage:.0f}")
            
            if avg_current[1] != 0:
                d_current_d_speed = 858 / avg_current[1]
                print(f"  d_current_d_speed = {d_current_d_speed:.0f}")
            
            if avg_current[2] != 0:
                d_current_d_current = 71582 / avg_current[2]
                print(f"  d_current_d_current = {d_current_d_current:.0f}")
            
            if avg_current[3] != 0:
                d_current_d_voltage = 178956 / avg_current[3]
                print(f"  d_current_d_voltage = {d_current_d_voltage:.0f}")


def main():
    trace_dir = "bench/results/sysid_20260904"
    
    # Identify EV3 Large (axes 0, 1)
    print("=" * 60)
    print("SYSTEM IDENTIFICATION - EV3 Large (Axes 0, 1)")
    print("=" * 60)
    identify_from_traces(trace_dir, "EV3_Large")
    
    print("\n" + "=" * 60)
    print("SYSTEM IDENTIFICATION - EV3 Medium (Axes 2, 3)")
    print("=" * 60)
    identify_from_traces(trace_dir, "EV3_Medium")


if __name__ == '__main__':
    main()