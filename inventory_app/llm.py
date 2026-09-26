"""Cliente del modelo de lenguaje: Chat Completions de Groq por HTTP (sin SDK).

`LLMClient.complete(messages, tools)` envía la conversación a Groq y devuelve un
`dict` sencillo con el texto de la respuesta o las herramientas que pide el modelo.
Quien lo usa no necesita conocer la URL, las cabeceras, la clave ni los errores HTTP.
Este módulo no conoce las herramientas del inventario: las recibe ya definidas.
"""

import json

import httpx2

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
# Modelo elegido para el proyecto: disponible en Groq y con tool use. No admite
# tool calls en paralelo, así que el agente pedirá y ejecutará herramientas en secuencia.
MODEL = "openai/gpt-oss-120b"
TIMEOUT_SECONDS = 30.0


class LLMError(Exception):
    """Fallo al consultar el modelo. El mensaje nunca incluye la clave ni cabeceras."""


class LLMClient:
    def __init__(self, api_key: str | None, http: httpx2.Client | None = None):
        if not api_key:
            raise LLMError("Falta GROQ_API_KEY: defínela en el archivo .env.")
        self._api_key = api_key
        # En los tests se pasa un httpx2.Client con MockTransport; sin él, uno real.
        self._http = http if http is not None else httpx2.Client()

    def complete(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        """Envía `messages` (y `tools`, en formato de Groq) y devuelve la respuesta del modelo.

        Devuelve {"content": str, "tool_calls": [{"id", "name", "arguments"}], "message": dict}.
        `message` es el mensaje del asistente tal como debe añadirse al historial.
        """
        payload = {"model": MODEL, "messages": messages}
        if tools:
            payload["tools"] = tools

        try:
            response = self._http.post(
                GROQ_CHAT_URL,
                json=payload,
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=TIMEOUT_SECONDS,
            )
        except httpx2.TimeoutException as exc:
            raise LLMError("Groq no respondió a tiempo.") from exc
        except httpx2.TransportError as exc:
            raise LLMError("No se puede conectar con Groq.") from exc

        if not response.is_success:
            raise LLMError(_http_error_message(response))
        return _parse_response(response)


def _http_error_message(response: httpx2.Response) -> str:
    # Solo el código HTTP y, si lo hay, el código de error de Groq (por ejemplo,
    # "invalid_api_key" o "model_decommissioned"); nunca el mensaje completo.
    try:
        code = response.json()["error"]["code"]
    except (ValueError, KeyError, TypeError):
        code = None
    detail = f", {code}" if isinstance(code, str) else ""
    return f"Groq rechazó la petición (HTTP {response.status_code}{detail})."


def _parse_response(response: httpx2.Response) -> dict:
    try:
        message = response.json()["choices"][0]["message"]
        content = message.get("content") or ""
        raw_tool_calls = message.get("tool_calls") or []
        tool_calls = []
        for call in raw_tool_calls:
            # Groq envía los argumentos como texto JSON.
            arguments = json.loads(call["function"]["arguments"])
            if not isinstance(arguments, dict):
                raise TypeError("los argumentos no son un objeto JSON")
            tool_calls.append({"id": call["id"], "name": call["function"]["name"], "arguments": arguments})
        if not isinstance(content, str):
            raise TypeError("content no es texto")
    except (ValueError, KeyError, IndexError, TypeError, AttributeError) as exc:
        raise LLMError("Groq devolvió una respuesta con un formato inesperado.") from exc

    assistant_message = {"role": "assistant", "content": content}
    if raw_tool_calls:
        assistant_message["tool_calls"] = raw_tool_calls
    return {"content": content, "tool_calls": tool_calls, "message": assistant_message}
