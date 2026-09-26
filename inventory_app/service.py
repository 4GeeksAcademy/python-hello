"""Lógica de negocio del inventario. No conoce HTTP ni el formato de almacenamiento."""

from inventory_app.errors import (
    InsufficientStock,
    InvalidStockChange,
    ProductAlreadyExists,
    ProductNotFound,
)
from inventory_app.models import Product, ProductCreate, name_key
from inventory_app.repository import CsvInventoryRepository


class InventoryService:
    def __init__(self, repository: CsvInventoryRepository):
        self._repository = repository

    def list_products(self) -> list[Product]:
        """Todos los productos, en el orden en que están almacenados."""
        return self._repository.load()

    def get_product(self, name: str) -> Product:
        products = self._repository.load()
        return products[_index_of(products, name)]

    def create_product(self, data: ProductCreate) -> Product:
        new_product = Product(**data.model_dump())

        def mutate(products: list[Product]) -> tuple[list[Product], Product]:
            key = name_key(new_product.name)
            if any(name_key(p.name) == key for p in products):
                raise ProductAlreadyExists(new_product.name)
            return [*products, new_product], new_product

        return self._repository.update(mutate)

    def adjust_stock(self, name: str, change: int) -> Product:
        """Suma `change` a la cantidad del producto (negativo para retirar stock)."""
        if isinstance(change, bool) or not isinstance(change, int) or change == 0:
            raise InvalidStockChange(
                f"El ajuste de stock debe ser un entero distinto de cero, se recibió {change!r}."
            )

        def mutate(products: list[Product]) -> tuple[list[Product], Product]:
            index = _index_of(products, name)
            current = products[index]
            new_quantity = current.quantity + change
            if new_quantity < 0:
                raise InsufficientStock(current.name, current.quantity, -change)
            updated = Product(
                name=current.name,
                quantity=new_quantity,
                unit=current.unit,
                min_stock=current.min_stock,
            )
            return [*products[:index], updated, *products[index + 1 :]], updated

        return self._repository.update(mutate)

    def list_low_stock(self) -> list[Product]:
        """Productos cuya cantidad es menor o igual que su stock mínimo."""
        return [p for p in self._repository.load() if p.low_stock]


def _index_of(products: list[Product], name: str) -> int:
    key = name_key(name)
    for index, product in enumerate(products):
        if name_key(product.name) == key:
            return index
    raise ProductNotFound(name.strip())
