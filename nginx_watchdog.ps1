# WA! CRM - Nginx Watchdog (Auto-Restart)
# Keeps nginx alive - restarts it every 10 seconds if it dies

$nginxExe  = "C:\nginx\nginx.exe"
$nginxConf = "C:/Users/CHN/Desktop/Wa CRM/nginx/nginx.conf"
$nginxDir  = "C:\nginx"
$checkIntervalSeconds = 10

Write-Host "WA! CRM Nginx Watchdog started. Checking every ${checkIntervalSeconds}s..." -ForegroundColor Green

while ($true) {
    $proc = Get-Process nginx -ErrorAction SilentlyContinue
    if (-not $proc) {
        Write-Host "$(Get-Date -Format 'HH:mm:ss') [WATCHDOG] Nginx not running - restarting..." -ForegroundColor Yellow
        taskkill /F /IM nginx.exe 2>$null | Out-Null
        Start-Sleep -Seconds 1
        Start-Process -FilePath $nginxExe `
                      -ArgumentList "-c `"$nginxConf`"" `
                      -WorkingDirectory $nginxDir `
                      -WindowStyle Hidden
        Start-Sleep -Seconds 3
        $proc2 = Get-Process nginx -ErrorAction SilentlyContinue
        if ($proc2) {
            Write-Host "$(Get-Date -Format 'HH:mm:ss') [WATCHDOG] Nginx restarted OK (PID $($proc2[0].Id))" -ForegroundColor Green
        } else {
            Write-Host "$(Get-Date -Format 'HH:mm:ss') [WATCHDOG] ERROR - Nginx failed to restart!" -ForegroundColor Red
        }
    } else {
        Write-Host "$(Get-Date -Format 'HH:mm:ss') [WATCHDOG] Nginx OK (PID $($proc[0].Id))" -ForegroundColor Cyan
    }
    Start-Sleep -Seconds $checkIntervalSeconds
}
