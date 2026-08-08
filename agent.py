"""CLI inventory agent for Carla's Bakery Supplies using Groq tool calling."""

from __future__ import annotations

import csv
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
import truststore
from dotenv import load_dotenv
from groq import Groq

# Use the OS certificate store so HTTPS works on Windows (corporate/AV SSL inspection).
truststore.inject_into_ssl()

MAX_TRIES = 3
API_BASE_URL = "http://127.0.0.1:8000"
MODEL = "llama-3.3-70b-versatile"
ROOT = Path(__file__).resolve().parent
CSV_PATH = ROOT / "conversation_history.csv"
PLACEHOLDER_KEY = "your_api_key_here"

SYSTEM_PROMPT = (
    "You are an inventory assistant for Carla's Bakery Supplies. "
    "Help Carla manage stock using the available tools. "
    "Be concise, conversational, and accurate. "
    "Use tools for inventory reads and updates; do not invent stock numbers."
)

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_products",
            "description": "List all products and their current stock levels.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "receive_stock",
            "description": (
                "Register received / delivered stock. Creates the product if it does not exist "
                "(unit required for new products)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Product name"},
                    "quantity": {
                        "type": "number",
                        "description": "Quantity received (must be > 0)",
                    },
                    "unit": {
                        "type": "string",
                        "description": "Unit such as units, bags, kg, liters",
                    },
                },
                "required": ["name", "quantity"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sell_stock",
            "description": "Record a sale by subtracting quantity from an existing product.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Product name"},
                    "quantity": {
                        "type": "number",
                        "description": "Quantity sold (must be > 0)",
                    },
                },
                "required": ["name", "quantity"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "low_stock",
            "description": "List products that are at or below the low-stock threshold.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]


def _ensure_csv_header() -> None:
    if CSV_PATH.exists() and CSV_PATH.stat().st_size > 0:
        return
    with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["session_id", "author", "content", "tool_call", "timestamp"])


def log_event(
    session_id: str,
    author: str,
    content: str,
    tool_call: str = "",
) -> None:
    _ensure_csv_header()
    timestamp = datetime.now(timezone.utc).isoformat()
    with CSV_PATH.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([session_id, author, content, tool_call, timestamp])


def _http_request(method: str, path: str, payload: dict[str, Any] | None = None) -> str:
    url = f"{API_BASE_URL}{path}"
    last_error = "unknown error"
    for attempt in range(1, MAX_TRIES + 1):
        try:
            if method == "GET":
                response = requests.get(url, timeout=10)
            else:
                response = requests.post(url, json=payload or {}, timeout=10)
            if response.status_code >= 500 and attempt < MAX_TRIES:
                last_error = f"HTTP {response.status_code}: {response.text}"
                time.sleep(0.4 * attempt)
                continue
            if response.status_code >= 400:
                return json.dumps(
                    {"error": True, "status": response.status_code, "detail": response.text}
                )
            return response.text
        except requests.RequestException as exc:
            last_error = str(exc)
            if attempt < MAX_TRIES:
                time.sleep(0.4 * attempt)
                continue
    return json.dumps({"error": True, "detail": f"request failed after {MAX_TRIES} tries: {last_error}"})


def execute_tool(name: str, arguments: dict[str, Any]) -> str:
    if name == "list_products":
        return _http_request("GET", "/products")
    if name == "low_stock":
        return _http_request("GET", "/products/low-stock")
    if name == "receive_stock":
        return _http_request("POST", "/products/receive", arguments)
    if name == "sell_stock":
        return _http_request("POST", "/products/sell", arguments)
    return json.dumps({"error": True, "detail": f"unknown tool: {name}"})


def _groq_chat(client: Groq, messages: list[dict[str, Any]]) -> Any:
    last_error: Exception | None = None
    for attempt in range(1, MAX_TRIES + 1):
        try:
            return client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
            )
        except Exception as exc:  # noqa: BLE001 - retry transient LLM failures
            last_error = exc
            if attempt < MAX_TRIES:
                time.sleep(0.5 * attempt)
                continue
            raise RuntimeError(
                f"Groq request failed after {MAX_TRIES} tries: {last_error}"
            ) from last_error


def _tool_calls_to_dict(message: Any) -> list[dict[str, Any]]:
    tool_calls = getattr(message, "tool_calls", None) or []
    serialized = []
    for tc in tool_calls:
        serialized.append(
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
        )
    return serialized


def handle_user_message(
    client: Groq,
    session_id: str,
    messages: list[dict[str, Any]],
    user_text: str,
) -> str:
    log_event(session_id, "user", user_text)
    messages.append({"role": "user", "content": user_text})

    tool_rounds = 0
    while tool_rounds <= MAX_TRIES:
        completion = _groq_chat(client, messages)
        assistant_message = completion.choices[0].message
        tool_calls = getattr(assistant_message, "tool_calls", None) or []

        if not tool_calls:
            reply = (assistant_message.content or "").strip() or "(no response)"
            messages.append({"role": "assistant", "content": reply})
            log_event(session_id, "agent", reply)
            return reply

        tool_rounds += 1
        if tool_rounds > MAX_TRIES:
            break

        messages.append(
            {
                "role": "assistant",
                "content": assistant_message.content or "",
                "tool_calls": _tool_calls_to_dict(assistant_message),
            }
        )

        for tc in tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            result = execute_tool(name, args)
            log_event(session_id, "tool", result, tool_call=name)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": name,
                    "content": result,
                }
            )

    fail_msg = (
        f"I could not finish this request within {MAX_TRIES} tool-calling rounds. "
        "Please try again with a simpler ask."
    )
    messages.append({"role": "assistant", "content": fail_msg})
    log_event(session_id, "agent", fail_msg)
    return fail_msg


def _require_api_key() -> str:
    load_dotenv(ROOT / ".env")
    key = (os.getenv("GROQ_API_KEY") or "").strip()
    if not key or key == PLACEHOLDER_KEY:
        raise SystemExit(
            "GROQ_API_KEY is missing or still set to the placeholder. "
            "Edit the local .env file and set your Groq API key."
        )
    return key


def main() -> None:
    api_key = _require_api_key()
    client = Groq(api_key=api_key)
    session_id = str(uuid.uuid4())
    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]

    print("Carla's Bakery inventory agent (Groq). Type 'quit' or 'exit' to stop.")
    print(f"Session: {session_id}")

    while True:
        try:
            user_text = input("You> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if not user_text:
            continue
        if user_text.lower() in {"quit", "exit"}:
            print("Goodbye.")
            break

        try:
            reply = handle_user_message(client, session_id, messages, user_text)
        except RuntimeError as exc:
            reply = str(exc)
            log_event(session_id, "agent", reply)
        print(f"Agent> {reply}")


if __name__ == "__main__":
    main()
