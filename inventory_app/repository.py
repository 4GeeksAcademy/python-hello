"""Persistencia del inventario en un archivo CSV.

Este módulo solo sabe leer y escribir productos. Las reglas de negocio
(duplicados al registrar, stock negativo, etc.) viven en `service.py`.
"""

import csv
import os
import re
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from pydantic import ValidationError

from inventory_app.errors import StorageError
from inventory_app.models import Product, name_key

FIELDNAMES = ("name", "quantity", "unit", "min_stock")

# utf-8-sig lee UTF-8 con o sin BOM (Excel añade BOM al guardar en UTF-8).
READ_ENCODING = "utf-8-sig"
WRITE_ENCODING = "utf-8"

_INTEGER_RE = re.compile(r"[0-9]+")

T = TypeVar("T")


class CsvInventoryRepository:
    def __init__(self, path: Path):
        self._path = Path(path)
        # Reentrante para que `update` pueda leer y escribir dentro del mismo bloqueo.
        self._lock = threading.RLock()

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> list[Product]:
        """Devuelve los productos guardados. Un archivo inexistente es un inventario vacío."""
        with self._lock:
            return self._read()

    def save(self, products: list[Product]) -> None:
        """Sustituye el contenido del archivo de forma atómica."""
        with self._lock:
            self._write(products)

    def update(self, mutate: Callable[[list[Product]], tuple[list[Product], T]]) -> T:
        """Lee, aplica `mutate` y escribe, todo bajo el mismo bloqueo.

        `mutate` recibe los productos actuales y devuelve la nueva lista junto con
        un resultado para el llamador. Si `mutate` lanza una excepción, no se escribe nada.
        """
        with self._lock:
            products, result = mutate(self._read())
            self._write(products)
            return result

    def _read(self) -> list[Product]:
        try:
            with self._path.open("r", encoding=READ_ENCODING, newline="") as file:
                return _parse_rows(csv.reader(file), self._path)
        except FileNotFoundError:
            return []
        except UnicodeDecodeError as exc:
            raise StorageError(f"'{self._path}' no está codificado en UTF-8.") from exc
        except csv.Error as exc:
            raise StorageError(f"'{self._path}' no es un CSV válido: {exc}") from exc
        except OSError as exc:
            raise StorageError(f"No se puede leer '{self._path}': {exc}") from exc

    def _write(self, products: list[Product]) -> None:
        # Se escribe en un temporal del mismo directorio y se sustituye con os.replace,
        # que es atómico: el archivo original queda intacto si algo falla antes.
        tmp_path: Path | None = None
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(
                prefix=f".{self._path.name}.", suffix=".tmp", dir=self._path.parent
            )
            tmp_path = Path(tmp_name)
            with os.fdopen(fd, "w", encoding=WRITE_ENCODING, newline="") as file:
                writer = csv.writer(file, lineterminator="\n")
                writer.writerow(FIELDNAMES)
                for product in products:
                    writer.writerow(
                        [product.name, product.quantity, product.unit, product.min_stock]
                    )
                file.flush()
                os.fsync(file.fileno())
            os.replace(tmp_path, self._path)
            tmp_path = None
        except OSError as exc:
            raise StorageError(f"No se puede escribir '{self._path}': {exc}") from exc
        finally:
            if tmp_path is not None:
                _remove_quietly(tmp_path)


def _parse_rows(reader, path: Path) -> list[Product]:
    header = next(reader, None)
    if header is None:
        return []
    if tuple(header) != FIELDNAMES:
        raise StorageError(
            f"Cabecera inválida en '{path}': se esperaba {','.join(FIELDNAMES)} "
            f"y se encontró {','.join(header)}."
        )

    products: list[Product] = []
    seen: dict[str, int] = {}
    for row in reader:
        line = reader.line_num
        if not row:
            continue
        if len(row) != len(FIELDNAMES):
            raise StorageError(
                f"Línea {line} de '{path}': se esperaban {len(FIELDNAMES)} columnas "
                f"y hay {len(row)}."
            )
        name, quantity, unit, min_stock = row
        try:
            product = Product(
                name=name,
                quantity=_parse_int(quantity, "quantity"),
                unit=unit,
                min_stock=_parse_int(min_stock, "min_stock"),
            )
        except (ValueError, ValidationError) as exc:
            raise StorageError(f"Línea {line} de '{path}': datos inválidos ({exc}).") from exc

        key = name_key(product.name)
        if key in seen:
            raise StorageError(
                f"Línea {line} de '{path}': el producto '{product.name}' está duplicado "
                f"(ya aparece en la línea {seen[key]})."
            )
        seen[key] = line
        products.append(product)
    return products


def _parse_int(value: str, field: str) -> int:
    # Solo dígitos ASCII: int() aceptaría "+5", "1_000" o " 5 ", que no son formato válido aquí.
    if not _INTEGER_RE.fullmatch(value):
        raise ValueError(f"'{field}' debe ser un entero no negativo, se encontró {value!r}")
    return int(value)


def _remove_quietly(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
