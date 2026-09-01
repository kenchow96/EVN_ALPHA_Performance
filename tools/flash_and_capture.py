#!/usr/bin/env python3
"""EVN ALPHA flash + capture wrapper.

One command replaces the error-prone flash -> sleep -> find-port -> capture
sequence that kept racing USB re-enumeration. Flashes the built UF2 with
picotool, robustly waits for the board's COM port to appear (and stabilise),
optionally sends a start character, then captures serial output.

Usage:
    python tools/flash_and_capture.py [--uf2 path] [--time 30] [--send s]
                                      [--expect "substr"] [--no-flash]
                                      [--baud 115200]

Exit codes: 0 = success (and --expect matched if given)
            1 = flash failed / port never appeared / --expect not seen
"""
import argparse
import os
import subprocess
import sys
import time

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    sys.exit("pyserial not installed. Run: pip install pyserial")

PICOTOOL = os.path.expandvars(
    r"%USERPROFILE%\.pico-sdk\picotool\2.3.0\picotool\picotool.exe")
RP2040_VID = 0x2E8A

def find_port():
    for p in list_ports.comports():
        if p.vid == RP2040_VID:
            return p.device
    return None

def wait_for_port_open(baud, timeout_s=25.0, stable_s=0.75, settle_s=1.0):
    """Wait for stable enumeration, then return a validated held handle+bytes.

    Picotool can return while the old COM instance is still disappearing. Wait
    until one port identity remains continuously present, open it once, and
    actively read through the settle interval so a reset is detected. Bytes
    consumed during validation are returned for the boot-banner acceptance gate.
    """
    deadline = time.time() + timeout_s
    stable_port = None
    stable_since = 0.0
    while time.time() < deadline:
        port = find_port()
        if port != stable_port:
            stable_port = port
            stable_since = time.time()
        if port and time.time() - stable_since >= stable_s:
            ser = None
            try:
                ser = serial.Serial(port, baud, timeout=0.05)
                # Pico stdio's connected predicate is DTR-based. Force a real
                # control-line transition; Windows does not reliably emit one
                # merely because pyserial opened with its default True state.
                ser.dtr = False
                time.sleep(0.05)
                ser.dtr = True
                warmup = []
                settle_deadline = time.time() + settle_s
                while time.time() < settle_deadline:
                    chunk = ser.read(4096)
                    if chunk:
                        warmup.append(chunk)
                return ser, b"".join(warmup)
            except (serial.SerialException, OSError):
                if ser is not None:
                    ser.close()
                stable_port = None
                stable_since = 0.0
        time.sleep(0.1)
    return None

def flash(uf2):
    if not os.path.exists(uf2):
        print(f"ERROR: UF2 not found: {uf2}", file=sys.stderr)
        return False
    print(f"[flash] {uf2}", file=sys.stderr)
    r = subprocess.run([PICOTOOL, "load", "-f", uf2, "-x"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f"ERROR: picotool failed:\n{r.stdout}\n{r.stderr}", file=sys.stderr)
        return False
    print("[flash] done, board rebooted", file=sys.stderr)
    return True

def capture(ser, seconds, send, expect, logpath, initial=b""):
    """Capture on an already-open, held serial handle."""
    print(f"[capture] {ser.port} @ {ser.baudrate} for {seconds}s", file=sys.stderr)
    buf = [initial] if initial else []
    t0 = time.time()
    if send:
        ser.write(send.encode() + b"\n")
    out = getattr(sys.stdout, "buffer", None)
    if initial:
        if out is not None:
            out.write(initial); out.flush()
        else:
            sys.stdout.write(initial.decode("utf-8", "replace")); sys.stdout.flush()
    while time.time() - t0 < seconds:
        chunk = ser.read(4096)
        if chunk:
            buf.append(chunk)
            try:
                if out is not None:
                    out.write(chunk); out.flush()
                else:
                    sys.stdout.write(chunk.decode("utf-8", "replace")); sys.stdout.flush()
            except (UnicodeEncodeError, OSError):
                pass
    ser.close()

    raw = b"".join(buf)
    text = raw.decode("utf-8", "replace")

    if logpath:
        os.makedirs(os.path.dirname(logpath) or ".", exist_ok=True)
        with open(logpath, "wb") as f:
            f.write(raw)
        print(f"[capture] logged {len(raw)} bytes -> {logpath}", file=sys.stderr)

    if expect and expect not in text:
        print(f"\n[capture] FAIL: expected '{expect}' not seen", file=sys.stderr)
        return 1
    print(f"\n[capture] done ({len(text)} bytes)", file=sys.stderr)
    return 0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uf2", default=r"build\EVN_ALPHA_Performance.uf2")
    ap.add_argument("--time", type=float, default=30.0)
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--send", default=None)
    ap.add_argument("--expect", default=None)
    ap.add_argument("--log", default=None, help="write raw capture to this file (e.g. bench/results/x.txt)")
    ap.add_argument("--no-flash", action="store_true")
    args = ap.parse_args()

    if not args.no_flash:
        if not flash(args.uf2):
            return 1
        # Picotool can return before Windows removes the pre-reset COM object.
        # Do not open anything during that stale-instance window.
        time.sleep(2.0)

    opened = wait_for_port_open(args.baud)
    if opened is None:
        print("ERROR: board COM port never appeared/openable", file=sys.stderr)
        return 1
    ser, initial = opened
    print(f"[capture] board on {ser.port}", file=sys.stderr)

    return capture(ser, args.time, args.send, args.expect, args.log, initial)

if __name__ == "__main__":
    sys.exit(main())
