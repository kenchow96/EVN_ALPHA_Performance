#!/usr/bin/env python3
"""
EVN ALPHA Torture Excitation Profile Generator

Generates rich test trajectories for motor tuning that uncover:
1. Reversal stiction / breakaway stalls
2. Gear-train backlash chatter across the deadband
3. Resonant hunting frequencies / limit cycles
4. Multi-frequency velocity dynamics (PRBS / Chirp-like step sequences)
"""

from typing import List, Dict


def get_torture_test_profiles() -> List[Dict]:
    """Return an array of 16 rich torture excitation cases across all 4 axes.

    Distribution:
    - Cases 00-03: Axis 0 (M1 EV3 Large)
        * Case 00: Large nominal +720° fast move (nominal tracking & overshoot)
        * Case 01: Reverse -720° fast move (reversal dynamics)
        * Case 02: Micro-step backlash perturbation (+30° rapid steps)
        * Case 03: Reversal cycle (-90° / +90° stiction & lash crossing)
    - Cases 04-07: Axis 1 (M2 EV3 Large)
        * Case 04: Large nominal +720° fast move
        * Case 05: Reverse -720° fast move
        * Case 06: Micro-step backlash perturbation (+30° rapid steps)
        * Case 07: Reversal cycle (-90° / +90° stiction & lash crossing)
    - Cases 08-11: Axis 2 (M3 EV3 Medium)
        * Case 08: Reverse -720° fast move (nominal tracking & settle)
        * Case 09: Forward +720° breakaway stiction torture test
        * Case 10: High-accel 450° step move (hunting & current limit test)
        * Case 11: Rapid micro-move perturbation (+45°)
    - Cases 12-15: Axis 3 (M4 EV3 Medium)
        * Case 12: Reverse -720° fast move
        * Case 13: Forward +720° breakaway stiction torture test
        * Case 14: High-accel 450° step move
        * Case 15: Rapid micro-move perturbation (+45°)
    """
    profiles = [
        # --- Axis 0: M1 EV3 Large ---
        {
            "axis": 0, "repeat_index": 0, "delta_deg": 720.0, "max_vel_degs": 800.0, "max_accel_degs2": 1600.0,
            "profile_type": "nominal_pos", "test_type": 0,
        },
        {
            "axis": 0, "repeat_index": 1, "delta_deg": -720.0, "max_vel_degs": 800.0, "max_accel_degs2": 1600.0,
            "profile_type": "reversal_neg", "test_type": 0,
        },
        {
            "axis": 0, "repeat_index": 2, "delta_deg": 45.0, "max_vel_degs": 400.0, "max_accel_degs2": 2000.0,
            "profile_type": "backlash_microstep", "test_type": 0,
        },
        {
            "axis": 0, "repeat_index": 3, "delta_deg": -90.0, "max_vel_degs": 600.0, "max_accel_degs2": 1800.0,
            "profile_type": "deadband_reversal", "test_type": 0,
        },

        # --- Axis 1: M2 EV3 Large ---
        {
            "axis": 1, "repeat_index": 0, "delta_deg": 720.0, "max_vel_degs": 800.0, "max_accel_degs2": 1600.0,
            "profile_type": "nominal_pos", "test_type": 0,
        },
        {
            "axis": 1, "repeat_index": 1, "delta_deg": -720.0, "max_vel_degs": 800.0, "max_accel_degs2": 1600.0,
            "profile_type": "reversal_neg", "test_type": 0,
        },
        {
            "axis": 1, "repeat_index": 2, "delta_deg": 45.0, "max_vel_degs": 400.0, "max_accel_degs2": 2000.0,
            "profile_type": "backlash_microstep", "test_type": 0,
        },
        {
            "axis": 1, "repeat_index": 3, "delta_deg": -90.0, "max_vel_degs": 600.0, "max_accel_degs2": 1800.0,
            "profile_type": "deadband_reversal", "test_type": 0,
        },

        # --- Axis 2: M3 EV3 Medium ---
        {
            "axis": 2, "repeat_index": 0, "delta_deg": -720.0, "max_vel_degs": 1100.0, "max_accel_degs2": 2200.0,
            "profile_type": "nominal_neg", "test_type": 0,
        },
        {
            "axis": 2, "repeat_index": 1, "delta_deg": 720.0, "max_vel_degs": 1100.0, "max_accel_degs2": 2200.0,
            "profile_type": "stiction_pos", "test_type": 0,
        },
        {
            "axis": 2, "repeat_index": 2, "delta_deg": -360.0, "max_vel_degs": 1200.0, "max_accel_degs2": 2500.0,
            "profile_type": "rapid_step_neg", "test_type": 0,
        },
        {
            "axis": 2, "repeat_index": 3, "delta_deg": 60.0, "max_vel_degs": 600.0, "max_accel_degs2": 2400.0,
            "profile_type": "stiction_microstep", "test_type": 0,
        },

        # --- Axis 3: M4 EV3 Medium ---
        {
            "axis": 3, "repeat_index": 0, "delta_deg": -720.0, "max_vel_degs": 1100.0, "max_accel_degs2": 2200.0,
            "profile_type": "nominal_neg", "test_type": 0,
        },
        {
            "axis": 3, "repeat_index": 1, "delta_deg": 720.0, "max_vel_degs": 1100.0, "max_accel_degs2": 2200.0,
            "profile_type": "stiction_pos", "test_type": 0,
        },
        {
            "axis": 3, "repeat_index": 2, "delta_deg": -360.0, "max_vel_degs": 1200.0, "max_accel_degs2": 2500.0,
            "profile_type": "rapid_step_neg", "test_type": 0,
        },
        {
            "axis": 3, "repeat_index": 3, "delta_deg": 60.0, "max_vel_degs": 600.0, "max_accel_degs2": 2400.0,
            "profile_type": "stiction_microstep", "test_type": 0,
        },
    ]
    return profiles
