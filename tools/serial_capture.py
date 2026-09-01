#!/usr/bin/env python3
"""EVN ALPHA serial capture tool.

Reads the board's USB-CDC serial output so the agent can verify firmware
behavior without asking the user to open a serial monitor.

Usage:
    python tools/serial_capture.py [--port COMx] [--baud 115200] [--time 5]
                                   [--send "cmd"] [--expect "substring"]

Exits 0 and prints captured text; --expect exits 1 if substring not seen.
"""
import argparse
import sys
import time

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    sys.exit("pyserial not installed. Run: pip install pyserial")

def find_board_port():
    """Auto-detect the EVN ALPHA (RP2040 USB-CDC) COM port."""
    for p in list_ports.comports():
        # RP2040 USB-CDC VID:PID = 2E8A:000A (stdio) or 2E8A:0003 (TinyUSB)
        if p.vid == 0x2E8A:
            return p.device
    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default=None, help="COM port (auto-detect if omitted)")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--time", type=float, default=5.0, help="capture seconds")
    ap.add_argument("--send", default=None, help="string to send on connect")
    ap.add_argument("--expect", default=None, help="substring that must appear")
    args = ap.parse_args()

    port = args.port or find_board_port()
    if not port:
        sys.exit("ERROR: no RP2040 board found on any COM port")

    print(f"[serial_capture] {port} @ {args.baud} for {args.time}s", file=sys.stderr)
    try:
        ser = serial.Serial(port, args.baud, timeout=0.2)
    except serial.SerialException as e:
        sys.exit(f"ERROR opening {port}: {e}")

    buf = []
    t0 = time.time()
    if args.send:
        ser.write(args.send.encode() + b"\n")
    while time.time() - t0 < args.time:
        chunk = ser.read(4096)
        if chunk:
            txt = chunk.decode("utf-8", errors="replace")
            buf.append(txt)
            sys.stdout.write(txt)
            sys.stdout.flush()
    ser.close()

    out = "".join(buf)
    if args.expect and args.expect not in out:
        print(f"\n[serial_capture] FAIL: expected '{args.expect}' not seen", file=sys.stderr)
        sys.exit(1)
    print(f"\n[serial_capture] done ({len(out)} bytes)", file=sys.stderr)

if __name__ == "__main__":
    main()
