"""Tests de las herramientas del agente.

Solo comprueban lo que añade `tools.py`: que cada herramienta llama al método correcto
del cliente con los mismos argumentos, devuelve su resultado y deja pasar sus
excepciones. HTTP, URLs y reglas del inventario ya se prueban en las demás capas.
"""

import pytest

from inventory_app import tools
from inventory_app.errors import (
    InsufficientStock,
    InventoryError,
    ProductAlreadyExists,
    ProductNotFound,
    StorageError,
)


class FakeApiClient:
    """Sustituye a InventoryApiClient: anota cada llamada y devuelve un resultado único."""

    def __init__(self, error: Exception | None = None):
        self.calls = []
        self.result = object()
        self.error = error

    def _call(self, *call):
        self.calls.append(call)
        if self.error:
            raise self.error
        return self.result

    def list_products(self):
        return self._call("list_products")

    def get_low_stock(self):
        return self._call("get_low_stock")

    def add_stock(self, name, quantity):
        return self._call("add_stock", name, quantity)

    def remove_stock(self, name, quantity):
        return self._call("remove_stock", name, quantity)

    def create_product(self, name, quantity, unit, min_stock):
        return self._call("create_product", name, quantity, unit, min_stock)


@pytest.mark.parametrize(
    ("tool", "args", "expected_call"),
    [
        (tools.list_products, (), ("list_products",)),
        (tools.get_low_stock, (), ("get_low_stock",)),
        (tools.add_stock, ("Leche de avena", 30), ("add_stock", "Leche de avena", 30)),
        # La cantidad llega positiva: el signo de la salida lo pone el cliente, no la herramienta.
        (tools.remove_stock, ("Café arábica", 12), ("remove_stock", "Café arábica", 12)),
        (
            tools.create_product,
            ("Leche entera", 48, "unidades", 24),
            ("create_product", "Leche entera", 48, "unidades", 24),
        ),
    ],
)
def test_tool_delegates_to_client(tool, args, expected_call):
    client = FakeApiClient()

    result = tool(client, *args)

    assert client.calls == [expected_call]
    assert result is client.result


@pytest.mark.parametrize(
    ("tool", "args", "error"),
    [
        (tools.list_products, (), StorageError("No se ha podido acceder al almacenamiento.")),
        (tools.get_low_stock, (), InventoryError("No se puede conectar con la API de inventario.")),
        (tools.add_stock, ("Leche de almendras", 5), ProductNotFound("Leche de almendras")),
        (tools.remove_stock, ("Jarabe de vainilla", 5), InsufficientStock("Jarabe de vainilla", 4, 5)),
        (
            tools.create_product,
            ("Leche de avena", 1, "unidades", 0),
            ProductAlreadyExists("Leche de avena"),
        ),
    ],
)
def test_tool_lets_client_errors_through(tool, args, error):
    with pytest.raises(type(error)) as exc_info:
        tool(FakeApiClient(error), *args)
    assert exc_info.value is error
