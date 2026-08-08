# AI basic inventory Agent Loop

## Challenge

Carla’s Bakery Supplies is losing money because inventory is hard to track across locations. Carla still relies on an outdated spreadsheet that is rarely updated. She needs a system where she can manage inventory using natural language—for example, recording deliveries and sales, checking stock levels, and asking what is running low—without wrestling with a complex UI.

## System architecture

The solution has two main parts:

1. **REST API (FastAPI)** — Backend that owns inventory data stored in `data.json`. It supports listing products, registering sales/arrivals, updating stock, and related inventory operations.
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
     data.json
```

## Agent loop and tool calling

API endpoints are exposed to the LLM as **tools** (name, description, and parameters). The agent loop is:

1. Receive the user message.
2. Decide which tool(s) to call based on intent.
3. Execute the tool (HTTP request to the FastAPI API).
4. Receive the tool output.
5. Reply to the user in natural language.

`agent.py` keeps **session memory** so follow-up messages in the same run can refer to earlier context. Stopping and restarting `agent.py` starts a new session; older events remain in the conversation log file.

### Loop safety

All retries and tool-calling rounds are hard-capped at **3** (`MAX_TRIES = 3`). No request path may loop indefinitely (Groq calls, HTTP to FastAPI, or tool rounds).

## Conversation history

Every loop event is appended to `conversation_history.csv` with:

| Field | Description |
|-------|-------------|
| `session_id` | Unique id for the session |
| `author` | `user`, `agent`, or `tool` |
| `content` | Message text or tool result |
| `tool_call` | Tool name when applicable |
| `timestamp` | ISO 8601 date/time |

The file is append-only; new sessions are written at the end. Runtime CSV is gitignored.

## Functional requirements

- Understand conversational inventory phrases such as “we just received 30 units of oat milk” or “we sold 12 bags of alkaline baking.”
- Answer questions like “what products are running low?” clearly and directly.
- Support flexible product data: name, quantity, and units (e.g. kg, liters, units).
- Feel like a natural conversation, not a form-driven UI.

## Environment and how to run

- **Language:** Python
- **API:** FastAPI + Uvicorn
- **LLM:** Groq (`llama-3.3-70b-versatile`)
- **Config:** local `.env` (never commit) with `GROQ_API_KEY=your_api_key_here` — replace the placeholder with your key manually
- **Install:** `python -m pip install -r requirements.txt`

**Terminal 1 — API:**

```bash
uvicorn app.api:app --reload
```

**Terminal 2 — Agent:**

```bash
python agent.py
```

Use `Ctrl+C` to stop either process. Relaunching the agent opens a new session while prior history stays in `conversation_history.csv`.

## Key deliverables

- FastAPI app in `app/api.py` backed by `data.json`
- Conversation logging to `conversation_history.csv`
- `agent.py` with Groq tool-calling, API integration, session memory, and max 3 tries
- End-to-end checks with Carla-style natural language inputs
