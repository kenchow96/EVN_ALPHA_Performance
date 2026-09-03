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
Write-Host "Listening for RP2040 BOOTSEL drive... Press Ctrl+C to stop."
$global:BootSelDrive = $null
while ($global:BootSelDrive -eq $null) { Start-Sleep -Milliseconds 500 }
Write-Host "Drive found: $global:BootSelDrive"