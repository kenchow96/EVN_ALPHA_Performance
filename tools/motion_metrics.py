#!/usr/bin/env python3
"""EVN ALPHA motion-metrics analyzer.

Parses the most recent 1 kHz TRACE block from a tune-session out.txt and
computes the full quantitative metric suite from docs/MOTION_METRICS.md.
Pure stdlib (no numpy) so it runs anywhere.

Usage:
    python tools/motion_metrics.py [out.txt] [--save metrics.json]
"""
import argparse
import json
import math
import os
import sys

RESULTS = os.path.join("bench", "results")


# ---------------------------------------------------------------- trace load
def load_last_trace(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = [l.rstrip("\n") for l in f]
    begin = None
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].startswith("TRACE BEGIN"):
            begin = i
            break
    if begin is None:
        return None, None
    meta = {}
    for tok in lines[begin].split()[2:]:
        if "=" in tok:
            k, v = tok.split("=", 1)
            meta[k] = v
    rows = []
    for i in range(begin + 2, len(lines)):   # skip header row
        l = lines[i].strip()
        if l.startswith("TRACE END"):
            break
        parts = l.split(",")
        if len(parts) < 7:
            continue
        try:
            r = [int(p) for p in parts[:7]]
            r.append(int(parts[7]) if len(parts) > 7 else 0)   # cur_01ma optional
            rows.append(r)
        except ValueError:
            continue
    return meta, rows


# ---------------------------------------------------------------- helpers
def boxcar(xs, w):
    """Centered boxcar smoothing; w must be odd."""
    if w < 3:
        return list(xs)
    h = w // 2
    out = []
    n = len(xs)
    for i in range(n):
        a = max(0, i - h)
        b = min(n, i + h + 1)
        out.append(sum(xs[a:b]) / (b - a))
    return out


def derivative(x, t):
    """d(x)/dt with central differences; x,t same length (t in ms -> per s)."""
    n = len(x)
    d = [0.0] * n
    for i in range(1, n - 1):
        dt = (t[i + 1] - t[i - 1]) / 1000.0
        d[i] = (x[i + 1] - x[i - 1]) / dt if dt > 0 else 0.0
    d[0] = d[1] if n > 1 else 0.0
    d[-1] = d[-2] if n > 1 else 0.0
    return d


def rms(xs):
    return math.sqrt(sum(v * v for v in xs) / len(xs)) if xs else 0.0


def dominant_freq(xs, dt_s):
    """Crude dominant-frequency estimate via zero-crossing rate (Hz)."""
    if len(xs) < 4:
        return 0.0
    m = sum(xs) / len(xs)
    crossings = sum(1 for i in range(1, len(xs)) if (xs[i - 1] - m) * (xs[i] - m) < 0)
    return crossings / (2.0 * len(xs) * dt_s)


