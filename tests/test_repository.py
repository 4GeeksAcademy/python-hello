import os
import threading
from pathlib import Path

import pytest

from inventory_app.errors import StorageError
from inventory_app.models import Product
from inventory_app.repository import CsvInventoryRepository

HEADER = "name,quantity,unit,min_stock\n"


def _leftover_temp_files(directory: Path) -> list[Path]:
    return [p for p in directory.iterdir() if p.suffix == ".tmp"]


# --- Archivo inexistente o vacío ---------------------------------------------


def test_missing_file_is_empty_inventory(repository, csv_path):
    assert repository.load() == []
    assert not csv_path.exists(), "leer no debe crear el archivo"


def test_empty_file_is_empty_inventory(repository, write_csv):
    write_csv("")
    assert repository.load() == []


def test_header_only_is_empty_inventory(repository, write_csv):
    write_csv(HEADER)
    assert repository.load() == []


# --- Creación, escritura y lectura -------------------------------------------


def test_save_creates_file_and_directory_with_header(repository, csv_path, sample_products):
    assert not csv_path.parent.exists()

    repository.save(sample_products)

    assert csv_path.read_text(encoding="utf-8") == (
        HEADER
        + "Café arábica,40,bolsas,10\n"
        + "Leche de avena,12,unidades,20\n"
        + "Jarabe de vainilla,4,botellas,4\n"
    )


def test_save_then_load_round_trip(repository, sample_products):
    repository.save(sample_products)
    assert repository.load() == sample_products


def test_data_persists_across_repository_instances(csv_path, sample_products):
    CsvInventoryRepository(csv_path).save(sample_products)
    assert CsvInventoryRepository(csv_path).load() == sample_products


def test_load_returns_typed_values(repository, write_csv):
    write_csv(HEADER + "Leche entera,48,unidades,24\n")
    [product] = repository.load()
    assert product == Product(name="Leche entera", quantity=48, unit="unidades", min_stock=24)
    assert isinstance(product.quantity, int) and isinstance(product.min_stock, int)


def test_low_stock_is_not_stored(repository, csv_path, sample_products):
    repository.save(sample_products)
    content = csv_path.read_text(encoding="utf-8")
    assert "low_stock" not in content
    assert "True" not in content and "False" not in content


def test_blank_lines_are_ignored(repository, write_csv):
    write_csv(HEADER + "\nLeche entera,48,unidades,24\n\n")
    assert [p.name for p in repository.load()] == ["Leche entera"]


def test_values_with_commas_and_quotes_round_trip(repository):
    product = Product(name='Vasos "take away", 12 oz', quantity=5, unit="cajas", min_stock=1)
    repository.save([product])
    assert repository.load() == [product]


def test_crlf_line_endings_are_accepted(repository, write_csv):
    write_csv(HEADER.replace("\n", "\r\n") + "Leche entera,48,unidades,24\r\n")
    assert [p.name for p in repository.load()] == ["Leche entera"]


# --- Unicode -------------------------------------------------------------------


def test_unicode_round_trip_is_utf8(repository, csv_path):
    products = [
        Product(name="Café arábica", quantity=1, unit="bolsas", min_stock=0),
        Product(name="Jarabe de piñón", quantity=2, unit="botellas", min_stock=0),
        Product(name="Té matcha 抹茶", quantity=3, unit="latas", min_stock=0),
    ]
    repository.save(products)

    assert repository.load() == products
    raw = csv_path.read_bytes()
    assert "Café arábica".encode("utf-8") in raw
    assert not raw.startswith(b"\xef\xbb\xbf"), "se escribe UTF-8 sin BOM"


def test_utf8_with_bom_is_accepted(repository, write_csv):
    write_csv(HEADER + "Café arábica,40,bolsas,10\n", encoding="utf-8-sig")
    assert [p.name for p in repository.load()] == ["Café arábica"]


def test_non_utf8_file_raises_storage_error(repository, write_csv):
    write_csv(HEADER + "Café arábica,40,bolsas,10\n", encoding="cp1252")
    with pytest.raises(StorageError, match="UTF-8"):
        repository.load()


# --- Cabecera -----------------------------------------------------------------


@pytest.mark.parametrize(
    "header",
    [
        "name,quantity,unit\n",
        "name,quantity,unit,min_stock,low_stock\n",
        "quantity,name,unit,min_stock\n",
        "Name,Quantity,Unit,Min_Stock\n",
        "nombre,cantidad,unidad,stock_minimo\n",
        "Leche entera,48,unidades,24\n",
    ],
)
def test_invalid_header_raises_storage_error(repository, write_csv, header):
    write_csv(header)
    with pytest.raises(StorageError, match="Cabecera"):
        repository.load()


# --- Tipos y datos inválidos -------------------------------------------------


@pytest.mark.parametrize(
    "row",
    [
        "Leche,abc,unidades,5",  # cantidad no numérica
        "Leche,-3,unidades,5",  # cantidad negativa
        "Leche,2.5,unidades,5",  # cantidad decimal
        "Leche,,unidades,5",  # cantidad vacía
        "Leche, 5,unidades,5",  # espacios dentro del número
        "Leche,+5,unidades,5",  # signo explícito
        "Leche,5,unidades,x",  # min_stock no numérico
        "Leche,5,unidades,-1",  # min_stock negativo
    ],
)
def test_invalid_numeric_values_raise_storage_error(repository, write_csv, row):
    write_csv(HEADER + row + "\n")
    with pytest.raises(StorageError, match="Línea 2"):
        repository.load()


