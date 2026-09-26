"""API REST del inventario.

Los endpoints solo traducen entre HTTP e `InventoryService`: validan la entrada con
los modelos, llaman al servicio y convierten los errores en respuestas JSON uniformes:

    {"code": "...", "message": "...", "details": {...}}

Arranque: `uvicorn inventory_app.api:app`
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from inventory_app.config import get_settings
from inventory_app.errors import (
    InsufficientStock,
    InvalidStockChange,
    InventoryError,
    ProductAlreadyExists,
    ProductNotFound,
)
from inventory_app.models import Product, ProductCreate, StockChange
from inventory_app.repository import CsvInventoryRepository
from inventory_app.service import InventoryService

logger = logging.getLogger(__name__)


def create_app(service: InventoryService | None = None) -> FastAPI:
    """Crea la aplicación con un único servicio (y, por tanto, un único repositorio).

    Todos los endpoints usan el mismo `service`, así que el bloqueo del repositorio
    protege todas las peticiones de la aplicación. Sin `service`, se usa el CSV
    configurado. Crear la aplicación no lee el CSV: se lee al atender cada petición.
    """
    if service is None:
        service = InventoryService(CsvInventoryRepository(get_settings().inventory_csv_path))

    app = FastAPI(title="Inventario de Carla")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/products")
    def list_products() -> list[Product]:
        return service.list_products()

    # Debe declararse antes de /products/{name}: las rutas se comprueban en orden y
    # {name} también coincidiría con "low-stock".
    @app.get("/products/low-stock")
    def list_low_stock() -> list[Product]:
        return service.list_low_stock()

    @app.get("/products/{name}")
    def get_product(name: str) -> Product:
        return service.get_product(name)

    @app.post("/products", status_code=status.HTTP_201_CREATED)
    def create_product(data: ProductCreate) -> Product:
        return service.create_product(data)

    @app.post("/products/{name}/stock")
    def adjust_stock(name: str, body: StockChange) -> Product:
        return service.adjust_stock(name, body.change)

    app.add_exception_handler(InventoryError, _handle_inventory_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_error)
    return app


# --- Errores -------------------------------------------------------------------

_DOMAIN_ERRORS: dict[type[InventoryError], tuple[int, str]] = {
    ProductNotFound: (status.HTTP_404_NOT_FOUND, "product_not_found"),
    ProductAlreadyExists: (status.HTTP_409_CONFLICT, "product_already_exists"),
    InsufficientStock: (status.HTTP_409_CONFLICT, "insufficient_stock"),
    InvalidStockChange: (status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_stock_change"),
}

_HTTP_ERRORS: dict[int, tuple[str, str]] = {
    status.HTTP_404_NOT_FOUND: ("not_found", "La ruta solicitada no existe."),
    status.HTTP_405_METHOD_NOT_ALLOWED: (
        "method_not_allowed",
        "El método HTTP no está permitido en esta ruta.",
    ),
}


def _error_response(
    status_code: int,
    code: str,
    message: str,
    details: dict | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"code": code, "message": message, "details": details or {}},
        headers=headers,
    )


def _handle_inventory_error(request: Request, exc: InventoryError) -> JSONResponse:
    if type(exc) in _DOMAIN_ERRORS:
        status_code, code = _DOMAIN_ERRORS[type(exc)]
        # vars(exc) son los datos que guarda cada error: name, available, requested.
        return _error_response(status_code, code, str(exc), vars(exc))

    # StorageError: el mensaje incluye rutas del sistema de archivos, así que solo
    # se registra en el log del servidor y el cliente recibe un mensaje genérico.
    logger.error("Error de almacenamiento del inventario: %s", exc)
    return _error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "storage_error",
        "No se ha podido acceder al almacenamiento del inventario.",
    )


def _handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [
        {"field": ".".join(str(part) for part in error["loc"]), "message": error["msg"]}
        for error in exc.errors()
    ]
    return _error_response(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "validation_error",
        "Los datos de la petición no son válidos.",
        {"errors": errors},
    )


def _handle_http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    # Rutas inexistentes (404) y métodos no permitidos (405) los genera el propio
    # enrutador; se conservan sus cabeceras (por ejemplo, Allow en un 405).
    code, message = _HTTP_ERRORS.get(exc.status_code, ("http_error", str(exc.detail)))
    return _error_response(exc.status_code, code, message, headers=exc.headers)


app = create_app()
