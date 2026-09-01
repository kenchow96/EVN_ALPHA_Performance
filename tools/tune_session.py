#!/usr/bin/env python3
"""EVN ALPHA persistent tuning session.

Holds the board's COM port OPEN for the whole session (no per-command reconnect,
which was wedging TinyUSB). Reads a command queue file, executes each command,
and appends the resulting telemetry to a results log. Runs until the queue file
contains the line "QUIT".

The agent drives it by appending commands to the queue file:
    echo "q"   >> bench/results/cmd.txt     (then poll the out log)

Usage:
    python tools/tune_session.py [--port COM7]
State files (created under bench/results/):
    cmd.txt   - command queue (one command per line, consumed top-down)
    out.txt   - full serial transcript
    done.txt  - marker lines "DONE <cmd>" written after each command's capture
"""
import argparse
import os
import sys
import time

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    sys.exit("pyserial not installed")

RP2040_VID = 0x2E8A
RESULTS = os.path.join("bench", "results")
CMD = os.path.join(RESULTS, "cmd.txt")
OUT = os.path.join(RESULTS, "out.txt")
DONE = os.path.join(RESULTS, "done.txt")

def find_port():
    for p in list_ports.comports():
        if p.vid == RP2040_VID:
            return p.device
    return None

def open_board(baud=115200, timeout_s=30):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        port = find_port()
        if port:
            try:
                s = serial.Serial(port, baud, timeout=0.1)
                time.sleep(1.0)
                return s
            except (serial.SerialException, OSError):
                time.sleep(0.4)
        else:
            time.sleep(0.3)
    return None

def drain(ser, out_f, seconds):
    """Read for `seconds`, appending to transcript and echoing."""
    t0 = time.time()
    while time.time() - t0 < seconds:
        chunk = ser.read(4096)
        if chunk:
            txt = chunk.decode("utf-8", "replace")
            out_f.write(txt)
            out_f.flush()
            sys.stdout.write(txt.encode("ascii", "replace").decode())
            sys.stdout.flush()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default=None)
    args = ap.parse_args()

    os.makedirs(RESULTS, exist_ok=True)
    # fresh queue
    for f in (CMD, DONE):
        if os.path.exists(f):
            os.remove(f)
    open(CMD, "a").close()

    ser = open_board()
    if ser is None:
        sys.exit("ERROR: board not found")
    print(f"[session] open on {ser.port}. Drop commands into {CMD}", file=sys.stderr)

    out_f = open(OUT, "a", encoding="utf-8", errors="replace")
    done_f = open(DONE, "a", encoding="utf-8", errors="replace")

    # consume banner
    drain(ser, out_f, 2.0)

    processed = 0
    while True:
        with open(CMD, "r") as cf:
            lines = [l.strip() for l in cf if l.strip()]
        if processed < len(lines):
            cmd = lines[processed]
            processed += 1
            if cmd.upper() == "QUIT":
                break
            print(f"[session] >> {cmd}", file=sys.stderr)
            ser.write(cmd.encode() + b"\n")
            # capture the response for a bounded window (enough for a move + settle)
            drain(ser, out_f, 3.0)
            done_f.write(f"DONE {cmd}\n")
            done_f.flush()
        else:
            # idle: keep draining any async telemetry
            drain(ser, out_f, 0.3)

    # safety: coast all before closing
    try:
        ser.write(b"c\n")
        drain(ser, out_f, 1.0)
    except Exception:
        pass
    ser.close()
    print("[session] closed (motors coasted)", file=sys.stderr)

if __name__ == "__main__":
    main()
