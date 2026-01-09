# Trading Copilot - Start Application
# Starts both backend and frontend services

Write-Host "=== Starting Trading Copilot ===" -ForegroundColor Cyan
Write-Host ""

# Start backend in background
Write-Host "Starting backend (FastAPI)..." -ForegroundColor Yellow
$backendJob = Start-Job -ScriptBlock {
    Set-Location "C:\tradingcopilot\services\core"
    & ".\.venv\Scripts\Activate.ps1"
    uvicorn app.main:app --host 0.0.0.0 --port 8080
}

Write-Host "✓ Backend started (Job ID: $($backendJob.Id))" -ForegroundColor Green
Write-Host ""

# Wait for backend to be ready
Write-Host "Waiting for backend to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

$maxRetries = 10
$retries = 0
$backendReady = $false

while ($retries -lt $maxRetries -and -not $backendReady) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8080/health" -UseBasicParsing -TimeoutSec 2
        if ($response.StatusCode -eq 200) {
            $backendReady = $true
            Write-Host "✓ Backend is ready!" -ForegroundColor Green
        }
    } catch {
        $retries++
        Write-Host "  Retrying... ($retries/$maxRetries)" -ForegroundColor Gray
        Start-Sleep -Seconds 2
    }
}

if (-not $backendReady) {
    Write-Host "✗ Backend failed to start. Check logs:" -ForegroundColor Red
    Write-Host "  Get-Job | Receive-Job" -ForegroundColor Yellow
    exit 1
}

Write-Host ""

# Start frontend
Write-Host "Starting frontend (Streamlit)..." -ForegroundColor Yellow
Set-Location "C:\tradingcopilot\services\ui"
& ".\.venv\Scripts\Activate.ps1"
streamlit run streamlit_app.py

# Note: Streamlit will block here until you close it

# Cleanup: Stop backend when Streamlit closes
Write-Host ""
Write-Host "Stopping backend..." -ForegroundColor Yellow
Stop-Job -Id $backendJob.Id
Remove-Job -Id $backendJob.Id
Write-Host "✓ Application stopped" -ForegroundColor Green
