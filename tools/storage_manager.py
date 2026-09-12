#!/usr/bin/env python3
"""
EVN ALPHA Storage Manager

Maintains a bounded disk footprint for autonomous tuning:
- Retains top N best performing runs based on composite score/passes.
- Retains latest M recent runs for debugging/provenance.
- Strips bulky 2MB tuning.uf2 flash images from older runs while preserving
  lightweight summary.csv and flash_records.json metadata.
- Prevents disk and directory exhaustion during multi-day/multi-week runs.
"""

import os
import shutil
import glob
import json
import csv
from pathlib import Path
from typing import List, Dict, Optional

REPO_ROOT = Path(__file__).parent.parent
RESULTS_DIR = REPO_ROOT / "bench" / "results"


def get_run_metadata(run_dir: Path) -> Optional[Dict]:
    """Extract performance metrics from a result directory."""
    summary_path = run_dir / "summary.csv"
    if not summary_path.exists():
        return None

    passes = 0
    total = 0
    avg_score = 999.0
    scores = []

    try:
        with open(summary_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                total += 1
                p = int(row.get("passed", 0))
                tot = int(row.get("total", 12))
                if tot > 0 and p == tot:
                    passes += 1
                try:
                    scores.append(float(row.get("score", 999.0)))
                except (ValueError, TypeError):
                    pass
        if scores:
            avg_score = sum(scores) / len(scores)
    except Exception:
        return None

    return {
        "path": run_dir,
        "name": run_dir.name,
        "mtime": run_dir.stat().st_mtime,
        "passes": passes,
        "total": total,
        "avg_score": avg_score,
    }


def prune_storage(
    results_dir: Path = RESULTS_DIR,
    max_recent_full: int = 5,
    max_best_full: int = 10,
    max_total_dirs: int = 50,
):
    """Prune storage ring buffer:
    1. Keep full UF2 in top `max_best_full` runs and `max_recent_full` newest runs.
    2. Strip 2MB UF2 from other directories (preserving summary.csv and flash_records.json).
    3. Delete oldest empty or stripped directories beyond `max_total_dirs`.
    """
    all_dirs = [Path(d) for d in glob.glob(str(results_dir / "autonomous_auto_*")) if os.path.isdir(d)]
    if not all_dirs:
        return 0, 0

    runs = []
    for d in all_dirs:
        meta = get_run_metadata(d)
        if meta:
            runs.append(meta)
        else:
            # Incomplete or corrupt directory, remove if not actively being written
            age_s = time.time() - d.stat().st_mtime if hasattr(time, "time") else 0
            if age_s > 300:
                shutil.rmtree(d, ignore_errors=True)

    if not runs:
        return 0, 0

    # Sort by mtime descending (newest first)
    runs_by_time = sorted(runs, key=lambda r: r["mtime"], reverse=True)
    recent_paths = set(r["path"] for r in runs_by_time[:max_recent_full])

    # Sort by passes descending, then avg_score ascending (best first)
    runs_by_perf = sorted(runs, key=lambda r: (-r["passes"], r["avg_score"]))
    best_paths = set(r["path"] for r in runs_by_perf[:max_best_full])

    keep_uf2_paths = recent_paths.union(best_paths)

    stripped_uf2_count = 0
    removed_dir_count = 0

    # 1. Strip UF2 from older non-best runs
    for r in runs:
        if r["path"] not in keep_uf2_paths:
            uf2_file = r["path"] / "tuning.uf2"
            if uf2_file.exists():
                try:
                    uf2_file.unlink()
                    stripped_uf2_count += 1
                except Exception:
                    pass

    # 2. If total directories still exceed max_total_dirs, delete oldest beyond limit
    if len(runs_by_time) > max_total_dirs:
        to_delete = runs_by_time[max_total_dirs:]
        for r in to_delete:
            if r["path"] not in best_paths:
                try:
                    shutil.rmtree(r["path"], ignore_errors=True)
                    removed_dir_count += 1
                except Exception:
                    pass

    return stripped_uf2_count, removed_dir_count


if __name__ == "__main__":
    import time
    stripped, removed = prune_storage()
    print(f"[storage_manager] Stripped UF2 from {stripped} runs. Removed {removed} old directories.")
