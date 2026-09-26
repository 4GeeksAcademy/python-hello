"""Herramientas del agente: las operaciones de inventario que podrá usar el modelo.

Cada herramienta delega en `InventoryApiClient`, que accede a la API por HTTP. Aquí
no hay lógica de inventario: el cliente valida la cantidad y fija el signo del
movimiento. Las excepciones del cliente (`ProductNotFound`, `InsufficientStock`,
`InvalidStockChange`, `ProductAlreadyExists`, `StorageError`, `InventoryError`) llegan
sin cambios a quien llama a la herramienta.
"""

from inventory_app.api_client import InventoryApiClient


def list_products(client: InventoryApiClient) -> list[dict]:
    """Todos los productos del inventario."""
    return client.list_products()


def get_low_stock(client: InventoryApiClient) -> list[dict]:
    """Productos cuya cantidad es menor o igual que su stock mínimo."""
    return client.get_low_stock()


def add_stock(client: InventoryApiClient, name: str, quantity: int) -> dict:
    """Registra una entrada de `quantity` unidades (positiva) del producto `name`."""
    return client.add_stock(name, quantity)


def remove_stock(client: InventoryApiClient, name: str, quantity: int) -> dict:
    """Registra una salida de `quantity` unidades (positiva) del producto `name`."""
    return client.remove_stock(name, quantity)


def create_product(
    client: InventoryApiClient, name: str, quantity: int, unit: str, min_stock: int
) -> dict:
    """Registra un producto nuevo con su cantidad inicial, unidad y stock mínimo."""
    return client.create_product(name, quantity, unit, min_stock)
