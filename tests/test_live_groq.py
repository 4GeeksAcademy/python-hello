"""Pruebas reales contra Groq (consumen tokens). No forman parte de la suite normal.

Solo se ejecutan de forma explícita:

    $env:GROQ_LIVE = "1"; pytest tests/test_live_groq.py

Comprueban lo que los tests simulados no pueden:

* que el endpoint, el modelo y el formato de tool calls siguen siendo los que espera
  LLMClient;
* que el agente completo, con el modelo real, cumple los flujos del enunciado sobre una
  copia del inventario inicial real (con la API en TestClient).

Para no depender del texto exacto del modelo, se comprueban los efectos: las cantidades
guardadas en el CSV y las herramientas que quedan registradas en el log.
"""

import csv
import json
import os
import shutil

import pytest
from fastapi.testclient import TestClient

import agent
from inventory_app.api import create_app
from inventory_app.api_client import InventoryApiClient
from inventory_app.config import DEFAULT_INVENTORY_CSV_PATH, get_settings
from inventory_app.conversation_log import ConversationLogger
from inventory_app.llm import LLMClient
from inventory_app.repository import CsvInventoryRepository
from inventory_app.service import InventoryService

pytestmark = pytest.mark.skipif(
    os.getenv("GROQ_LIVE") != "1", reason="prueba real con Groq: requiere GROQ_LIVE=1"
)


@pytest.fixture
def llm() -> LLMClient:
    api_key = get_settings().groq_api_key
    if not api_key:
        pytest.fail("GROQ_API_KEY no está definida en .env")
    return LLMClient(api_key)


# --- LLMClient ---------------------------------------------------------------------------


def test_live_text_response(llm):
    response = llm.complete([{"role": "user", "content": "Responde solo con la palabra: hola"}])

    assert response["content"].strip()
    assert response["tool_calls"] == []


def test_live_tool_call(llm):
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_low_stock",
                "description": "Devuelve los productos del inventario que están por agotarse.",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]

    response = llm.complete(
        [{"role": "user", "content": "¿Qué productos están por agotarse? Usa la herramienta."}], tools
    )

    assert [call["name"] for call in response["tool_calls"]] == ["get_low_stock"]
    # Solo se comprueba que los argumentos llegan como objeto: en la primera prueba real,
    # el modelo envió {"": {}} para esta herramienta sin parámetros. Qué hacer con
    # argumentos inesperados es responsabilidad del agente (Fase 6), no de LLMClient.
    assert isinstance(response["tool_calls"][0]["arguments"], dict)


# --- Agente completo con el modelo real (flujos del enunciado) ----------------------------


@pytest.fixture
def real_inventory(tmp_path):
    """API sobre una copia del inventario inicial real. Devuelve (cliente, ruta de la copia)."""
    csv_copy = tmp_path / "inventory.csv"
    shutil.copyfile(DEFAULT_INVENTORY_CSV_PATH, csv_copy)
    app = create_app(InventoryService(CsvInventoryRepository(csv_copy)))
    return InventoryApiClient(TestClient(app)), csv_copy


def run_turn(llm, api, tmp_path, text: str) -> tuple[str, list[dict]]:
    """Ejecuta un mensaje con el agente real; devuelve la respuesta y las herramientas ejecutadas."""
    log_path = tmp_path / "conversation_log.csv"
    messages = [{"role": "system", "content": agent.SYSTEM_PROMPT}]
    reply = agent.handle_message(text, messages, llm, api, ConversationLogger(log_path))

    with log_path.open(encoding="utf-8", newline="") as file:
        rows = [row for row in csv.DictReader(file) if row["actor"] == "tool"]
    executed = [
        {**json.loads(row["tool_call"]), "outcome": json.loads(row["message"])} for row in rows
    ]

    # La respuesta no se compara literalmente: solo debe ser una respuesta final real.
    assert reply.strip()
    assert reply != agent.LIMIT_REPLY
    assert not reply.startswith("No he podido consultar el modelo")
    return reply, executed


def quantities(csv_path) -> dict[str, int]:
    """Cantidades leídas del archivo en disco con un repositorio nuevo."""
    return {p.name: p.quantity for p in CsvInventoryRepository(csv_path).load()}


def test_live_f1_stock_arrival(llm, real_inventory, tmp_path):
    api, csv_path = real_inventory
    before = quantities(csv_path)

    _, executed = run_turn(llm, api, tmp_path, "Acaban de llegar 30 unidades de leche de avena.")

    assert quantities(csv_path) == {**before, "Leche de avena": before["Leche de avena"] + 30}
    assert any(t["name"] == "add_stock" and "result" in t["outcome"] for t in executed)


def test_live_f2_sale_with_approximate_name(llm, real_inventory, tmp_path):
    # "arábica" no es el nombre exacto: el modelo debe llegar a "Café arábica" por el
    # camino que quiera (list_products u otro), sin exigir una secuencia concreta.
    api, csv_path = real_inventory
    before = quantities(csv_path)

    _, executed = run_turn(llm, api, tmp_path, "Vendimos 12 bolsas de arábica hoy.")

    assert quantities(csv_path) == {**before, "Café arábica": before["Café arábica"] - 12}
    assert any(t["name"] == "remove_stock" and "result" in t["outcome"] for t in executed)


def test_live_f3_low_stock(llm, real_inventory, tmp_path):
    api, csv_path = real_inventory
    original = csv_path.read_bytes()

    reply, executed = run_turn(llm, api, tmp_path, "¿Qué productos están por agotarse?")

    # Inventario inicial: Leche de avena (12 <= 20), Tapas para vasos 12 oz (150 <= 200)
    # y Jarabe de vainilla (4 <= 4, caso límite).
    for keyword in ("avena", "tapas", "vainilla"):
        assert keyword in reply.lower()
    assert any(t["name"] in ("get_low_stock", "list_products") and "result" in t["outcome"] for t in executed)
    assert csv_path.read_bytes() == original


def test_live_f4_unknown_product_is_not_created(llm, real_inventory, tmp_path):
    api, csv_path = real_inventory
    original = csv_path.read_bytes()

    _, executed = run_turn(llm, api, tmp_path, "Acaban de llegar 10 unidades de leche de almendras.")

    assert all(t["name"] != "create_product" for t in executed)
    assert csv_path.read_bytes() == original


def test_live_f5_insufficient_stock_does_not_change_csv(llm, real_inventory, tmp_path):
    # Hay 40 bolsas de Café arábica y se piden 50. Con el modelo real se verifica que no
    # se vende más de lo disponible y que la decisión se basa en datos reales:
    # * el modelo consulta el stock (list_products) y se niega, o intenta la salida
    #   (remove_stock) y recibe InsufficientStock de la API real; ambas son válidas;
    # * no basta con responder sin consultar nada;
    # * el CSV no cambia.
    # En las pruebas observadas el modelo consulta list_products y se niega. El camino
    # remove_stock → InsufficientStock → modelo lo cubre de forma determinista
    # test_agent.py::test_tool_error_is_sent_to_the_model.
    api, csv_path = real_inventory
    original = csv_path.read_bytes()

    _, executed = run_turn(llm, api, tmp_path, "Vendimos 50 bolsas de café arábica.")

    assert csv_path.read_bytes() == original
    assert any(t["name"] in ("list_products", "remove_stock") for t in executed)
    for t in executed:
        if t["name"] == "remove_stock":
            assert t["outcome"]["error"]["type"] == "InsufficientStock"
