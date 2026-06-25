# build.ps1 — Genera StockToner.exe listo para distribuir
# Uso: .\build.ps1
# Requiere: PyInstaller instalado en el .venv del proyecto

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ROOT     = $PSScriptRoot
$VENV     = Join-Path $ROOT ".venv"
$PYTHON   = Join-Path $VENV "Scripts\python.exe"
$PIP      = Join-Path $VENV "Scripts\pip.exe"
$PYINST   = Join-Path $VENV "Scripts\pyinstaller.exe"
$DIST     = Join-Path $ROOT "dist\StockToner"
$EXE      = Join-Path $DIST "StockToner.exe"
$DESKTOP  = [Environment]::GetFolderPath("Desktop")

Write-Host ""
Write-Host "=== StockToner — Build ===" -ForegroundColor Cyan
Write-Host ""

# ── 1. Verificar entorno ──────────────────────────────────────────
if (-not (Test-Path $PYTHON)) {
    Write-Host "[ERROR] No se encontró el .venv. Ejecutá primero:" -ForegroundColor Red
    Write-Host "  python -m venv .venv" -ForegroundColor Yellow
    Write-Host "  .venv\Scripts\pip install -r requirements.txt" -ForegroundColor Yellow
    exit 1
}

Write-Host "[1/4] Colectando archivos estáticos..." -ForegroundColor Green
& $PYTHON manage.py collectstatic --noinput --clear 2>&1 | Out-Null
Write-Host "      OK" -ForegroundColor DarkGreen

# ── 2. Limpiar builds anteriores ──────────────────────────────────
Write-Host "[2/4] Limpiando builds anteriores..." -ForegroundColor Green
if (Test-Path (Join-Path $ROOT "dist")) {
    Remove-Item (Join-Path $ROOT "dist") -Recurse -Force
}
if (Test-Path (Join-Path $ROOT "build")) {
    Remove-Item (Join-Path $ROOT "build") -Recurse -Force
}
Write-Host "      OK" -ForegroundColor DarkGreen

# ── 3. Compilar con PyInstaller ───────────────────────────────────
Write-Host "[3/4] Compilando con PyInstaller..." -ForegroundColor Green
Write-Host "      Esto puede tardar 2-5 minutos..." -ForegroundColor Gray
Set-Location $ROOT
& $PYINST StockToner.spec --noconfirm
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] PyInstaller falló con código $LASTEXITCODE" -ForegroundColor Red
    exit 1
}
Write-Host "      OK" -ForegroundColor DarkGreen

# ── 4. Crear acceso directo en el escritorio ──────────────────────
Write-Host "[4/4] Creando acceso directo en el escritorio..." -ForegroundColor Green
$WShell   = New-Object -ComObject WScript.Shell
$Shortcut = $WShell.CreateShortcut((Join-Path $DESKTOP "StockToner.lnk"))
$Shortcut.TargetPath       = $EXE
$Shortcut.WorkingDirectory = $DIST
$Shortcut.Description      = "StockToner — Sistema de inventario"
$Shortcut.Save()
Write-Host "      OK — Acceso directo creado en el escritorio" -ForegroundColor DarkGreen

# ── Resumen ───────────────────────────────────────────────────────
Write-Host ""
Write-Host "=============================" -ForegroundColor Cyan
Write-Host " Build completado con exito!" -ForegroundColor Green
Write-Host "=============================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  EXE:       $EXE" -ForegroundColor White
Write-Host "  Carpeta:   $DIST" -ForegroundColor White
Write-Host "  Acceso dir: $DESKTOP\StockToner.lnk" -ForegroundColor White
Write-Host ""
Write-Host "Para distribuir: comprime la carpeta dist\StockToner\ y enviala." -ForegroundColor Gray
Write-Host ""
