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
import os
import sys
import time

try:
    import serial
except ImportError:
    sys.exit("pyserial not installed. Run: pip install -r tools/requirements.txt")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import find_board_port  # noqa: E402

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
    # stdout may be a legacy-codepage console (cp1252) that can't encode UTF-8
    # glyphs (e.g. '→'). Write bytes through the buffer, falling back to
    # ASCII-safe replacement so a stray glyph never kills the capture.
    out_stream = getattr(sys.stdout, "buffer", None)
    while time.time() - t0 < args.time:
        chunk = ser.read(4096)
        if chunk:
            txt = chunk.decode("utf-8", errors="replace")
            buf.append(txt)
            try:
                if out_stream is not None:
                    out_stream.write(chunk)
                    out_stream.flush()
                else:
                    sys.stdout.write(txt.encode("ascii", "replace").decode())
                    sys.stdout.flush()
            except (UnicodeEncodeError, OSError):
                pass  # never let a console encoding issue abort capture
    ser.close()

    out = "".join(buf)
    if args.expect and args.expect not in out:
        print(f"\n[serial_capture] FAIL: expected '{args.expect}' not seen", file=sys.stderr)
        sys.exit(1)
    print(f"\n[serial_capture] done ({len(out)} bytes)", file=sys.stderr)

if __name__ == "__main__":
    main()
