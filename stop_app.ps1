# Trading Copilot - Stop Application
# Stops all background jobs and services

Write-Host "=== Stopping Trading Copilot ===" -ForegroundColor Cyan
Write-Host ""

# Stop all Python processes running uvicorn or streamlit
Write-Host "Stopping backend (uvicorn)..." -ForegroundColor Yellow
Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -like "*uvicorn*"
} | Stop-Process -Force

Write-Host "Stopping frontend (streamlit)..." -ForegroundColor Yellow
Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -like "*streamlit*"
} | Stop-Process -Force

# Stop any background jobs
Get-Job | Stop-Job
Get-Job | Remove-Job

Write-Host ""
Write-Host "✓ Application stopped" -ForegroundColor Green
