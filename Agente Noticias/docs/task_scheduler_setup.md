# Programar el agente con Task Scheduler de Windows

El script `scripts/run_scheduled.ps1` esta pensado para correr de forma desatendida.
Asegurate de:

- Tener Outlook Desktop **abierto y autenticado** con la cuenta `jquispeh@win.pe`
  cuando se dispare la tarea (si Outlook esta cerrado el envio falla).
- Que la PC no este suspendida a la hora programada (usa "Despertar el equipo
  para ejecutar esta tarea" en la pestania *Condiciones*).
- Las dependencias estan instaladas en el venv del curso o en `.venv` local.

## Opcion A: comando de una sola linea (recomendado)

Abre PowerShell **como administrador** y ejecuta (ajusta la ruta si copiaste el
proyecto a otro lado):

```powershell
$ps1 = "C:\Users\jquispeh\OneDrive - WIN EMPRESAS SAC\Escritorio\Langchain\Agente Noticias\scripts\run_scheduled.ps1"

schtasks /Create `
    /TN "AgenteNoticiasWIN" `
    /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$ps1`"" `
    /SC DAILY /ST 08:00 `
    /RL LIMITED /F
```

Esto crea una tarea diaria a las 08:00. Para cambiar la hora, ajusta `/ST`.
Si necesitas que corra solo en dias laborables, reemplaza por:

```powershell
schtasks /Create `
    /TN "AgenteNoticiasWIN" `
    /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$ps1`"" `
    /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 08:00 `
    /RL LIMITED /F
```

## Opcion B: interfaz grafica (Programador de tareas)

1. Abre **Programador de tareas** (`taskschd.msc`).
2. *Crear tarea...* (no "Crear tarea basica", para tener mas opciones).
3. **General**: nombre `AgenteNoticiasWIN`. Marca *Ejecutar solo cuando el usuario haya iniciado sesion*.
4. **Desencadenadores**: nuevo, diario, a la hora deseada.
5. **Acciones**: iniciar un programa.
   - Programa o script: `powershell.exe`
   - Argumentos: `-NoProfile -ExecutionPolicy Bypass -File "C:\Users\jquispeh\OneDrive - WIN EMPRESAS SAC\Escritorio\Langchain\Agente Noticias\scripts\run_scheduled.ps1"`
6. **Condiciones**: desmarca *Iniciar la tarea solo si el equipo esta con CA* si quieres que corra con bateria.
7. **Configuracion**: marca *Permitir que la tarea se ejecute a demanda*.

## Probar manualmente

```powershell
schtasks /Run /TN "AgenteNoticiasWIN"
```

Revisa el log en `output/scheduled.log` y los runs en LangSmith.

## Quitar la tarea

```powershell
schtasks /Delete /TN "AgenteNoticiasWIN" /F
```

## Troubleshooting

| Sintoma | Causa probable | Solucion |
|---------|----------------|----------|
| `python.exe` no se encuentra | venv eliminado o ruta cambiada | Edita `run_scheduled.ps1` para apuntar al python correcto |
| Outlook abre ventana de seguridad pidiendo permiso | Politica Outlook "Programmatic Access" | En Outlook *Centro de confianza > Acceso programatico*, configura "Nunca avisarme" (requiere antivirus actualizado) |
| `pywintypes.com_error: -2147221005` | Outlook no esta corriendo | Abre Outlook antes de la hora programada (puedes anadir un trigger extra "Al iniciar sesion") |
| Sin trace en LangSmith | `.env` no se carga en sesion de Task Scheduler | Verifica que `lca-lc-foundations/.env` exista y sea legible por el usuario |