# ---------------------------------------------------------------- metrics
def compute(meta, rows):
    t = [r[0] for r in rows]                       # ms (relative)
    ref = [r[1] / 1000.0 for r in rows]            # deg
    enc = [r[2] / 1000.0 for r in rows]            # deg
    vref = [r[4] / 1000.0 for r in rows]           # deg/s
    duty = [r[6] / 1000.0 for r in rows]           # -1..1
    cur = [r[7] / 10000.0 for r in rows]           # A (0.1mA -> A)

    n = len(rows)
    if n < 10:
        return None
    target = ref[-1]
    start = ref[0]

    # --- smooth kinematics from encoder ---
    vel = boxcar(derivative(enc, t), 21)
    acc = boxcar(derivative(vel, t), 21)
    jerk = boxcar(derivative(acc, t), 21)

    # --- tracking windows ---
    # cruise: |vref| >= 90% of peak
    pk_vref = max((abs(v) for v in vref), default=0.0)
    cruise = [i for i in range(n) if pk_vref > 1.0 and abs(vref[i]) >= 0.9 * pk_vref]

    # settle: first index where ref reaches target (profile done) -> |err|<0.5 stays
    prof_end = n - 1
    for i in range(n):
        if vref[i] == 0.0 and ref[i] == target and i > 0:
            prof_end = i
            break
    band = 0.5
    settle_idx = n - 1
    for i in range(prof_end, n):
        if all(abs(enc[j] - target) < band for j in range(i, n)):
            settle_idx = i
            break
    settle_ms = max(0, t[settle_idx] - t[prof_end])

    err = [ref[i] - enc[i] for i in range(n)]
    tail = err[-200:] if n >= 200 else err

    # residual vibration: p-p of enc in last 500 ms
    last500 = [enc[i] for i in range(n) if t[-1] - t[i] <= 500]
    resid_pp = (max(last500) - min(last500)) if last500 else 0.0

    # regressive instability: sign reversals of (enc-target) after settle
    srevs = 0
    ssign = 0
    for i in range(settle_idx, n):
        s = 1 if enc[i] - target > 0.05 else (-1 if enc[i] - target < -0.05 else 0)
        if s and ssign and s != ssign:
            srevs += 1
        if s:
            ssign = s

    # --- control-effort quality ---
    sat = sum(1 for d in duty if abs(d) >= 0.98) / n
    dduty = [abs(duty[i] - duty[i - 1]) for i in range(1, n)]
    rough = rms(dduty) / (rms(duty) + 1e-9)
    smoothness = 1.0 / (1.0 + rough)
    cruise_duty = [duty[i] for i in cruise]
    duty_ripple = (max(cruise_duty) - min(cruise_duty)) if cruise_duty else 0.0
    limit_freq = dominant_freq([duty[i] for i in cruise], (t[1] - t[0]) / 1000.0) if len(cruise) > 8 else 0.0
    sat_margin = 1.0 - max((abs(d) for d in duty), default=0.0)

    # --- energy proxy ---
    irms = rms(cur)
    ipeak = max((abs(c) for c in cur), default=0.0)
    energy = sum(duty[i] * vel[i] * ((t[i] - t[i - 1]) / 1000.0) for i in range(1, n))

    m = {
        "axis": meta.get("axis"),
        "gains": {k: meta.get(k) for k in ("kp", "ki", "kv", "kd", "kff")},
        "feedforward": meta.get("ff"),
        "move_deg": [round(start, 2), round(target, 2)],
        "rows": n,
        "span_ms": t[-1] - t[0],

        # limits
        "peak_vel_degs": round(max((abs(v) for v in vel), default=0.0), 1),
        "peak_accel_degs2": round(max((abs(a) for a in acc), default=0.0), 0),
        "peak_jerk_degs3": round(max((abs(j) for j in jerk), default=0.0), 0),

        # tracking
        "max_track_err_deg": round(max((abs(e) for e in err), default=0.0), 3),
        "rms_track_err_deg": round(rms(err), 3),
        "final_err_deg": round(target - enc[-1], 3),
        "overshoot_deg": round(max((enc[i] - target for i in range(n)), default=0.0)
                               if target > start else
                               -min((enc[i] - target for i in range(n)), default=0.0), 3),
        "settle_ms": settle_ms,
        "residual_vibration_pp_deg": round(resid_pp, 3),
        "regressive_reversals": srevs,

        # control-effort quality
        "duty_saturation_frac": round(sat, 3),
        "duty_smoothness": round(smoothness, 3),
        "duty_cruise_ripple_pp": round(duty_ripple, 3),
        "duty_limit_cycle_hz": round(limit_freq, 1),
        "saturation_margin": round(sat_margin, 3),

        # energy proxy
        "current_rms_A": round(irms, 3),
        "current_peak_A": round(ipeak, 3),
        "energy_proxy": round(energy, 1),
    }
    return m


# acceptance thresholds (docs/MOTION_METRICS.md)
ACCEPT = {
    "max_track_err_deg": ("<=", 2.0),
    "rms_track_err_deg": ("<=", 1.0),
    "final_err_deg": ("abs<=", 0.5),
    "overshoot_deg": ("abs<=", 0.5),
    "settle_ms": ("<=", 300),
    "residual_vibration_pp_deg": ("<=", 0.5),
    "duty_saturation_frac": ("<=", 0.15),
    "duty_smoothness": (">=", 0.7),
}


def verdicts(m):
    out = []
    for k, (op, thr) in ACCEPT.items():
        v = m.get(k)
        if v is None:
            continue
        if op == "<=":
            ok = v <= thr
        elif op == ">=":
            ok = v >= thr
        else:  # abs<=
            ok = abs(v) <= thr
        out.append((k, v, op, thr, ok))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", default=os.path.join(RESULTS, "out.txt"))
    ap.add_argument("--save", default=None)
    args = ap.parse_args()
    meta, rows = load_last_trace(args.path)
    if meta is None:
        sys.exit("no TRACE block in " + args.path)
    m = compute(meta, rows)
    if m is None:
        sys.exit("trace too short")

    g = m["gains"]
    print(f"== M{m['axis']}  move {m['move_deg'][0]}->{m['move_deg'][1]} deg  "
          f"kp={g['kp']} ki={g['ki']} kv={g['kv']} kff={g['kff']} ff={m['feedforward']} ==")
    for group, keys in (
        ("Limits", ["peak_vel_degs", "peak_accel_degs2", "peak_jerk_degs3"]),
        ("Tracking", ["max_track_err_deg", "rms_track_err_deg", "final_err_deg",
                      "overshoot_deg", "settle_ms", "residual_vibration_pp_deg",
                      "regressive_reversals"]),
        ("Control effort", ["duty_saturation_frac", "duty_smoothness",
                            "duty_cruise_ripple_pp", "duty_limit_cycle_hz", "saturation_margin"]),
        ("Energy", ["current_rms_A", "current_peak_A", "energy_proxy"]),
    ):
        print(f"  {group}:")
        for k in keys:
            print(f"    {k:32s} {m[k]}")

    vd = verdicts(m)
    npass = sum(1 for *_, ok in vd if ok)
    print(f"  ACCEPTANCE: {npass}/{len(vd)} pass")
    for k, v, op, thr, ok in vd:
        if not ok:
            print(f"    FAIL  {k} {v} {op} {thr}")

    if args.save:
        os.makedirs(os.path.dirname(args.save) or ".", exist_ok=True)
        with open(args.save, "w") as f:
            json.dump(m, f, indent=2)
        print(f"saved -> {args.save}")


if __name__ == "__main__":
    main()
