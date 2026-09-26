import hashlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from inventory_app.api import create_app
from inventory_app.config import DEFAULT_INVENTORY_CSV_PATH
from inventory_app.models import Product
from inventory_app.repository import CsvInventoryRepository
from inventory_app.service import InventoryService


def _fingerprint(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


@pytest.fixture(scope="session", autouse=True)
def real_inventory_is_untouched():
    """Falla la sesión si algún test modifica el CSV real del proyecto."""
    before = _fingerprint(DEFAULT_INVENTORY_CSV_PATH)
    yield
    assert _fingerprint(DEFAULT_INVENTORY_CSV_PATH) == before, (
        "Los tests han modificado data/inventory.csv"
    )


@pytest.fixture
def csv_path(tmp_path: Path) -> Path:
    """Ruta aislada (todavía inexistente) para el CSV de inventario."""
    return tmp_path / "data" / "inventory.csv"


@pytest.fixture
def write_csv(csv_path: Path):
    """Escribe texto crudo en el CSV temporal, para preparar casos concretos."""

    def _write(text: str, encoding: str = "utf-8") -> Path:
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        csv_path.write_bytes(text.encode(encoding))
        return csv_path

    return _write


@pytest.fixture
def repository(csv_path: Path) -> CsvInventoryRepository:
    return CsvInventoryRepository(csv_path)


@pytest.fixture
def sample_products() -> list[Product]:
    return [
        Product(name="Café arábica", quantity=40, unit="bolsas", min_stock=10),
        Product(name="Leche de avena", quantity=12, unit="unidades", min_stock=20),
        Product(name="Jarabe de vainilla", quantity=4, unit="botellas", min_stock=4),
    ]


@pytest.fixture
def service(repository: CsvInventoryRepository, sample_products) -> InventoryService:
    repository.save(sample_products)
    return InventoryService(repository)


@pytest.fixture
def client(service: InventoryService) -> TestClient:
    """Cliente HTTP de una aplicación que usa el CSV temporal con `sample_products`."""
    return TestClient(create_app(service))
