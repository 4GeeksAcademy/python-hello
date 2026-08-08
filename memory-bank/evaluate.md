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

## Evaluation results (live run)

**Score: 10 / 10**

| Criterion | Result | Evidence |
|-----------|--------|----------|
| Four required endpoints | **Pass** | GET /products -> 200; GET /products/low-stock -> 200; POST /products/receive -> 200; POST /products/sell -> 200 |
| Products persisted in products.csv and survive restart | **Pass** | path=products.csv; written=True; reload_sees_product=True |
| Agent loop Observe-Think-Act-Update-Repeat | **Pass** | handle_user_message contains Groq call, tool execution, message updates, and repeat loop |
| Tools have names, descriptions, typed parameters | **Pass** | tools=['list_products', 'receive_stock', 'sell_stock', 'low_stock'] |
| Agent calls correct API endpoint for each tool | **Pass** | execute_tool maps list/receive/sell/low_stock to matching paths |
| LLM/tool result injected into conversation history | **Pass** | tool and assistant messages appended to messages before next iteration |
| conversation_log.csv created with all four fields | **Pass** | file=conversation_log.csv; header=['author', 'content', 'tool_call', 'timestamp']; rows_logged=31 |
| Log is append-only across sessions | **Pass** | open_mode_append=True; rows_before=45; rows_after=48 |
| Multi-step interaction support | **Pass** | main() reuses the same messages list across user turns |
| No agent framework; hand-coded loop | **Pass** | No banned frameworks in agent.py/requirements; custom loop present |

