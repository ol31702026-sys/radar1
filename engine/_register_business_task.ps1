# One-shot helper: registers the RadarDailyCollectBusiness scheduled task.
# Run once via: powershell.exe -NoProfile -ExecutionPolicy Bypass -File <this>
$ErrorActionPreference = 'Stop'

$scriptPath = '\\wsl.localhost\Ubuntu\home\oleg\projects\useful_Claude\engine\daily_collect_business.ps1'
$arg = '-NoProfile -ExecutionPolicy Bypass -File "' + $scriptPath + '"'

$action   = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arg
$trigger  = New-ScheduledTaskTrigger -Daily -At '02:00'
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
              -ExecutionTimeLimit (New-TimeSpan -Hours 1)

Register-ScheduledTask -TaskName 'RadarDailyCollectBusiness' `
  -Action $action -Trigger $trigger -Settings $settings `
  -Description 'Ezhednevnyy sbor business-hits v 02:00 (offset ot claude-code)' `
  -Force | Out-Null

Write-Output 'REGISTERED'
Get-ScheduledTask -TaskName 'RadarDailyCollectBusiness' |
  Select-Object TaskName, State | Format-Table -AutoSize
