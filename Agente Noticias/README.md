# Agente Noticias IA - Win Internet

Agente construido con **LangGraph** que arma un **briefing semanal de noticias de IA**
(digeribles, para una audiencia de nivel inicial/intermedio) y lo envia por correo a
los directivos de Win Internet. En cada corrida:

1. **researcher**: busca noticias recientes de IA en Tavily (nuevos modelos, IA agentica,
   productos y novedades de las grandes), con dominios curados. Deduplica por URL y por
   similitud de titulo.
2. **history_filter**: descarta noticias que ya se enviaron en las ultimas semanas
   (historial en Supabase), para no repetir contenido entre briefings.
3. **evaluator**: el LLM puntua cada noticia (0-10) con un rubric estricto, le asigna
   categoria, la resume y la explica "en simple". Usa salida estructurada (Pydantic).
4. **ranker**: ve todas las candidatas juntas, colapsa duplicados del mismo evento y
   asigna scores diferenciados (solo lo mas grande de la semana llega a 10). Elige el top 5.
5. **summarizer**: arma headline + TL;DR (lectura de 30 segundos) + **concepto del dia**
   + **chiste** de cierre, con el tono de marca Win.
6. **email_writer**: renderiza el correo HTML con el look and feel de Win y guarda
   `output/preview.html`.
7. **outlook_sender**: envia el correo via **Outlook Desktop** (`pywin32`/COM) a los
   destinatarios configurados (soporta varios).
8. **persist_history**: guarda en Supabase las noticias enviadas para el anti-repeticion.

Flujo automatico (sin aprobacion humana). Todo queda trazado en **LangSmith** bajo el
proyecto `agente-noticias-win`.

## Estructura

```
Agente Noticias/
├── agente_noticias/
│   ├── config.py                # audiencia, queries, dominios curados, parametros
│   ├── state.py                 # NewsState (TypedDict)
│   ├── schemas.py               # Article, ArticleEvaluation, Ranking, Briefing
│   ├── prompts.py               # prompts + tono de marca Win
│   ├── text_utils.py            # normalizacion/similitud de titulos (dedup)
│   ├── db.py                    # cliente Supabase (historial)
│   ├── email_template.py        # plantilla HTML con paleta Win
│   ├── graph.py                 # StateGraph (flujo automatico)
│   ├── studio.py                # grafo para langgraph dev / Studio
│   ├── assets/                  # win_logo.png (logo del header)
│   └── nodes/
│       ├── researcher.py        # Tavily multi-query + dedup
│       ├── history_filter.py    # anti-repeticion contra Supabase
│       ├── evaluator.py         # LLM scoring (solo puntua)
│       ├── ranker.py            # scoring comparativo diferenciado
│       ├── summarizer.py        # briefing + concepto + chiste
│       ├── email_writer.py      # renderiza HTML + preview
│       ├── outlook_sender.py    # pywin32 -> Outlook (CID logo, multi-destino)
│       └── persist_history.py   # guarda historial en Supabase
├── scripts/run.py
├── langgraph.json
├── pyproject.toml
├── requirements.txt
└── .env.example
```

## Requisitos

