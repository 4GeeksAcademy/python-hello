# What We Will Evaluate

- [x] The FastAPI exposes all four required endpoints and they return correct responses
- [x] Products are persisted in `products.csv` and survive a server restart
- [x] The agent loop correctly implements the Observe → Think → Act → Update → Repeat cycle
- [x] Tools are defined with names, descriptions, and typed parameters that the LLM can reliably use
- [x] The agent calls the correct API endpoint when the LLM selects a tool
- [x] The LLM result is injected back into the conversation history before the next iteration
- [x] `conversation_log.csv` is created and populated with all four fields on every event
- [x] The log is append-only across multiple sessions
- [x] The agent handles at least one multi-step interaction (e.g., add a product and immediately ask for alerts)
- [x] No agent framework is used — the loop is hand-coded in Python

**Note:** UI design and visual presentation are not evaluated. A terminal interface is sufficient.

---

## Evaluation results (2026-08-07)

**Score: 10 / 10** (gaps closed: `products.csv` + `conversation_log.csv`)

| Criterion | Result | Evidence |
|-----------|--------|----------|
| Four FastAPI endpoints | **Pass** | `GET /products`, `GET /products/low-stock`, `POST /products/receive`, `POST /products/sell` in [`app/api.py`](../app/api.py) |
| Persist in `products.csv` | **Pass** | Inventory read/written via [`products.csv`](../products.csv); survives process restart |
| Observe → Think → Act → Update → Repeat | **Pass** | Hand-coded loop in [`agent.py`](../agent.py) with `MAX_TRIES = 3` |
| Tools with name/description/typed params | **Pass** | `TOOLS` definitions for list/receive/sell/low_stock |
| Tool → correct API endpoint | **Pass** | `execute_tool` maps tool names to HTTP paths |
| Inject tool/LLM result into history | **Pass** | Tool and assistant messages appended before the next Groq call |
| `conversation_log.csv` + four fields | **Pass** | Append-only log with `author`, `content`, `tool_call`, `timestamp` |
| Append-only across sessions | **Pass** | CSV opened in append mode; prior rows retained |
| Multi-step interaction | **Pass** | In-memory `messages` reused across user turns |
| No agent framework | **Pass** | `groq` + `requests` only; no LangChain/etc. |
