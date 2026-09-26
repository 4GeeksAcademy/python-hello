"""Registro de conversaciones en un CSV de solo añadir (append-only).

Cada llamada a `log` añade una fila `actor,message,tool_call,timestamp` y nunca
reescribe las anteriores. Este módulo solo escribe el registro: no guarda la
conversación en memoria ni sabe nada del agente, las herramientas o la API.
"""

import csv
from datetime import datetime
from pathlib import Path

FIELDNAMES = ("actor", "message", "tool_call", "timestamp")
HEADER_LINE = ",".join(FIELDNAMES) + "\n"
ACTORS = ("user", "agent", "tool")


class ConversationLogger:
    def __init__(self, path: Path):
        self._path = Path(path)

    def log(self, actor: str, message: str, tool_call: str = "") -> None:
        """Añade un evento al registro con la fecha y hora actuales.

        Los errores de escritura (`OSError`) se propagan a quien llama.
        """
        if actor not in ACTORS:
            raise ValueError(f"actor debe ser uno de {', '.join(ACTORS)}; se recibió {actor!r}.")
        if not isinstance(message, str) or not isinstance(tool_call, str):
            raise TypeError("message y tool_call deben ser texto (str).")

        # Hora local con su desfase horario (p. ej. 2026-09-25T21:30:00+02:00): ISO 8601
        # y sin ambigüedad de zona horaria.
        timestamp = datetime.now().astimezone().isoformat(timespec="seconds")

        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Modo "a+": permite leer la cabecera y todo lo que se escribe va siempre al
        # final, así que nunca se reescriben las filas anteriores.
        with self._path.open("a+", encoding="utf-8", newline="") as file:
            file.seek(0)
            first_line = file.readline()
            if first_line and first_line != HEADER_LINE:
                # No se repara ni se sobrescribe: el archivo queda como estaba.
                raise ValueError(
                    f"'{self._path}' no es un registro de conversaciones válido: "
                    f"su primera línea debe ser exactamente {HEADER_LINE.strip()!r}."
                )
            file.seek(0, 2)  # final del archivo
            writer = csv.writer(file, lineterminator="\n")
            if not first_line:
                writer.writerow(FIELDNAMES)
            writer.writerow([actor, message, tool_call, timestamp])
