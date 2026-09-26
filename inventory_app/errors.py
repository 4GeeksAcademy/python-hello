"""Errores de dominio y de persistencia del inventario."""


class InventoryError(Exception):
    """Base de todos los errores del inventario."""


class ProductNotFound(InventoryError):
    def __init__(self, name: str):
        self.name = name
        super().__init__(f"El producto '{name}' no existe en el inventario.")


class ProductAlreadyExists(InventoryError):
    def __init__(self, name: str):
        self.name = name
        super().__init__(f"El producto '{name}' ya existe en el inventario.")


class InsufficientStock(InventoryError):
    def __init__(self, name: str, available: int, requested: int):
        self.name = name
        self.available = available
        self.requested = requested
        super().__init__(
            f"Stock insuficiente de '{name}': hay {available} y se intentan retirar {requested}."
        )


class InvalidStockChange(InventoryError):
    """El ajuste de stock no es un entero distinto de cero."""


class StorageError(InventoryError):
    """No se ha podido leer o escribir el almacenamiento, o su contenido no es válido."""
