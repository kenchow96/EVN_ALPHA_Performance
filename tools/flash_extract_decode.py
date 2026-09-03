#!/usr/bin/env python3
"""
EVN ALPHA flash-extract-decode automation.

One command to:
1. Build autonomous firmware (EVN_AUTONOMOUS_TUNING=1)
2. Flash via picotool
3. Wait for BOOTSEL drive to appear (using PowerShell WMI event)
4. Extract tuning flash region via picotool save
5. Decode with decode_tuning_flash.py
6. Print summary table of results

Usage:
    python tools/flash_extract_decode.py [--output-dir bench/results/run_name]
    python tools/flash_extract_decode.py --no-build --port COM7  # if already built
"""

import argparse
import os
import subprocess
import sys
import time
import json
from pathlib import Path
from datetime import datetime

REPO_ROOT = Path(__file__).parent.parent
BUILD_DIR = REPO_ROOT / "build"
TOOLS_DIR = REPO_ROOT / "tools"
RESULTS_DIR = REPO_ROOT / "bench" / "results"

# UF2 flash region for tuning log
FLASH_REGION_START = 0x10F00000
FLASH_REGION_END = 0x10FF0000

# picotool paths
PICOTOOL = Path(os.environ.get("USERPROFILE", "")) / ".pico-sdk" / "picotool" / "2.3.0" / "picotool" / "picotool.exe"
NINJA = Path(os.environ.get("USERPROFILE", "")) / ".pico-sdk" / "ninja" / "v1.13.2" / "ninja.exe"


def run_cmd(cmd, cwd=None, capture=True, timeout=60, check=True, shell=False):
    """Run command and return (returncode, stdout, stderr)."""
    print(f"[flash_extract] $ {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    try:
        result = subprocess.run(
            cmd, cwd=cwd or REPO_ROOT, capture_output=capture,
            text=True, timeout=timeout, shell=shell
        )
        if capture and result.stdout:
            print(result.stdout.strip())
        if capture and result.stderr:
            print(result.stderr.strip(), file=sys.stderr)
        if check and result.returncode != 0:
            print(f"[flash_extract] ERROR: command failed with code {result.returncode}", file=sys.stderr)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        print(f"[flash_extract] ERROR: command timed out after {timeout}s", file=sys.stderr)
        return -1, "", "timeout"


def wait_for_bootsel_drive(timeout_s=60):
    """Wait for BOOTSEL drive to appear using PowerShell WMI event subscription.
    Returns the drive letter (e.g., 'D:') or None on timeout."""
    
    print(f"[flash_extract] Waiting for BOOTSEL drive (timeout {timeout_s}s)...")
    
    # PowerShell script to wait for drive insertion
    ps_script = f"""
$Query = "SELECT * FROM Win32_VolumeChangeEvent WHERE EventType = 2"
$action = {{
    $DriveLetter = $EventArgs.NewEvent.DriveName
    $vol = Get-WmiObject -Query "SELECT * FROM Win32_LogicalDisk WHERE DeviceID = '$DriveLetter'"
    if ($vol.VolumeName -eq 'RP2350' -or $vol.VolumeName -eq 'RPI-RP2') {{
        Write-Output $DriveLetter
        Unregister-Event -SourceIdentifier "BootSelDriveEvent" -Force
    }}
}}
Register-CimIndicationEvent -Query $Query -SourceIdentifier "BootSelDriveEvent" -Action $action
Write-Host "Listening for RP2040 BOOTSEL drive..."
$timer = [System.Diagnostics.Stopwatch]::StartNew()
while ($timer.Elapsed.TotalSeconds -lt {timeout_s}) {{
    Start-Sleep -Milliseconds 500
}}
Unregister-Event -SourceIdentifier "BootSelDriveEvent" -Force -ErrorAction SilentlyContinue
Write-Host "TIMEOUT"
"""
    
    # Write PS script to temp file
    ps_file = REPO_ROOT / "tools" / "_wait_bootsel.ps1"
    ps_file.write_text(ps_script, encoding="utf-8")
    
    try:
        # Run PowerShell
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps_file)],
            capture_output=True, text=True, timeout=timeout_s + 10
        )
        
        output = result.stdout.strip()
        print(f"[flash_extract] PowerShell output: {output}")
        
        # Parse output for drive letter
        for line in output.splitlines():
            line = line.strip()
            if line and ":" in line and len(line) <= 3:
                # Found drive letter like "D:"
                return line
        
        return None
    finally:
        if ps_file.exists():
            ps_file.unlink()


