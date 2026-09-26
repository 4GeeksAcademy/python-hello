"""Tests del cliente HTTP de la API.

El cliente se prueba contra la aplicación FastAPI real mediante TestClient (sin Uvicorn).
Solo las respuestas que la API no puede producir con estos métodos se simulan con
httpx2.MockTransport.
"""

import httpx2
import pytest
from fastapi.testclient import TestClient

from inventory_app.api import create_app
from inventory_app.api_client import InventoryApiClient
from inventory_app.errors import (
    InsufficientStock,
    InvalidStockChange,
    InventoryError,
    ProductAlreadyExists,
    ProductNotFound,
    StorageError,
)
from inventory_app.models import ProductCreate
from inventory_app.repository import CsvInventoryRepository
from inventory_app.service import InventoryService


@pytest.fixture
def api(client) -> InventoryApiClient:
    """Cliente contra la API real con el CSV temporal de `sample_products`."""
    return InventoryApiClient(client)


def api_answering(status_code: int, **response_kwargs) -> InventoryApiClient:
    """Cliente cuya API simulada responde siempre lo mismo."""
    transport = httpx2.MockTransport(lambda request: httpx2.Response(status_code, **response_kwargs))
    return InventoryApiClient(httpx2.Client(transport=transport, base_url="http://api"))


# --- Consultas ---------------------------------------------------------------------


def test_list_products(api):
    products = api.list_products()
    assert [p["name"] for p in products] == ["Café arábica", "Leche de avena", "Jarabe de vainilla"]
    assert products[0] == {
        "name": "Café arábica",
        "quantity": 40,
        "unit": "bolsas",
        "min_stock": 10,
        "low_stock": False,
    }


def test_get_low_stock(api):
    assert [p["name"] for p in api.get_low_stock()] == ["Leche de avena", "Jarabe de vainilla"]


# --- Movimientos de stock ------------------------------------------------------------


def test_add_stock_sends_positive_change(api, service):
    product = api.add_stock("Leche de avena", 30)

    assert product["quantity"] == 42
    assert service.get_product("Leche de avena").quantity == 42


def test_remove_stock_sends_negative_change(api, service):
    product = api.remove_stock("Café arábica", 12)

    assert product["quantity"] == 28
    assert service.get_product("Café arábica").quantity == 28


def test_name_with_spaces_unicode_and_url_characters(api, service):
    # "?", "#" y "%" romperían la URL si el nombre no se codificara por completo.
    name = "Té matcha 抹茶 ¿100%? #1"
    service.create_product(ProductCreate(name=name, quantity=5, unit="latas", min_stock=1))

    product = api.add_stock("té MATCHA 抹茶 ¿100%? #1", 3)

    assert product["name"] == name
    assert product["quantity"] == 8


@pytest.mark.parametrize("method", ["add_stock", "remove_stock"])
@pytest.mark.parametrize("quantity", [0, -3])
def test_non_positive_quantity_is_rejected_before_any_request(method, quantity):
    # Con object() como cliente HTTP, cualquier intento de petición fallaría con
    # AttributeError: si se lanza InvalidStockChange, no se ha llegado a enviar nada.
    api = InventoryApiClient(object())
    with pytest.raises(InvalidStockChange):
        getattr(api, method)("Leche de avena", quantity)


# --- Traducción de errores de la API ------------------------------------------------------


def test_missing_product_raises_product_not_found(api):
    with pytest.raises(ProductNotFound) as exc_info:
        api.add_stock("Leche de almendras", 5)
    assert exc_info.value.name == "Leche de almendras"


def test_insufficient_stock_raises_insufficient_stock(api):
    with pytest.raises(InsufficientStock) as exc_info:
        api.remove_stock("Jarabe de vainilla", 5)
    assert (exc_info.value.name, exc_info.value.available, exc_info.value.requested) == (
        "Jarabe de vainilla",
        4,
        5,
    )


def test_storage_error_raises_storage_error_without_internal_paths(write_csv, csv_path):
    write_csv("nombre,cantidad\nLeche,5\n")  # cabecera inválida
    api = InventoryApiClient(TestClient(create_app(InventoryService(CsvInventoryRepository(csv_path)))))

    with pytest.raises(StorageError) as exc_info:
        api.list_products()
    assert csv_path.name not in str(exc_info.value)


def test_unknown_route_is_not_reported_as_missing_product(api):
    # Un nombre con "/" no llega a ninguna ruta de la API (404 not_found). No es
    # "producto inexistente": con una URL base incorrecta pasaría lo mismo.
    with pytest.raises(InventoryError) as exc_info:
        api.add_stock("Leche 1/2", 5)
    assert exc_info.type is InventoryError


def test_invalid_stock_change_code_raises_invalid_stock_change():
    # El cliente valida la cantidad antes de enviarla, así que la API real no llega a
    # responder invalid_stock_change a estos métodos: se simula la respuesta.
    body = {"code": "invalid_stock_change", "message": "mensaje de la API", "details": {}}

    with pytest.raises(InvalidStockChange):
        api_answering(422, json=body).list_products()


# --- Registrar productos ---------------------------------------------------------------


def test_create_product(api, service):
    product = api.create_product("Leche entera", 48, "unidades", 24)

    assert product == {
        "name": "Leche entera",
        "quantity": 48,
        "unit": "unidades",
        "min_stock": 24,
        "low_stock": False,
    }
    assert service.get_product("leche entera").quantity == 48


def test_create_existing_product_raises_product_already_exists(api):
    with pytest.raises(ProductAlreadyExists) as exc_info:
        api.create_product("LECHE DE AVENA", 1, "unidades", 0)
    assert exc_info.value.name == "LECHE DE AVENA"


def test_create_product_with_invalid_data_explains_why(api):
    # validation_error no es un cambio de stock: da InventoryError con los motivos de la API.
    with pytest.raises(InventoryError) as exc_info:
        api.create_product("Leche 1/2", 1, "unidades", 0)
    assert exc_info.type is InventoryError
    assert "body.name" in str(exc_info.value)
    assert "'/'" in str(exc_info.value)


def test_response_not_from_our_api_does_not_expose_its_body():
    api = api_answering(502, text="<html>proxy interno 10.0.0.7</html>")

    with pytest.raises(InventoryError) as exc_info:
        api.list_products()
    assert exc_info.type is InventoryError
    assert "10.0.0.7" not in str(exc_info.value)


def test_connection_error_raises_inventory_error():
    def refuse(request):
        raise httpx2.ConnectError("conexión rechazada", request=request)

    api = InventoryApiClient(httpx2.Client(transport=httpx2.MockTransport(refuse), base_url="http://api"))

    with pytest.raises(InventoryError, match="No se puede conectar"):
        api.list_products()
