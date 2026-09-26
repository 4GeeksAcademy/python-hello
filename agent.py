"""Agente de inventario de Carla: bucle del agente y CLI de terminal.

Flujo de cada mensaje (`handle_message`):

    mensaje del usuario → modelo → ¿herramientas? → sí: ejecutar, devolver resultado, repetir
                                                 → no: respuesta final

El modelo solo *pide* herramientas; este módulo decide si la petición es válida y las
ejecuta a través de `tools.py`, que llega a la API por HTTP. El historial completo de
la sesión es una lista de mensajes en memoria, y cada evento se registra con
`ConversationLogger`.

Uso (con la API arrancada en otra terminal: `uvicorn inventory_app.api:app`):

    python agent.py
"""

import json
import sys

import httpx2

from inventory_app import tools
from inventory_app.api_client import InventoryApiClient
from inventory_app.config import PROJECT_ROOT, get_settings
from inventory_app.conversation_log import ConversationLogger
from inventory_app.errors import InventoryError
from inventory_app.llm import LLMClient, LLMError

LOG_PATH = PROJECT_ROOT / "data" / "conversation_log.csv"

# Llamadas al modelo por mensaje del usuario. Los flujos legítimos más largos (por
# ejemplo, buscar el nombre exacto y registrar dos entradas) necesitan unas 4, porque
# el modelo pide las herramientas de una en una; 8 deja margen y corta un bucle sin fin.
MAX_STEPS = 8

SYSTEM_PROMPT = """\
Eres el asistente de inventario de Carla, que gestiona un pequeño negocio familiar de \
suministros para cafeterías. Responde siempre en español, de forma breve y clara.

Reglas:
- Consulta y modifica el inventario solo con las herramientas disponibles. No inventes \
productos, cantidades ni resultados: básate en lo que devuelven las herramientas.
- Si no conoces el nombre exacto de un producto, usa list_products para encontrarlo \
antes de modificar su stock.
- Las cantidades son siempre enteros positivos: usa add_stock para las entradas de \
mercancía y remove_stock para las salidas o ventas.
- Si un producto no existe, no lo crees por tu cuenta: díselo a Carla y pregúntale si \
quiere registrarlo con su cantidad inicial, unidad y stock mínimo. Usa create_product \
solo cuando Carla lo confirme y te haya dado esos datos.
- Si la petición es ambigua, pregunta antes de modificar datos.
- Si una herramienta devuelve un error, explícaselo a Carla con claridad.
- Las herramientas sin parámetros se llaman con los argumentos vacíos: {}.
"""

_NAME = {"type": "string", "description": "Nombre exacto del producto."}
_POSITIVE_QUANTITY = {"type": "integer", "minimum": 1, "description": "Número de unidades (entero positivo)."}

# Definiciones que recibe el modelo (formato de Chat Completions de Groq).
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "list_products",
            "description": "Devuelve todos los productos del inventario con su cantidad, unidad y stock mínimo.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_low_stock",
            "description": "Devuelve los productos por agotarse (cantidad menor o igual que su stock mínimo).",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_stock",
            "description": "Registra una entrada de mercancía: suma unidades a un producto existente.",
            "parameters": {
                "type": "object",
                "properties": {"name": _NAME, "quantity": _POSITIVE_QUANTITY},
                "required": ["name", "quantity"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_stock",
            "description": "Registra una salida o venta: resta unidades de un producto existente.",
            "parameters": {
                "type": "object",
                "properties": {"name": _NAME, "quantity": _POSITIVE_QUANTITY},
                "required": ["name", "quantity"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_product",
            "description": "Registra un producto nuevo. Úsala solo cuando Carla lo haya confirmado.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": _NAME,
                    "quantity": {"type": "integer", "minimum": 0, "description": "Cantidad inicial."},
                    "unit": {"type": "string", "description": "Unidad de medida (unidades, bolsas, kg...)."},
                    "min_stock": {"type": "integer", "minimum": 0, "description": "Stock mínimo."},
                },
                "required": ["name", "quantity", "unit", "min_stock"],
                "additionalProperties": False,
            },
        },
    },
]

# Argumentos que espera cada herramienta, tomados de sus definiciones.
TOOL_PARAMETERS = {
    definition["function"]["name"]: set(definition["function"]["parameters"]["properties"])
    for definition in TOOL_DEFINITIONS
}

LIMIT_REPLY = "No he podido completar la petición en los pasos permitidos. ¿Puedes reformularla?"


