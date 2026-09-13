#!/usr/bin/env python3
from typing import List, Dict

def get_torture_test_profiles() -> List[Dict]:
    return [
        # --- Axis 0 (EV3 Large M1) ---
        {'axis': 0, 'repeat_index': 0, 'profile_type': 'nominal_pos', 'delta_deg': 720.0, 'max_vel_degs': 800.0, 'max_accel_degs2': 1600.0, 'test_type': 0, 'trajectory_type': 0},
        {'axis': 0, 'repeat_index': 1, 'profile_type': 'high_speed_neg', 'delta_deg': -720.0, 'max_vel_degs': 1000.0, 'max_accel_degs2': 2200.0, 'test_type': 0, 'trajectory_type': 0},
        {'axis': 0, 'repeat_index': 2, 'profile_type': 'microstep_backlash', 'delta_deg': 35.0, 'max_vel_degs': 350.0, 'max_accel_degs2': 2400.0, 'test_type': 0, 'trajectory_type': 0},
        {'axis': 0, 'repeat_index': 3, 'profile_type': 'min_jerk_s_curve', 'delta_deg': -180.0, 'max_vel_degs': 600.0, 'max_accel_degs2': 1800.0, 'test_type': 0, 'trajectory_type': 1},

        # --- Axis 1 (EV3 Large M2) ---
        {'axis': 1, 'repeat_index': 0, 'profile_type': 'nominal_pos', 'delta_deg': 720.0, 'max_vel_degs': 800.0, 'max_accel_degs2': 1600.0, 'test_type': 0, 'trajectory_type': 0},
        {'axis': 1, 'repeat_index': 1, 'profile_type': 'high_speed_neg', 'delta_deg': -720.0, 'max_vel_degs': 1000.0, 'max_accel_degs2': 2200.0, 'test_type': 0, 'trajectory_type': 0},
        {'axis': 1, 'repeat_index': 2, 'profile_type': 'microstep_backlash', 'delta_deg': 35.0, 'max_vel_degs': 350.0, 'max_accel_degs2': 2400.0, 'test_type': 0, 'trajectory_type': 0},
        {'axis': 1, 'repeat_index': 3, 'profile_type': 'min_jerk_s_curve', 'delta_deg': -180.0, 'max_vel_degs': 600.0, 'max_accel_degs2': 1800.0, 'test_type': 0, 'trajectory_type': 1},

        # --- Axis 2 (EV3 Medium M3) ---
        {'axis': 2, 'repeat_index': 0, 'profile_type': 'nominal_neg', 'delta_deg': -720.0, 'max_vel_degs': 1100.0, 'max_accel_degs2': 2200.0, 'test_type': 0, 'trajectory_type': 0},
        {'axis': 2, 'repeat_index': 1, 'profile_type': 'high_speed_pos', 'delta_deg': 720.0, 'max_vel_degs': 1400.0, 'max_accel_degs2': 3000.0, 'test_type': 0, 'trajectory_type': 0},
        {'axis': 2, 'repeat_index': 2, 'profile_type': 'microstep_stiction', 'delta_deg': -45.0, 'max_vel_degs': 500.0, 'max_accel_degs2': 2600.0, 'test_type': 0, 'trajectory_type': 0},
        {'axis': 2, 'repeat_index': 3, 'profile_type': 'min_jerk_s_curve', 'delta_deg': 180.0, 'max_vel_degs': 800.0, 'max_accel_degs2': 2200.0, 'test_type': 0, 'trajectory_type': 1},

        # --- Axis 3 (EV3 Medium M4) ---
        {'axis': 3, 'repeat_index': 0, 'profile_type': 'nominal_neg', 'delta_deg': -720.0, 'max_vel_degs': 1100.0, 'max_accel_degs2': 2200.0, 'test_type': 0, 'trajectory_type': 0},
        {'axis': 3, 'repeat_index': 1, 'profile_type': 'high_speed_pos', 'delta_deg': 720.0, 'max_vel_degs': 1400.0, 'max_accel_degs2': 3000.0, 'test_type': 0, 'trajectory_type': 0},
        {'axis': 3, 'repeat_index': 2, 'profile_type': 'microstep_stiction', 'delta_deg': -45.0, 'max_vel_degs': 500.0, 'max_accel_degs2': 2600.0, 'test_type': 0, 'trajectory_type': 0},
        {'axis': 3, 'repeat_index': 3, 'profile_type': 'min_jerk_s_curve', 'delta_deg': 180.0, 'max_vel_degs': 800.0, 'max_accel_degs2': 2200.0, 'test_type': 0, 'trajectory_type': 1},
    ]
