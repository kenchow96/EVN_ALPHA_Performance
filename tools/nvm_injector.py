#!/usr/bin/env python3
"""
EVN ALPHA NVM Parameter Injector

Generates a tiny UF2 binary containing only the 256-byte NVM parameter table
targeted at flash address 0x10FF8000.
Flashing this 512-byte UF2 file takes < 1 second via picotool and updates motor
control gains directly in flash memory WITHOUT recompiling the firmware!
"""

import struct
import zlib
from pathlib import Path
from typing import Dict, Optional

# Constants matching hal_tuning_log.h
EVN_TUNING_PARAM_MAGIC = 0x31505645   # 'EVP1'
EVN_TUNING_SCHEMA_VERSION = 1
FLASH_TARGET_ADDR = 0x10FF8000        # Top 32KB of flash

UF2_MAGIC_START0 = 0x0A324655
UF2_MAGIC_START1 = 0x9E5D5157
UF2_MAGIC_END = 0x0AB16413
RP2040_FAMILY_ID = 0xE48FF56A


def build_param_payload(
    run_id: int,
    axis_params: Dict[int, Dict[str, float]],
    active: bool = True
) -> bytes:
    """Build the exact 256-byte evn_tuning_nvm_params_t struct payload."""
    magic = EVN_TUNING_PARAM_MAGIC
    schema = EVN_TUNING_SCHEMA_VERSION
    flags = 1 if active else 0

    header = struct.pack("<4I", magic, schema, run_id, flags)

    # 4 axes, each has 8 floats (32 bytes)
    axes_data = bytearray()
    for ax in range(4):
        p = axis_params.get(ax, {})
        kp_pos = float(p.get("kp_pos", 0.0))
        kp_vel = float(p.get("kp_vel", 0.0))
        ekp_vel = float(p.get("endpoint_kp_vel", 0.0))
        accel_scale = float(p.get("accel_scale", 0.0))
        start_duty = float(p.get("start_duty", 0.0))
        ax_block = struct.pack("<8f", kp_pos, kp_vel, ekp_vel, accel_scale, start_duty, 0.0, 0.0, 0.0)
        axes_data.extend(ax_block)

    pre_crc = header + axes_data
    # Compute CRC32 with crc=0 initially
    crc_placeholder = struct.pack("<I", 0)
    padding = bytes(108)

    full_unhashed = pre_crc + crc_placeholder + padding
    assert len(full_unhashed) == 256, f"Length must be 256, got {len(full_unhashed)}"

    # CRC32 of copy with crc32=0
    calculated_crc = zlib.crc32(full_unhashed) & 0xFFFFFFFF
    crc_bytes = struct.pack("<I", calculated_crc)

    final_payload = pre_crc + crc_bytes + padding
    assert len(final_payload) == 256
    return final_payload


def generate_nvm_uf2(
    run_id: int,
    axis_params: Dict[int, Dict[str, float]],
    output_path: Path
) -> Path:
    """Wrap 256-byte payload into a standard 512-byte RP2040 UF2 block."""
    payload = build_param_payload(run_id, axis_params, active=True)
    # Pad payload to 476 bytes of data
    data_block = payload + bytes(476 - len(payload))

    flags = 0x00002000  # Family ID present
    block_no = 0
    num_blocks = 1
    payload_size = 256  # Only 256 bytes programmed

    header = struct.pack(
        "<8I",
        UF2_MAGIC_START0,
        UF2_MAGIC_START1,
        flags,
        FLASH_TARGET_ADDR,
        payload_size,
        block_no,
        num_blocks,
        RP2040_FAMILY_ID,
    )
    trailer = struct.pack("<I", UF2_MAGIC_END)

    uf2_block = header + data_block + trailer
    assert len(uf2_block) == 512, f"UF2 block must be 512 bytes, got {len(uf2_block)}"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(uf2_block)
    return output_path


if __name__ == "__main__":
    test_params = {
        0: {"kp_pos": 2.0e-4, "kp_vel": 1.0e-5, "endpoint_kp_vel": 2.5e-6, "accel_scale": 0.60, "start_duty": 0.12},
        1: {"kp_pos": 2.0e-4, "kp_vel": 1.0e-5, "endpoint_kp_vel": 2.5e-6, "accel_scale": 0.60, "start_duty": 0.12},
        2: {"kp_pos": 2.5e-4, "kp_vel": 1.0e-6, "endpoint_kp_vel": 2.0e-6, "accel_scale": 0.35, "start_duty": 0.90},
        3: {"kp_pos": 2.5e-4, "kp_vel": 1.0e-6, "endpoint_kp_vel": 2.0e-6, "accel_scale": 0.35, "start_duty": 0.90},
    }
    out = Path("build/params.uf2")
    generate_nvm_uf2(0x26090455, test_params, out)
    print(f"Generated test NVM parameter UF2: {out} ({out.stat().st_size} bytes)")