def run_tool(client: InventoryApiClient, name: str, arguments: dict) -> dict:
    """Ejecuta una herramienta pedida por el modelo.

    Devuelve {"result": ...} o {"error": {"type", "message"}}; nunca lanza por un error
    de la herramienta, para que el modelo pueda explicárselo a Carla.
    """
    if name not in TOOL_PARAMETERS:
        return _error("UnknownTool", f"No existe la herramienta {name!r}.")
    if set(arguments) != TOOL_PARAMETERS[name]:
        expected = sorted(TOOL_PARAMETERS[name])
        return _error(
            "InvalidArguments",
            f"{name} espera exactamente los argumentos {expected}; se recibieron {sorted(arguments)}.",
        )

    try:
        if name == "list_products":
            result = tools.list_products(client)
        elif name == "get_low_stock":
            result = tools.get_low_stock(client)
        elif name == "add_stock":
            result = tools.add_stock(client, arguments["name"], arguments["quantity"])
        elif name == "remove_stock":
            result = tools.remove_stock(client, arguments["name"], arguments["quantity"])
        else:  # create_product
            result = tools.create_product(
                client,
                arguments["name"],
                arguments["quantity"],
                arguments["unit"],
                arguments["min_stock"],
            )
    except InventoryError as exc:
        # Producto inexistente, stock insuficiente, cantidad o datos inválidos, API caída...
        return _error(type(exc).__name__, str(exc))
    except TypeError:
        # Un argumento con un tipo que no se puede usar (por ejemplo, un nombre que no es texto).
        return _error("InvalidArguments", f"Argumentos no válidos para {name}: {arguments}.")
    return {"result": result}


def _error(error_type: str, message: str) -> dict:
    return {"error": {"type": error_type, "message": message}}


def handle_message(
    text: str,
    messages: list[dict],
    llm: LLMClient,
    client: InventoryApiClient,
    logger: ConversationLogger,
) -> str:
    """Procesa un mensaje del usuario y devuelve la respuesta para mostrarle.

    `messages` es el historial de la sesión: se amplía con lo que envía el usuario, lo que
    responde el modelo y los resultados de las herramientas. Los errores de escritura del
    registro se propagan.
    """
    logger.log("user", text)
    messages.append({"role": "user", "content": text})

    for _ in range(MAX_STEPS):
        try:
            response = llm.complete(messages, TOOL_DEFINITIONS)
        except LLMError as exc:
            return _agent_reply(f"No he podido consultar el modelo de lenguaje: {exc}", logger)

        messages.append(response["message"])
        if not response["tool_calls"]:
            logger.log("agent", response["content"])
            return response["content"]

        # El modelo no pide herramientas en paralelo: se ejecutan una tras otra, en orden.
        for call in response["tool_calls"]:
            result = run_tool(client, call["name"], call["arguments"])
            content = json.dumps(result, ensure_ascii=False)
            tool_call = json.dumps({"name": call["name"], "arguments": call["arguments"]}, ensure_ascii=False)
            logger.log("tool", content, tool_call)
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": content})

    return _agent_reply(LIMIT_REPLY, logger)


def _agent_reply(text: str, logger: ConversationLogger) -> str:
    """Respuesta generada por el agente (error del modelo o límite de pasos), no por el modelo.

    Se registra y se muestra al usuario, pero no se añade al historial: el modelo nunca la
    escribió. El historial sigue siendo válido: el siguiente mensaje `user` puede ir tras
    otro `user` o tras los resultados `tool` (comprobado con Groq).
    """
    logger.log("agent", text)
    return text


def main() -> int:
    settings = get_settings()
    try:
        llm = LLMClient(settings.groq_api_key)
    except LLMError as exc:
        print(f"Error: {exc}")
        return 1
    client = InventoryApiClient(httpx2.Client(base_url=settings.inventory_api_url))
    logger = ConversationLogger(LOG_PATH)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    print('Carla: ¡Hola! ¿En qué puedo ayudarte? (escribe "salir" para terminar)')
    while True:
        try:
            text = input("Tú: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not text:
            continue
        if text.lower() == "salir":
            break

        try:
            reply = handle_message(text, messages, llm, client, logger)
        except (OSError, ValueError):
            # Registrar la conversación es obligatorio: sin registro no se continúa.
            print(
                "Error: no se puede escribir el registro de conversaciones "
                "(data/conversation_log.csv). La sesión se cierra."
            )
            return 1
        except KeyboardInterrupt:
            print()
            break
        print(f"Carla: {reply}")

    print("Carla: ¡Hasta luego!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