def build_autonomous():
    """Build autonomous firmware (EVN_AUTONOMOUS_TUNING=1)."""
    print("[flash_extract] Building autonomous firmware...")
    
    # Modify CMakeLists.txt to set EVN_AUTONOMOUS_TUNING=1
    cmake_file = REPO_ROOT / "CMakeLists.txt"
    content = cmake_file.read_text()
    
    # Replace EVN_AUTONOMOUS_TUNING=0 with =1
    if "EVN_AUTONOMOUS_TUNING=0" in content:
        content = content.replace("EVN_AUTONOMOUS_TUNING=0", "EVN_AUTONOMOUS_TUNING=1")
        cmake_file.write_text(content)
        print("[flash_extract] Set EVN_AUTONOMOUS_TUNING=1 in CMakeLists.txt")
    
    # Build
    rc, _, _ = run_cmd([str(NINJA), "-C", str(BUILD_DIR)], timeout=120)
    if rc != 0:
        print("[flash_extract] Build failed", file=sys.stderr)
        return False
    
    uf2_path = BUILD_DIR / "EVN_ALPHA_Performance.uf2"
    if not uf2_path.exists():
        print("[flash_extract] UF2 not found after build", file=sys.stderr)
        return False
    
    print(f"[flash_extract] Built: {uf2_path}")
    return True


def flash_uf2(uf2_path):
    """Flash UF2 via picotool."""
    print(f"[flash_extract] Flashing {uf2_path}...")
    rc, _, _ = run_cmd([str(PICOTOOL), "load", "-f", str(uf2_path), "-x"], timeout=60)
    return rc == 0


