# ############################################################################
# dev.ps1 — HRI Platform developer helper for PowerShell
# Usage:  .\dev.ps1 <command>
#
# Commands:
#   start       Build and start all services
#   stop        Stop all services
#   restart     Restart a specific service (e.g. .\dev.ps1 restart backend)
#   logs        Stream logs (all or specific service)
#   test        Run backend pytest suite
#   status      Show container health
#   clean       Stop and remove volumes (DESTRUCTIVE)
#   pull-model  Pull Ollama VLM model
#   health      Hit the health endpoint
#   shell       Open a shell in the backend container
# ############################################################################

param(
    [Parameter(Position=0)]
    [string]$Command = "help",

    [Parameter(Position=1)]
    [string]$Service = ""
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir   = Resolve-Path (Join-Path $ScriptDir "..\..")

function Write-Info  { param($msg) Write-Host "[INFO]  $msg" -ForegroundColor Cyan }
function Write-OK    { param($msg) Write-Host "[OK]    $msg" -ForegroundColor Green }
function Write-Warn  { param($msg) Write-Host "[WARN]  $msg" -ForegroundColor Yellow }

Push-Location $RootDir

switch ($Command.ToLower()) {

    "start" {
        Write-Info "Starting HRI Platform..."
        docker compose up -d --build
        Write-OK "Services started → http://localhost:3000"
    }

    "stop" {
        Write-Info "Stopping HRI Platform..."
        docker compose down
        Write-OK "Services stopped"
    }

    "restart" {
        if ($Service -eq "") { $Service = "backend" }
        Write-Info "Restarting $Service..."
        docker compose restart $Service
        Write-OK "$Service restarted"
    }

    "logs" {
        if ($Service -eq "") {
            Write-Info "Streaming all logs (Ctrl+C to stop)..."
            docker compose logs -f
        } else {
            Write-Info "Streaming logs for $Service (Ctrl+C to stop)..."
            docker compose logs -f $Service
        }
    }

    "test" {
        Write-Info "Running backend pytest suite..."
        docker compose exec backend python -m pytest tests/ -v --tb=short `
            --cov=app --cov-report=term-missing
    }

    "status" {
        Write-Info "Container status:"
        docker compose ps
        Write-Host ""
        Write-Info "Health check:"
        try {
            $r = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/health" -TimeoutSec 5
            Write-Host "  Status     : $($r.status)"     -ForegroundColor Green
            Write-Host "  Version    : $($r.version)"    -ForegroundColor White
            Write-Host "  DB OK      : $($r.database_ok)" -ForegroundColor White
            Write-Host "  Ollama     : $($r.ollama_available)" -ForegroundColor White
            Write-Host "  VLM Model  : $($r.ollama_model)"    -ForegroundColor White
        } catch {
            Write-Warn "Backend not responding yet — try again in a moment"
        }
    }

    "pull-model" {
        $model = if ($Service -ne "") { $Service } else { "llava:13b" }
        Write-Info "Pulling model: $model"
        docker exec hri_ollama ollama pull $model
        Write-OK "$model ready"
    }

    "health" {
        $r = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/health"
        $r | ConvertTo-Json
    }

    "shell" {
        $svc = if ($Service -ne "") { $Service } else { "backend" }
        Write-Info "Opening shell in $svc container..."
        docker compose exec $svc /bin/bash
    }

    "clean" {
        Write-Warn "This will DESTROY all containers AND volumes (database, uploads, models)."
        $confirm = Read-Host "Type 'yes' to confirm"
        if ($confirm -eq "yes") {
            docker compose down -v --remove-orphans
            Write-OK "Cleaned up"
        } else {
            Write-Info "Cancelled"
        }
    }

    default {
        Write-Host ""
        Write-Host "  HRI Platform — Dev Helper" -ForegroundColor Magenta
        Write-Host ""
        Write-Host "  Usage: .\dev.ps1 <command> [service]" -ForegroundColor White
        Write-Host ""
        Write-Host "  Commands:" -ForegroundColor Yellow
        Write-Host "    start                  Build & start all services"
        Write-Host "    stop                   Stop all services"
        Write-Host "    restart [service]      Restart a service (default: backend)"
        Write-Host "    logs    [service]      Stream logs (default: all)"
        Write-Host "    test                   Run backend test suite"
        Write-Host "    status                 Show container & API health"
        Write-Host "    pull-model [model]     Pull Ollama model (default: llava:13b)"
        Write-Host "    health                 Raw health endpoint JSON"
        Write-Host "    shell  [service]       Shell into container (default: backend)"
        Write-Host "    clean                  Remove containers + volumes (DESTRUCTIVE)"
        Write-Host ""
        Write-Host "  Examples:" -ForegroundColor Yellow
        Write-Host "    .\dev.ps1 start"
        Write-Host "    .\dev.ps1 logs backend"
        Write-Host "    .\dev.ps1 restart backend"
        Write-Host "    .\dev.ps1 pull-model llava:7b"
        Write-Host "    .\dev.ps1 test"
        Write-Host ""
    }
}

Pop-Location
