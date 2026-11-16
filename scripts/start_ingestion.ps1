#Requires -Version 5.1
<#
.SYNOPSIS
    راه‌اندازی کامل سیستم داده‌های بازار بورس با Docker
.DESCRIPTION
    این اسکریپت:
    ۱. زیرساخت‌های Docker رو راه می‌ندازه (PostgreSQL, TimescaleDB, Redis, MinIO)
    ۲. ingestion engine رو برای دریافت خودکار داده اجرا می‌کنه
    ۳. لاگ‌ها رو ذخیره و نشون میده
    
    دو حالت اجرا:
    - Full Docker:    .\start_ingestion.ps1          (همه سرویس‌ها در Docker)
    - Local Python:   .\start_ingestion.ps1 -Local    (فقط زیرساخت Docker، ingestion لوکال)
    - Infra Only:     .\start_ingestion.ps1 -Infra    (فقط زیرساخت، بدون ingestion)
.EXAMPLE
    .\start_ingestion.ps1
    .\start_ingestion.ps1 -Local
    .\start_ingestion.ps1 -Infra
    .\start_ingestion.ps1 -SkipMarketHours  # بدون محدودیت ساعت بازار
#>

param(
    [switch]$Local,           # اجرای ingestion به صورت لوکال (نه داخل Docker)
    [switch]$Infra,           # فقط زیرساخت (بدون ingestion)
    [switch]$SkipMarketHours, # رد شدن از محدودیت ساعت بازار
    [switch]$NoBuild,         # بیلد نکردن Docker imageها
    [switch]$Clean            # پاک کردن volumeها و شروع تمیز
)

$ErrorActionPreference = "Stop"
$rootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$logDir = Join-Path $rootDir "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

# ── Utility Functions ──────────────────────────────────────

function Write-Title($text) {
    Write-Host "`n============================================================" -ForegroundColor Cyan
    Write-Host "  $text" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
}

function Write-Step($text) {
    Write-Host "`n  ➤ $text..." -ForegroundColor Yellow
}

function Write-OK($text) {
    Write-Host "    ✅ $text" -ForegroundColor Green
}

function Write-ERR($text) {
    Write-Host "    ❌ $text" -ForegroundColor Red
}

function Write-INFO($text) {
    Write-Host "    ℹ️  $text" -ForegroundColor DarkGray
}

# ── Main ──────────────────────────────────────────────────

Clear-Host
Write-Title "🚀  راه‌اندازی سیستم دریافت داده بازار بورس"

# ════════════════════════════════════════════════════════════
# Step 0: Clean (optional)
# ════════════════════════════════════════════════════════════
if ($Clean) {
    Write-Step "پاک‌سازی volumeهای Docker"
    docker compose down -v 2>$null
    Write-OK "Volumeها پاک شدن"
}

# ════════════════════════════════════════════════════════════
# Step 1: Check Docker
# ════════════════════════════════════════════════════════════
Write-Step "بررسی Docker"
$dockerCheck = docker --version 2>$null
if (-not $dockerCheck) {
    Write-ERR "Docker نصب نیست یا اجرا نشده!"
    Write-INFO "Docker Desktop رو از https://www.docker.com/products/docker-desktop نصب کن"
    exit 1
}
Write-OK "Docker موجود: $dockerCheck"

# ════════════════════════════════════════════════════════════
# Step 2: Start Infrastructure
# ════════════════════════════════════════════════════════════
Write-Title "📦  راه‌اندازی زیرساخت (PostgreSQL + TimescaleDB + Redis + MinIO)"

$infraServices = @("postgres", "timescaledb", "redis", "minio")

# Stop any existing infra (to get fresh state)
docker compose stop @infraServices 2>$null | Out-Null

if ($NoBuild) {
    Write-INFO "بیلد Docker skip شد"
    docker compose up -d @infraServices 2>&1 | Out-Null
} else {
    docker compose up -d --build @infraServices 2>&1 | Out-Null
}

# ════════════════════════════════════════════════════════════
# Step 3: Wait for Health
# ════════════════════════════════════════════════════════════
Write-Step "منتظر آماده شدن سرویس‌ها (حداکثر ۶۰ ثانیه)"

$services = @{
    "postgres"     = $false
    "timescaledb"  = $false
    "redis"        = $false
    "minio"        = $false
}

$timeout = 60
$elapsed = 0
while ($elapsed -lt $timeout) {
    $status = docker ps --format "{{.Names}} {{.Status}}" 2>$null
    foreach ($svc in $services.Keys) {
        if (-not $services[$svc] -and $status -match "$svc.*\(healthy\)") {
            $services[$svc] = $true
            Write-OK "$svc آماده شد"
        }
    }
    $allHealthy = ($services.Values | Where-Object { -not $_ }).Count -eq 0
    
    # Redis doesn't show "healthy" in docker ps format; check separately
    if (-not $services["redis"]) {
        $redisCheck = docker compose exec -T redis redis-cli ping 2>$null
        if ($redisCheck -eq "PONG") {
            $services["redis"] = $true
            Write-OK "redis آماده شد"
        }
    }
    
    $allHealthy = ($services.Values | Where-Object { -not $_ }).Count -eq 0
    if ($allHealthy) { break }
    
    Start-Sleep -Seconds 3
    $elapsed += 3
}

