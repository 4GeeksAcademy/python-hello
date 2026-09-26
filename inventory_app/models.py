"""Modelos de producto y sus validaciones."""

from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    StringConstraints,
    computed_field,
)

# Nombre que no puede usarse como producto porque coincide con la ruta GET /products/low-stock.
RESERVED_NAME = "low-stock"


def name_key(name: str) -> str:
    """Clave de identidad de un producto: sin espacios exteriores y sin distinguir mayúsculas."""
    return name.strip().casefold()


def _check_product_name(name: str) -> str:
    # El nombre viaja en la ruta (/products/{name}); una "/" o el nombre reservado
    # harían que la petición llegara a otra ruta o a ninguna.
    if "/" in name:
        raise ValueError("el nombre no puede contener '/'")
    if "  " in name:
        raise ValueError("el nombre no puede contener espacios dobles")
    if name_key(name) == RESERVED_NAME:
        raise ValueError(f"'{RESERVED_NAME}' es un nombre reservado")
    return name


# Los espacios exteriores se eliminan antes de comprobar la longitud y las demás reglas,
# de modo que "   " se rechaza como nombre vacío.
ProductName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
    AfterValidator(_check_product_name),
]
Unit = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)]
# strict: rechaza booleanos, decimales y cadenas numéricas en lugar de convertirlos.
NonNegativeInt = Annotated[int, Field(ge=0, strict=True)]


class ProductCreate(BaseModel):
    """Datos necesarios para registrar un producto."""

    model_config = ConfigDict(frozen=True)

    name: ProductName
    quantity: NonNegativeInt
    unit: Unit
    min_stock: NonNegativeInt


class Product(ProductCreate):
    """Producto del inventario. `low_stock` se calcula y no se almacena."""

    @computed_field
    @property
    def low_stock(self) -> bool:
        return self.quantity <= self.min_stock


class StockChange(BaseModel):
    """Movimiento de stock: positivo para entradas, negativo para salidas.

    Que sea distinto de cero lo comprueba `InventoryService.adjust_stock`, no este modelo.
    """

    change: StrictInt
