import pytest
from pydantic import ValidationError

from inventory_app.errors import (
    InsufficientStock,
    InvalidStockChange,
    ProductAlreadyExists,
    ProductNotFound,
)
from inventory_app.models import Product, ProductCreate, StockChange
from inventory_app.repository import CsvInventoryRepository
from inventory_app.service import InventoryService

# --- Listar y consultar -----------------------------------------------------


def test_list_products(service, sample_products):
    assert service.list_products() == sample_products


def test_list_products_empty_inventory(repository):
    assert InventoryService(repository).list_products() == []


def test_get_product(service):
    product = service.get_product("Leche de avena")
    assert product == Product(name="Leche de avena", quantity=12, unit="unidades", min_stock=20)


@pytest.mark.parametrize("name", ["leche de avena", "LECHE DE AVENA", "  Leche De Avena  "])
def test_get_product_is_case_insensitive(service, name):
    assert service.get_product(name).name == "Leche de avena"


def test_get_product_does_not_ignore_accents(service):
    with pytest.raises(ProductNotFound):
        service.get_product("Cafe arabica")


def test_get_missing_product_raises_not_found(service):
    with pytest.raises(ProductNotFound) as exc_info:
        service.get_product("Leche de almendras")
    assert exc_info.value.name == "Leche de almendras"


def test_get_product_on_missing_file_raises_not_found(repository):
    with pytest.raises(ProductNotFound):
        InventoryService(repository).get_product("Leche")


# --- Registrar ----------------------------------------------------------------


def test_create_product_persists(service, csv_path):
    created = service.create_product(
        ProductCreate(name="Leche entera", quantity=48, unit="unidades", min_stock=24)
    )

    assert created == Product(name="Leche entera", quantity=48, unit="unidades", min_stock=24)
    reloaded = InventoryService(CsvInventoryRepository(csv_path))
    assert reloaded.get_product("leche entera") == created
    assert len(reloaded.list_products()) == 4


def test_create_product_creates_file_when_missing(repository, csv_path):
    service = InventoryService(repository)
    service.create_product(ProductCreate(name="Azúcar", quantity=10, unit="kg", min_stock=2))

    assert csv_path.exists()
    assert [p.name for p in service.list_products()] == ["Azúcar"]


def test_create_product_strips_name_and_unit(service):
    created = service.create_product(
        ProductCreate(name="  Leche entera  ", quantity=1, unit=" unidades ", min_stock=0)
    )
    assert created.name == "Leche entera"
    assert created.unit == "unidades"


@pytest.mark.parametrize("name", ["Leche de avena", "leche DE avena", "  LECHE DE AVENA "])
def test_create_duplicate_product_raises_already_exists(service, csv_path, name):
    original = csv_path.read_bytes()

    with pytest.raises(ProductAlreadyExists):
        service.create_product(ProductCreate(name=name, quantity=1, unit="unidades", min_stock=0))

    assert csv_path.read_bytes() == original


# --- Validación de los datos de alta -----------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        {"name": ""},
        {"name": "   "},
        {"name": "N" * 101},
        {"unit": ""},
        {"unit": "u" * 31},
        {"quantity": -1},
        {"min_stock": -1},
        {"quantity": 2.5},
        {"quantity": "10"},
        {"quantity": True},
        {"min_stock": None},
    ],
)
def test_product_create_rejects_invalid_data(overrides):
    data = {"name": "Leche", "quantity": 1, "unit": "unidades", "min_stock": 0, **overrides}
    with pytest.raises(ValidationError):
        ProductCreate(**data)


def test_product_create_accepts_limits():
    product = ProductCreate(name="N" * 100, quantity=0, unit="u" * 30, min_stock=0)
    assert len(product.name) == 100 and product.quantity == 0


def test_product_create_length_is_checked_after_stripping():
    assert ProductCreate(name=" " + "N" * 100 + " ", quantity=0, unit="u", min_stock=0)


@pytest.mark.parametrize(
    "name",
    [
        "Leche 1/2",
        "Leche  de avena",
        "low-stock",
        "LOW-STOCK",
        "  Low-Stock  ",
    ],
)
def test_product_name_rejects_slash_double_spaces_and_reserved_name(name):
    with pytest.raises(ValidationError):
        ProductCreate(name=name, quantity=1, unit="unidades", min_stock=0)


