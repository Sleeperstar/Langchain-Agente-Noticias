# Arranca LangGraph Studio de forma segura (sin doble envio de correo).
#
# - --no-reload: desactiva el auto-reload que provoca el bucle de recargas
#   (y el doble envio del correo) al escribirse archivos dentro del proyecto.
# - --allow-blocking: permite las llamadas bloqueantes de los nodos
#   (Tavily, OpenAI, Outlook, Supabase) sin que el servidor de dev las marque.
#
# Uso:  powershell -ExecutionPolicy Bypass -File scripts/studio.ps1 [-Port 2024]

param(
    [int]$Port = 2024
)

$ErrorActionPreference = "SilentlyContinue"

# Si el puerto esta ocupado por una corrida anterior, avisa y sugiere otro.
$busy = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($busy) {
    Write-Host "El puerto $Port esta ocupado. Probando con $($Port + 1)..." -ForegroundColor Yellow
    $Port = $Port + 1
}

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

Write-Host "Iniciando LangGraph Studio en el puerto $Port (sin auto-reload)..." -ForegroundColor Cyan
uv run --extra studio langgraph dev --no-reload --allow-blocking --port $Port
