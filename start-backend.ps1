# MemAgent Backend - Quick Start Script

Write-Host "🚀 Starting MemAgent Backend..." -ForegroundColor Green

# Check if virtual environment exists
if (!(Test-Path "backend\.venv")) {
    Write-Host "❌ Virtual environment not found. Please run setup first:" -ForegroundColor Red
    Write-Host "   cd backend" -ForegroundColor Yellow
    Write-Host "   uv venv" -ForegroundColor Yellow
    Write-Host "   .venv\Scripts\activate" -ForegroundColor Yellow
    Write-Host "   uv sync" -ForegroundColor Yellow
    exit 1
}

# Check if .env.local exists
if (!(Test-Path ".env.local")) {
    Write-Host "❌ .env.local not found. Please configure your environment variables." -ForegroundColor Red
    exit 1
}

Write-Host "✅ Environment configured" -ForegroundColor Green

# Create temp directories
if (!(Test-Path "tmp\images")) {
    New-Item -ItemType Directory -Force -Path "tmp\images" | Out-Null
    Write-Host "✅ Created temp directories" -ForegroundColor Green
}

# Start the backend
Write-Host "`n📡 Starting FastAPI server on http://localhost:8000" -ForegroundColor Cyan
Write-Host "📖 API docs available at http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "`nPress Ctrl+C to stop the server`n" -ForegroundColor Yellow

Set-Location backend
& .venv\Scripts\activate.ps1
uv run uvicorn app.main:app --reload --port 8000
