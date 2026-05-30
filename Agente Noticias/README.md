# Agente Noticias - Win Internet

Agente construido con **LangGraph** que cada vez que se ejecuta:

1. Busca noticias recientes de IA en Tavily con varias queries especializadas (telecom, Peru, competencia, regulacion, atencion al cliente).
2. Evalua cada noticia con un LLM (`gpt-5-nano`) usando salida estructurada (Pydantic) para puntuar relevancia 0-10 y clasificar el area de impacto para Win Internet.
3. Resume y agrupa las noticias por categoria.
4. Genera un correo HTML estructurado y compatible con Outlook.
5. Pausa con **HITL** (`interrupt`) para que tu apruebes/rechaces.
6. Si apruebas, envia el correo a `jquispeh@win.pe` usando la sesion activa de **Outlook Desktop** via `pywin32` (COM).

Todo el flujo queda trazado en **LangSmith** bajo el proyecto `agente-noticias-win`.

## Estructura

```
Agente Noticias/
├── agente_noticias/             # paquete Python reusable
│   ├── config.py                # contexto Win, queries, modelo
│   ├── state.py                 # NewsState (TypedDict)
│   ├── schemas.py               # Article, ArticleEvaluation, Briefing
│   ├── prompts.py               # prompts en espanol
│   ├── email_template.py        # plantilla HTML Outlook-safe (Jinja2)
│   ├── graph.py                 # StateGraph + HITL
│   └── nodes/
│       ├── researcher.py        # Tavily multi-query
│       ├── evaluator.py         # LLM scoring relevancia
│       ├── summarizer.py        # consolida briefing
│       ├── email_writer.py      # renderiza HTML + guarda preview
│       └── outlook_sender.py    # pywin32 -> Outlook.Application
├── notebooks/
│   └── agente_noticias.ipynb    # version didactica estilo curso
├── scripts/
│   ├── run.py                   # on-demand
│   └── run_scheduled.ps1        # wrapper para Task Scheduler
├── docs/
│   └── task_scheduler_setup.md  # como programar la ejecucion diaria
├── output/                      # se genera preview.html aqui
├── .env.example
├── pyproject.toml
└── requirements.txt
```

## Prerrequisitos

- Windows + Python 3.11 o superior.
- **Outlook Desktop instalado, abierto y con sesion iniciada** en `jquispeh@win.pe`.
- `OPENAI_API_KEY`, `TAVILY_API_KEY` y `LANGSMITH_API_KEY` (puedes reutilizar las del curso `lca-lc-foundations`, el codigo carga ese `.env` automaticamente).

## Instalacion

Desde la carpeta `Agente Noticias/`:

```powershell
# Opcion A: reusar el venv del curso
..\lca-lc-foundations\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Opcion B: venv propio
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

`pywin32` puede requerir el post-install:

```powershell
python .venv\Scripts\pywin32_postinstall.py -install
```

## Uso

### On-demand (con aprobacion humana)

```powershell
python scripts/run.py
```

Mostrara el preview en `output/preview.html` y abrira el archivo. Te pedira en consola: `enviar? [s/N]`.

### On-demand sin aprobacion (envio automatico)

```powershell
python scripts/run.py --auto-approve
```

### Programado (Task Scheduler de Windows)

Ver [docs/task_scheduler_setup.md](docs/task_scheduler_setup.md).

### Notebook didactico

```powershell
jupyter lab notebooks/agente_noticias.ipynb
```

Ejecuta celda por celda para entender cada nodo del grafo, como en los notebooks del curso.

## Trazabilidad LangSmith

Cada ejecucion crea un run en https://smith.langchain.com bajo el proyecto **`agente-noticias-win`** con:

- Tag `agente_noticias`, `win_internet`, fecha.
- Metadata con las queries usadas.
- Un run trace por nodo del grafo (researcher, evaluator, summarizer, email_writer, outlook_sender).
- El `run_id` queda incluido como pie de pagina del correo enviado para auditoria.

## Troubleshooting

- **`pywintypes.com_error` al instanciar Outlook**: asegura que Outlook esta abierto y que el proceso de Python corre en la misma sesion de usuario (no como SYSTEM).
- **Correo no llega**: revisa "Elementos enviados" en Outlook; Win puede tener reglas de DLP que retengan el correo.
- **Sin resultados de Tavily**: aumenta `days` en `agente_noticias/config.py` o relaja las queries.
- **Trace no aparece en LangSmith**: confirma `LANGSMITH_TRACING=true` y reinicia el proceso (la variable se lee al import).
