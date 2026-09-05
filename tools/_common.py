"""Shared helpers for EVN ALPHA host tools.

Single source of truth for logic that was previously copy-pasted across
flash_and_capture.py, serial_capture.py, tune_session.py, motion_sweep.py,
evn_dashboard.py and flash_extract_decode.py:

  * RP2040 USB-CDC COM-port auto-detection (find_board_port)
  * BOOTSEL (UF2) drive detection via check_bootsel.ps1 (find_bootsel_drive)

Import as:
    from _common import find_board_port, find_bootsel_drive, RP2040_VID
(tools/ is on sys.path when scripts are run from the repo root, e.g.
`python tools/flash_and_capture.py ...`).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

try:
    from serial.tools import list_ports
except ImportError:  # pragma: no cover - environment guard
    sys.exit("pyserial not installed. Run: pip install -r tools/requirements.txt")

# Raspberry Pi RP2040 USB vendor ID. USB-CDC stdio enumerates as 2E8A:000A,
# TinyUSB as 2E8A:0003; both share the VID.
RP2040_VID = 0x2E8A

REPO_ROOT = Path(__file__).resolve().parent.parent


def find_board_port() -> str | None:
    """Return the COM device of the first RP2040 USB-CDC board, else None."""
    for p in list_ports.comports():
        if p.vid == RP2040_VID:
            return p.device
    return None


def list_board_ports() -> list[str]:
    """Return all RP2040 USB-CDC COM devices currently enumerated."""
    return [p.device for p in list_ports.comports() if p.vid == RP2040_VID]


def find_bootsel_drive(timeout_s: float = 0.0) -> str | None:
    """Return the BOOTSEL UF2 drive letter (e.g. 'D:') via check_bootsel.ps1.

    Polls once by default; pass timeout_s > 0 to poll until the drive appears
    or the timeout elapses. Returns None if the board is not in BOOTSEL mode.
    """
    import time

    check_script = REPO_ROOT / "tools" / "check_bootsel.ps1"
    if not check_script.exists():
        return None

    deadline = time.time() + max(timeout_s, 0.0)
    while True:
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                 "-File", str(check_script)],
                capture_output=True, text=True, timeout=10,
            )
            drive = result.stdout.strip()
            if drive:
                return drive
        except (subprocess.SubprocessError, OSError):
            pass
        if time.time() >= deadline:
            return None
        time.sleep(0.5)