@pytest.mark.parametrize("name", ["low stock", "low-stock extra", "Leche de avena", "Té matcha 抹茶"])
def test_product_name_accepts_similar_valid_names(name):
    assert ProductCreate(name=name, quantity=1, unit="unidades", min_stock=0).name == name


def test_product_name_rules_apply_after_stripping():
    # Los espacios exteriores se eliminan: no cuentan como espacios dobles.
    assert ProductCreate(name="  Leche  ", quantity=1, unit="u", min_stock=0).name == "Leche"


# --- Modelo de movimiento de stock ---------------------------------------------


@pytest.mark.parametrize("change", [10, -10, 0])
def test_stock_change_accepts_integers(change):
    # El 0 lo rechaza el servicio (InvalidStockChange), no el modelo.
    assert StockChange(change=change).change == change


@pytest.mark.parametrize("change", ["5", 1.5, True, None])
def test_stock_change_rejects_non_integers(change):
    with pytest.raises(ValidationError):
        StockChange(change=change)


# --- Ajustar stock ------------------------------------------------------------


def test_add_stock(service):
    updated = service.adjust_stock("Leche de avena", 30)
    assert updated.quantity == 42
    assert service.get_product("Leche de avena").quantity == 42


def test_remove_stock(service):
    updated = service.adjust_stock("Café arábica", -12)
    assert updated.quantity == 28
    assert service.get_product("Café arábica").quantity == 28


def test_adjust_stock_is_case_insensitive_and_keeps_stored_name(service):
    updated = service.adjust_stock("  café ARÁBICA ", -1)
    assert updated.name == "Café arábica"


def test_adjust_stock_keeps_other_products_and_order(service, sample_products):
    service.adjust_stock("Leche de avena", 1)
    products = service.list_products()
    assert [p.name for p in products] == [p.name for p in sample_products]
    assert products[0] == sample_products[0]
    assert products[2] == sample_products[2]


def test_remove_all_stock_down_to_zero(service):
    assert service.adjust_stock("Jarabe de vainilla", -4).quantity == 0


def test_negative_stock_is_rejected_and_not_persisted(service, csv_path):
    original = csv_path.read_bytes()

    with pytest.raises(InsufficientStock) as exc_info:
        service.adjust_stock("Jarabe de vainilla", -5)

    assert exc_info.value.available == 4
    assert exc_info.value.requested == 5
    assert csv_path.read_bytes() == original


def test_adjust_stock_of_missing_product_raises_not_found(service, csv_path):
    original = csv_path.read_bytes()
    with pytest.raises(ProductNotFound):
        service.adjust_stock("Leche de almendras", 5)
    assert csv_path.read_bytes() == original


@pytest.mark.parametrize("change", [0, True, 1.5, "5", None])
def test_adjust_stock_rejects_invalid_change(service, change):
    with pytest.raises(InvalidStockChange):
        service.adjust_stock("Leche de avena", change)


# --- Stock bajo ---------------------------------------------------------------


def test_low_stock_property():
    assert Product(name="A", quantity=3, unit="u", min_stock=5).low_stock is True
    assert Product(name="A", quantity=5, unit="u", min_stock=5).low_stock is True
    assert Product(name="A", quantity=6, unit="u", min_stock=5).low_stock is False


def test_list_low_stock(service):
    # Leche de avena: 12 <= 20; Jarabe de vainilla: 4 <= 4 (límite); Café arábica: 40 > 10.
    assert [p.name for p in service.list_low_stock()] == ["Leche de avena", "Jarabe de vainilla"]


def test_low_stock_updates_after_adjustment(service):
    service.adjust_stock("Leche de avena", 9)  # 21 > 20
    service.adjust_stock("Café arábica", -30)  # 10 <= 10
    assert [p.name for p in service.list_low_stock()] == ["Café arábica", "Jarabe de vainilla"]


def test_list_low_stock_empty_inventory(repository):
    assert InventoryService(repository).list_low_stock() == []
