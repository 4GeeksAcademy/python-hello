"""Tests de la API a través de HTTP con TestClient.

Las reglas de validación (nombres, enteros estrictos) se prueban caso a caso en los
tests del modelo; aquí basta un caso representativo de cada una para comprobar que
llegan al cliente con el código HTTP y el formato de error correctos.
"""

import logging

import pytest
from fastapi.testclient import TestClient

from inventory_app.api import create_app
from inventory_app.config import INVENTORY_CSV_PATH_VAR
from inventory_app.repository import CsvInventoryRepository
from inventory_app.service import InventoryService

CAFE = {"name": "Café arábica", "quantity": 40, "unit": "bolsas", "min_stock": 10, "low_stock": False}
LECHE = {"name": "Leche de avena", "quantity": 12, "unit": "unidades", "min_stock": 20, "low_stock": True}
JARABE = {"name": "Jarabe de vainilla", "quantity": 4, "unit": "botellas", "min_stock": 4, "low_stock": True}

NEW_PRODUCT = {"name": "Leche entera", "quantity": 48, "unit": "unidades", "min_stock": 24}


def assert_error(response, status_code: int, code: str) -> dict:
    """Comprueba el código HTTP y el formato uniforme de error; devuelve `details`."""
    assert response.status_code == status_code
    body = response.json()
    assert set(body) == {"code", "message", "details"}
    assert body["code"] == code
    assert isinstance(body["message"], str) and body["message"]
    assert isinstance(body["details"], dict)
    return body["details"]


def error_fields(response) -> list[str]:
    return [error["field"] for error in response.json()["details"]["errors"]]


# --- Salud ----------------------------------------------------------------------


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# --- Consultar ----------------------------------------------------------------------


def test_list_products(client):
    response = client.get("/products")
    assert response.status_code == 200
    assert response.json() == [CAFE, LECHE, JARABE]


def test_list_low_stock(client):
    # Leche de avena: 12 <= 20; Jarabe de vainilla: 4 <= 4 (límite).
    # Además demuestra que /products/low-stock no se interpreta como un nombre de producto.
    response = client.get("/products/low-stock")
    assert response.status_code == 200
    assert response.json() == [LECHE, JARABE]


def test_get_product(client):
    response = client.get("/products/Leche de avena")
    assert response.status_code == 200
    assert response.json() == LECHE


def test_get_product_with_encoded_name(client):
    # Así llega un nombre con espacios y acentos en la URL; además, en otras mayúsculas.
    response = client.get("/products/caf%C3%A9%20AR%C3%81BICA")
    assert response.status_code == 200
    assert response.json() == CAFE


def test_get_missing_product(client):
    details = assert_error(client.get("/products/Leche de almendras"), 404, "product_not_found")
    assert details == {"name": "Leche de almendras"}


# --- Registrar ---------------------------------------------------------------------


def test_create_product(client, csv_path):
    response = client.post("/products", json=NEW_PRODUCT)

    assert response.status_code == 201
    assert response.json() == {**NEW_PRODUCT, "low_stock": False}
    # Se ha guardado en el CSV: otro repositorio lo lee.
    reloaded = InventoryService(CsvInventoryRepository(csv_path))
    assert reloaded.get_product("Leche entera").quantity == 48


def test_create_duplicate_product(client, csv_path):
    original = csv_path.read_bytes()

    response = client.post("/products", json={**NEW_PRODUCT, "name": "LECHE DE AVENA"})

    details = assert_error(response, 409, "product_already_exists")
    assert details == {"name": "LECHE DE AVENA"}
    assert csv_path.read_bytes() == original


@pytest.mark.parametrize("name", ["Leche 1/2", "Leche  de avena", "low-stock"])
def test_create_product_with_invalid_name(client, csv_path, name):
    original = csv_path.read_bytes()

    response = client.post("/products", json={**NEW_PRODUCT, "name": name})

    assert_error(response, 422, "validation_error")
    assert error_fields(response) == ["body.name"]
    assert csv_path.read_bytes() == original