def extract_flash(output_dir, drive_letter=None):
    """Extract tuning flash region via picotool save."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    uf2_output = output_dir / "tuning.uf2"
    
    # picotool save doesn't need -d if only one RP2040
    cmd = [str(PICOTOOL), "save", "-r", f"0x{FLASH_REGION_START:08X}", f"0x{FLASH_REGION_END:08X}", "-f", str(uf2_output)]
    print(f"[flash_extract] Extracting flash to {uf2_output}...")
    
    rc, _, _ = run_cmd(cmd, timeout=60)
    if rc != 0:
        print("[flash_extract] Flash extraction failed", file=sys.stderr)
        return None
    
    if not uf2_output.exists() or uf2_output.stat().st_size == 0:
        print("[flash_extract] Extracted file is empty", file=sys.stderr)
        return None
    
    print(f"[flash_extract] Extracted {uf2_output.stat().st_size} bytes")
    return uf2_output


def decode_flash(uf2_path, output_dir):
    """Decode extracted flash using decode_tuning_flash.py."""
    output_dir = Path(output_dir)
    print(f"[flash_extract] Decoding {uf2_path}...")
    
    rc, stdout, stderr = run_cmd([
        sys.executable, str(TOOLS_DIR / "decode_tuning_flash.py"),
        str(uf2_path), "--output", str(output_dir)
    ], timeout=60)
    
    if rc != 0:
        print("[flash_extract] Decode failed", file=sys.stderr)
        return None
    
    # Look for summary.csv
    summary_path = output_dir / "summary.csv"
    if summary_path.exists():
        print(f"[flash_extract] Summary: {summary_path}")
        return summary_path
    
    return None


def print_summary(summary_path):
    """Print a nice summary table from summary.csv."""
    import csv
    
    with open(summary_path, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    if not rows:
        print("[flash_extract] No results in summary")
        return
    
    print("\n" + "=" * 100)
    print("AUTONOMOUS TUNING RESULTS SUMMARY")
    print("=" * 100)
    print(f"{'Case':>4} {'Axis':>4} {'Status':>10} {'Delta':>8} {'Vmax':>8} {'Accel':>8} {'KP':>10} {'KV':>10} {'Endpoint KP':>12} {'Accel Scale':>10} {'Score':>8}")
    print("-" * 100)
    
    for row in rows:
        status = "PASS" if row.get('status') == '1' else "FAIL"
        print(f"{row.get('case_index', '?'):>4} {row.get('axis', '?'):>4} {status:>10} "
              f"{float(row.get('delta_mdeg', 0))/1000:>8.1f} "
              f"{float(row.get('vmax_mdegs', 0))/1000:>8.1f} "
              f"{float(row.get('accel_mdegs2', 0))/1000:>8.1f} "
              f"{float(row.get('kp', 0)):>10.2e} "
              f"{float(row.get('kv', 0)):>10.2e} "
              f"{float(row.get('endpoint_kp_vel', 0)):>12.2e} "
              f"{float(row.get('accel_scale', 0)):>10.2f} "
              f"{float(row.get('score', 0)):>8.2f}")
    
    # Count passes
    passes = sum(1 for r in rows if r.get('status') == '1')
    total = len(rows)
    print(f"\nTotal: {passes}/{total} PASS")
    print("=" * 100)


def restore_console_build():
    """Restore CMakeLists.txt to console build (EVN_AUTONOMOUS_TUNING=0)."""
    cmake_file = REPO_ROOT / "CMakeLists.txt"
    content = cmake_file.read_text()
    
    if "EVN_AUTONOMOUS_TUNING=1" in content:
        content = content.replace("EVN_AUTONOMOUS_TUNING=1", "EVN_AUTONOMOUS_TUNING=0")
        cmake_file.write_text(content)
        print("[flash_extract] Restored EVN_AUTONOMOUS_TUNING=0 in CMakeLists.txt")
        
        # Rebuild console
        print("[flash_extract] Rebuilding console firmware...")
        rc, _, _ = run_cmd([str(NINJA), "-C", str(BUILD_DIR)], timeout=120)
        if rc == 0:
            print("[flash_extract] Console firmware rebuilt successfully")
        else:
            print("[flash_extract] WARNING: Console rebuild failed", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(description="Flash autonomous, extract tuning log, decode, and summarize")
    ap.add_argument("--output-dir", default=None, help="Output directory (default: bench/results/auto_YYYYMMDD_HHMMSS)")
    ap.add_argument("--no-build", action="store_true", help="Skip build step (use existing UF2)")
    ap.add_argument("--no-restore", action="store_true", help="Don't restore console build after")
    ap.add_argument("--timeout", type=int, default=120, help="BOOTSEL wait timeout (seconds)")
    args = ap.parse_args()
    
    # Determine output directory
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = RESULTS_DIR / f"autonomous_auto_{timestamp}"
    
    print(f"[flash_extract] Output directory: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Step 1: Build (unless --no-build)
        if not args.no_build:
            if not build_autonomous():
                return 1
        
        uf2_path = BUILD_DIR / "EVN_ALPHA_Performance.uf2"
        if not uf2_path.exists():
            print("[flash_extract] UF2 not found", file=sys.stderr)
            return 1
        
        # Step 2: Flash
        print("[flash_extract] Please ensure board is in BOOTSEL mode (hold BOOTSEL while plugging in)")
        print("[flash_extract] Or if running autonomous firmware, it will reboot to BOOTSEL on completion")
        
        if not flash_uf2(uf2_path):
            return 1
        
        # Step 3: Wait for BOOTSEL drive
        drive = wait_for_bootsel_drive(args.timeout)
        if not drive:
            print("[flash_extract] BOOTSEL drive not detected within timeout", file=sys.stderr)
            return 1
        
        print(f"[flash_extract] BOOTSEL drive detected: {drive}")
        
        # Step 4: Extract flash
        time.sleep(1.0)  # Give drive time to settle
        extracted = extract_flash(output_dir)
        if not extracted:
            return 1
        
        # Step 5: Decode
        summary = decode_flash(extracted, output_dir)
        if not summary:
            return 1
        
        # Step 6: Print summary
        print_summary(summary)
        
        print(f"\n[flash_extract] Complete! Results in: {output_dir}")
        
        # Step 7: Restore console build
        if not args.no_restore:
            restore_console_build()
            print("[flash_extract] Console firmware ready. Power cycle board and flash console.")
        
        return 0
        
    except KeyboardInterrupt:
        print("\n[flash_extract] Interrupted")
        return 130
    except Exception as e:
        print(f"[flash_extract] ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())