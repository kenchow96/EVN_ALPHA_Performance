<#
.SYNOPSIS
    Primary BOOTSEL detection tool - polls for RP2040 UF2 drive.
.DESCRIPTION
    Checks if the EVN ALPHA board is in BOOTSEL mode (UF2 drive mounted).
    This is the PRIMARY detection method - fast, reliable polling.
    Returns the drive letter if found, nothing if not found.
.USAGE
    powershell -NoProfile -ExecutionPolicy Bypass -File tools/check_bootsel.ps1
.OUTPUTS
    Drive letter (e.g., "D:") if BOOTSEL detected, empty string otherwise.
.NOTES
    This is the preferred method over wait_bootsel.ps1 (WMI event subscription)
    which is timing-dependent and should only be used as a fallback.
#>

$drive = Get-WmiObject Win32_LogicalDisk | Where-Object { $_.VolumeName -eq 'RPI-RP2' -or $_.VolumeName -eq 'RP2350' } | Select-Object -ExpandProperty DeviceID

if ($drive) {
    Write-Output $drive
    exit 0
} else {
    exit 1
}