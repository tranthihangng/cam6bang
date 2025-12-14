# =============================================================
# Coal Mine Monitoring - Docker Deployment Script (Windows)
# =============================================================
# Sử dụng: .\docker-deploy.ps1 [build|run|stop|logs|export]
# =============================================================

param(
    [Parameter(Position=0)]
    [ValidateSet("build", "run", "stop", "logs", "export", "status", "help")]
    [string]$Action = "help"
)

$ErrorActionPreference = "Stop"
$ImageName = "coal-monitoring"
$ContainerName = "coal-monitoring-app"

function Show-Help {
    Write-Host "
=============================================================
 Coal Mine Monitoring - Docker Deployment
=============================================================

Cach su dung:
    .\docker-deploy.ps1 <action>

Actions:
    build   - Build Docker image
    run     - Chay container
    stop    - Dung container
    logs    - Xem logs
    export  - Export image thanh file .tar
    status  - Xem trang thai container
    help    - Hien thi huong dan nay

Vi du:
    .\docker-deploy.ps1 build   # Build image
    .\docker-deploy.ps1 run     # Chay container
    .\docker-deploy.ps1 logs    # Xem logs

=============================================================
" -ForegroundColor Cyan
}

function Build-Image {
    Write-Host "Building Docker image..." -ForegroundColor Yellow
    
    # Kiem tra Docker
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Host "ERROR: Docker chua duoc cai dat!" -ForegroundColor Red
        Write-Host "Tai Docker Desktop tai: https://www.docker.com/products/docker-desktop/" -ForegroundColor Yellow
        exit 1
    }
    
    # Tao thu muc can thiet
    $dirs = @("config", "models", "logs", "artifacts")
    foreach ($dir in $dirs) {
        if (-not (Test-Path $dir)) {
            New-Item -ItemType Directory -Path $dir | Out-Null
            Write-Host "  Created: $dir/" -ForegroundColor Gray
        }
    }
    
    # Build
    docker-compose build
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "`nBuild thanh cong!" -ForegroundColor Green
        Write-Host "Tiep theo: .\docker-deploy.ps1 run" -ForegroundColor Cyan
    } else {
        Write-Host "`nBuild that bai!" -ForegroundColor Red
        exit 1
    }
}

function Run-Container {
    Write-Host "Khoi dong container..." -ForegroundColor Yellow
    
    # Kiem tra config
    if (-not (Test-Path "config/system_config.json")) {
        Write-Host "CANH BAO: Chua co file config/system_config.json" -ForegroundColor Yellow
        Write-Host "Copy file config:" -ForegroundColor Cyan
        Write-Host "  cp system_config.json config/" -ForegroundColor Gray
        
        if (Test-Path "system_config.json") {
            $copy = Read-Host "Ban co muon copy tu system_config.json? (y/n)"
            if ($copy -eq "y") {
                Copy-Item "system_config.json" "config/"
                Write-Host "  Copied!" -ForegroundColor Green
            }
        }
    }
    
    # Kiem tra models
    $models = Get-ChildItem -Path "models" -Filter "*.pt" -ErrorAction SilentlyContinue
    if (-not $models) {
        Write-Host "CANH BAO: Chua co file model trong models/" -ForegroundColor Yellow
        Write-Host "Copy file .pt vao thu muc models/" -ForegroundColor Cyan
        
        $ptFiles = Get-ChildItem -Filter "*.pt" -ErrorAction SilentlyContinue
        if ($ptFiles) {
            Write-Host "Tim thay cac file .pt:" -ForegroundColor Gray
            foreach ($pt in $ptFiles) {
                Write-Host "  - $($pt.Name)" -ForegroundColor Gray
            }
            $copy = Read-Host "Ban co muon copy tat ca vao models/? (y/n)"
            if ($copy -eq "y") {
                Copy-Item "*.pt" "models/"
                Write-Host "  Copied!" -ForegroundColor Green
            }
        }
    }
    
    # Chay container
    docker-compose up -d
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "`nContainer dang chay!" -ForegroundColor Green
        Write-Host "Xem logs: .\docker-deploy.ps1 logs" -ForegroundColor Cyan
        Write-Host "Dung: .\docker-deploy.ps1 stop" -ForegroundColor Cyan
    } else {
        Write-Host "`nKhoi dong that bai!" -ForegroundColor Red
        exit 1
    }
}