- Windows + Python 3.11+
- [uv](https://docs.astral.sh/uv/) como gestor de paquetes
- Outlook Desktop abierto y autenticado (para el envio real)
- API keys: OpenAI, Tavily, LangSmith y (opcional pero recomendado) Supabase

## Instalacion (uv)

```bash
cd "Agente Noticias"
uv sync                  # instala dependencias
uv sync --extra studio   # incluye LangGraph Studio (langgraph dev)
```

## Configuracion

Copia `.env.example` a `.env` y completa:

```env
OPENAI_API_KEY=...
TAVILY_API_KEY=...
LANGSMITH_API_KEY=...
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=agente-noticias-win
NEWS_RECIPIENT=directivo1@win.pe,directivo2@win.pe   # varios separados por coma
NEWS_MODEL=gpt-5-mini
SUPABASE_URL=https://nknpunmqivtvbiwaubqd.supabase.co
SUPABASE_SERVICE_ROLE_KEY=...   # del proyecto Automatizaciones (Settings > API)
DEDUP_WEEKS=6
```

### Logo de Win

Coloca el logo blanco + claim (PNG transparente) en
`agente_noticias/assets/win_logo.png`. Si falta, el header usa un wordmark de texto.

## Uso

```bash
uv run python scripts/run.py              # busca, arma briefing y envia por Outlook
uv run python scripts/run.py --dry-run    # solo genera output/preview.html (no envia ni guarda)
uv run python scripts/run.py --headless   # no abre el navegador
uv run python scripts/run.py --model gpt-5-mini
```

## Interfaz web (recomendada para uso diario)

```bash
uv run python scripts/serve.py
# abre http://127.0.0.1:8800
```

App local con el look & feel de Win para operar el agente sin tocar codigo:

1. Boton "Enviar Correo Noticias IA Semanal" -> genera el borrador mostrando el
   flujo de los agentes EN VIVO (cada nodo se ilumina conforme corre).
2. Revisa las 5 noticias (titulo, resumen, "en simple", categoria, relevancia),
   el concepto del dia y el chiste.
3. Edita lo que no te guste:
   - "Regenerar con otra noticia": cambia esa noticia por el siguiente mejor
     candidato ya encontrado.
   - "Cambiar por un tema...": escribes un tema y el agente busca una noticia de
     ese tema (Tavily) y reemplaza esa seccion.
   - Concepto del dia: "Regenerar concepto" (elige otro sin repetir los de semanas
     anteriores) o escribe tu propio concepto/tema y pulsa "Usar mi concepto".
   - "Regenerar chiste": genera uno nuevo (sin repetir los de semanas anteriores,
     validado contra Supabase).
4. "Ver correo" -> vista previa real del correo en una ventana.
5. "Enviar correo" -> manda el correo por Outlook y guarda el historial en Supabase.

Requiere Outlook Desktop abierto para el envio. El flujo completo tambien queda
trazado en LangSmith (`agente-noticias-win`).

## LangGraph Studio

```bash
uv run --extra studio langgraph dev --no-reload --allow-blocking
# o el atajo:
powershell -ExecutionPolicy Bypass -File scripts/studio.ps1
```

Lee `langgraph.json` (grafo `agente_noticias`) y muestra todos los nodos del flujo.
Abre la URL que imprime (algo como
`https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024`), deja el input
en `{}` y presiona **Submit**.

> [!IMPORTANT]
> Usa SIEMPRE `--no-reload`. Sin esa bandera, el auto-reload de `langgraph dev`
> vigila la carpeta del proyecto; como el runtime escribe su estado en
> `.langgraph_api/` (y se genera `output/preview.html`), entra en un bucle de
> recargas que **re-ejecuta el grafo y envia el correo dos veces** con un solo
> Submit. `--allow-blocking` evita que el servidor de dev marque como problema las
> llamadas bloqueantes de los nodos (Tavily, OpenAI, Outlook, Supabase).

## Historial anti-repeticion (Supabase)

- Proyecto: **Automatizaciones** (`nknpunmqivtvbiwaubqd`), esquema `agente_noticias`.
- Tablas: `briefings` y `sent_articles` (con RLS; el acceso es via service role key).
- `history_filter` consulta lo enviado en las ultimas `DEDUP_WEEKS` semanas y descarta
  repetidos; `persist_history` guarda lo enviado tras cada correo.
- Si no configuras Supabase, el agente sigue funcionando (no filtra ni guarda).

## Trazabilidad LangSmith

Cada corrida se agrupa en el proyecto **`agente-noticias-win`** con tags, metadata y
`run_name`. Cada nodo es un span y el `run_id` se incrusta en el pie del correo.

## Troubleshooting

- **`pywintypes.com_error: No se ha llamado a CoInitialize`**: ya resuelto; el sender
  llama a `CoInitialize()` por hilo. Asegura que Outlook este abierto.
- **El logo no se ve en el correo**: confirma que `assets/win_logo.png` existe; en el
  preview del navegador se usa data URI y en el correo `cid:winlogo`.
- **No filtra repetidos**: revisa `SUPABASE_SERVICE_ROLE_KEY` (no debe quedar en
  `PENDIENTE_...`).
- **Trace no aparece en LangSmith**: confirma `LANGSMITH_TRACING=true`.
```