@pytest.mark.parametrize(
    "row",
    [
        ",5,unidades,5",  # nombre vacío
        "   ,5,unidades,5",  # nombre solo con espacios
        "Leche,5,,5",  # unidad vacía
        "N" * 101 + ",5,unidades,5",  # nombre demasiado largo
        "Leche,5," + "u" * 31 + ",5",  # unidad demasiado larga
        "Leche 1/2,5,unidades,5",  # nombre con "/" (las reglas de nombre se prueban en el modelo)
    ],
)
def test_invalid_text_values_raise_storage_error(repository, write_csv, row):
    write_csv(HEADER + row + "\n")
    with pytest.raises(StorageError, match="Línea 2"):
        repository.load()


@pytest.mark.parametrize(
    "row",
    [
        "Leche,5,unidades",  # faltan columnas
        "Leche,5,unidades,5,extra",  # sobran columnas
        "Leche",
    ],
)
def test_wrong_column_count_raises_storage_error(repository, write_csv, row):
    write_csv(HEADER + "Café,1,bolsas,1\n" + row + "\n")
    with pytest.raises(StorageError, match="Línea 3"):
        repository.load()


def test_unclosed_quote_raises_storage_error(repository, write_csv):
    write_csv(HEADER + 'Leche,5,unidades,"5\n')
    with pytest.raises(StorageError):
        repository.load()


# --- Duplicados ---------------------------------------------------------------


@pytest.mark.parametrize("duplicate", ["Leche de avena", "LECHE DE AVENA", "  leche de avena  "])
def test_duplicate_products_raise_storage_error(repository, write_csv, duplicate):
    write_csv(HEADER + "Leche de avena,12,unidades,20\n" + f"{duplicate},3,unidades,1\n")
    with pytest.raises(StorageError, match="duplicado"):
        repository.load()


# --- Datos corruptos no se sobrescriben -------------------------------------


def test_update_does_not_overwrite_corrupted_file(repository, write_csv, csv_path):
    write_csv(HEADER + "Leche,abc,unidades,5\n")
    original = csv_path.read_bytes()

    with pytest.raises(StorageError):
        repository.update(lambda products: (products, None))

    assert csv_path.read_bytes() == original


def test_update_does_not_write_when_mutation_fails(repository, csv_path, sample_products):
    repository.save(sample_products)
    original = csv_path.read_bytes()

    def failing_mutation(products):
        raise ValueError("fallo de la regla de negocio")

    with pytest.raises(ValueError):
        repository.update(failing_mutation)

    assert csv_path.read_bytes() == original


# --- Errores de lectura/escritura del sistema --------------------------------


def test_read_permission_error_raises_storage_error(repository, write_csv, monkeypatch):
    write_csv(HEADER)

    def denied(*args, **kwargs):
        raise PermissionError("archivo bloqueado por otra aplicación")

    monkeypatch.setattr(Path, "open", denied)
    with pytest.raises(StorageError, match="No se puede leer"):
        repository.load()


def test_replace_failure_keeps_original_and_cleans_temp(
    repository, csv_path, sample_products, monkeypatch
):
    repository.save(sample_products)
    original = csv_path.read_bytes()

    def failing_replace(src, dst):
        raise PermissionError("archivo bloqueado por otra aplicación")

    monkeypatch.setattr(os, "replace", failing_replace)
    with pytest.raises(StorageError, match="No se puede escribir"):
        repository.save(sample_products[:1])

    assert csv_path.read_bytes() == original
    assert _leftover_temp_files(csv_path.parent) == []


def test_failure_while_writing_keeps_original_and_cleans_temp(
    repository, csv_path, sample_products, monkeypatch
):
    repository.save(sample_products)
    original = csv_path.read_bytes()

    def failing_fsync(fd):
        raise OSError("disco lleno")

    monkeypatch.setattr(os, "fsync", failing_fsync)
    with pytest.raises(StorageError, match="disco lleno"):
        repository.save(sample_products[:1])

    assert csv_path.read_bytes() == original
    assert _leftover_temp_files(csv_path.parent) == []


def test_failure_on_first_write_does_not_create_file(repository, csv_path, sample_products, monkeypatch):
    def failing_replace(src, dst):
        raise OSError("fallo simulado")

    monkeypatch.setattr(os, "replace", failing_replace)
    with pytest.raises(StorageError):
        repository.save(sample_products)

    assert not csv_path.exists()
    assert _leftover_temp_files(csv_path.parent) == []


# --- Escritura atómica --------------------------------------------------------


def test_write_goes_through_temp_file_in_same_directory(
    repository, csv_path, sample_products, monkeypatch
):
    calls = []
    real_replace = os.replace

    def spy_replace(src, dst):
        src, dst = Path(src), Path(dst)
        calls.append((src, dst))
        # En el momento del reemplazo, el temporal ya contiene los datos completos.
        assert src.read_text(encoding="utf-8").startswith(HEADER)
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", spy_replace)
    repository.save(sample_products)

    [(src, dst)] = calls
    assert dst == csv_path
    assert src.parent == csv_path.parent
    assert src != csv_path
    assert _leftover_temp_files(csv_path.parent) == []


def test_concurrent_updates_are_serialized(repository, sample_products):
    repository.save(sample_products)
    threads_count = 20

    def increment(products):
        first = products[0]
        updated = Product(
            name=first.name,
            quantity=first.quantity + 1,
            unit=first.unit,
            min_stock=first.min_stock,
        )
        return [updated, *products[1:]], None

    threads = [
        threading.Thread(target=repository.update, args=(increment,))
        for _ in range(threads_count)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert repository.load()[0].quantity == sample_products[0].quantity + threads_count