function Stop-Container {
    Write-Host "Dung container..." -ForegroundColor Yellow
    docker-compose down
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Da dung container!" -ForegroundColor Green
    }
}

function Show-Logs {
    Write-Host "Dang xem logs (Ctrl+C de thoat)..." -ForegroundColor Yellow
    docker-compose logs -f
}

function Export-Image {
    Write-Host "Export Docker image..." -ForegroundColor Yellow
    
    $exportFile = "${ImageName}.tar"
    $gzipFile = "${ImageName}.tar.gz"
    
    # Export
    Write-Host "  Exporting to $exportFile..." -ForegroundColor Gray
    docker save "${ImageName}:latest" -o $exportFile
    
    if ($LASTEXITCODE -eq 0) {
        # Nen file
        Write-Host "  Compressing..." -ForegroundColor Gray
        if (Get-Command gzip -ErrorAction SilentlyContinue) {
            gzip -f $exportFile
            $size = (Get-Item $gzipFile).Length / 1GB
            Write-Host "`nExport thanh cong: $gzipFile ($([math]::Round($size, 2)) GB)" -ForegroundColor Green
        } else {
            $size = (Get-Item $exportFile).Length / 1GB
            Write-Host "`nExport thanh cong: $exportFile ($([math]::Round($size, 2)) GB)" -ForegroundColor Green
            Write-Host "Goi y: Cai gzip de nen file nho hon" -ForegroundColor Yellow
        }
        
        Write-Host "`nTren may moi, chay:" -ForegroundColor Cyan
        Write-Host "  docker load -i $gzipFile" -ForegroundColor Gray
    } else {
        Write-Host "Export that bai!" -ForegroundColor Red
        exit 1
    }
}

function Show-Status {
    Write-Host "Trang thai Docker:" -ForegroundColor Yellow
    Write-Host ""
    
    # Kiem tra Docker
    $dockerRunning = docker info 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  Docker: KHONG CHAY" -ForegroundColor Red
        Write-Host "  Khoi dong Docker Desktop truoc!" -ForegroundColor Yellow
        return
    }
    Write-Host "  Docker: DANG CHAY" -ForegroundColor Green
    
    # Kiem tra GPU
    Write-Host ""
    Write-Host "Kiem tra GPU:" -ForegroundColor Yellow
    $gpu = docker run --rm --gpus all nvidia/cuda:11.8-base-ubuntu22.04 nvidia-smi 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  GPU: CO SAN" -ForegroundColor Green
    } else {
        Write-Host "  GPU: KHONG TIM THAY hoac nvidia-container-toolkit chua cai" -ForegroundColor Yellow
    }
    
    # Kiem tra container
    Write-Host ""
    Write-Host "Container $ContainerName`:" -ForegroundColor Yellow
    $container = docker ps -a --filter "name=$ContainerName" --format "{{.Status}}"
    if ($container) {
        Write-Host "  Status: $container" -ForegroundColor Green
    } else {
        Write-Host "  Status: CHUA TAO" -ForegroundColor Gray
    }
    
    # Kiem tra image
    Write-Host ""
    Write-Host "Images:" -ForegroundColor Yellow
    docker images $ImageName --format "  {{.Repository}}:{{.Tag}} ({{.Size}})"
}

# Main
switch ($Action) {
    "build"  { Build-Image }
    "run"    { Run-Container }
    "stop"   { Stop-Container }
    "logs"   { Show-Logs }
    "export" { Export-Image }
    "status" { Show-Status }
    "help"   { Show-Help }
    default  { Show-Help }
}

