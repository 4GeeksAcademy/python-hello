"""Cliente HTTP de la API de inventario.

Es la vía por la que el agente accede al inventario: solo habla HTTP con la API y no
importa el servicio ni el repositorio. Las respuestas de error de la API
({"code", "message", "details"}) se traducen a las excepciones de `errors.py`.
"""

from urllib.parse import quote

import httpx2

from inventory_app.errors import (
    InsufficientStock,
    InvalidStockChange,
    InventoryError,
    ProductAlreadyExists,
    ProductNotFound,
    StorageError,
)


class InventoryApiClient:
    def __init__(self, http: httpx2.Client):
        # `http` ya apunta a la API: en ejecución, httpx2.Client(base_url=...);
        # en los tests, el TestClient de FastAPI, que es un httpx2.Client.
        self._http = http

    def list_products(self) -> list[dict]:
        return self._request("GET", "/products")

    def get_low_stock(self) -> list[dict]:
        return self._request("GET", "/products/low-stock")

    def add_stock(self, name: str, quantity: int) -> dict:
        """Registra una entrada: envía `quantity` como cambio positivo."""
        return self._change_stock(name, _check_quantity(quantity))

    def remove_stock(self, name: str, quantity: int) -> dict:
        """Registra una salida: envía `quantity` como cambio negativo."""
        return self._change_stock(name, -_check_quantity(quantity))

    def create_product(self, name: str, quantity: int, unit: str, min_stock: int) -> dict:
        """Registra un producto nuevo. Los datos los valida la API."""
        data = {"name": name, "quantity": quantity, "unit": unit, "min_stock": min_stock}
        return self._request("POST", "/products", json=data)

    def _change_stock(self, name: str, change: int) -> dict:
        # safe="": también se codifican "/", "?", "#" y "%", que de otro modo
        # cambiarían la ruta o cortarían la URL.
        path = f"/products/{quote(name, safe='')}/stock"
        return self._request("POST", path, json={"change": change})

    def _request(self, method: str, path: str, json: dict | None = None):
        try:
            response = self._http.request(method, path, json=json)
        except httpx2.TransportError as exc:
            raise InventoryError("No se puede conectar con la API de inventario.") from exc
        if response.is_success:
            return response.json()
        raise _error_from_response(response)


def _check_quantity(quantity: int) -> int:
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
        raise InvalidStockChange(
            f"La cantidad debe ser un entero positivo, se recibió {quantity!r}."
        )
    return quantity


def _error_from_response(response: httpx2.Response) -> InventoryError:
    try:
        body = response.json()
        code, message, details = body["code"], body["message"], body["details"]
    except (ValueError, KeyError, TypeError):
        # No es una respuesta de error de nuestra API (por ejemplo, otra aplicación
        # en esa URL). No se incluye el cuerpo para no exponer detalles del servidor.
        return InventoryError(
            f"Respuesta inesperada de la API de inventario (HTTP {response.status_code})."
        )

    if code == "product_not_found":
        return ProductNotFound(details["name"])
    if code == "product_already_exists":
        return ProductAlreadyExists(details["name"])
    if code == "insufficient_stock":
        return InsufficientStock(details["name"], details["available"], details["requested"])
    if code == "invalid_stock_change":
        return InvalidStockChange(message)
    if code == "validation_error":
        # Datos rechazados por la API (por ejemplo, un nombre con "/" al crear un
        # producto): se incluyen los motivos para que se puedan corregir.
        reasons = "; ".join(f"{e['field']}: {e['message']}" for e in details.get("errors", []))
        return InventoryError(f"{message} {reasons}".strip())
    if code == "storage_error":
        # El mensaje de la API ya es genérico: no contiene rutas internas.
        return StorageError(message)
    # not_found (ruta inexistente), method_not_allowed u otros: la petición no
    # corresponde al contrato de la API (por ejemplo, una URL base incorrecta).
    return InventoryError(f"La API de inventario rechazó la petición ({code}): {message}")
