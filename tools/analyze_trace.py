#!/usr/bin/env python3
"""Parse the most recent TRACE block from a tune-session out.txt and report
tracking metrics (cruise position/velocity error, overshoot, settle, final error).

Usage:
    python tools/analyze_trace.py [path-to-out.txt] [--save csv-path]
"""
import argparse
import os
import sys

RESULTS = os.path.join("bench", "results")


def load_last_trace(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = [l.rstrip("\n") for l in f]

    end = next((i for i in range(len(lines) - 1, -1, -1)
                if lines[i].startswith("TRACE END")), None)
    if end is None:
        return None, None
    begin = next((i for i in range(end - 1, -1, -1)
                  if lines[i].startswith("TRACE BEGIN")), None)
    if begin is None:
        return None, None

    meta = {}
    for tok in lines[begin].split()[2:]:
        if "=" in tok:
            k, v = tok.split("=", 1)
            meta[k] = v

    header_idx = begin + 1
    rows = []
    for i in range(header_idx + 1, end):
        l = lines[i].strip()
        if l.startswith("TRACE END"):
            break
        if not l or "," not in l:
            continue
        parts = l.split(",")
        if len(parts) < 7:
            continue
        try:
            row = [int(p) for p in parts[:7]]
            row.append(int(parts[7]) if len(parts) > 7 else 0)
            rows.append(row)
        except ValueError:
            continue
    return meta, rows


def report(meta, rows):
    if not rows:
        print("no trace rows")
        return
    ax = meta.get("axis", "?")
    # columns: t_ms, ref_mdeg, enc_mdeg, hat_mdeg, vref_mdegs,
    #          what_mdegs, duty_milli, cur_01ma
    t = [r[0] for r in rows]
    ref = [r[1] / 1000.0 for r in rows]
    enc = [r[2] / 1000.0 for r in rows]
    hat = [r[3] / 1000.0 for r in rows]
    vref = [r[4] / 1000.0 for r in rows]
    what = [r[5] / 1000.0 for r in rows]
    duty = [r[6] / 1000.0 for r in rows]

    target = max(ref, key=abs)  # peak reference (deg)
    start = ref[0]
    dist = target - start
    adist = abs(dist)

    # cruise window: vref at plateau (>= 90% of peak |vref|)
    pk_vref = max(abs(v) for v in vref) if vref else 0.0
    cruise = [i for i in range(len(rows)) if abs(vref[i]) >= 0.9 * pk_vref and pk_vref > 1.0]

    def rms(xs):
        return (sum(x * x for x in xs) / len(xs)) ** 0.5 if xs else 0.0

    # true encoder-derived speed (deg/s), boxcar-smoothed over ~20 ms to remove
    # the 0.5-deg/tick quantization noise that would otherwise dominate it
    WIN = 20
    enc_speed = [0.0] * len(rows)
    for i in range(WIN, len(rows)):
        dt = (t[i] - t[i - WIN]) / 1000.0
        enc_speed[i] = (enc[i] - enc[i - WIN]) / dt if dt > 0 else 0.0

    cruise_pos_err = [ref[i] - enc[i] for i in cruise]
    # `what` now carries the actual velocity-loop feedback (encoder edge-timed speed)
    cruise_vel_err = [vref[i] - what[i] for i in cruise]
    # velocity-loop chatter: peak-to-peak duty swing in cruise (limit-cycle indicator)
    cruise_duty = [duty[i] for i in cruise]
    duty_pp = (max(cruise_duty) - min(cruise_duty)) if cruise_duty else 0.0

    # overshoot: how far enc goes past target after first reaching it
    overshoot = 0.0
    if adist > 1.0:
        past = [enc[i] - target for i in range(len(rows))]
        overshoot = max(past) if dist > 0 else -min(past)

    # settled final error: mean enc-target over last 150 rows
    tail = rows[-150:] if len(rows) >= 150 else rows
    final_err = sum((r[1] - r[2]) / 1000.0 for r in tail) / len(tail)
    final_hat_err = sum((r[1] - r[3]) / 1000.0 for r in tail) / len(tail)

    # observer-vs-encoder divergence over whole run
    obs_div = [abs(hat[i] - enc[i]) for i in range(len(rows))]

    print(f"axis M{ax}  rows={len(rows)}  span={t[-1]-t[0]} ms  move={start:.1f}->{target:.1f} deg")
    print(f"  gains kp={meta.get('kp')} ki={meta.get('ki')} kv={meta.get('kv')} "
          f"kd={meta.get('kd')} kff={meta.get('kff')} ff={meta.get('ff')}")
    if cruise:
        print(f"  cruise: n={len(cruise)}  pos_err mean={sum(cruise_pos_err)/len(cruise_pos_err):+.2f} "
              f"rms={rms(cruise_pos_err):.2f} deg")
        print(f"          vel_err mean={sum(cruise_vel_err)/len(cruise_vel_err):+.2f} "
              f"rms={rms(cruise_vel_err):.2f} deg/s   duty p-p={duty_pp:.2f}")
    else:
        print("  cruise: (no plateau)")
    print(f"  overshoot={overshoot:+.2f} deg")
    print(f"  final err (last {len(tail)} rows): enc={final_err:+.3f} deg  hat={final_hat_err:+.3f} deg")
    print(f"  observer divergence |hat-enc|: max={max(obs_div):.2f} mean={sum(obs_div)/len(obs_div):.2f} deg")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", default=os.path.join(RESULTS, "out.txt"))
    ap.add_argument("--save", default=None)
    args = ap.parse_args()
    meta, rows = load_last_trace(args.path)
    if meta is None:
        sys.exit("no TRACE block found in " + args.path)
    report(meta, rows)
    if args.save and rows:
        os.makedirs(os.path.dirname(args.save) or ".", exist_ok=True)
        with open(args.save, "w") as f:
            f.write("t_ms,ref_deg,enc_deg,hat_deg,vref_degs,what_degs,duty\n")
            for r in rows:
                f.write(f"{r[0]},{r[1]/1000:.3f},{r[2]/1000:.3f},{r[3]/1000:.3f},"
                        f"{r[4]/1000:.2f},{r[5]/1000:.2f},{r[6]/1000:.4f}\n")
        print(f"saved -> {args.save}")


if __name__ == "__main__":
    main()
