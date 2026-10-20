# Wrapper PowerShell para Windows Task Scheduler.
# Ejecuta el agente en modo no interactivo (--headless).
# Loguea cada corrida en output/scheduled.log.

$ErrorActionPreference = "Stop"

# Resolver rutas relativas al script.
$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ProjectRoot = Split-Path -Parent $ScriptDir
$Workspace   = Split-Path -Parent $ProjectRoot
$LogPath     = Join-Path $ProjectRoot "output\scheduled.log"
$Python      = Join-Path $Workspace "lca-lc-foundations\.venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    # Fallback: venv local del proyecto.
    $Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
}

$Stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $LogPath -Value "[$Stamp] iniciando agente_noticias..."

try {
    Set-Location $ProjectRoot
    # Native stderr (warnings, progress) must not abort the run under "Stop".
    $ErrorActionPreference = "Continue"
    & $Python "scripts\run.py" --headless 2>&1 |
        Tee-Object -FilePath $LogPath -Append | Out-Null
    $ExitCode = $LASTEXITCODE
    $ErrorActionPreference = "Stop"
    if ($ExitCode -ne 0) {
        throw "run.py exited with code $ExitCode"
    }
    Add-Content -Path $LogPath -Value "[$Stamp] OK"
}
catch {
    Add-Content -Path $LogPath -Value "[$Stamp] ERROR: $($_.Exception.Message)"
    throw
}
