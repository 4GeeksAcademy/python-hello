"""Tests del bucle del agente.

Solo el modelo es falso (FakeLLM, con respuestas guionizadas en el formato de
LLMClient) para que los tests sean deterministas y no consuman Groq. Las herramientas
llegan a la API real mediante TestClient sobre un CSV temporal, y el registro se
escribe en un archivo temporal.
"""

import copy
import csv
import json
import shutil
import threading
import time

import pytest
import uvicorn

import agent
from inventory_app.api import create_app
from inventory_app.api_client import InventoryApiClient
from inventory_app.config import (
    DEFAULT_INVENTORY_API_URL,
    DEFAULT_INVENTORY_CSV_PATH,
    INVENTORY_API_URL_VAR,
    get_settings,
)
from inventory_app.conversation_log import ConversationLogger
from inventory_app.llm import LLMError
from inventory_app.repository import CsvInventoryRepository
from inventory_app.service import InventoryService


class FakeLLM:
    """Devuelve las respuestas indicadas, en orden, y guarda lo que recibe en cada llamada."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def complete(self, messages, tools=None):
        self.calls.append({"messages": copy.deepcopy(messages), "tools": tools})
        if not self.responses:
            raise AssertionError("Llamada al modelo no prevista en el test")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def text(content: str) -> dict:
    """Respuesta final del modelo (sin herramientas)."""
    return {"content": content, "tool_calls": [], "message": {"role": "assistant", "content": content}}


def tool_call(name: str, arguments: dict, call_id: str = "call_1") -> dict:
    """Respuesta del modelo que pide una herramienta."""
    raw = [{"id": call_id, "type": "function", "function": {"name": name, "arguments": json.dumps(arguments)}}]
    return {
        "content": "",
        "tool_calls": [{"id": call_id, "name": name, "arguments": arguments}],
        "message": {"role": "assistant", "content": "", "tool_calls": raw},
    }


@pytest.fixture
def api(client) -> InventoryApiClient:
    """Cliente de la API real sobre el CSV temporal con `sample_products`."""
    return InventoryApiClient(client)


@pytest.fixture
def log_path(tmp_path):
    return tmp_path / "conversation_log.csv"


@pytest.fixture
def logger(log_path) -> ConversationLogger:
    return ConversationLogger(log_path)


@pytest.fixture
def messages() -> list[dict]:
    return [{"role": "system", "content": agent.SYSTEM_PROMPT}]


def log_rows(path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def tool_result(message: dict) -> dict:
    assert message["role"] == "tool"
    return json.loads(message["content"])


# --- Bucle -----------------------------------------------------------------------------


def test_direct_answer_without_tools(messages, api, logger):
    llm = FakeLLM(text("¡Hola! ¿En qué te ayudo?"))

    reply = agent.handle_message("Hola", messages, llm, api, logger)

    assert reply == "¡Hola! ¿En qué te ayudo?"
    assert len(llm.calls) == 1  # respuesta final: el bucle termina
    assert llm.calls[0]["tools"] == agent.TOOL_DEFINITIONS
    assert [m["role"] for m in messages] == ["system", "user", "assistant"]


def test_tool_result_is_sent_back_to_the_model(messages, api, logger):
    llm = FakeLLM(tool_call("get_low_stock", {}), text("Por agotarse: leche de avena y jarabe de vainilla."))

    reply = agent.handle_message("¿Qué productos están por agotarse?", messages, llm, api, logger)

    assert reply == "Por agotarse: leche de avena y jarabe de vainilla."
    second_call = llm.calls[1]["messages"]
    assert second_call[-1]["tool_call_id"] == "call_1"
    result = tool_result(second_call[-1])
    assert [p["name"] for p in result["result"]] == ["Leche de avena", "Jarabe de vainilla"]


def test_consecutive_tool_calls(messages, api, logger, service):
    llm = FakeLLM(
        tool_call("list_products", {}, "call_1"),
        tool_call("add_stock", {"name": "Leche de avena", "quantity": 30}, "call_2"),
        text("Registradas 30 unidades de leche de avena: ahora hay 42."),
    )

    agent.handle_message("Acaban de llegar 30 unidades de leche de avena", messages, llm, api, logger)

    assert len(llm.calls) == 3
    assert tool_result(llm.calls[2]["messages"][-1])["result"]["quantity"] == 42
    assert service.get_product("Leche de avena").quantity == 42
    assert [m["role"] for m in messages] == ["system", "user", "assistant", "tool", "assistant", "tool", "assistant"]


def test_remove_stock_keeps_positive_quantity(messages, api, logger, service):
    llm = FakeLLM(tool_call("remove_stock", {"name": "Café arábica", "quantity": 12}), text("Hecho."))

    agent.handle_message("Vendimos 12 bolsas de arábica", messages, llm, api, logger)

    assert service.get_product("Café arábica").quantity == 28


def test_create_product(messages, api, logger, service):
    arguments = {"name": "Leche entera", "quantity": 48, "unit": "unidades", "min_stock": 24}
    llm = FakeLLM(tool_call("create_product", arguments), text("Registrada la leche entera."))

    agent.handle_message("Sí, regístrala: 48 unidades, mínimo 24", messages, llm, api, logger)

    assert tool_result(llm.calls[1]["messages"][-1])["result"]["name"] == "Leche entera"
    assert service.get_product("Leche entera").quantity == 48


# --- Errores de las herramientas ---------------------------------------------------------


def test_tool_error_is_sent_to_the_model(messages, api, logger, service):
    llm = FakeLLM(
        tool_call("remove_stock", {"name": "Café arábica", "quantity": 50}),
        text("No hay suficiente café arábica: quedan 40 bolsas."),
    )

    reply = agent.handle_message("Vendimos 50 bolsas de café arábica", messages, llm, api, logger)

    error = tool_result(llm.calls[1]["messages"][-1])["error"]
    assert error["type"] == "InsufficientStock"
    assert "hay 40" in error["message"]
    assert service.get_product("Café arábica").quantity == 40
    assert reply == "No hay suficiente café arábica: quedan 40 bolsas."


@pytest.mark.parametrize(
    ("name", "arguments", "error_type"),
    [
        ("delete_product", {"name": "Leche de avena"}, "UnknownTool"),
        ("get_low_stock", {"": {}}, "InvalidArguments"),  # observado con el modelo real
        ("add_stock", {"name": "Leche de avena"}, "InvalidArguments"),  # falta quantity
        ("add_stock", {"name": "Leche de avena", "quantity": 5, "unit": "cajas"}, "InvalidArguments"),
        ("remove_stock", {"name": 7, "quantity": 1}, "InvalidArguments"),  # nombre que no es texto
        ("add_stock", {"name": "Leche de avena", "quantity": -5}, "InvalidStockChange"),
    ],
)
def test_invalid_tool_request_is_reported_to_the_model(messages, api, logger, service, name, arguments, error_type):
    llm = FakeLLM(tool_call(name, arguments), text("No he podido hacerlo."))

    agent.handle_message("Haz algo", messages, llm, api, logger)

    assert tool_result(llm.calls[1]["messages"][-1])["error"]["type"] == error_type
    assert service.get_product("Leche de avena").quantity == 12


def test_create_existing_product_is_reported_to_the_model(messages, api, logger):
    arguments = {"name": "leche de avena", "quantity": 1, "unit": "unidades", "min_stock": 0}
    llm = FakeLLM(tool_call("create_product", arguments), text("Ese producto ya existe."))

    agent.handle_message("Registra leche de avena", messages, llm, api, logger)

    assert tool_result(llm.calls[1]["messages"][-1])["error"]["type"] == "ProductAlreadyExists"


# --- Historial, registro y límites ---------------------------------------------------------


def test_history_is_kept_between_turns(messages, api, logger):
    llm = FakeLLM(text("Hola, Carla."), text("Te decía hola."))

    agent.handle_message("Hola", messages, llm, api, logger)
    agent.handle_message("¿Qué me has dicho antes?", messages, llm, api, logger)

    second_turn = llm.calls[1]["messages"]
    assert [m["content"] for m in second_turn[1:]] == ["Hola", "Hola, Carla.", "¿Qué me has dicho antes?"]


def test_multi_step_create_product_then_ask_for_low_stock(messages, api, logger, csv_path):
    # Dos turnos de la misma sesión (misma lista `messages`): el turno 2 usa el estado
    # real que dejó el turno 1. La API es la real de la prueba (TestClient sobre el CSV
    # temporal); solo el modelo es falso.
    new_product = {"name": "Leche de coco", "quantity": 2, "unit": "unidades", "min_stock": 5}
    llm = FakeLLM(
        tool_call("create_product", new_product, "call_1"),
        text("Registrada la leche de coco."),
        tool_call("get_low_stock", {}, "call_2"),
        text("Por agotarse: leche de avena, jarabe de vainilla y leche de coco."),
    )

    # Turno 1: registrar un producto nuevo con stock bajo (2 <= 5).
    agent.handle_message("Registra la leche de coco: 2 unidades, stock mínimo 5", messages, llm, api, logger)

    saved = {p.name: p for p in CsvInventoryRepository(csv_path).load()}
    assert saved["Leche de coco"].quantity == 2 and saved["Leche de coco"].low_stock

    # Turno 2: preguntar por las alertas.
    agent.handle_message("¿Qué productos están por agotarse?", messages, llm, api, logger)

    # El turno 2 recibe el historial completo del turno 1.
    first_call_turn_2 = llm.calls[2]["messages"]
    assert [m["role"] for m in first_call_turn_2] == ["system", "user", "assistant", "tool", "assistant", "user"]
    assert tool_result(first_call_turn_2[3])["result"]["name"] == "Leche de coco"
    # El resultado real de la API incluye el producto recién creado.
    low_stock = tool_result(llm.calls[3]["messages"][-1])["result"]
    assert [p["name"] for p in low_stock] == ["Leche de avena", "Jarabe de vainilla", "Leche de coco"]


def test_events_are_logged(messages, api, logger, log_path):
    llm = FakeLLM(tool_call("add_stock", {"name": "Leche de avena", "quantity": 30}), text("Hecho: hay 42."))

    agent.handle_message("Llegaron 30 de leche de avena", messages, llm, api, logger)

    rows = log_rows(log_path)
    assert [row["actor"] for row in rows] == ["user", "tool", "agent"]
    assert rows[0]["message"] == "Llegaron 30 de leche de avena"
    assert json.loads(rows[1]["tool_call"]) == {
        "name": "add_stock",
        "arguments": {"name": "Leche de avena", "quantity": 30},
    }
    assert rows[1]["message"] == messages[3]["content"]  # el mismo resultado que recibió el modelo
    assert (rows[2]["message"], rows[2]["tool_call"]) == ("Hecho: hay 42.", "")


def test_loop_stops_after_max_steps(messages, api, logger, log_path):
    llm = FakeLLM(*[tool_call("get_low_stock", {}, f"call_{i}") for i in range(agent.MAX_STEPS)])

    reply = agent.handle_message("¿Qué falta?", messages, llm, api, logger)

    assert agent.MAX_STEPS == 8
    assert len(llm.calls) == agent.MAX_STEPS  # FakeLLM fallaría con una llamada más
    assert reply == agent.LIMIT_REPLY
    # El mensaje de límite lo genera el agente: se registra, pero no entra en el historial.
    assert messages[-1]["role"] == "tool"
    assert all(m.get("content") != agent.LIMIT_REPLY for m in messages)
    assert log_rows(log_path)[-1]["message"] == agent.LIMIT_REPLY


def test_llm_error_gives_safe_reply_and_session_continues(messages, api, logger, log_path):
    llm = FakeLLM(LLMError("Groq no respondió a tiempo."), text("Ahora sí: hola."))

    reply = agent.handle_message("Hola", messages, llm, api, logger)

    assert reply == "No he podido consultar el modelo de lenguaje: Groq no respondió a tiempo."
    row = log_rows(log_path)[-1]
    assert (row["actor"], row["message"], row["tool_call"]) == ("agent", reply, "")
    # El historial no incluye un mensaje "assistant" que el modelo nunca escribió.
    assert [m["role"] for m in messages] == ["system", "user"]

    assert agent.handle_message("Hola otra vez", messages, llm, api, logger) == "Ahora sí: hola."
    assert [m["content"] for m in llm.calls[1]["messages"][1:]] == ["Hola", "Hola otra vez"]


# --- CLI y configuración -------------------------------------------------------------------


def test_cli_stops_when_log_cannot_be_written(monkeypatch, capsys, tmp_path):
    bad_log = tmp_path / "conversation_log.csv"
    bad_log.write_text("otra,cabecera\n", encoding="utf-8")
    monkeypatch.setattr(agent, "LOG_PATH", bad_log)
    monkeypatch.setattr(agent, "LLMClient", lambda api_key: FakeLLM(text("no debería llegar")))
    monkeypatch.setenv("GROQ_API_KEY", "clave-falsa")
    monkeypatch.setattr("builtins.input", lambda prompt: "Hola")

    assert agent.main() == 1

    out = capsys.readouterr().out
    assert "no se puede escribir el registro de conversaciones" in out
    assert str(tmp_path) not in out  # sin rutas internas
    assert bad_log.read_text(encoding="utf-8") == "otra,cabecera\n"


def test_log_is_append_only_across_two_agent_sessions(monkeypatch, tmp_path):
    # Dos ejecuciones completas de main() sobre el mismo log: cada una crea su propio
    # logger, su propio historial y su propio modelo, como dos arranques del programa.
    log_path = tmp_path / "conversation_log.csv"
    monkeypatch.setattr(agent, "LOG_PATH", log_path)
    monkeypatch.setenv("GROQ_API_KEY", "clave-falsa")
    session_llms = []

    def run_session(user_text: str, reply: str):
        llm = FakeLLM(text(reply))
        session_llms.append(llm)
        monkeypatch.setattr(agent, "LLMClient", lambda api_key: llm)
        user_inputs = iter([user_text, "salir"])
        monkeypatch.setattr("builtins.input", lambda prompt: next(user_inputs))
        assert agent.main() == 0

    run_session("Hola, soy Carla", "Hola, Carla.")
    after_first_session = log_path.read_bytes()
    run_session("¿Qué falta?", "Nada por ahora.")

    content = log_path.read_bytes()
    # La primera sesión queda intacta byte a byte y la segunda solo añade filas.
    assert content.startswith(after_first_session) and len(content) > len(after_first_session)
    assert content.decode("utf-8").count("actor,message,tool_call,timestamp") == 1
    assert [(row["actor"], row["message"]) for row in log_rows(log_path)] == [
        ("user", "Hola, soy Carla"),
        ("agent", "Hola, Carla."),
        ("user", "¿Qué falta?"),
        ("agent", "Nada por ahora."),
    ]
    # Son sesiones independientes: la segunda no recibe el historial de la primera.
    assert [m["content"] for m in session_llms[1].calls[0]["messages"][1:]] == ["¿Qué falta?"]


@pytest.fixture
def http_api_server(tmp_path):
    """API real servida por Uvicorn en un hilo, sobre una copia del inventario inicial.

    Devuelve (url, ruta_de_la_copia). El puerto lo asigna el sistema (port=0).
    """
    csv_copy = tmp_path / "inventory.csv"
    shutil.copyfile(DEFAULT_INVENTORY_CSV_PATH, csv_copy)
    app = create_app(InventoryService(CsvInventoryRepository(csv_copy)))
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.monotonic() + 10
    while not server.started:
        if not thread.is_alive() or time.monotonic() > deadline:
            raise RuntimeError("El servidor Uvicorn de prueba no arrancó")
        time.sleep(0.01)
    port = server.servers[0].sockets[0].getsockname()[1]

    yield f"http://127.0.0.1:{port}", csv_copy

    server.should_exit = True
    thread.join(timeout=10)


def test_cli_end_to_end_with_real_http_server(monkeypatch, capsys, tmp_path, http_api_server):
    # El programa tal como se ejecuta: main() → INVENTORY_API_URL → HTTP real → Uvicorn →
    # servicio → CSV en disco, con el registro de la conversación. Solo el modelo es falso.
    url, csv_path = http_api_server
    log_path = tmp_path / "conversation_log.csv"
    original = {p.name: p.quantity for p in CsvInventoryRepository(csv_path).load()}
    llm = FakeLLM(
        tool_call("add_stock", {"name": "Leche de avena", "quantity": 30}),
        text("Registradas 30 unidades de leche de avena: ahora hay 42."),
    )
    monkeypatch.setattr(agent, "LLMClient", lambda api_key: llm)
    monkeypatch.setattr(agent, "LOG_PATH", log_path)
    monkeypatch.setenv(INVENTORY_API_URL_VAR, url)
    monkeypatch.setenv("GROQ_API_KEY", "clave-falsa")
    user_inputs = iter(["Acaban de llegar 30 unidades de leche de avena", "salir"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(user_inputs))

    assert agent.main() == 0

    # Salida de la CLI.
    assert "Carla: Registradas 30 unidades de leche de avena: ahora hay 42." in capsys.readouterr().out
    # El modelo recibió lo que respondió el servidor por HTTP.
    assert tool_result(llm.calls[1]["messages"][-1])["result"]["quantity"] == 42
    # Persistencia real: el archivo en disco, leído con un repositorio nuevo.
    saved = {p.name: p.quantity for p in CsvInventoryRepository(csv_path).load()}
    assert saved == {**original, "Leche de avena": original["Leche de avena"] + 30}
    # Registro de la conversación.
    rows = log_rows(log_path)
    assert [row["actor"] for row in rows] == ["user", "tool", "agent"]
    assert json.loads(rows[1]["tool_call"]) == {
        "name": "add_stock",
        "arguments": {"name": "Leche de avena", "quantity": 30},
    }
    assert log_path.read_text(encoding="utf-8").count("actor,message,tool_call,timestamp") == 1


def test_inventory_api_url_setting(monkeypatch):
    monkeypatch.setenv(INVENTORY_API_URL_VAR, "")
    assert get_settings().inventory_api_url == DEFAULT_INVENTORY_API_URL == "http://127.0.0.1:8000"

    monkeypatch.setenv(INVENTORY_API_URL_VAR, "http://localhost:9000")
    assert get_settings().inventory_api_url == "http://localhost:9000"
