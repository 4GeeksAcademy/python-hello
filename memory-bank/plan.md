# Implementation Plan — Groq Inventory Agent

## LLM

- Provider: **Groq**
- Env: `GROQ_API_KEY` (placeholder `your_api_key_here` in local `.env`; never commit)
- SDK: `groq`
- Model: `llama-3.3-70b-versatile`

## Architecture

```
User → agent.py (Groq + tools) → FastAPI (app/api.py) → data.json
                 ↓
        conversation_history.csv
```

## Secrets (local only)

- `.gitignore` ignores `.env`, venvs, `__pycache__/`, and `conversation_history.csv`
- Local `.env` with `GROQ_API_KEY=your_api_key_here` (user pastes real key manually)
- Committed `.env.example` with the same placeholder

## Dependencies

`requirements.txt`: `fastapi`, `uvicorn`, `python-dotenv`, `requests`, `groq`

## 1. FastAPI backend — `app/api.py`

- Inventory in `data.json`: `name`, `quantity`, `unit`
- Low-stock threshold: quantity `<= 10`
- Endpoints:
  - `GET /products` — list all
  - `POST /products/receive` — add stock (create if missing; `unit` required for new)
  - `POST /products/sell` — subtract stock
  - `GET /products/low-stock` — low stock report
- Run: `uvicorn app.api:app --reload`

## 2. Conversation logging

- Append-only `conversation_history.csv`
- Columns: `session_id`, `author` (`user`|`agent`|`tool`), `content`, `tool_call`, `timestamp` (ISO 8601)
- New UUID `session_id` each agent process start

## 3. Agent — `agent.py`

- Load `.env`; exit clearly if key missing or still placeholder
- Base URL: `http://127.0.0.1:8000`
- Tools map to the four API endpoints
- CLI loop with in-memory session history; exit on `quit` / `exit` / `Ctrl+C`

### Loop safety — max 3 tries (no infinite loops)

`MAX_TRIES = 3` for:

- Tool-calling rounds per user message
- HTTP calls to FastAPI (transient failures)
- Groq chat completion calls (transient failures)

After the limit, surface a clear error and continue the CLI session (do not spin).

## 4. Run

```bash
python -m pip install -r requirements.txt
# put real key in .env (local only)
uvicorn app.api:app --reload
python agent.py
```

## Out of scope

- Committing or pushing secrets
- Changing Flask `server.py` boilerplate
- Multi-location inventory beyond one shared `data.json`
