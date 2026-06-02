# Agente IA Personal

Agente personal construido con **LangGraph** que en cada corrida recolecta noticias de
IA, selecciona las **5 mas importantes** sobre **nuevos modelos** e **IA agentica**
(con angulo de aprendizaje para un futuro **AI Engineer**), arma un briefing y lo
**envia por correo via Outlook Desktop**. Toda la ejecucion queda trazada en **LangSmith**.

## Arquitectura (grafo LangGraph)

```
START -> researcher -> evaluator -> summarizer -> email_writer -> outlook_sender -> END
```

- **researcher**: lanza varias queries en Tavily (en paralelo) con foco en nuevos
  modelos e IA agentica, mezclando busqueda abierta con dominios curados
  (OpenAI, Anthropic, Google, HuggingFace, arXiv, Hacker News, LangChain, etc.).
- **evaluator**: el LLM puntua cada noticia (0-10), le asigna categoria, resume y
  explica por que importa y que aprender. Usa structured output (Pydantic).
- **summarizer**: genera headline + TL;DR (3 bullets) + "skill del dia".
- **email_writer**: renderiza el HTML del correo y guarda `output/preview.html`.
- **outlook_sender**: envia el correo via Outlook Desktop (pywin32). Automatico.

El flujo es **automatico** (sin aprobacion humana). El briefing es **bilingue**:
texto en espanol con los terminos tecnicos en ingles.

## Requisitos

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) como gestor de paquetes
- Outlook Desktop abierto y autenticado (solo para el envio real, en Windows)
- API keys: OpenAI, Tavily y LangSmith

## Instalacion (uv)

```bash
cd "Agente IA Personal"
uv sync                  # crea el .venv e instala dependencias
# para LangGraph Studio (opcional):
uv sync --extra studio
```

## Configuracion

Copia `.env.example` a `.env` y completa tus claves:

```bash
cp .env.example .env
```

```env
OPENAI_API_KEY=...
TAVILY_API_KEY=...
LANGSMITH_API_KEY=...
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=agente-ia-personal
NEWS_RECIPIENT=tu_correo@ejemplo.com
NEWS_MODEL=gpt-5-mini
```

## Uso

```bash
uv run python scripts/run.py              # busca, arma briefing y envia por Outlook
uv run python scripts/run.py --dry-run    # solo genera output/preview.html (no envia)
uv run python scripts/run.py --headless   # no abre el navegador
uv run python scripts/run.py --model gpt-5-mini   # override del modelo
uv run python scripts/run.py --thread mi-id       # thread_id custom
```

## Visualizar el grafo en LangGraph Studio

```bash
uv run --extra studio langgraph dev
```

Esto levanta LangGraph Studio (lee `langgraph.json`, grafo `agente_ia`).

## Trazabilidad en LangSmith

Cada corrida activa el tracing y se agrupa en el proyecto **`agente-ia-personal`**
(con tags, metadata y `run_name`). Cada nodo aparece como un span. El `run_id` se
incrusta en el pie del correo para correlacionar el resultado con su traza.

## Ajustes utiles

- `agente_ia/config.py`: `SEARCH_QUERIES`, `CURATED_DOMAINS`, `CATEGORIAS`,
  `MIN_RELEVANCE_SCORE`, `MAX_ARTICLES` (5 por defecto), modelo y destinatario.
- `agente_ia/prompts.py`: prompts del evaluator y summarizer.
- `agente_ia/email_template.py`: diseno del correo HTML.
