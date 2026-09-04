#!/usr/bin/env python3
"""
EVN ALPHA Performance - Modern Minimalist GUI Dashboard
A dashboard for console mode operation of the EVN ALPHA robotics controller.

Features:
- Check BOOTSEL mode using check_bootsel.ps1
- Connect to board via USB CDC serial
- Battery indicator (parsed from console 'h' or 'B' command)
- LED control (on/off/toggle) via console 'L' command
- Button status display via console 'y' command
- Motor control panel (4 motors) with real telemetry from console 'S' command
- Servo control panel (4 servos) with pulse width (us) via console 'E' command
- I2C port scanner via console 'I' command
- Console command log
- Heartbeat to keep console alive
- Quit button that sends board back to UF2 mode

Requires: Python 3.6+, pyserial, tkinter
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import serial
import serial.tools.list_ports
import threading
import time
import subprocess
import sys
import re
import os
from datetime import datetime
import queue

class EVNDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("EVN ALPHA Performance Dashboard")
        self.root.geometry("1200x800")
        self.root.minsize(1000, 700)
        
        # Serial connection
        self.serial_port = None
        self.serial_thread = None
        self.serial_running = False
        self.serial_queue = queue.Queue()
        
        # Dashboard state - all real data from console
        self.battery_voltage = 0.0
        self.battery_cells = (0.0, 0.0)
        self.led_state = False
        self.button_state = False
        self.motor_angles = [0.0, 0.0, 0.0, 0.0]
        self.motor_speeds = [0.0, 0.0, 0.0, 0.0]
        self.motor_stalled = [False, False, False, False]
        self.motor_done = [False, False, False, False]
        self.motor_moving = [False, False, False, False]
        self.motor_targets = [0.0, 0.0, 0.0, 0.0]
        self.servo_pulses = [1500, 1500, 1500, 1500]  # Pulse width in microseconds
        
        # Heartbeat
        self.heartbeat_thread = None
        self.heartbeat_running = False
        self.last_heartbeat_response = 0
        
        # Command tracking for parsing responses
        self.pending_commands = {}
        self.command_counter = 0
        
        # Setup UI
        self.setup_ui()
        self.setup_styles()
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Run startup sequence in background thread
        self.startup_thread = threading.Thread(target=self.startup_sequence, daemon=True)
        self.startup_thread.start()
        
        # Start periodic updates
        self.update_gui()
    
    def setup_styles(self):
        """Setup custom styles for modern minimalist look"""
        style = ttk.Style()
        
        # Configure colors for modern look
        style.configure('TFrame', background='#f8f9fa')
        style.configure('TLabel', background='#f8f9fa', font=('Segoe UI', 9))
        style.configure('TButton', font=('Segoe UI', 9), padding=6)
        style.configure('Accent.TButton', font=('Segoe UI', 9, 'bold'), padding=8, foreground='white', background='#dc3545')
        style.map('Accent.TButton', background=[('active', '#c82333'), ('pressed', '#bd2130')], foreground=[('active', 'white'), ('pressed', 'white')])
        style.configure('Header.TLabel', font=('Segoe UI', 10, 'bold'))
        style.configure('Status.TLabel', font=('Segoe UI', 9), foreground='#6c757d')
        style.configure('Success.TLabel', foreground='#28a745')
        style.configure('Warning.TLabel', foreground='#ffc107')
        style.configure('Error.TLabel', foreground='#dc3545')
        style.configure('Info.TLabel', foreground='#17a2b8')
        
        # Configure notebook - use full width
        style.configure('TNotebook', background='#f8f9fa', tabposition='n')
        style.configure('TNotebook.Tab', padding=[20, 8], font=('Segoe UI', 9))
        
        # Configure labelframe
        style.configure('TLabelframe', background='#f8f9fa')
        style.configure('TLabelframe.Label', background='#f8f9fa', font=('Segoe UI', 9, 'bold'))
        
        # Add tag configurations for console output
        self.console_tags_configured = False
    
    def setup_ui(self):
        """Setup the user interface"""
        # Main container
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(header_frame, text="EVN ALPHA Performance Dashboard", 
                 style='Header.TLabel', font=('Segoe UI', 14, 'bold')).pack(side=tk.LEFT)
        
        self.connection_status = ttk.Label(header_frame, text="● Disconnected", 
                                          style='Error.TLabel')
        self.connection_status.pack(side=tk.RIGHT)
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Tab 1: Dashboard
        self.dashboard_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.dashboard_tab, text="Dashboard")
        self.setup_dashboard_tab()
        
        # Tab 2: Motors
        self.motors_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.motors_tab, text="Motors")
        self.setup_motors_tab()
        
        # Tab 3: Servos
        self.servos_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.servos_tab, text="Servos")
        self.setup_servos_tab()
        
        # Tab 4: I2C Scanner
        self.i2c_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.i2c_tab, text="I2C Scanner")
        self.setup_i2c_tab()
        
        # Tab 5: Console
        self.console_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.console_tab, text="Console")
        self.setup_console_tab()
        
        # Footer with quit button
        footer_frame = ttk.Frame(main_frame)
        footer_frame.pack(fill=tk.X, pady=(15, 0))
        
        ttk.Button(footer_frame, text="Quit & Reboot to UF2", 
                  command=self.quit_and_reboot, style='Accent.TButton').pack(side=tk.RIGHT)
        
        # Modern status bar with dark mode support
        self.status_bar_frame = ttk.Frame(main_frame, relief=tk.FLAT)
        self.status_bar_frame.pack(fill=tk.X, pady=(5, 0), padx=5)
        
        self.status_bar = ttk.Label(self.status_bar_frame, text="Ready", anchor=tk.W, padding=(10, 5))
        self.status_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Connection indicator in status bar
        self.status_connection = ttk.Label(self.status_bar_frame, text="● Disconnected", foreground='#dc3545', padding=(10, 5))
        self.status_connection.pack(side=tk.RIGHT)
        
        # Dark mode toggle in status bar
        self.dark_mode_var = tk.BooleanVar(value=False)
        self.dark_mode_btn = ttk.Checkbutton(self.status_bar_frame, text="Dark Mode", variable=self.dark_mode_var, command=self.toggle_dark_mode)
        self.dark_mode_btn.pack(side=tk.RIGHT, padx=(0, 10))
    
    def setup_dashboard_tab(self):
        """Setup the main dashboard tab"""
        # Battery section
        battery_frame = ttk.LabelFrame(self.dashboard_tab, text="Battery Status", padding=15)
        battery_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.battery_label = ttk.Label(battery_frame, text="--.-- V", 
                                      font=('Segoe UI', 24, 'bold'))
        self.battery_label.pack()
        
        self.battery_detail_label = ttk.Label(battery_frame, text="Cell 1: --.-- V  |  Cell 2: --.-- V",
                                             style='Status.TLabel')
        self.battery_detail_label.pack(pady=(5, 0))
        
        # Control section
        control_frame = ttk.LabelFrame(self.dashboard_tab, text="System Controls", padding=15)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # LED controls
        led_frame = ttk.Frame(control_frame)
        led_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(led_frame, text="User LED (GP25):").pack(side=tk.LEFT)
        
        self.led_on_btn = ttk.Button(led_frame, text="ON", width=8,
                                    command=lambda: self.set_led(True))
        self.led_on_btn.pack(side=tk.LEFT, padx=(10, 5))
        
        self.led_off_btn = ttk.Button(led_frame, text="OFF", width=8,
                                     command=lambda: self.set_led(False))
        self.led_off_btn.pack(side=tk.LEFT, padx=5)
        
        self.led_toggle_btn = ttk.Button(led_frame, text="TOGGLE", width=8,
                                        command=self.toggle_led)
        self.led_toggle_btn.pack(side=tk.LEFT, padx=5)
        
        self.led_indicator = ttk.Label(led_frame, text="● OFF", 
                                      font=('Segoe UI', 10),
                                      foreground='#6c757d')
        self.led_indicator.pack(side=tk.LEFT, padx=(20, 0))
        
        # Button status
        button_frame = ttk.Frame(control_frame)
        button_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(button_frame, text="User Button (GP24):").pack(side=tk.LEFT)
        
        self.button_indicator = ttk.Label(button_frame, text="● Released", 
                                         font=('Segoe UI', 10),
                                         foreground='#28a745')
        self.button_indicator.pack(side=tk.LEFT, padx=(10, 0))
        
        # Connection controls
        conn_frame = ttk.LabelFrame(self.dashboard_tab, text="Connection", padding=15)
        conn_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(conn_frame, text="Serial Port:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(conn_frame, textvariable=self.port_var, width=20)
        self.port_combo.grid(row=0, column=1, padx=5)
        
        self.refresh_btn = ttk.Button(conn_frame, text="Refresh", width=8,
                                     command=self.refresh_ports)
        self.refresh_btn.grid(row=0, column=2, padx=5)
        
        self.connect_btn = ttk.Button(conn_frame, text="Connect", width=10,
                                     command=self.toggle_connection)
        self.connect_btn.grid(row=0, column=3, padx=5)
        
        # Check BOOTSEL button (shortened text)
        self.check_bootsel_btn = ttk.Button(conn_frame, text="BOOTSEL", width=10,
                                           command=self.check_bootsel_mode)
        self.check_bootsel_btn.grid(row=0, column=4, padx=(15, 5))
        
        # Configure grid weights
        conn_frame.columnconfigure(1, weight=1)
    
    def setup_motors_tab(self):
        """Setup the motors control tab - using full width"""
        # Create scrollable frame
        canvas = tk.Canvas(self.motors_tab)
        scrollbar = ttk.Scrollbar(self.motors_tab, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        # Store canvas window ID for width configuration
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Make canvas expand to full width
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Configure canvas window to expand to canvas width
        def on_canvas_configure(event):
            canvas.itemconfig(canvas_window, width=event.width)
        canvas.bind("<Configure>", on_canvas_configure)
        
        # Motor panels - use grid for better layout control
        for i in range(4):
            motor_frame = ttk.LabelFrame(scrollable_frame, text=f"Motor {i+1}", padding=15)
            motor_frame.pack(fill=tk.X, padx=10, pady=8)
            
            # Motor status - use grid for alignment
            status_frame = ttk.Frame(motor_frame)
            status_frame.pack(fill=tk.X, pady=(0, 10))
            
            ttk.Label(status_frame, text="Angle:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
            angle_label = ttk.Label(status_frame, text="--.--°", font=('Segoe UI', 10, 'bold'))
            angle_label.grid(row=0, column=1, sticky=tk.W, padx=(0, 20))
            setattr(self, f'motor{i+1}_angle_label', angle_label)
            
            ttk.Label(status_frame, text="Speed:").grid(row=0, column=2, sticky=tk.W, padx=(0, 5))
            speed_label = ttk.Label(status_frame, text="--.--°/s", font=('Segoe UI', 10, 'bold'))
            speed_label.grid(row=0, column=3, sticky=tk.W, padx=(0, 20))
            setattr(self, f'motor{i+1}_speed_label', speed_label)
            
            ttk.Label(status_frame, text="Target:").grid(row=0, column=4, sticky=tk.W, padx=(0, 5))
            target_label = ttk.Label(status_frame, text="--.--°", font=('Segoe UI', 10, 'bold'), foreground='#17a2b8')
            target_label.grid(row=0, column=5, sticky=tk.W, padx=(0, 20))
            setattr(self, f'motor{i+1}_target_label', target_label)
            
            stall_label = ttk.Label(status_frame, text="● N/A", foreground='#6c757d')
            stall_label.grid(row=0, column=6, sticky=tk.W, padx=(5, 0))
            setattr(self, f'motor{i+1}_stall_label', stall_label)
            
            done_label = ttk.Label(status_frame, text="○ N/A", foreground='#6c757d')
            done_label.grid(row=0, column=7, sticky=tk.W, padx=(5, 0))
            setattr(self, f'motor{i+1}_done_label', done_label)
            
            # Configure grid weights for full width usage
            for col in range(8):
                status_frame.columnconfigure(col, weight=1)
            
            # Motor controls
            control_frame = ttk.Frame(motor_frame)
            control_frame.pack(fill=tk.X, pady=10)
            
            ttk.Label(control_frame, text="Move By (deg):").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
            angle_entry = ttk.Entry(control_frame, width=8)
            angle_entry.grid(row=0, column=1, sticky=tk.W, padx=(0, 15))
            setattr(self, f'motor{i+1}_target_entry', angle_entry)
            
            ttk.Button(control_frame, text="Move", width=8,
                      command=lambda idx=i: self.move_motor(idx)).grid(row=0, column=2, padx=5)
            
            # Coast button with active state tracking
            coast_btn = ttk.Button(control_frame, text="Coast", width=8,
                      command=lambda idx=i: self.coast_motor(idx))
            coast_btn.grid(row=0, column=3, padx=5)
            setattr(self, f'motor{i+1}_coast_btn', coast_btn)
            
            # Hold button with active state tracking
            hold_btn = ttk.Button(control_frame, text="Hold", width=8,
                      command=lambda idx=i: self.hold_motor(idx))
            hold_btn.grid(row=0, column=4, padx=5)
            setattr(self, f'motor{i+1}_hold_btn', hold_btn)
            
            ttk.Button(control_frame, text="Coast", width=8,
                      command=lambda idx=i: self.coast_motor(idx)).grid(row=0, column=3, padx=5)
            
            ttk.Button(control_frame, text="Hold", width=8,
                      command=lambda idx=i: self.hold_motor(idx)).grid(row=0, column=4, padx=5)
            
            # Quick presets
            preset_frame = ttk.Frame(motor_frame)
            preset_frame.pack(fill=tk.X, pady=(5, 0))
            
            ttk.Label(preset_frame, text="Presets:").pack(side=tk.LEFT, padx=(0, 10))
            
            ttk.Button(preset_frame, text="0°", width=6,
                      command=lambda idx=i: self.set_motor_angle(idx, 0.0)).pack(side=tk.LEFT, padx=2)
            ttk.Button(preset_frame, text="90°", width=6,
                      command=lambda idx=i: self.set_motor_angle(idx, 90.0)).pack(side=tk.LEFT, padx=2)
            ttk.Button(preset_frame, text="180°", width=6,
                      command=lambda idx=i: self.set_motor_angle(idx, 180.0)).pack(side=tk.LEFT, padx=2)
            ttk.Button(preset_frame, text="-90°", width=6,
                      command=lambda idx=i: self.set_motor_angle(idx, -90.0)).pack(side=tk.LEFT, padx=2)
            ttk.Button(preset_frame, text="+360°", width=6,
                      command=lambda idx=i: self.set_motor_angle(idx, 360.0)).pack(side=tk.LEFT, padx=2)
            ttk.Button(preset_frame, text="-360°", width=6,
                      command=lambda idx=i: self.set_motor_angle(idx, -360.0)).pack(side=tk.LEFT, padx=2)
    
    def setup_servos_tab(self):
        """Setup the servos control tab - using full width and pulse width (us)"""
        # Create scrollable frame
        canvas = tk.Canvas(self.servos_tab)
        scrollbar = ttk.Scrollbar(self.servos_tab, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        # Store canvas window ID for width configuration
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Make canvas expand to full width
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Configure canvas window to expand to canvas width
        def on_canvas_configure(event):
            canvas.itemconfig(canvas_window, width=event.width)
        canvas.bind("<Configure>", on_canvas_configure)
        
        # Servo panels - use full width
        for i in range(4):
            servo_frame = ttk.LabelFrame(scrollable_frame, text=f"Servo {i+1} (GP{[2, 3, 10, 11][i]})", padding=15)
            servo_frame.pack(fill=tk.X, padx=10, pady=8)
            
            # Servo status - pulse width display
            status_frame = ttk.Frame(servo_frame)
            status_frame.pack(fill=tk.X, pady=(0, 10))
            
            ttk.Label(status_frame, text="Pulse Width:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
            pulse_label = ttk.Label(status_frame, text="---- us", font=('Segoe UI', 12, 'bold'), foreground='#17a2b8')
            pulse_label.grid(row=0, column=1, sticky=tk.W, padx=(0, 20))
            setattr(self, f'servo{i+1}_pulse_label', pulse_label)
            
            ttk.Label(status_frame, text="Range:").grid(row=0, column=2, sticky=tk.W, padx=(20, 5))
            range_label = ttk.Label(status_frame, text="200-2800 us", foreground='#6c757d')
            range_label.grid(row=0, column=3, sticky=tk.W)
            
            # Configure grid weights
            status_frame.columnconfigure(1, weight=1)
            status_frame.columnconfigure(3, weight=1)
            
            # Servo control - pulse width slider (200-2800 us)
            slider_frame = ttk.Frame(servo_frame)
            slider_frame.pack(fill=tk.X, pady=10)
            
            ttk.Label(slider_frame, text="Pulse (us):").pack(side=tk.LEFT, padx=(0, 10))
            
            pulse_var = tk.IntVar(value=1500)
            pulse_slider = ttk.Scale(slider_frame, from_=200, to=2800, 
                                   variable=pulse_var, orient=tk.HORIZONTAL,
                                   length=400)
            pulse_slider.pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)
            pulse_slider.bind("<ButtonRelease-1>", 
                            lambda e, idx=i, var=pulse_var: self.set_servo_pulse(idx, var.get()))
            pulse_slider.bind("<B1-Motion>", 
                            lambda e, idx=i, var=pulse_var: self.on_servo_slider_drag(idx, var.get()))
            
            pulse_display = ttk.Label(slider_frame, text="1500 us", width=10, font=('Segoe UI', 10, 'bold'))
            pulse_display.pack(side=tk.LEFT, padx=10)
            setattr(self, f'servo{i+1}_slider', pulse_slider)
            setattr(self, f'servo{i+1}_slider_var', pulse_var)
            setattr(self, f'servo{i+1}_pulse_display', pulse_display)
            
            # Preset pulse widths
            preset_frame = ttk.Frame(servo_frame)
            preset_frame.pack(fill=tk.X, pady=5)
            
            ttk.Label(preset_frame, text="Presets:").pack(side=tk.LEFT, padx=(0, 10))
            
            ttk.Button(preset_frame, text="Min (200 us)", width=12,
                      command=lambda idx=i: self.set_servo_pulse_with_slider(idx, 200)).pack(side=tk.LEFT, padx=2)
            ttk.Button(preset_frame, text="Center (1500 us)", width=14,
                      command=lambda idx=i: self.set_servo_pulse_with_slider(idx, 1500)).pack(side=tk.LEFT, padx=2)
            ttk.Button(preset_frame, text="Max (2800 us)", width=12,
                      command=lambda idx=i: self.set_servo_pulse_with_slider(idx, 2800)).pack(side=tk.LEFT, padx=2)
            ttk.Button(preset_frame, text="1000 us", width=10,
                      command=lambda idx=i: self.set_servo_pulse_with_slider(idx, 1000)).pack(side=tk.LEFT, padx=2)
            ttk.Button(preset_frame, text="2000 us", width=10,
                      command=lambda idx=i: self.set_servo_pulse_with_slider(idx, 2000)).pack(side=tk.LEFT, padx=2)
            
            # Enable/Disable not directly supported via console
            # ttk.Button(preset_frame, text="Query", width=8,
            #           command=lambda idx=i: self.send_console_command_raw(f"E {idx+1} 0")).pack(side=tk.LEFT, padx=(10, 2))
    
    def setup_i2c_tab(self):
        """Setup the I2C scanner tab"""
        # Control panel
        control_frame = ttk.LabelFrame(self.i2c_tab, text="I2C Scanner Controls", padding=15)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(control_frame, text="Scan I2C Bus", width=15,
                  command=self.scan_i2c_bus).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(control_frame, text="Scan All Ports", width=15,
                  command=self.scan_all_i2c_ports).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(control_frame, text="Port:").pack(side=tk.LEFT, padx=(20, 5))
        self.i2c_port_var = tk.StringVar(value="1")
        ttk.Spinbox(control_frame, from_=1, to=16, width=5,
                   textvariable=self.i2c_port_var).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(control_frame, text="Scan Port", width=12,
                  command=self.scan_i2c_port).pack(side=tk.LEFT, padx=5)
        
        # Results display
        results_frame = ttk.LabelFrame(self.i2c_tab, text="Scan Results", padding=15)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.i2c_results = scrolledtext.ScrolledText(results_frame, height=20,
                                                    font=('Consolas', 9))
        self.i2c_results.pack(fill=tk.BOTH, expand=True)
    
    def setup_console_tab(self):
        """Setup the console tab"""
        # Console output
        console_frame = ttk.LabelFrame(self.console_tab, text="Console Output", padding=10)
        console_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.console_output = scrolledtext.ScrolledText(console_frame, height=20,
                                                       font=('Consolas', 9),
                                                       wrap=tk.WORD)
        self.console_output.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Console input
        input_frame = ttk.Frame(self.console_tab)
        input_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(input_frame, text="Command:").pack(side=tk.LEFT)
        
        self.console_input = ttk.Entry(input_frame, width=50)
        self.console_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.console_input.bind("<Return>", self.send_console_command)
        
        ttk.Button(input_frame, text="Send", width=8,
                  command=self.send_console_command).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(input_frame, text="Clear", width=8,
                  command=self.clear_console).pack(side=tk.LEFT, padx=5)
        
        # Quick commands
        quick_frame = ttk.LabelFrame(self.console_tab, text="Quick Commands", padding=10)
        quick_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(quick_frame, text="Heartbeat (H)", width=12,
                  command=lambda: self.send_console_command_raw("h")).pack(side=tk.LEFT, padx=2)
        ttk.Button(quick_frame, text="Status (S)", width=12,
                  command=lambda: self.send_console_command_raw("s")).pack(side=tk.LEFT, padx=2)
        ttk.Button(quick_frame, text="Battery (B)", width=12,
                  command=lambda: self.send_console_command_raw("B")).pack(side=tk.LEFT, padx=2)
        ttk.Button(quick_frame, text="Coast All (c)", width=12,
                  command=lambda: self.send_console_command_raw("c")).pack(side=tk.LEFT, padx=2)
    
    def log_to_console(self, message, tag=None):
        """Add message to console output"""
        # Configure tags on first use
        if not self.console_tags_configured:
            self.console_output.tag_config('command', foreground='#17a2b8', font=('Consolas', 9, 'bold'))
            self.console_output.tag_config('error', foreground='#dc3545')
            self.console_output.tag_config('warning', foreground='#ffc107')
            self.console_output.tag_config('info', foreground='#28a745')
            self.console_tags_configured = True
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}\n"
        
        if tag:
            self.console_output.insert(tk.END, formatted_message, tag)
        else:
            self.console_output.insert(tk.END, formatted_message)
        self.console_output.see(tk.END)
        self.console_output.update_idletasks()
    
    def clear_console(self):
        """Clear the console output"""
        self.console_output.delete(1.0, tk.END)
        self.log_to_console("Console cleared", "info")
    
    def update_status(self, message):
        """Update status bar"""
        self.status_bar.config(text=message)
        self.root.update_idletasks()
    
    # Serial communication methods
    def refresh_ports(self):
        """Refresh available serial ports"""
        ports = [port.device for port in serial.tools.list_ports.comports()]
        self.port_combo['values'] = ports
        if ports:
            self.port_combo.set(ports[0])
        self.log_to_console(f"Found {len(ports)} serial ports")
    
    def check_bootsel_mode(self):
        """Check if board is in BOOTSEL mode using check_bootsel.ps1"""
        try:
            # Get the directory of this script to find check_bootsel.ps1
            import os
            script_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(script_dir)  # Go up one level from tools/
            bootsel_script = os.path.join(project_root, 'tools', 'check_bootsel.ps1')
            
            result = subprocess.run(['powershell', '-ExecutionPolicy', 'Bypass', 
                                   '-File', bootsel_script], 
                                  capture_output=True, text=True, cwd=project_root)
            if result.returncode == 0 and result.stdout.strip():
                port = result.stdout.strip()
                self.port_var.set(port)
                self.log_to_console(f"BOOTSEL detected on port {port}")
                messagebox.showinfo("BOOTSEL Detected", f"Board is in BOOTSEL mode on port {port}")
                return port
            else:
                self.log_to_console("BOOTSEL not detected")
                messagebox.showinfo("BOOTSEL Check", "Board is not in BOOTSEL mode")
                return None
        except Exception as e:
            self.log_to_console(f"Error checking BOOTSEL: {e}")
            messagebox.showerror("Error", f"Failed to check BOOTSEL: {e}")
            return None
    
    def startup_sequence(self):
        """Startup sequence: check for console mode first, then BOOTSEL, connect to board"""
        self.log_to_console("Starting EVN ALPHA Dashboard...")
        self.update_status("Checking board state...")
        
        # Step 1: First check if board is already running console mode (CDC port)
        cdc_port = self._find_cdc_port()
        if cdc_port:
            self.port_var.set(cdc_port)
            self.log_to_console(f"Board already running console mode on {cdc_port}")
            self.update_status("Found console mode - connecting...")
            self.root.after(0, self._connect_after_startup)
            return
        
        # Step 2: Board not in console mode - check if in BOOTSEL mode
        self.log_to_console("Board not in console mode - checking for BOOTSEL...")
        self.update_status("Checking for BOOTSEL mode...")
        bootsel_port = self._check_bootsel_silent()
        if bootsel_port:
            self.log_to_console(f"Board detected in BOOTSEL mode on {bootsel_port}")
            self.update_status("Board in BOOTSEL mode - flashing firmware...")
            self._flash_firmware()
            # Wait for board to re-enumerate
            self._wait_for_cdc_port()
        else:
            self.log_to_console("Board not in BOOTSEL mode either")
            self.update_status("No board detected - please connect board or put in BOOTSEL")
            # Start periodic reconnection attempts
            self._start_reconnect_timer()
            return
        
        # Step 3: Connect to the serial port
        self.update_status("Connecting to board...")
        self.root.after(0, self._connect_after_startup)
    
    def _check_bootsel_silent(self):
        """Check BOOTSEL mode without showing message boxes"""
        try:
            import os
            script_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(script_dir)
            bootsel_script = os.path.join(project_root, 'tools', 'check_bootsel.ps1')
            
            result = subprocess.run(['powershell', '-ExecutionPolicy', 'Bypass', 
                                   '-File', bootsel_script], 
                                  capture_output=True, text=True, cwd=project_root)
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
            return None
        except Exception as e:
            self.log_to_console(f"Error checking BOOTSEL: {e}")
            return None
    
    def _flash_firmware(self):
        """Flash the console firmware using picotool"""
        try:
            self.log_to_console("Flashing firmware...")
            self.update_status("Flashing firmware...")
            
            import os
            script_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(script_dir)
            uf2_path = os.path.join(project_root, 'build', 'EVN_ALPHA_Performance.uf2')
            
            if not os.path.exists(uf2_path):
                self.log_to_console(f"UF2 not found at {uf2_path}")
                return False
            
            picotool_path = os.path.join(os.path.expanduser('~'), '.pico-sdk', 'picotool', '2.3.0', 'picotool', 'picotool.exe')
            if not os.path.exists(picotool_path):
                self.log_to_console("picotool not found")
                return False
            
            result = subprocess.run([picotool_path, 'load', uf2_path, '-fx'], 
                                  capture_output=True, text=True, cwd=project_root)
            
            if result.returncode == 0:
                self.log_to_console("Firmware flashed successfully")
                return True
            else:
                self.log_to_console(f"Flash failed: {result.stderr}")
                return False
        except Exception as e:
            self.log_to_console(f"Flash error: {e}")
            return False
    
    def _wait_for_cdc_port(self, timeout=30):
        """Wait for board to re-enumerate as CDC serial port after flashing"""
        self.log_to_console("Waiting for board to re-enumerate...")
        self.update_status("Waiting for board to re-enumerate...")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            cdc_port = self._find_cdc_port()
            if cdc_port:
                self.port_var.set(cdc_port)
                self.log_to_console(f"Board re-enumerated on {cdc_port}")
                return cdc_port
            time.sleep(1)
        
        self.log_to_console("Timeout waiting for CDC port")
        return None
    
    def _find_cdc_port(self):
        """Find the CDC serial port for the EVN board"""
        try:
            ports = serial.tools.list_ports.comports()
            for port in ports:
                # Look for Pico/RP2040 CDC device
                if 'Pico' in port.description or 'RP2040' in port.description or 'CDC' in port.description:
                    return port.device
                # Fallback: any USB serial device
                if 'USB' in port.description or 'Serial' in port.description:
                    return port.device
            return None
        except Exception:
            return None
    
    def _connect_after_startup(self):
        """Connect to serial port after startup sequence completes"""
        port = self.port_var.get()
        if port:
            self.log_to_console(f"Auto-connecting to {port}...")
            self.connect_serial()
        else:
            self.log_to_console("No port available for connection")
            self.update_status("No port available - please connect board")
    
    def _start_reconnect_timer(self):
        """Start a periodic timer to attempt reconnection"""
        if hasattr(self, '_reconnect_timer') and self._reconnect_timer:
            self.root.after_cancel(self._reconnect_timer)
        # Try to reconnect every 5 seconds
        self._reconnect_timer = self.root.after(5000, self._attempt_reconnect)
    
    def _attempt_reconnect(self):
        """Attempt to reconnect to the board"""
        if self.serial_running:
            return  # Already connected
        
        self.log_to_console("Attempting to reconnect...")
        self.update_status("Attempting to reconnect...")
        
        # First check for CDC port (console mode)
        cdc_port = self._find_cdc_port()
        if cdc_port:
            self.port_var.set(cdc_port)
            self.log_to_console(f"Found console mode on {cdc_port}")
            self.connect_serial()
            return
        
        # If not in console mode, check for BOOTSEL
        bootsel_port = self._check_bootsel_silent()
        if bootsel_port:
            self.log_to_console(f"Board in BOOTSEL mode on {bootsel_port} - flashing firmware...")
            self.update_status("Board in BOOTSEL - flashing firmware...")
            if self._flash_firmware():
                self._wait_for_cdc_port()
                self.root.after(0, self._connect_after_startup)
            return
        
        # Neither console nor BOOTSEL - schedule another attempt
        self.log_to_console("Board not found - will retry in 5 seconds")
        self.update_status("Board not found - retrying in 5s...")
        self._start_reconnect_timer()
    
    def toggle_connection(self):
        """Toggle serial connection"""
        if self.serial_running:
            self.disconnect_serial()
        else:
            self.connect_serial()
    
    def connect_serial(self):
        """Connect to serial port"""
        port = self.port_var.get()
        if not port:
            messagebox.showerror("Error", "Please select a serial port")
            return
        
        try:
            baud = 115200  # Pico only runs at 115200
            self.serial_port = serial.Serial(port, baudrate=baud, timeout=1)
            self.serial_running = True
            
            # Start serial reading thread
            self.serial_thread = threading.Thread(target=self.serial_read_loop, daemon=True)
            self.serial_thread.start()
            
            # Start heartbeat
            self.start_heartbeat()
            
            # Update UI
            self.connect_btn.config(text="Disconnect")
            self.connection_status.config(text="● Connected", style='Success.TLabel')
            self.log_to_console(f"Connected to {port} at {baud} baud")
            self.update_status(f"Connected to {port}")
            
            # Send initial heartbeat to wake up console
            self.send_heartbeat()
            
        except Exception as e:
            self.log_to_console(f"Failed to connect: {e}")
            messagebox.showerror("Connection Error", f"Failed to connect to {port}: {e}")
    
    def disconnect_serial(self):
        """Disconnect from serial port and attempt to reconnect"""
        self.serial_running = False
        self.heartbeat_running = False
        
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        
        # Update UI
        self.connect_btn.config(text="Connect")
        self.connection_status.config(text="● Disconnected - Reconnecting...", style='Warning.TLabel')
        self.log_to_console("Disconnected from serial port - attempting reconnect...")
        self.update_status("Disconnected - attempting reconnect...")
        
        # Start reconnection attempts
        self._start_reconnect_timer()
    
    def serial_read_loop(self):
        """Background thread to read from serial port"""
        buffer = ""
        while self.serial_running and self.serial_port and self.serial_port.is_open:
            try:
                if self.serial_port.in_waiting:
                    data = self.serial_port.read(self.serial_port.in_waiting).decode('utf-8', errors='ignore')
                    buffer += data
                    
                    # Process complete lines
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        line = line.strip()
                        if line:
                            self.serial_queue.put(('output', line))
                
                time.sleep(0.01)  # 10ms delay to prevent hogging CPU
            except Exception as e:
                if self.serial_running:
                    self.serial_queue.put(('error', f"Serial read error: {e}"))
                break
        
        # Signal thread end
        self.serial_queue.put(('disconnected', None))
    
    def process_serial_queue(self):
        """Process messages from serial queue and parse telemetry"""
        try:
            while True:
                msg_type, content = self.serial_queue.get_nowait()
                if msg_type == 'output':
                    self.log_to_console(content)
                    self.parse_console_output(content)
                elif msg_type == 'error':
                    self.log_to_console(content, 'error')
                elif msg_type == 'disconnected':
                    self.disconnect_serial()
                    break
        except queue.Empty:
            pass
    
    def parse_console_output(self, line):
        """Parse console output for telemetry data"""
        # Parse battery from heartbeat: "Battery: 7.432 V (cells 3.712 / 3.720)"
        batt_match = re.search(r'Battery:\s+([\d.]+)\s+V\s+\(cells\s+([\d.]+)\s*/\s*([\d.]+)\)', line)
        if batt_match:
            self.battery_voltage = float(batt_match.group(1))
            self.battery_cells = (float(batt_match.group(2)), float(batt_match.group(3)))
            self.root.after(0, self.update_battery_display)
            return
        
        # Parse button from heartbeat or status: "H alive" or "BUTTON: PRESSED/RELEASED"
        if 'BUTTON:' in line:
            self.button_state = 'PRESSED' in line
            self.root.after(0, self.update_button_display)
            return
        
        # Parse motor status from 'S' command:
        # "M1:  12.3 deg   45.6 d/s  tgt=  90  moving"
        motor_match = re.match(r'M(\d):\s+([-\d.]+)\s+deg\s+([-\d.]+)\s+d/s\s+tgt=([-\d.]+)\s+(\w+)?\s*(\w+)?', line)
        if motor_match:
            motor_idx = int(motor_match.group(1)) - 1
            self.motor_angles[motor_idx] = float(motor_match.group(2))
            self.motor_speeds[motor_idx] = float(motor_match.group(3))
            self.motor_targets[motor_idx] = float(motor_match.group(4))
            status_words = line.lower()
            self.motor_stalled[motor_idx] = 'stall' in status_words
            self.motor_done[motor_idx] = 'done' in status_words
            self.motor_moving[motor_idx] = 'moving' in status_words
            self.root.after(0, lambda: self.update_motor_display(motor_idx))
            return
        
        # Parse servo pulse from E command response: ">> Servo 1 pulse=1500 us"
        servo_match = re.match(r'>> Servo (\d) pulse=(\d+) us', line)
        if servo_match:
            servo_idx = int(servo_match.group(1)) - 1
            self.servo_pulses[servo_idx] = int(servo_match.group(2))
            self.root.after(0, lambda: self.update_servo_display(servo_idx))
            return
        
        # Parse LED response: ">> LED ON/OFF/TOGGLE"
        if line.startswith('>> LED'):
            if 'ON' in line and 'OFF' not in line and 'TOGGLE' not in line:
                self.led_state = True
            elif 'OFF' in line:
                self.led_state = False
            # TOGGLE - we don't know the new state, query again
            self.root.after(0, self.update_led_indicator)
            return
        
        # Parse I2C scan results
        # "Port X: N device(s)" or "  Found: 0xYY" or "  0xYY"
        i2c_port_match = re.match(r'Port (\d+):\s+(\d+)\s+device', line)
        if i2c_port_match:
            port = int(i2c_port_match.group(1))
            count = int(i2c_port_match.group(2))
            self.i2c_results.insert(tk.END, f"Port {port}: {count} device(s)\n")
            self.i2c_results.see(tk.END)
            return
        
        i2c_found_match = re.match(r'\s+(?:Found:)?\s*(0x[0-9A-Fa-f]{2})', line)
        if i2c_found_match:
            addr = i2c_found_match.group(1)
            self.i2c_results.insert(tk.END, f"  {addr}\n")
            self.i2c_results.see(tk.END)
            return
        
        i2c_scanning_match = re.match(r'Scanning (?:all \d+ |)I2C ports?\.?', line, re.IGNORECASE)
        if i2c_scanning_match:
            self.i2c_results.delete(1.0, tk.END)
            self.i2c_results.insert(tk.END, f"{line}\n")
            return
        
        i2c_port_scanning_match = re.match(r'Scanning I2C port (\d+)\.?', line, re.IGNORECASE)
        if i2c_port_scanning_match:
            port = int(i2c_port_scanning_match.group(1))
            self.i2c_results.delete(1.0, tk.END)
            self.i2c_results.insert(tk.END, f"Scanning I2C port {port}...\n")
            return
    
    def send_console_command(self, event=None):
        """Send command from console input"""
        command = self.console_input.get().strip()
        if command and self.serial_running:
            self.send_console_command_raw(command)
            self.console_input.delete(0, tk.END)
        elif not self.serial_running:
            messagebox.showwarning("Warning", "Not connected to serial port")
    
    def send_console_command_raw(self, command):
        """Send raw command to serial port"""
        if self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.write((command + '\r\n').encode('utf-8'))
                self.log_to_console(f"> {command}", 'command')
            except Exception as e:
                self.log_to_console(f"Send error: {e}", 'error')
    
    # Heartbeat methods
    def start_heartbeat(self):
        """Start heartbeat thread to keep console alive"""
        self.heartbeat_running = True
        self.heartbeat_thread = threading.Thread(target=self.heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()
    
    def heartbeat_loop(self):
        """Heartbeat loop - sends 'h' command every 5 seconds"""
        while self.heartbeat_running:
            time.sleep(5)
            if self.heartbeat_running and self.serial_running:
                self.send_heartbeat()
    
    def send_heartbeat(self):
        """Send heartbeat command"""
        self.send_console_command_raw("h")
    
    # LED control methods
    def set_led(self, state):
        """Set LED state via console 'L' command: 0=off, 1=on, 2=toggle"""
        cmd_val = 1 if state else 0
        self.send_console_command_raw(f"L {cmd_val}")
        # Don't update local state immediately - wait for console response
    
    def toggle_led(self):
        """Toggle LED state via console 'L 2' command"""
        self.send_console_command_raw("L 2")
    
    def update_led_indicator(self):
        """Update LED indicator in UI"""
        if self.led_state:
            self.led_indicator.config(text="● ON", foreground='#28a745')
            self.led_on_btn.config(state='disabled')
            self.led_off_btn.config(state='normal')
            self.led_toggle_btn.config(text="TOGGLE")
        else:
            self.led_indicator.config(text="● OFF", foreground='#6c757d')
            self.led_on_btn.config(state='normal')
            self.led_off_btn.config(state='disabled')
            self.led_toggle_btn.config(text="TOGGLE")
    
    # Motor control methods
    def move_motor(self, motor_index):
        """Move motor to target angle using relative move (compute delta from current)"""
        try:
            target_angle = float(getattr(self, f'motor{motor_index+1}_target_entry').get())
            current_angle = self.motor_angles[motor_index]
            delta = target_angle - current_angle
            # Use 'M' command: M motor delta_degs (relative move)
            self.send_console_command_raw(f"M {motor_index+1} {delta}")
            self.log_to_console(f"Moving Motor {motor_index+1} by {delta:.1f}° (to {target_angle:.1f}°)")
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid angle")
        except Exception as e:
            self.log_to_console(f"Error moving motor: {e}", 'error')
    
    def coast_motor(self, motor_index):
        """Coast motor (and all motors - 'c' command coasts all)"""
        self.send_console_command_raw("c")
        self.log_to_console(f"Coasting all motors")
    
    def hold_motor(self, motor_index):
        """Hold motor position - send move to current position (delta=0)"""
        self.send_console_command_raw(f"M {motor_index+1} 0")
        self.log_to_console(f"Holding Motor {motor_index+1} at current position")
    
    def set_motor_angle(self, motor_index, angle):
        """Set motor to specific angle (preset button)"""
        getattr(self, f'motor{motor_index+1}_target_entry').delete(0, tk.END)
        getattr(self, f'motor{motor_index+1}_target_entry').insert(0, str(angle))
        self.move_motor(motor_index)
    
    # Servo control methods - using pulse width in microseconds
    def set_servo_pulse(self, servo_index, pulse_us):
        """Set servo pulse width in microseconds via console 'E' command"""
        # Clamp to safe range
        pulse_us = max(200, min(2800, int(pulse_us)))
        self.send_console_command_raw(f"E {servo_index+1} {pulse_us}")
        self.log_to_console(f"Setting Servo {servo_index+1} to {pulse_us} us")
    
    def on_servo_slider_drag(self, servo_index, pulse_us):
        """Called during slider drag for live feedback (no console command until release)"""
        # Update display only, don't send command
        pulse_us = max(200, min(2800, int(pulse_us)))
        getattr(self, f'servo{servo_index+1}_pulse_display').config(text=f"{pulse_us} us")
    
    def set_servo_pulse_with_slider(self, servo_index, pulse_us):
        """Set servo pulse and update slider position (for preset buttons)"""
        pulse_us = max(200, min(2800, int(pulse_us)))
        self.send_console_command_raw(f"E {servo_index+1} {pulse_us}")
        self.log_to_console(f"Setting Servo {servo_index+1} to {pulse_us} us")
        # Update slider variable and display
        getattr(self, f'servo{servo_index+1}_slider_var').set(pulse_us)
        getattr(self, f'servo{servo_index+1}_pulse_display').config(text=f"{pulse_us} us")
    
    def set_servo_angle(self, servo_index, angle):
        """Set servo angle - converts to pulse width (for backward compatibility)"""
        # Convert angle to pulse width (0-180 -> 500-2500 us, typical servo range)
        pulse_us = 500 + (angle / 180.0) * 2000
        self.set_servo_pulse(servo_index, pulse_us)
    
    def disable_servo(self, servo_index):
        """Disable servo - not directly supported, set to center"""
        self.set_servo_pulse(servo_index, 1500)
        self.log_to_console(f"Servo {servo_index+1} centered (disable not directly supported)")
    
    def enable_servo(self, servo_index):
        """Enable servo - not directly supported"""
        self.log_to_console(f"Servo {servo_index+1} always enabled when PWM active")
    
    # I2C scanning methods - using console 'I' command
    def scan_i2c_bus(self):
        """Scan current I2C bus (port 16 for battery) via console 'I' command"""
        if not self.serial_running:
            messagebox.showwarning("Warning", "Not connected to serial port")
            return
        
        self.log_to_console("Starting I2C bus scan (port 16)...")
        self.update_status("Scanning I2C bus...")
        self.send_console_command_raw("I 16")
    
    def scan_all_i2c_ports(self):
        """Scan all I2C ports via console 'I' command"""
        if not self.serial_running:
            messagebox.showwarning("Warning", "Not connected to serial port")
            return
        
        self.log_to_console("Starting scan of all I2C ports...")
        self.update_status("Scanning all I2C ports...")
        self.send_console_command_raw("I")
    
    def scan_i2c_port(self):
        """Scan specific I2C port via console 'I' command"""
        if not self.serial_running:
            messagebox.showwarning("Warning", "Not connected to serial port")
            return
        
        port = self.i2c_port_var.get()
        self.log_to_console(f"Scanning I2C port {port}...")
        self.update_status(f"Scanning I2C port {port}...")
        self.send_console_command_raw(f"I {port}")
    
    # GUI update methods
    def update_gui(self):
        """Periodic GUI update"""
        # Process serial queue
        self.process_serial_queue()
        
        # Only update sensor displays when connected
        if self.serial_running:
            # Send periodic queries for telemetry
            self.send_periodic_queries()
            
            # Update displays with real data
            self.update_battery_display()
            self.update_button_display()
            self.update_all_motor_displays()
            self.update_all_servo_displays()
        else:
            # Show disconnected state
            self.show_disconnected_state()
        
        # Schedule next update
        self.root.after(100, self.update_gui)  # Update every 100ms
    
    def send_periodic_queries(self):
        """Send periodic queries to get fresh telemetry"""
        current_time = time.time()
        
        # Send heartbeat (h) every 2 seconds - gets battery + core1 status
        if current_time - self.last_heartbeat_response > 2:
            self.send_console_command_raw("h")
            self.last_heartbeat_response = current_time
        
        # Send status (S) every 500ms - gets motor angles, speeds, targets
        # Note: S command outputs all 4 motors at once
        if not hasattr(self, '_last_status_query'):
            self._last_status_query = 0
        if current_time - self._last_status_query > 0.5:
            self.send_console_command_raw("S")
            self._last_status_query = current_time
        
        # Send button query (y) every 1 second
        if not hasattr(self, '_last_button_query'):
            self._last_button_query = 0
        if current_time - self._last_button_query > 1:
            self.send_console_command_raw("y")
            self._last_button_query = current_time
        
        # Query servo pulses every 2 seconds
        if not hasattr(self, '_last_servo_query'):
            self._last_servo_query = 0
        if current_time - self._last_servo_query > 2:
            for i in range(4):
                self.send_console_command_raw(f"E {i+1} 0")  # Query current pulse
            self._last_servo_query = current_time
    
    def show_disconnected_state(self):
        """Show N/A for all sensor values when disconnected"""
        self.battery_label.config(text="--.-- V", foreground='#6c757d')
        self.battery_detail_label.config(text="Cell 1: --.-- V  |  Cell 2: --.-- V")
        self.button_indicator.config(text="● Unknown", foreground='#6c757d')
        
        for i in range(4):
            getattr(self, f'motor{i+1}_angle_label').config(text="--.--°")
            getattr(self, f'motor{i+1}_speed_label').config(text="--.--°/s")
            getattr(self, f'motor{i+1}_stall_label').config(text="● N/A", foreground='#6c757d')
            getattr(self, f'motor{i+1}_done_label').config(text="○ N/A", foreground='#6c757d')
            getattr(self, f'motor{i+1}_target_label').config(text="--.--°")
            getattr(self, f'servo{i+1}_pulse_label').config(text="---- us")
    
    def update_battery_display(self):
        """Update battery display with real data from console"""
        self.battery_label.config(text=f"{self.battery_voltage:.2f} V")
        self.battery_detail_label.config(
            text=f"Cell 1: {self.battery_cells[0]:.2f} V  |  Cell 2: {self.battery_cells[1]:.2f} V"
        )
        
        # Color code based on voltage
        if self.battery_voltage < 6.5:
            self.battery_label.config(foreground='#dc3545')  # Red - low
        elif self.battery_voltage < 7.0:
            self.battery_label.config(foreground='#ffc107')  # Yellow - medium
        else:
            self.battery_label.config(foreground='#28a745')  # Green - good
    
    def update_button_display(self):
        """Update button display with real data from console"""
        if self.button_state:
            self.button_indicator.config(text="● PRESSED", foreground='#dc3545')
        else:
            self.button_indicator.config(text="● Released", foreground='#28a745')
    
    def update_all_motor_displays(self):
        """Update all motor displays with real data from console"""
        for i in range(4):
            self.update_motor_display(i)
    
    def update_motor_display(self, motor_index):
        """Update single motor display with real data"""
        getattr(self, f'motor{motor_index+1}_angle_label').config(text=f"{self.motor_angles[motor_index]:.1f}°")
        getattr(self, f'motor{motor_index+1}_speed_label').config(text=f"{self.motor_speeds[motor_index]:.1f}°/s")
        getattr(self, f'motor{motor_index+1}_target_label').config(text=f"{self.motor_targets[motor_index]:.1f}°")
        
        # Update stall indicator
        stall_label = getattr(self, f'motor{motor_index+1}_stall_label')
        if self.motor_stalled[motor_index]:
            stall_label.config(text="● STALLED", foreground='#dc3545')
        else:
            stall_label.config(text="● OK", foreground='#28a745')
        
        # Update done/moving indicator
        done_label = getattr(self, f'motor{motor_index+1}_done_label')
        if self.motor_done[motor_index]:
            done_label.config(text="● DONE", foreground='#28a745')
        elif self.motor_moving[motor_index]:
            done_label.config(text="● MOVING", foreground='#17a2b8')
        else:
            done_label.config(text="○ IDLE", foreground='#6c757d')
        
        # Update coast/hold button states based on motor status
        coast_btn = getattr(self, f'motor{motor_index+1}_coast_btn', None)
        hold_btn = getattr(self, f'motor{motor_index+1}_hold_btn', None)
        
        # Coast is active when motor is idle (not moving, done, speed ~0)
        is_coasting = (abs(self.motor_speeds[motor_index]) < 1.0 and 
                      self.motor_done[motor_index] and 
                      not self.motor_moving[motor_index])
        
        # Hold is active when motor is done at target (position hold)
        is_holding = self.motor_done[motor_index] and not is_coasting
        
        if coast_btn:
            if is_coasting:
                coast_btn.configure(style='Accent.TButton')
            else:
                coast_btn.configure(style='TButton')
        
        if hold_btn:
            if is_holding:
                hold_btn.configure(style='Accent.TButton')
            else:
                hold_btn.configure(style='TButton')
    
    def update_all_servo_displays(self):
        """Update all servo displays with real data from console"""
        for i in range(4):
            self.update_servo_display(i)
    
    def update_servo_display(self, servo_index):
        """Update single servo display with real data"""
        getattr(self, f'servo{servo_index+1}_pulse_label').config(text=f"{self.servo_pulses[servo_index]} us")
    
    def on_closing(self):
        """Handle window close event"""
        if self.serial_running:
            if messagebox.askyesno("Exit", "Board is still connected. Disconnect and exit?"):
                self.final_quit()
        else:
            self.final_quit()
    
    def toggle_dark_mode(self):
        """Toggle dark/light mode for the dashboard"""
        is_dark = self.dark_mode_var.get()
        if is_dark:
            # Dark mode colors
            bg_color = '#1e1e1e'
            fg_color = '#d4d4d4'
            frame_bg = '#252526'
            accent_bg = '#0e639c'
            accent_active = '#1177bb'
            text_color = '#ffffff'
            disabled_fg = '#808080'
            border_color = '#3e3e42'
        else:
            # Light mode colors (default)
            bg_color = '#f8f9fa'
            fg_color = '#212529'
            frame_bg = '#ffffff'
            accent_bg = '#0d6efd'
            accent_active = '#0b5ed7'
            text_color = '#212529'
            disabled_fg = '#6c757d'
            border_color = '#dee2e6'
        
        style = ttk.Style()
        
        # Configure base styles
        style.configure('TFrame', background=bg_color)
        style.configure('TLabel', background=bg_color, foreground=fg_color)
        style.configure('TLabelFrame', background=bg_color)
        style.configure('TLabelFrame.Label', background=bg_color, foreground=fg_color)
        style.configure('TButton', background=frame_bg, foreground=fg_color)
        style.map('TButton', 
                 background=[('active', accent_bg), ('pressed', accent_active)],
                 foreground=[('active', text_color), ('pressed', text_color)])
        style.configure('TNotebook', background=bg_color, borderwidth=0)
        style.configure('TNotebook.Tab', background=frame_bg, foreground=fg_color, padding=[20, 8])
        style.map('TNotebook.Tab', 
                 background=[('selected', accent_bg), ('active', '#e2e6ea')],
                 foreground=[('selected', text_color), ('active', fg_color)])
        style.configure('TCombobox', fieldbackground=frame_bg, background=frame_bg, foreground=fg_color)
        style.configure('TEntry', fieldbackground=frame_bg, foreground=fg_color)
        style.configure('TCheckbutton', background=bg_color, foreground=fg_color)
        style.configure('TSpinbox', fieldbackground=frame_bg, foreground=fg_color)
        style.configure('TScale', background=bg_color)
        style.configure('Horizontal.TScale', background=bg_color)
        style.configure('Vertical.TScale', background=bg_color)
        style.configure('TScrollbar', background=frame_bg, troughcolor=bg_color, bordercolor=bg_color, arrowcolor=fg_color)
        
        # Status styles
        style.configure('Status.TLabel', background=bg_color, foreground=disabled_fg)
        style.configure('Success.TLabel', foreground='#28a745')
        style.configure('Warning.TLabel', foreground='#ffc107')
        style.configure('Error.TLabel', foreground='#dc3545')
        style.configure('Info.TLabel', foreground='#17a2b8')
        style.configure('Header.TLabel', background=bg_color, foreground=fg_color, font=('Segoe UI', 10, 'bold'))
        
        # Accent button
        style.configure('Accent.TButton', font=('Segoe UI', 9, 'bold'), padding=8, 
                       foreground='white', background='#dc3545')
        style.map('Accent.TButton', 
                 background=[('active', '#c82333'), ('pressed', '#bd2130')],
                 foreground=[('active', 'white'), ('pressed', 'white')])
        
        # Update status bar frame
        self.status_bar_frame.configure(style='TFrame')
        self.status_bar.configure(background=frame_bg, foreground=fg_color)
        self.status_connection.configure(background=frame_bg)
        
        # Update root window
        self.root.configure(background=bg_color)
        
        # Update all frames recursively
        self._update_widget_colors(self.root, bg_color, fg_color, frame_bg, disabled_fg)
        
        # Update console output colors
        if hasattr(self, 'console_output'):
            self.console_output.configure(bg=frame_bg, fg=fg_color, insertbackground=fg_color)
        
        # Update I2C results
        if hasattr(self, 'i2c_results'):
            self.i2c_results.configure(bg=frame_bg, fg=fg_color, insertbackground=fg_color)
    
    def _update_widget_colors(self, widget, bg_color, fg_color, frame_bg, disabled_fg):
        """Recursively update widget colors for dark mode"""
        try:
            widget_class = widget.winfo_class()
            if widget_class in ('Frame', 'Labelframe', 'TFrame', 'TLabelframe'):
                widget.configure(background=bg_color)
            elif widget_class in ('Label', 'TLabel'):
                widget.configure(background=bg_color, foreground=fg_color)
            elif widget_class in ('Button', 'TButton'):
                widget.configure(background=frame_bg, foreground=fg_color)
            elif widget_class in ('Entry', 'TEntry'):
                widget.configure(background=frame_bg, foreground=fg_color, insertbackground=fg_color)
            elif widget_class in ('Text', 'ScrolledText'):
                widget.configure(background=frame_bg, foreground=fg_color, insertbackground=fg_color)
            elif widget_class in ('Canvas',):
                widget.configure(background=bg_color)
        except:
            pass
        
        # Recurse into children
        for child in widget.winfo_children():
            self._update_widget_colors(child, bg_color, fg_color, frame_bg, disabled_fg)
    
    def quit_and_reboot(self):
        """Quit application and reboot board to UF2 mode"""
        if messagebox.askyesno("Quit & Reboot", 
                              "This will send the board back to BOOTSEL mode and exit the application.\n\nContinue?"):
            self.log_to_console("Sending reboot to BOOTSEL command...")
            if self.serial_running:
                self.send_console_command_raw("R")  # Reset to BOOTSEL
                # Wait a bit for command to be sent
                self.root.after(1000, self.final_quit)
            else:
                self.final_quit()
    
    def final_quit(self):
        """Final cleanup and quit"""
        self.disconnect_serial()
        self.root.quit()
        self.root.destroy()

def main():
    """Main entry point"""
    root = tk.Tk()
    
    # Set application icon if available
    try:
        # Try to set icon (optional)
        root.iconbitmap(default='evn_icon.ico')
    except:
        pass  # Icon not found, continue without
    
    app = EVNDashboard(root)
    
    # Refresh ports on startup
    app.refresh_ports()
    
    # Start the GUI
    root.mainloop()

if __name__ == "__main__":
    main()