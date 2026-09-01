#!/usr/bin/env python3
"""Send one command to a running tune_session.py and print the response.

Usage:
    python tools/tune_cmd.py "m 360" [--wait 8]

Appends the command to bench/results/cmd.txt, waits for the session to mark it
DONE in bench/results/done.txt, then prints the output appended to
bench/results/out.txt in the meantime. Use "@<secs> <cmd>" (handled by
tune_session) for long-running commands like trace dumps, plus a --wait that
comfortably exceeds the drain window.
"""
import argparse
import os
import sys
import time

RESULTS = os.path.join("bench", "results")
CMD = os.path.join(RESULTS, "cmd.txt")
OUT = os.path.join(RESULTS, "out.txt")
DONE = os.path.join(RESULTS, "done.txt")


def count_done():
    try:
        with open(DONE, "r") as f:
            return sum(1 for l in f if l.startswith("DONE"))
    except FileNotFoundError:
        return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd")
    ap.add_argument("--wait", type=float, default=8.0,
                    help="timeout waiting for the DONE marker")
    args = ap.parse_args()

    if not os.path.exists(CMD):
        sys.exit("ERROR: no session (cmd.txt missing) — start tune_session.py first")

    before_done = count_done()
    out_pos = os.path.getsize(OUT) if os.path.exists(OUT) else 0

    with open(CMD, "a") as f:
        f.write(args.cmd + "\n")

    deadline = time.time() + args.wait
    while time.time() < deadline:
        if count_done() > before_done:
            break
        time.sleep(0.1)
    else:
        print(f"[tune_cmd] WARNING: no DONE within {args.wait}s "
              f"(session running? cmd consumed?)", file=sys.stderr)

    # give the writer a beat to flush the tail, then print new output
    time.sleep(0.2)
    with open(OUT, "r", encoding="utf-8", errors="replace") as f:
        f.seek(out_pos)
        sys.stdout.write(f.read())


if __name__ == "__main__":
    main()
