# MemAgent Startup Script for PowerShell
# Starts both backend and frontend in separate windows

Write-Host "Starting MemAgent..." -ForegroundColor Green

# Detect which PowerShell executable to use
$psExe = if (Get-Command pwsh -ErrorAction SilentlyContinue) { "pwsh" } else { "powershell" }

# Start backend
Write-Host "Starting backend..." -ForegroundColor Cyan
Start-Process $psExe -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\backend'; .\.venv\Scripts\activate; uv run uvicorn app.main:app --reload --port 8000"

# Wait a bit for backend to start
Start-Sleep -Seconds 3

# Start frontend
Write-Host "Starting frontend..." -ForegroundColor Cyan
Start-Process $psExe -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\frontend'; npm run dev"

Write-Host ""
Write-Host "MemAgent is starting up!" -ForegroundColor Green
Write-Host "Backend: http://localhost:8000" -ForegroundColor Cyan
Write-Host "Frontend: http://localhost:3002" -ForegroundColor Cyan
Write-Host "API Docs: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press Ctrl+C to stop this script (servers will continue running in separate windows)" -ForegroundColor Gray
