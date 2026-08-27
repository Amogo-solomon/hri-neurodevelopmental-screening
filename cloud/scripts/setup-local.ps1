# ############################################################################
# setup-local.ps1 — HRI Platform local dev setup (Windows PowerShell / VSCode)
# Usage: .\cloud\scripts\setup-local.ps1
# Prereqs: Docker Desktop running
# ############################################################################
$ErrorActionPreference = "Stop"

function Write-Info    { param($m) Write-Host "[INFO]  $m" -ForegroundColor Cyan }
function Write-OK      { param($m) Write-Host "[OK]    $m" -ForegroundColor Green }
function Write-Warn    { param($m) Write-Host "[WARN]  $m" -ForegroundColor Yellow }
function Write-Err     { param($m) Write-Host "[ERROR] $m" -ForegroundColor Red; exit 1 }

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir   = Resolve-Path (Join-Path $ScriptDir "..\..")

Write-Host ""
Write-Host "  ╔══════════════════════════════════════════════════╗" -ForegroundColor Magenta
Write-Host "  ║  HRI Explainable Behaviour Analysis Platform     ║" -ForegroundColor Magenta
Write-Host "  ║  University of Lincoln · MSc Cloud Computing     ║" -ForegroundColor Magenta
Write-Host "  ╚══════════════════════════════════════════════════╝" -ForegroundColor Magenta
Write-Host ""

# ── Pre-flight ────────────────────────────────────────────────────────────────
Write-Info "Checking prerequisites..."
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Err "Docker not found. Install Docker Desktop: https://www.docker.com/products/docker-desktop/"
}
try { docker info 2>&1 | Out-Null; Write-OK "Docker Desktop is running" }
catch { Write-Err "Docker Desktop is not running. Start it and try again." }

# ── Create .env ───────────────────────────────────────────────────────────────
$EnvFile    = Join-Path $RootDir ".env"
$EnvExample = Join-Path $RootDir ".env.example"
if (-not (Test-Path $EnvFile)) {
    if (Test-Path $EnvExample) {
        Copy-Item $EnvExample $EnvFile
        Write-OK ".env created from .env.example"
    }
} else {
    Write-Info ".env already exists — skipping"
}

# ── Create data directories ───────────────────────────────────────────────────
Write-Info "Creating local directories..."
@("backend\uploads", "backend\data") | ForEach-Object {
    $dir = Join-Path $RootDir $_
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null; Write-OK "Created: $_" }
}

# ── Build & start Docker Compose ──────────────────────────────────────────────
Write-Info "Building and starting Docker Compose stack..."
Push-Location $RootDir
try {
    $result = docker compose up -d --build 2>&1
    if ($LASTEXITCODE -ne 0) {
        $result = docker-compose up -d --build 2>&1
        if ($LASTEXITCODE -ne 0) { Write-Err "docker compose failed. See output above." }
    }
    Write-OK "All containers started"
} finally { Pop-Location }

# ── Wait for backend health ───────────────────────────────────────────────────
Write-Info "Waiting for backend to become healthy (up to 60s)..."
$healthy = $false
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 3
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/health" -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
        if ($r.StatusCode -eq 200) { $healthy = $true; break }
    } catch { Write-Host "  ... waiting ($([int](($i+1)*3))s)" -ForegroundColor DarkGray }
}
if ($healthy) { Write-OK "Backend is healthy" }
else { Write-Warn "Backend health check timed out — it may still be starting. Check: docker compose logs backend" }

# ── Seed admin user ───────────────────────────────────────────────────────────
Write-Info "Creating admin user..."
docker exec hri_backend python seed_admin.py 2>&1 | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
Write-OK "Admin user ready"

# ── Pull VLM model ────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  VLM Model Setup" -ForegroundColor Yellow
Write-Host "  ──────────────────────────────────────────────────" -ForegroundColor DarkGray
Write-Host "  Y = Pull llava:13b  (~8GB, best accuracy)"   -ForegroundColor White
Write-Host "  L = Pull llava:7b   (~4GB, faster, less accurate)" -ForegroundColor White
Write-Host "  S = Skip (pull manually later)"               -ForegroundColor White
Write-Host ""
$choice = Read-Host "  Your choice"

switch ($choice.Trim().ToUpper()) {
    "Y" {
        Write-Info "Pulling llava:13b (this may take 5-20 min on first run)..."
        docker exec hri_ollama ollama pull llava:13b
        if ($LASTEXITCODE -eq 0) { Write-OK "llava:13b ready" }
        else { Write-Warn "Pull failed. Run manually: docker exec hri_ollama ollama pull llava:13b" }
    }
    "L" {
        Write-Info "Pulling llava:7b..."
        docker exec hri_ollama ollama pull llava:7b
        if ($LASTEXITCODE -eq 0) { Write-OK "llava:7b ready" }
        else { Write-Warn "Pull failed. Run manually: docker exec hri_ollama ollama pull llava:7b" }
    }
    default {
        Write-Warn "Skipped. Pull later with: docker exec hri_ollama ollama pull llava:13b"
    }
}

# ── Summary ───────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  ════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host "  ✅  HRI Platform is ready!" -ForegroundColor Green
Write-Host "  ════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""
Write-Host "  Open in browser:" -ForegroundColor White
Write-Host "    Platform UI   →  http://localhost:3000"      -ForegroundColor Cyan
Write-Host "    API Docs      →  http://localhost:8000/api/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Default login:" -ForegroundColor White
Write-Host "    Email    :  admin@hri-platform.local"        -ForegroundColor Yellow
Write-Host "    Password :  Admin1234!@hri"                  -ForegroundColor Yellow
Write-Host "    ⚠ Change this password after first login!"   -ForegroundColor Red
Write-Host ""
Write-Host "  Daily use:" -ForegroundColor White
Write-Host "    Start    :  .\dev.ps1 start"                 -ForegroundColor DarkGray
Write-Host "    Stop     :  .\dev.ps1 stop"                  -ForegroundColor DarkGray
Write-Host "    Logs     :  .\dev.ps1 logs"                  -ForegroundColor DarkGray
Write-Host "    Tests    :  .\dev.ps1 test"                  -ForegroundColor DarkGray
Write-Host "    Status   :  .\dev.ps1 status"                -ForegroundColor DarkGray
Write-Host ""
