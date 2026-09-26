import csv
from datetime import datetime
from pathlib import Path

import pytest

from inventory_app.conversation_log import ConversationLogger

HEADER = "actor,message,tool_call,timestamp\n"


@pytest.fixture
def log_path(tmp_path: Path) -> Path:
    """Ruta aislada (todavía inexistente) para el registro."""
    return tmp_path / "data" / "conversation_log.csv"


@pytest.fixture
def logger(log_path: Path) -> ConversationLogger:
    return ConversationLogger(log_path)


def read_rows(path: Path) -> list[list[str]]:
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.reader(file))


def test_first_event_creates_file_with_header(logger, log_path):
    assert not log_path.exists()

    logger.log("user", "Hola")

    assert log_path.read_text(encoding="utf-8").startswith(HEADER)
    assert len(read_rows(log_path)) == 2


@pytest.mark.parametrize(
    ("actor", "message", "tool_call"),
    [
        ("user", "¿Qué productos están por agotarse?", ""),
        ("agent", "Están por agotarse la leche de avena y el jarabe de vainilla.", ""),
        ("tool", '[{"name": "Leche de avena", "quantity": 12}]', "get_low_stock"),
        # tool_call es opcional también para "tool": el logger no impone cómo lo usará el agente.
        ("tool", '{"quantity": 28}', ""),
    ],
)
def test_logs_event(logger, log_path, actor, message, tool_call):
    logger.log(actor, message, tool_call)

    [row] = read_rows(log_path)[1:]
    assert row[:3] == [actor, message, tool_call]


def test_new_events_keep_previous_ones_and_header_is_written_once(log_path):
    ConversationLogger(log_path).log("user", "Vendimos 12 bolsas de arábica")
    # Otra instancia, como en una nueva ejecución del agente.
    logger = ConversationLogger(log_path)
    logger.log("tool", '{"quantity": 28}', "remove_stock")
    logger.log("agent", "Hecho: quedan 28 bolsas.")

    rows = read_rows(log_path)
    assert [row[0] for row in rows] == ["actor", "user", "tool", "agent"]
    assert log_path.read_text(encoding="utf-8").count(HEADER) == 1


def test_commas_quotes_and_newlines_are_escaped(logger, log_path):
    message = 'Vasos "take away", 12 oz\nsegunda línea'

    logger.log("user", message)

    [row] = read_rows(log_path)[1:]
    assert row[1] == message


def test_utf8_is_kept(logger, log_path):
    message = "Café arábica, piñón y té matcha 抹茶 ☕"

    logger.log("user", message)

    content = log_path.read_bytes()
    assert not content.startswith(b"\xef\xbb\xbf")  # sin BOM, como inventory.csv
    assert message in content.decode("utf-8")


@pytest.mark.parametrize("actor", ["system", "User", ""])
def test_invalid_actor_is_rejected(logger, log_path, actor):
    with pytest.raises(ValueError):
        logger.log(actor, "Hola")
    assert not log_path.exists()


@pytest.mark.parametrize(("message", "tool_call"), [(123, ""), ("Hola", None)])
def test_non_text_values_are_rejected(logger, log_path, message, tool_call):
    with pytest.raises(TypeError):
        logger.log("agent", message, tool_call)
    assert not log_path.exists()


@pytest.mark.parametrize(
    "content",
    [
        "nombre,mensaje\n",  # otro CSV
        "actor,message,tool_call\n",  # falta una columna
        "actor,message,tool_call,timestamp",  # sin salto de línea: la fila nueva se pegaría
        "user,Hola,,2026-09-26T10:00:00+02:00\n",  # datos sin cabecera
    ],
)
def test_existing_file_with_wrong_header_is_rejected_and_untouched(logger, log_path, content):
    log_path.parent.mkdir(parents=True)
    log_path.write_bytes(content.encode("utf-8"))

    with pytest.raises(ValueError, match="actor,message,tool_call,timestamp"):
        logger.log("user", "Hola")

    assert log_path.read_bytes() == content.encode("utf-8")


def test_timestamp_is_iso8601_with_timezone(logger, log_path):
    before = datetime.now().astimezone().replace(microsecond=0)
    logger.log("user", "Hola")
    after = datetime.now().astimezone()

    [row] = read_rows(log_path)[1:]
    timestamp = datetime.fromisoformat(row[3])
    assert timestamp.tzinfo is not None
    assert before <= timestamp <= after
