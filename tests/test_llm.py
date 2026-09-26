"""Tests de LLMClient con respuestas de Groq simuladas (httpx2.MockTransport).

Ningún test llega a Internet: la fixture `no_real_network` hace fallar cualquier
intento de conexión real.
"""

import json

import httpx2
import pytest

from inventory_app.config import GROQ_API_KEY_VAR, get_settings
from inventory_app.llm import GROQ_CHAT_URL, MODEL, LLMClient, LLMError

FAKE_KEY = "gsk_clave_falsa_para_tests_123"
MESSAGES = [
    {"role": "system", "content": "Eres el asistente de inventario."},
    {"role": "user", "content": "¿Qué productos están por agotarse?"},
]
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_low_stock",
            "description": "Productos por agotarse.",
            "parameters": {"type": "object", "properties": {}},
        },
    }
]


@pytest.fixture(autouse=True)
def no_real_network(monkeypatch):
    def refuse(self, request):
        raise AssertionError(f"Intento de conexión real a {request.url.host}")

    monkeypatch.setattr(httpx2.HTTPTransport, "handle_request", refuse)


def llm_answering(handler):
    """LLMClient cuyo transporte simulado responde con `handler`; devuelve también las peticiones."""
    requests = []

    def record(request):
        requests.append(request)
        return handler(request)

    http = httpx2.Client(transport=httpx2.MockTransport(record))
    return LLMClient(FAKE_KEY, http=http), requests


def groq_reply(message: dict) -> httpx2.Response:
    return httpx2.Response(200, json={"choices": [{"index": 0, "message": message}]})


def assert_safe(error: LLMError):
    assert FAKE_KEY not in str(error)
    assert "Bearer" not in str(error)


# --- Configuración y construcción ----------------------------------------------------


@pytest.mark.parametrize("api_key", [None, ""])
def test_client_requires_api_key(api_key):
    with pytest.raises(LLMError, match="GROQ_API_KEY"):
        LLMClient(api_key)


def test_settings_read_groq_api_key(monkeypatch):
    monkeypatch.setenv(GROQ_API_KEY_VAR, FAKE_KEY)
    assert get_settings().groq_api_key == FAKE_KEY

    monkeypatch.setenv(GROQ_API_KEY_VAR, "  ")
    assert get_settings().groq_api_key is None


def test_default_http_client_would_use_the_network_and_is_blocked_in_tests():
    # Sin cliente inyectado, LLMClient crea un httpx2.Client real; la fixture lo bloquea.
    with pytest.raises(AssertionError, match="api.groq.com"):
        LLMClient(FAKE_KEY).complete(MESSAGES)


# --- Petición --------------------------------------------------------------------------


def test_request_sends_model_messages_tools_and_auth_header():
    llm, requests = llm_answering(lambda request: groq_reply({"role": "assistant", "content": "Hola"}))

    llm.complete(MESSAGES, TOOLS)

    [request] = requests
    assert request.method == "POST"
    assert str(request.url) == GROQ_CHAT_URL
    assert request.headers["Authorization"] == f"Bearer {FAKE_KEY}"
    assert json.loads(request.content) == {"model": MODEL, "messages": MESSAGES, "tools": TOOLS}


def test_request_without_tools_does_not_send_tools():
    llm, requests = llm_answering(lambda request: groq_reply({"role": "assistant", "content": "Hola"}))

    llm.complete(MESSAGES)

    assert "tools" not in json.loads(requests[0].content)


# --- Respuestas ------------------------------------------------------------------------


def test_text_response():
    llm, _ = llm_answering(
        lambda request: groq_reply({"role": "assistant", "content": "Están por agotarse 2 productos."})
    )

    assert llm.complete(MESSAGES) == {
        "content": "Están por agotarse 2 productos.",
        "tool_calls": [],
        "message": {"role": "assistant", "content": "Están por agotarse 2 productos."},
    }


def test_tool_calls_response():
    raw_tool_calls = [
        {"id": "call_1", "type": "function", "function": {"name": "get_low_stock", "arguments": "{}"}},
        {
            "id": "call_2",
            "type": "function",
            "function": {"name": "add_stock", "arguments": '{"name": "Leche de avena", "quantity": 30}'},
        },
    ]
    llm, _ = llm_answering(
        lambda request: groq_reply({"role": "assistant", "content": None, "tool_calls": raw_tool_calls})
    )

    response = llm.complete(MESSAGES, TOOLS)

    assert response["content"] == ""
    assert response["tool_calls"] == [
        {"id": "call_1", "name": "get_low_stock", "arguments": {}},
        {"id": "call_2", "name": "add_stock", "arguments": {"name": "Leche de avena", "quantity": 30}},
    ]
    # Mensaje listo para añadirlo al historial antes de enviar los resultados de las herramientas.
    assert response["message"] == {"role": "assistant", "content": "", "tool_calls": raw_tool_calls}


# --- Errores ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (
            httpx2.Response(
                401,
                json={"error": {"message": f"Invalid API Key {FAKE_KEY}", "code": "invalid_api_key"}},
            ),
            "HTTP 401, invalid_api_key",
        ),
        (httpx2.Response(500, text="Internal Server Error"), "HTTP 500"),
    ],
)
def test_http_error_becomes_llm_error(response, expected):
    llm, _ = llm_answering(lambda request: response)

    with pytest.raises(LLMError, match=expected) as exc_info:
        llm.complete(MESSAGES)
    assert_safe(exc_info.value)
    assert "Invalid API Key" not in str(exc_info.value)  # no se copia el mensaje de Groq


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (httpx2.ConnectError, "No se puede conectar con Groq"),
        (httpx2.ReadTimeout, "no respondió a tiempo"),
    ],
)
def test_connection_error_and_timeout_become_llm_error(error, expected):
    def fail(request):
        raise error("detalle interno de httpx2", request=request)

    llm, _ = llm_answering(fail)

    with pytest.raises(LLMError, match=expected) as exc_info:
        llm.complete(MESSAGES)
    assert_safe(exc_info.value)
    assert "detalle interno" not in str(exc_info.value)


def _tool_call(arguments: str) -> dict:
    return {"id": "call_1", "type": "function", "function": {"name": "add_stock", "arguments": arguments}}


@pytest.mark.parametrize(
    "response",
    [
        httpx2.Response(200, text="esto no es JSON"),
        httpx2.Response(200, json={"choices": []}),
        httpx2.Response(200, json={"choices": [{"message": {"role": "assistant", "content": 123}}]}),
        groq_reply({"role": "assistant", "tool_calls": [_tool_call("no es JSON")]}),
        groq_reply({"role": "assistant", "tool_calls": [_tool_call("[1, 2]")]}),
    ],
)
def test_unexpected_response_becomes_llm_error(response):
    llm, _ = llm_answering(lambda request: response)

    with pytest.raises(LLMError, match="formato inesperado") as exc_info:
        llm.complete(MESSAGES)
    assert_safe(exc_info.value)
