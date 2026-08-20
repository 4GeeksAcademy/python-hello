# AI basic inventory Agent Loop

## Challenge

Carla’s Bakery Supplies is losing money because inventory is hard to track across locations. Carla still relies on an outdated spreadsheet that is rarely updated. She needs a system where she can manage inventory using natural language—for example, recording deliveries and sales, checking stock levels, and asking what is running low—without wrestling with a complex UI.

## System architecture

The solution has two main parts:

1. **REST API (FastAPI)** — Backend that owns inventory data stored in `products.csv`. It supports listing products, registering sales/arrivals, updating stock, and related inventory operations. Data survives server restarts.
2. **AI Agent (`agent.py`)** — A Python script that sits between Carla and the API. It uses a **Groq** LLM so she can talk in plain language; the agent decides which API endpoints (tools) to call and replies conversationally.

```
User (natural language)
        │
        ▼
   agent.py (Groq LLM + tools)
        │
        ▼
   FastAPI (app/api.py)
        │
        ▼
    products.csv
```

## Agent loop and tool calling

API endpoints are exposed to the LLM as **tools** (name, description, and parameters). The agent loop is Observe → Think → Act → Update → Repeat:

1. **Observe** — receive the user message.
2. **Think** — Groq decides which tool(s) to call based on intent.
3. **Act** — execute the tool (HTTP request to the FastAPI API).
4. **Update** — inject the tool result into conversation history, then form a reply.
5. **Repeat** — continue tool rounds as needed (hard-capped; see loop safety).

`agent.py` keeps **session memory** so follow-up messages in the same run can refer to earlier context (multi-step interactions). Stopping and restarting `agent.py` starts a new session; older events remain in the conversation log file.

### Loop safety

All retries and tool-calling rounds are hard-capped at **3** (`MAX_TRIES = 3`). No request path may loop indefinitely (Groq calls, HTTP to FastAPI, or tool rounds).

## Conversation log

Every loop event is appended to `conversation_log.csv` with exactly four fields:

| Field | Description |
|-------|-------------|
| `author` | `user`, `agent`, or `tool` |
| `content` | Message text or tool result |
| `tool_call` | Tool name when applicable (empty otherwise) |
| `timestamp` | ISO 8601 date/time |

The file is append-only; new sessions continue writing at the end. Runtime CSV is gitignored.

## Functional requirements

- Understand conversational inventory phrases such as “we just received 30 units of oat milk” or “we sold 12 bags of alkaline baking.”
- Answer questions like “what products are running low?” clearly and directly.
- Support flexible product data: name, quantity, and units (e.g. kg, liters, units) in `products.csv`.
- Feel like a natural conversation, not a form-driven UI.

## Environment and how to run

- **Language:** Python
- **API:** FastAPI + Uvicorn
- **LLM:** Groq (`llama-3.3-70b-versatile`)
- **Config:** local `.env` (never commit) with `GROQ_API_KEY=your_api_key_here` — replace the placeholder with your key manually
- **Install:** `python -m pip install -r requirements.txt`

**Terminal 1 — API:**

```bash
python -m uvicorn app.api:app --reload
```

**Terminal 2 — Agent:**

```bash
python agent.py
```

Use `Ctrl+C` to stop either process. Relaunching the agent opens a new session while prior history stays in `conversation_log.csv`.

## Key deliverables

- FastAPI app in `app/api.py` backed by `products.csv`
- Conversation logging to `conversation_log.csv` (four fields)
- `agent.py` with hand-coded Groq tool-calling loop, API integration, session memory, and max 3 tries
- End-to-end checks with Carla-style natural language inputs