$notReady = ($services.GetEnumerator() | Where-Object { -not $_.Value })
if ($notReady) {
    Write-ERR "این سرویس‌ها آماده نشدن: $($notReady.Name -join ', ')"
    Write-INFO "لاگ‌ها رو بررسی کن: docker compose logs"
    $continue = Read-Host "می‌خوای ادامه بدی؟ (y/n)"
    if ($continue -ne "y") { exit 1 }
} else {
    Write-OK "همه سرویس‌ها آماده هستن"
}

# ════════════════════════════════════════════════════════════
# Step 4: Check .env
# ════════════════════════════════════════════════════════════
$envFile = Join-Path $rootDir ".env"
if (-not (Test-Path $envFile)) {
    Write-ERR ".env پیدا نشد! یه فایل .env با تنظیمات Docker لازمه"
    exit 1
}
Write-OK ".env موجوده"

# ════════════════════════════════════════════════════════════
# Step 5: Override market hours if requested
# ════════════════════════════════════════════════════════════
if ($SkipMarketHours) {
    Write-INFO "محدودیت ساعت بازار غیرفعال شد (برای تست)"
}

# ════════════════════════════════════════════════════════════
# Step 6: Run Ingestion
# ════════════════════════════════════════════════════════════
if ($Infra) {
    Write-Title "🏁  زیرساخت آماده — ingestion اجرا نشد"
    Write-INFO ""
    Write-INFO "سرویس‌های در حال اجرا:"
    docker ps --format "  • {{.Names}} ({{.Status}})" 2>$null
    Write-INFO ""
    Write-INFO "برای اجرای دستی ingestion:"
    Write-INFO "  docker compose up ingestion"
    Write-INFO "  یا لوکال:"
    Write-INFO "  set INGESTION_DB_DSN=postgresql+asyncpg://market:market@localhost:5433/market"
    Write-INFO "  set INGESTION_REDIS_URL=redis://localhost:6379/0"
    Write-INFO "  python -m ingestion.main"
    exit 0
}

if ($Local) {
    Write-Title "🐍  اجرای ingestion به صورت لوکال"
    Write-INFO "دیتابیس روی localhost:5433 در دسترسه (TimescaleDB)"
    Write-INFO "Redis روی localhost:6379"
    Write-INFO "MinIO روی localhost:9000"
    Write-INFO ""
    
    # Override env vars for localhost
    $env:INGESTION_DB_DSN = "postgresql+asyncpg://market:market@localhost:5433/market"
    $env:INGESTION_REDIS_URL = "redis://localhost:6379/0"
    $env:INGESTION_LAKE_ENDPOINT = "http://localhost:9000"
    
    if ($SkipMarketHours) {
        $env:INGESTION_MARKET_OPEN = ""
        $env:INGESTION_MARKET_CLOSE = ""
    }
    
    $logFile = Join-Path $logDir "ingestion_local.log"
    Write-INFO "لاگ‌ها: $logFile"
    Write-INFO "برای خروج: Ctrl+C"
    Write-INFO ""
    
    Set-Location $rootDir
    python -m ingestion.main 2>&1 | Tee-Object -FilePath $logFile
} else {
    Write-Title "🐳  اجرای ingestion داخل Docker"
    Write-INFO "همه سرویس‌ها داخل Docker network اجرا می‌شن"
    Write-INFO ""
    
    if ($SkipMarketHours) {
        # Create temporary override
        $overrideContent = @"
services:
  ingestion:
    environment:
      INGESTION_MARKET_OPEN: ""
      INGESTION_MARKET_CLOSE: ""
"@
        $overrideFile = Join-Path $rootDir "docker-compose.test-override.yml"
        $overrideContent | Out-File -FilePath $overrideFile -Encoding utf8
        $composeArgs = @("-f", "docker-compose.yml", "-f", $overrideFile, "up", "--build", "ingestion")
    } else {
        $composeArgs = @("up", "--build", "ingestion")
    }
    
    Write-INFO "برای خروج: Ctrl+C"
    Write-INFO "برای دیدن لاگ‌ها در پنجره دیگه: docker compose logs -f ingestion"
    Write-INFO ""
    
    try {
        docker compose @composeArgs
    } finally {
        # Cleanup temp override even on Ctrl+C
        if ($SkipMarketHours) {
            Remove-Item $overrideFile -ErrorAction SilentlyContinue
        }
    }
}
