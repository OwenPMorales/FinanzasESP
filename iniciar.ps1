# Levanta todo el proyecto FinanzasESP en Windows:
#   PowerShell -ExecutionPolicy Bypass -File .\iniciar.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv")) {
    Write-Host "Creando entorno virtual..." -ForegroundColor Cyan
    python -m venv .venv
    .\.venv\Scripts\python.exe -m pip install --upgrade pip
    .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
}

if (-not (Test-Path ".env")) {
    Write-Host "Creando .env con una SECRET_KEY nueva..." -ForegroundColor Cyan
    $key = .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(64))"
    (Get-Content .env.example) -replace '^SECRET_KEY=.*', "SECRET_KEY=$key" | Set-Content .env -Encoding utf8
}

Write-Host "Levantando PostgreSQL y MinIO (Docker)..." -ForegroundColor Cyan
docker compose up -d

Write-Host "Esperando a PostgreSQL..." -ForegroundColor Cyan
do {
    Start-Sleep -Seconds 2
    $estado = docker inspect -f "{{.State.Health.Status}}" finanzas_esp_db
} until ($estado -eq "healthy")

Write-Host "Aplicando migraciones (Alembic)..." -ForegroundColor Cyan
.\.venv\Scripts\alembic.exe upgrade head

$ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -like "Wi-Fi*" -and $_.IPAddress -notlike "169.*" } | Select-Object -First 1).IPAddress
Write-Host ""
Write-Host "Panel web:      http://localhost:8000/" -ForegroundColor Green
Write-Host "Swagger:        http://localhost:8000/docs" -ForegroundColor Green
Write-Host "Consola MinIO:  http://localhost:9031  (finanzas_admin / finanzas_minio_2026)" -ForegroundColor Green
if ($ip) { Write-Host "URL para el ESP32: http://${ip}:8000" -ForegroundColor Yellow }
Write-Host ""

# --host 0.0.0.0 para que el ESP32 de la red local pueda llegar al servidor
.\.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
