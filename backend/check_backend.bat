@echo off
powershell -NoProfile -Command "try { $r=Invoke-RestMethod 'http://127.0.0.1:8000/api/health'; $r | ConvertTo-Json -Depth 5 } catch { Write-Host 'Backend is not available.' -ForegroundColor Red }"
pause
