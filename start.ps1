# IDP System Quick Start Script
Write-Host "=== Intelligent Document Processing System ===" -ForegroundColor Cyan
Write-Host ""

# Check Docker
$dockerRunning = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker is not running. Please start Docker Desktop and retry." -ForegroundColor Red
    exit 1
}

Write-Host "✓ Docker is running" -ForegroundColor Green

# Copy env file if not exists
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "✓ Created .env from template" -ForegroundColor Green
}

# Build and start
Write-Host ""
Write-Host "Starting all services (this may take a few minutes on first run)..." -ForegroundColor Yellow
docker compose up --build -d

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to start services" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=== Services Started ===" -ForegroundColor Green
Write-Host "  Frontend (Label Studio):  http://localhost:3000" -ForegroundColor Cyan
Write-Host "  Backend API:              http://localhost:8000" -ForegroundColor Cyan
Write-Host "  API Docs:                 http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "  MinIO Console:            http://localhost:9001" -ForegroundColor Cyan
Write-Host ""
Write-Host "Waiting for services to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 15

# Health check
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 10
    Write-Host "✓ Backend API is healthy" -ForegroundColor Green
} catch {
    Write-Host "⚠ Backend API not yet ready. Check: docker compose logs backend" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "To view logs: docker compose logs -f" -ForegroundColor Gray
Write-Host "To stop:      docker compose down" -ForegroundColor Gray
