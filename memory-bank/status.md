# Project Status — AI basic inventory Agent Loop

| Area | Status | Notes |
|------|--------|-------|
| Documents / memory-bank scaffolding | Done | Context, plan, and status docs in place |
| Environment setup | Done | `requirements.txt`, `.env` placeholder, `.env.example`, `.gitignore` (`.env` not public) |
| FastAPI backend + `products.csv` | Done | `app/api.py` with list/receive/sell/low-stock; CSV persistence |
| Conversation CSV logging | Done | Append-only `conversation_log.csv` with four fields (gitignored) |
| Agent (`agent.py`) | Done | Groq tools, session memory, `MAX_TRIES = 3` |
| Testing / validation | Done | Live rubric run: **10/10** (see `memory-bank/evaluate.md`) |

## Checklist

- [x] Create `Documents/` and `memory-bank/`
- [x] Write project context (`Documents/context.md`)
- [x] Write implementation plan (`memory-bank/plan.md`)
- [x] Write status tracker (`memory-bank/status.md`)
- [x] Environment setup (deps + local `.env` placeholder; gitignored)
- [x] FastAPI backend & `products.csv`
- [x] CSV conversation logging (`conversation_log.csv`, four fields)
- [x] AI agent development (Groq, max 3 tries)
- [x] System testing & validation (rubric live run 10/10)

## How to run

1. Set `GROQ_API_KEY` in local `.env` (do not commit).
2. `python -m pip install -r requirements.txt`
3. Terminal 1: `python -m uvicorn app.api:app --reload`
4. Terminal 2: `python agent.py`

## Last updated

2026-08-07 — Aligned to rubric: `products.csv` + `conversation_log.csv`; context/evaluate updated.
