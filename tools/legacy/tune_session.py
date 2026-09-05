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
    python tools/tune_session.py --command "c" --command "t 1" \
        --command "@5 M 1 90" --command "@30 d"
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
                # write_timeout=0 -> writes never block (drop if TX busy), so a
                # saturated RX path can never wedge the host with a WriteTimeout
                s = serial.Serial(port, baud, timeout=0.02, write_timeout=0)
                time.sleep(1.0)
                return s
            except (serial.SerialException, OSError):
                time.sleep(0.4)
        else:
            time.sleep(0.3)
    return None

def drain(ser, out_f, seconds, expect=None):
    """Read for `seconds`, appending to transcript and echoing. Small reads +
    short timeout keep the device RX polled so the host never times out a write
    mid-dump (which was the wedge source). Return whether `expect` was seen."""
    t0 = time.time()
    expected = [expect] if isinstance(expect, str) else list(expect or [])
    expected_index = 0
    received = ""
    while time.time() - t0 < seconds:
        try:
            chunk = ser.read(1024)
        except serial.SerialException:
            raise   # propagate so the session can exit cleanly
        if chunk:
            txt = chunk.decode("utf-8", "replace")
            out_f.write(txt)
            out_f.flush()
            sys.stdout.write(txt.encode("ascii", "replace").decode())
            sys.stdout.flush()
            if expected:
                received += txt
                while expected_index < len(expected):
                    marker = expected[expected_index]
                    marker_at = received.find(marker)
                    if marker_at < 0:
                        received = received[-max(1, len(marker) - 1):]
                        break
                    received = received[marker_at + len(marker):]
                    expected_index += 1
                    if expected_index == len(expected):
                        return True
    return not expected

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default=None)
    ap.add_argument("--command", action="append", default=[],
                    help="run a batch command; repeat for a complete session")
    args = ap.parse_args()

    os.makedirs(RESULTS, exist_ok=True)
    # fresh queue
    for f in (CMD, DONE):
        if os.path.exists(f):
            os.remove(f)
    with open(CMD, "w", encoding="utf-8") as cmd_f:
        for command in args.command:
            cmd_f.write(command + "\n")
        if args.command:
            cmd_f.write("QUIT\n")

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
            # optional drain-time prefix: "@12 d" -> capture for 12 s
            drain_s = 3.0
            if cmd.startswith("@"):
                head, _, rest = cmd.partition(" ")
                try:
                    drain_s = float(head[1:])
                    cmd = rest.strip()
                except ValueError:
                    pass
            print(f"[session] >> {cmd} (drain {drain_s:g}s)", file=sys.stderr)
            try:
                ser.reset_input_buffer()
                ser.write(cmd.encode() + b"\n")
                ser.flush()
                # A trace is a framed transaction. Never send another command
                # or close CDC until the device has emitted the closing marker.
                if cmd.split(maxsplit=1)[0] == "d":
                    if not drain(ser, out_f, max(drain_s, 30.0),
                                 expect=("TRACE BEGIN", "TRACE END\n")):
                        print("[session] ERROR: trace did not reach TRACE END", file=sys.stderr)
                        break
                else:
                    drain(ser, out_f, drain_s)
            except (serial.SerialException, serial.SerialTimeoutException, OSError) as e:
                print(f"[session] serial error, ending session: {e}", file=sys.stderr)
                break
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