@pytest.mark.parametrize("quantity", [-1, "10"])
def test_create_product_with_invalid_quantity(client, quantity):
    response = client.post("/products", json={**NEW_PRODUCT, "quantity": quantity})
    assert_error(response, 422, "validation_error")
    assert error_fields(response) == ["body.quantity"]


def test_create_product_with_malformed_json(client):
    response = client.post(
        "/products", content="{no es json", headers={"Content-Type": "application/json"}
    )
    assert_error(response, 422, "validation_error")


# --- Ajustar stock -------------------------------------------------------------------


def test_add_stock(client):
    response = client.post("/products/Leche de avena/stock", json={"change": 30})

    assert response.status_code == 200
    assert response.json() == {**LECHE, "quantity": 42, "low_stock": False}
    assert client.get("/products/Leche de avena").json()["quantity"] == 42


def test_remove_stock(client):
    response = client.post("/products/Café arábica/stock", json={"change": -12})

    assert response.status_code == 200
    assert response.json() == {**CAFE, "quantity": 28}
    assert client.get("/products/Café arábica").json()["quantity"] == 28


def test_insufficient_stock(client, csv_path):
    original = csv_path.read_bytes()

    response = client.post("/products/Jarabe de vainilla/stock", json={"change": -5})

    details = assert_error(response, 409, "insufficient_stock")
    assert details == {"name": "Jarabe de vainilla", "available": 4, "requested": 5}
    assert csv_path.read_bytes() == original


def test_stock_change_of_zero(client, csv_path):
    original = csv_path.read_bytes()

    response = client.post("/products/Leche de avena/stock", json={"change": 0})

    assert_error(response, 422, "invalid_stock_change")
    assert csv_path.read_bytes() == original


@pytest.mark.parametrize("body", [{"change": "5"}, {}])
def test_invalid_stock_change(client, body):
    response = client.post("/products/Leche de avena/stock", json=body)
    assert_error(response, 422, "validation_error")
    assert error_fields(response) == ["body.change"]


def test_adjust_stock_of_missing_product(client, csv_path):
    original = csv_path.read_bytes()

    response = client.post("/products/Leche de almendras/stock", json={"change": 5})

    assert_error(response, 404, "product_not_found")
    assert csv_path.read_bytes() == original


# --- Rutas y métodos -------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "/no-existe",
        # Aunque la "/" vaya codificada, el servidor la decodifica antes de elegir ruta:
        # por eso los nombres de producto no pueden contener "/".
        "/products/Leche%201%2F2",
    ],
)
def test_unknown_route(client, path):
    assert_error(client.get(path), 404, "not_found")


def test_method_not_allowed(client):
    response = client.delete("/products/Leche de avena")
    assert_error(response, 405, "method_not_allowed")
    assert response.headers["allow"] == "GET"


# --- Errores de almacenamiento -----------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("GET", "/products", None),
        ("POST", "/products/Leche/stock", {"change": 1}),
    ],
)
def test_storage_error_does_not_expose_internal_paths(
    write_csv, csv_path, caplog, method, path, body
):
    write_csv("nombre,cantidad\nLeche,5\n")  # cabecera inválida
    client = TestClient(create_app(InventoryService(CsvInventoryRepository(csv_path))))

    with caplog.at_level(logging.ERROR, logger="inventory_app.api"):
        response = client.request(method, path, json=body)

    assert_error(response, 500, "storage_error")
    assert str(csv_path) not in response.text
    assert csv_path.name not in response.text
    # El detalle real sí queda en el log del servidor.
    assert str(csv_path) in caplog.text


# --- Creación de la aplicación -------------------------------------------------------------


def test_create_app_uses_configured_csv_and_reads_it_only_on_request(
    monkeypatch, write_csv, csv_path
):
    # Un CSV inválido no impide crear la aplicación: solo falla la petición que lo lee.
    write_csv("contenido inválido\n")
    monkeypatch.setenv(INVENTORY_CSV_PATH_VAR, str(csv_path))

    client = TestClient(create_app())
    assert_error(client.get("/products"), 500, "storage_error")

    write_csv("name,quantity,unit,min_stock\nLeche entera,48,unidades,24\n")
    assert [p["name"] for p in client.get("/products").json()] == ["Leche entera"]
