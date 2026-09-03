<#
.SYNOPSIS
    Fallback BOOTSEL detection tool - WMI event subscription.
.DESCRIPTION
    Uses WMI event subscription to detect when RP2040 enters BOOTSEL mode.
    This is the SECONDARY/FALLBACK method - timing-dependent, must be initialized
    BEFORE any flash/operation so it has time to capture the event.
    Only use if check_bootsel.ps1 polling fails.
.USAGE
    # Terminal 1: Start listener BEFORE any other scripts run
    powershell -NoProfile -ExecutionPolicy Bypass -File tools/wait_bootsel.ps1
    
    # Terminal 2: Build autonomous (EVN_AUTONOMOUS_TUNING=1) → Compile Project task
    # Terminal 2: Flash autonomous
    picotool load -f build\EVN_ALPHA_Performance.uf2 -x
    
    # Terminal 1 will print: [BOOTSEL DETECTED] Drive D: at ...
    # Drive found: D:
.OUTPUTS
    Prints detected drive letter to console.
.NOTES
    - Must be started BEFORE flash operation to catch the event
    - Timing-dependent; may miss events if not initialized early
    - Preferred primary method: tools/check_bootsel.ps1 (polling)
    - This script is called automatically by flash_extract_decode.py as fallback
#>

$Query = "SELECT * FROM Win32_VolumeChangeEvent WHERE EventType = 2"
$action = {
    $DriveLetter = $EventArgs.NewEvent.DriveName
    $vol = Get-WmiObject -Query "SELECT * FROM Win32_LogicalDisk WHERE DeviceID = '$DriveLetter'"
    if ($vol.VolumeName -eq 'RP2350' -or $vol.VolumeName -eq 'RPI-RP2') {
        Write-Host "[BOOTSEL DETECTED] Drive $DriveLetter at $(Get-Date)" -ForegroundColor Green
        $global:BootSelDrive = $DriveLetter
        Unregister-Event -SourceIdentifier "BootSelDriveEvent" -Force
    }
}
Register-CimIndicationEvent -Query $Query -SourceIdentifier "BootSelDriveEvent" -Action $action
Write-Host "Listening for RP2040 BOOTSEL drive (FALLBACK - WMI event subscription)..."
Write-Host "NOTE: This must be started BEFORE flash operation. Primary method: check_bootsel.ps1"
$global:BootSelDrive = $null
while ($global:BootSelDrive -eq $null) { Start-Sleep -Milliseconds 500 }
Write-Host "Drive found: $global:BootSelDrive"