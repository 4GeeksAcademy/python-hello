# Contexto técnico

## Lenguaje principal

Python 3.13 (versión del entorno en la Fase 0).

Entorno actual (desde la Fase 2, en otro ordenador): `.venv` con **Python 3.14.6**. La suite pasa con esta versión.

El proyecto se ejecutará utilizando un entorno virtual local situado en:

`.venv/`

No se instalarán dependencias globales para el proyecto.

## API

La API REST se desarrollará utilizando:

* FastAPI
* Uvicorn
* Pydantic

FastAPI será responsable de exponer los endpoints HTTP y Pydantic de validar los datos de entrada y salida cuando sea necesario.

### Decisiones aprobadas (Fase 2)

Implementada en `inventory_app/api.py`. Arranque: `uvicorn inventory_app.api:app`.

Endpoints:

| Método y ruta | Entrada | Respuesta correcta |
|---|---|---|
| `GET /health` | — | 200 `{"status": "ok"}` (no lee el CSV) |
| `GET /products` | — | 200, lista de productos |
| `GET /products/low-stock` | — | 200, productos con `quantity <= min_stock` |
| `GET /products/{name}` | nombre en la ruta | 200, producto |
| `POST /products` | `{"name", "quantity", "unit", "min_stock"}` | 201, producto creado |
| `POST /products/{name}/stock` | `{"change": n}` | 200, producto actualizado |

* Cada producto se devuelve como `{"name", "quantity", "unit", "min_stock", "low_stock"}`.
* `/products/low-stock` se declara antes que `/products/{name}`.
* `change` es un entero estricto distinto de cero: positivo para entradas, negativo para salidas. No hay endpoint para fijar el stock absoluto, ni SKU, ni ID público.
* El nombre de la ruta se busca sin distinguir mayúsculas y quitando los espacios exteriores. El cliente debe codificarlo en la URL.

Reglas del nombre de producto (en `models.py`, así que también valen al leer el CSV):

* De 1 a 100 caracteres tras quitar los espacios exteriores.
* Sin espacios dobles.
* Sin `/`. El servidor decodifica `%2F` antes de elegir ruta, así que un nombre con `/` nunca llegaría a `/products/{name}`.
* `low-stock` está reservado (sin distinguir mayúsculas), porque coincide con la ruta de stock bajo.
* La identidad no distingue mayúsculas; los acentos sí cuentan.

Formato uniforme de error:

```json
{"code": "...", "message": "...", "details": {}}
```

| Situación | HTTP | `code` | `details` |
|---|---|---|---|
| `ProductNotFound` | 404 | `product_not_found` | `name` |
| `ProductAlreadyExists` | 409 | `product_already_exists` | `name` |
| `InsufficientStock` | 409 | `insufficient_stock` | `name`, `available`, `requested` |
| `InvalidStockChange` (`change` igual a 0) | 422 | `invalid_stock_change` | — |
| Entrada inválida (tipos, campos, JSON mal formado) | 422 | `validation_error` | `errors`: lista de `{field, message}` |
| `StorageError` | 500 | `storage_error` | — |
| Ruta inexistente | 404 | `not_found` | — |
| Método no permitido | 405 | `method_not_allowed` | — (se conserva la cabecera `Allow`) |

* Los errores 500 no exponen rutas ni detalles del sistema de archivos: el mensaje es genérico y el detalle se registra con `logging` (biblioteca estándar).
* Cualquier otro error HTTP del enrutador usaría `http_error`. No debería producirse con los endpoints actuales.

Diseño:

* `create_app(service=None)` crea la aplicación y declara las rutas dentro de la función. Todos los endpoints usan el mismo `InventoryService` y, por tanto, el mismo repositorio y su `RLock`. Sin `service`, se construye a partir de `get_settings()`.
* No se usan `APIRouter`, `Depends` ni `app.state`. Con 6 endpoints, declarar las rutas dentro de `create_app` es suficiente y tiene menos conceptos. Se decidió explícitamente por el carácter educativo del proyecto.
* Crear la aplicación (y, por tanto, importar `api.py`) no lee el CSV; se lee al atender cada petición.
* `api.py` no contiene lógica de negocio: valida la entrada con los modelos, llama al servicio y traduce los errores a HTTP.

## Agente de IA

El agente se desarrollará en Python y estará contenido en:

`agent.py`

El agente será responsable de:

* Mantener el historial de conversación durante la sesión.
* Enviar mensajes al modelo de lenguaje.
* Interpretar las llamadas a herramientas.
* Ejecutar las herramientas disponibles.
* Incorporar los resultados de las herramientas al contexto.
* Repetir el ciclo de razonamiento y ejecución cuando sea necesario.
* Generar la respuesta final para el usuario.
* Registrar la actividad de la conversación.

## Modelo de lenguaje

La integración con el modelo de lenguaje se realizará mediante Groq.

La clave de API se almacenará en un archivo `.env` situado en la raíz del proyecto.

Variable esperada:

`GROQ_API_KEY`

La clave nunca debe escribirse directamente en el código ni incluirse en Git.

### Decisiones aprobadas (Fase 5): `LLMClient`

Implementado en `inventory_app/llm.py`. Se usa **directamente la API HTTP de Groq, sin los SDK `groq` ni `openai`**. El cliente HTTP es `httpx2==2.13.1`, que ya era dependencia de ejecución.

```text
futuro agent.py → LLMClient → httpx2 → Groq API
```

* `LLMClient` es la única capa que conoce la comunicación HTTP con Groq: URL, cabeceras, clave, formato de la petición y errores HTTP.
* Las herramientas se reciben como datos. `LLMClient` no importa ni ejecuta `tools.py`.

Petición (verificada en la documentación oficial de Groq y con una prueba real):

* `POST https://api.groq.com/openai/v1/chat/completions` (Chat Completions, compatible con el formato de OpenAI).
* Cabecera `Authorization: Bearer <GROQ_API_KEY>`.
* Cuerpo JSON: `{"model": ..., "messages": [...]}`, más `"tools": [...]` solo si se pasan herramientas. No se envían más parámetros (el valor por defecto de `tool_choice` es `auto`).
* Formato de `tools` (lo construirá el agente): `[{"type": "function", "function": {"name", "description", "parameters": <JSON Schema>}}]`.
* Timeout explícito de 30 s por petición. Sin reintentos, backoff, streaming ni gestión de límites.
* URL, modelo y timeout son constantes del módulo (`GROQ_CHAT_URL`, `MODEL`, `TIMEOUT_SECONDS`): el nombre del modelo está en un único sitio.

Modelo (decisión definitiva del usuario): **`openai/gpt-oss-120b`**.

* Es el modelo elegido para todo el proyecto. Está disponible en Groq, admite tool use y se usa mediante HTTP directo.
* Está centralizado en la constante `MODEL` de `llm.py`. No se repite en `agent.py`, `.env` ni los tests (que importan `MODEL`), y no hay variable `GROQ_MODEL` ni configuración para elegir modelo.
* Según la documentación de Groq **no admite tool calls en paralelo**, así que la Fase 6 diseñará el bucle de forma secuencial. Aun así, `LLMClient` acepta varias tool calls en una respuesta, porque el formato de la API lo permite.

Configuración:

* `config.py`: `Settings.groq_api_key` se lee de `GROQ_API_KEY` (entorno o `.env`). Vale `None` si falta o está vacía.
* `LLMClient(api_key, http=None)` recibe la clave. Si falta, lanza `LLMError("Falta GROQ_API_KEY: defínela en el archivo .env.")`.
* `http` permite inyectar un `httpx2.Client` (en los tests, con `MockTransport`). Sin él, se crea un `httpx2.Client()` real.

Interfaz:

* `complete(messages, tools=None) -> dict`. `messages` y `tools` se reciben ya en formato de Groq y se envían tal cual. `LLMClient` no conoce las herramientas del inventario ni importa `tools.py`.
* No ejecuta herramientas ni implementa el bucle del agente.

Respuesta normalizada (un `dict` de Python; nunca el objeto de `httpx2` ni el JSON crudo completo de Groq). Permite distinguir una respuesta de texto (`tool_calls` vacío) de una petición de herramientas:

```python
{
    "content": "texto del asistente",   # "" si el modelo solo pide herramientas
    "tool_calls": [                     # [] si es una respuesta normal
        {"id": "call_1", "name": "add_stock", "arguments": {"name": "Leche de avena", "quantity": 30}},
    ],
    "message": {"role": "assistant", "content": "...", "tool_calls": [...]},
}
```

* `tool_calls[].arguments` ya es un `dict`: Groq envía los argumentos como texto JSON y `LLMClient` los convierte. No corrige ni interpreta su contenido.
* `message` es un `dict` normal: el mensaje del asistente, listo para añadirlo directamente al historial antes de enviar los resultados de las herramientas. Incluye los `tool_calls` tal como los devolvió Groq, para que el agente no tenga que reconstruir su formato. Los resultados se envían como `{"role": "tool", "tool_call_id": <id>, "content": ...}`.
* Solo se valida la estructura necesaria:
  * `choices[0].message`.
  * `content` debe ser texto o `null`.
  * Cada tool call debe tener `id`, `function.name` y `function.arguments` con un objeto JSON.

Errores (`LLMError`, definida en `llm.py` porque no pertenece a los errores del inventario):

| Caso | Mensaje de `LLMError` |
|---|---|
| Falta la clave | `Falta GROQ_API_KEY: defínela en el archivo .env.` |
| Respuesta HTTP de error | `Groq rechazó la petición (HTTP <status>[, <code>]).` Solo incluye el `error.code` de Groq (por ejemplo `invalid_api_key`), nunca su mensaje completo |
| Timeout | `Groq no respondió a tiempo.` |
| Error de conexión | `No se puede conectar con Groq.` |
| JSON mal formado o estructura inesperada | `Groq devolvió una respuesta con un formato inesperado.` |

* Los mensajes nunca contienen la clave, la cabecera `Authorization` ni detalles internos. La excepción original queda encadenada (`from exc`) solo para depurar; no debe llegar al modelo.

Comportamiento observado en la prueba real: para una herramienta sin parámetros, `openai/gpt-oss-120b` envió los argumentos `{"": {}}` en lugar de `{}`.

* No es responsabilidad de `LLMClient`: se limita a convertir el JSON en `dict` y no lo corrige.
* La tolerancia o corrección de argumentos se decidirá en la Fase 6, al definir las herramientas y el comportamiento del agente.
* El test real comprueba que existe la tool call esperada y que `arguments` es un `dict`, sin exigir `{}`.

## Variables de entorno

Las variables sensibles se gestionarán mediante `.env`.

El archivo `.env` debe estar incluido en `.gitignore`.

No se deben registrar claves, tokens ni credenciales en archivos versionados.

## Persistencia

La primera versión utilizará archivos CSV como sistema de persistencia.

El inventario tendrá un archivo CSV dedicado.

El registro de conversaciones utilizará:

`conversation_log.csv`

### Decisiones aprobadas (Fase 0)

Rutas:

* Inventario: `data/inventory.csv`
* Registro de conversaciones: `data/conversation_log.csv`

Los CSV de `data/` forman parte del proyecto y se versionan en Git (no se excluyen en `.gitignore`), para facilitar la evaluación y la ejecución desde un clon limpio. El contenido inicial de `inventory.csv` se decidirá en la Fase 1.

Formato de `data/inventory.csv`:

```text
name,quantity,unit,min_stock
```

* `name`: texto; identificador del producto. Se compara sin distinguir mayúsculas/minúsculas y se guarda tal como se registró.
* `quantity`: entero `>= 0`.
* `unit`: texto (por ejemplo, "unidades", "bolsas", "kg").
* `min_stock`: entero `>= 0`, específico de cada producto.

Un producto está en stock bajo cuando `quantity <= min_stock`. Este valor se calcula y no se almacena.

Formato de `data/conversation_log.csv`:

```text
actor,message,tool_call,timestamp
```

* Append-only: solo se añaden filas; nunca se sobrescribe ni se reescribe.

### Decisiones aprobadas (Fase 4): registro de conversaciones

Implementado en `inventory_app/conversation_log.py`:

* Una clase `ConversationLogger(path)` con un único método: `log(actor, message, tool_call="")`. Solo usa la biblioteca estándar (`csv`, `datetime`, `pathlib`).
* La ruta es obligatoria; no hay ruta por defecto ni variable de entorno. El agente le pasará `data/conversation_log.csv` cuando se implemente.
* Crear el logger no crea el archivo. El primer `log` crea el archivo y su directorio si no existen.
* Solo añade (append): el archivo se abre en modo `"a+"`, que permite leer la primera línea y escribe siempre al final. Nunca se reescriben las filas anteriores.
* Cabecera:
  * Si el archivo no existe o está vacío, se escribe `actor,message,tool_call,timestamp` antes de la primera fila, así que nunca se duplica.
  * Si ya tiene contenido, su primera línea debe ser exactamente `actor,message,tool_call,timestamp` seguida de salto de línea. Si no lo es, se lanza `ValueError` con un mensaje claro y el archivo no se modifica: no se repara ni se sobrescribe.
* UTF-8 sin BOM y fin de línea `\n`, igual que `inventory.csv`. `csv.writer` escapa comas, comillas y saltos de línea.
* Validación del evento (formato, no reglas del agente):
  * `actor` debe ser `user`, `agent` o `tool` (`ValueError`).
  * `message` y `tool_call` deben ser texto (`str`), sin convertir otros tipos (`TypeError`). Pueden estar vacíos.
  * `tool_call` **no** es obligatorio para `actor="tool"`: el logger no impone cómo lo usará el agente.
  * Si la validación falla, no se toca el archivo.
* El formato interno de `tool_call` queda deliberadamente abierto: el logger guarda el texto que reciba.
* Los errores de escritura (`OSError`) se propagan a quien llama a `log`; no se ocultan ni se convierten en éxito.
* `timestamp`: lo genera el logger con `datetime.now().astimezone().isoformat(timespec="seconds")`. Es la hora local con su desfase horario (por ejemplo `2026-09-25T21:30:00+02:00`): ISO 8601 y con zona horaria explícita.
* No mantiene memoria de la conversación: la memoria completa de la sesión será responsabilidad del futuro agente. No conoce FastAPI, el servicio, el cliente HTTP, las herramientas ni Groq.
* No hay bloqueo entre hilos ni procesos: el agente escribe los eventos uno tras otro.

Pendiente para la Fase 6 (depende del agente), **resuelto en la Fase 6** (ver "Decisiones aprobadas (Fase 6)"):

* El formato concreto de `tool_call` (por ejemplo, solo el nombre de la herramienta o también sus argumentos) y qué texto lleva `message` en cada tipo de fila.
* Cómo maneja el agente un fallo al escribir el log (`OSError` o cabecera inválida), incluido cómo se transforman esos errores para el agente o el LLM.

Comportamiento previsto de la persistencia (propuesto en Fase 0, se validará con pruebas en la Fase 1):

* Si el archivo de inventario no existe, se considera inventario vacío y se crea con cabecera en la primera escritura.
* Codificación UTF-8, separador `,`.
* Escritura atómica del inventario (archivo temporal en el mismo directorio + `os.replace`) para evitar pérdida de datos.
* Un lock protege cada ciclo lectura-modificación-escritura.
* Si el archivo no se puede leer o su contenido no es válido (cabecera incorrecta, tipos inválidos, duplicados), se produce un error explícito y el archivo no se sobrescribe.
* Los errores de acceso (por ejemplo, el archivo está abierto y bloqueado por otra aplicación) se informan explícitamente.

## Herramientas del agente

El agente no deberá modificar directamente los archivos de inventario desde su lógica de conversación.

Las operaciones sobre el inventario deberán realizarse mediante herramientas claramente definidas que utilicen la API del proyecto.

Las herramientas deberán representar acciones reales que el agente pueda ejecutar, por ejemplo:

* Consultar productos.
* Añadir stock.
* Reducir stock.
* Consultar productos con stock bajo.
* Registrar productos.

La lista definitiva de herramientas y sus contratos se establecerá durante la fase de diseño de la API y del agente.

### Decisiones aprobadas (Fase 0)

* El agente accede al inventario exclusivamente mediante HTTP a la API. No importa la lógica de negocio ni la persistencia.
* `add_stock` y `remove_stock` son herramientas independientes. Ambas reciben una cantidad positiva; el signo del movimiento lo determina la herramienta, no el modelo.
* Los productos inexistentes no se crean automáticamente: si una operación falla porque el producto no existe, el agente debe preguntar al usuario antes de registrarlo.
* Los errores de las herramientas (producto inexistente, stock insuficiente, argumentos inválidos, API no disponible) se devuelven al modelo como resultado estructurado, sin interrumpir el bucle.
* El bucle del agente tiene un límite máximo de pasos (llamadas al modelo por mensaje del usuario) para evitar bucles infinitos.

### Propuesta de herramientas (Fase 0; la lista actual está en "Decisiones aprobadas (Fase 3)")

| Herramienta | Operación de API propuesta |
|---|---|
| `list_products` | `GET /products` |
| `get_product` | `GET /products/{name}` |
| `create_product` | `POST /products` |
| `add_stock` | `POST /products/{name}/stock` con `change` positivo |
| `remove_stock` | `POST /products/{name}/stock` con `change` negativo |
| `get_low_stock_products` | `GET /products/low-stock` |

### Decisiones aprobadas (Fase 3)

Cliente HTTP (`inventory_app/api_client.py`, clase `InventoryApiClient`):

* Métodos: `list_products()`, `get_low_stock()`, `add_stock(name, quantity)` y `remove_stock(name, quantity)`.
* Recibe un `httpx2.Client` ya configurado. En los tests se usa el `TestClient` de FastAPI (que es un `httpx2.Client`) y en producción se usará un `httpx2.Client(base_url=...)`. No hay una capa HTTP propia.
* Es el único módulo que usa `httpx2`. No importa `InventoryService` ni `CsvInventoryRepository` y no accede al CSV. Solo importa `errors.py` para reutilizar sus excepciones.
* El nombre del producto se codifica con `urllib.parse.quote(name, safe="")`. `httpx2` codifica los espacios y el Unicode, pero no `/`, `?`, `#` ni `%`, que romperían la ruta.
* `quantity` debe ser un entero positivo (se rechazan también los booleanos). Si no lo es, lanza `InvalidStockChange` sin hacer ninguna petición. `add_stock` envía `change` positivo y `remove_stock` lo envía negativo: el signo lo fija el cliente.
* Devuelve el JSON de la API tal cual (`dict` o lista de `dict`).
* Traduce los errores según el `code` de la respuesta (no solo según el código HTTP), reutilizando las excepciones de `errors.py`:

| `code` de la API | Excepción |
|---|---|
| `product_not_found` | `ProductNotFound` |
| `product_already_exists` | `ProductAlreadyExists` |
| `insufficient_stock` | `InsufficientStock` |
| `invalid_stock_change` | `InvalidStockChange` |
| `validation_error` | `InventoryError` con los motivos de la API (desde la Fase 6; antes `InvalidStockChange`) |
| `storage_error` | `StorageError` (con el mensaje genérico de la API) |
| `not_found`, `method_not_allowed`, otros | `InventoryError` |
| Respuesta que no es de nuestra API | `InventoryError`, sin incluir el cuerpo de la respuesta |
| Error de conexión (`httpx2.TransportError`) | `InventoryError("No se puede conectar con la API de inventario.")` |

* `404 + not_found` (ruta inexistente) no se trata como producto inexistente. Con una URL base incorrecta, el agente propondría crear un producto que ya existe. Por eso, un nombre con `/` también da `InventoryError`.
* El mensaje del error de conexión no incluye detalles de `httpx2`. El error original queda encadenado (`from exc`) y solo aparece en una traza completa de Python.

Herramientas (`inventory_app/tools.py`):

* Cuatro funciones de módulo: `list_products(client)`, `get_low_stock(client)`, `add_stock(client, name, quantity)` y `remove_stock(client, name, quantity)`.
* Cada una llama a un solo método de `InventoryApiClient` y devuelve su resultado sin cambios. No contienen lógica de inventario ni HTTP.
* Solo importan `InventoryApiClient`. No conocen FastAPI, el servicio, el repositorio ni el CSV.
* No hay clase `Tool`, registro ni framework de herramientas.
* No capturan excepciones: `ProductNotFound`, `InsufficientStock`, `InvalidStockChange`, `StorageError` e `InventoryError` llegan intactas a quien las llama.
* Reciben la cantidad positiva. La conversión a cambio negativo de `remove_stock` la hace `InventoryApiClient`. Esto matiza la decisión de la Fase 0: el signo no lo decide el modelo, pero lo fija el cliente y no la herramienta.
* No hay herramientas para consultar un producto concreto ni para crear productos (en la Fase 6 se añadió `create_product`; ver abajo).
* Son funciones normales de Python, independientes de Groq. Convertirlas en definiciones que vea el modelo queda para la integración con el LLM.

Pendiente (no decidido), **resuelto en la Fase 6**:

* Dónde se convierten las excepciones de las herramientas en el resultado estructurado para el modelo que prevé la Fase 0: en `run_tool()` de `agent.py`.
* La URL base de la API y su configuración: variable `INVENTORY_API_URL` en `config.py`.

### Decisiones aprobadas (Fase 6): agente

Cambios en las capas anteriores (solo lo necesario):

* **Quinta herramienta `create_product`**, porque registrar productos es un requisito funcional (`productContext.md`) y `POST /products` ya existía. Se añadió `InventoryApiClient.create_product(name, quantity, unit, min_stock)`, que valida en la API, y `tools.create_product(client, name, quantity, unit, min_stock)`. El contrato de la API no cambia.
* **Cambio en la traducción de errores del cliente:** `validation_error` ya no da `InvalidStockChange` sino `InventoryError` con los motivos de la API (por ejemplo, `body.name: Value error, el nombre no puede contener '/'`). Con `create_product`, un dato inválido no es un "cambio de stock inválido". En los métodos de stock no cambia nada en la práctica, porque el cliente valida la cantidad antes de enviar. `invalid_stock_change` sigue dando `InvalidStockChange`.
* **`config.py`:** `Settings.inventory_api_url`, leída de `INVENTORY_API_URL` (entorno o `.env`), con valor por defecto `http://127.0.0.1:8000`. Está documentada en `.env.example`.

`agent.py` (en la raíz), sin clases, legible de arriba abajo:

* Constantes:
  * `LOG_PATH` (`data/conversation_log.csv`).
  * `MAX_STEPS = 8`.
  * `SYSTEM_PROMPT`, dentro de `agent.py`: no se creó `prompts.py`, que estaba previsto en la estructura de la Fase 0.
  * `TOOL_DEFINITIONS`: las 5 herramientas en formato de Groq, con JSON Schema, `required` y `additionalProperties: false`.
  * `TOOL_PARAMETERS`: los argumentos de cada herramienta, derivados de las definiciones.
  * `LIMIT_REPLY`.
* `run_tool(client, name, arguments) -> dict`:
  * Valida de forma explícita: la herramienta debe existir (`UnknownTool`) y los argumentos deben ser exactamente los de su definición (`InvalidArguments`). Así, argumentos que faltan, que sobran o como `{"": {}}` se rechazan y no se ignoran.
  * Ejecuta la función de `tools.py` con un `if` por herramienta.
  * Devuelve `{"result": ...}` o `{"error": {"type", "message"}}`. `type` es el nombre de la excepción (`InsufficientStock`, `ProductNotFound`...), o `InvalidArguments` si falla con `TypeError`.
  * Nunca lanza por un error de herramienta. La cantidad se pasa tal cual: el agente no cambia el signo.
* `handle_message(text, messages, llm, client, logger) -> str`, el bucle:
  1. Registra `user` y añade el mensaje al historial.
  2. Hasta `MAX_STEPS` veces: llama a `llm.complete(messages, TOOL_DEFINITIONS)` y añade `response["message"]` al historial.
     * Sin `tool_calls`: registra `agent` y devuelve el texto.
     * Con `tool_calls`: ejecuta cada una **en orden** (el modelo no las pide en paralelo), registra `tool` y añade `{"role": "tool", "tool_call_id": id, "content": <JSON del resultado>}`.
  3. Si se agotan los pasos: devuelve `LIMIT_REPLY` y lo registra como `agent`, pero **no** lo añade al historial.
* El historial solo contiene mensajes reales: lo que escribe el usuario, lo que responde el modelo y los resultados de las herramientas. Las respuestas generadas por el agente (error del modelo o límite de pasos) se muestran y se registran, pero no se añaden como `assistant`, porque el modelo nunca las escribió. El formato sigue siendo válido: se comprobó con Groq que acepta un `user` tras otro `user` y un `user` tras mensajes `tool`.
* `main()`, la CLI:
  * Crea `LLMClient` (si falta la clave, muestra el error y sale), `InventoryApiClient(httpx2.Client(base_url=settings.inventory_api_url))`, `ConversationLogger(LOG_PATH)` y el historial con el system prompt.
  * Lee la entrada con `input("Tú: ")` y muestra `Carla: <respuesta>`. Termina con `salir`, EOF o Ctrl+C.
* Historial: una única `list[dict]` para toda la sesión, en formato de Chat Completions. Contiene `system`, `user`, los mensajes del asistente tal como los devuelve `LLMClient` y los mensajes `tool` con su `tool_call_id`.

Registro (`ConversationLogger` es el único que escribe el log):

| Evento | `actor` | `message` | `tool_call` |
|---|---|---|---|
| Mensaje del usuario | `user` | su texto | `""` |
| Herramienta ejecutada | `tool` | el JSON exacto enviado al modelo (`{"result": ...}` o `{"error": ...}`) | `{"name": ..., "arguments": {...}}` en JSON |
| Respuesta final, mensaje de límite o error del modelo | `agent` | el texto que ve el usuario | `""` |

Los mensajes intermedios del modelo que solo piden herramientas no se registran como `agent`.

Errores:

* **Error de una herramienta:** se envía al modelo como resultado y el bucle continúa.
* **`LLMError`:** se responde `"No he podido consultar el modelo de lenguaje: <mensaje seguro>"`, que se registra como `agent` pero no se añade al historial. La sesión continúa y no se muestra ningún traceback.
* **Fallo al escribir el registro (`OSError` o `ValueError` del logger):** `main()` muestra un mensaje claro, sin rutas internas, y termina la sesión con código 1. Registrar la conversación es obligatorio.

Pruebas: `tests/test_agent.py` usa un `FakeLLM` (lo único falso) con la API real en `TestClient` sobre un CSV temporal y el logger sobre un archivo temporal. `tests/test_live_groq.py` incluye un test opt-in del agente completo con el modelo real.

## Arquitectura inicial

La arquitectura prevista deberá mantener separadas estas responsabilidades:

```text
Usuario
   │
   ▼
Agente
   │
   ├── Modelo de lenguaje (Groq)
   │
   └── Herramientas
          │
          ▼
       API FastAPI
          │
          ▼
      Persistencia CSV
```

La estructura exacta de archivos se decidirá durante la fase de arquitectura antes de implementar la aplicación.

### Arquitectura implementada (tras la Fase 3)

```text
tools.py
    ↓
InventoryApiClient        (api_client.py; único módulo que usa httpx2)
    ↓ HTTP
FastAPI                   (api.py)
    ↓
InventoryService          (service.py)
    ↓
CsvInventoryRepository    (repository.py)
    ↓
data/inventory.csv
```

* `tools.py` no conoce FastAPI ni la persistencia.
* `InventoryApiClient` es la única capa que usa `httpx2`.
* El agente accede al inventario solo a través de las herramientas y el cliente HTTP. Nunca accede directamente al CSV ni importa el servicio o el repositorio.
* El agente (`agent.py`, Fase 6) orquesta el bucle: usa `LLMClient`, `tools.py` (a través de `InventoryApiClient` y HTTP) y `ConversationLogger`. El system prompt está dentro de `agent.py`.
* El cliente del modelo (`LLMClient` en `llm.py`, Fase 5) es independiente: solo usa `httpx2` y no conoce las herramientas del inventario.
* El registro de conversaciones (`conversation_log.py`, Fase 4) es un componente aislado. Lo usará el agente, pero no depende de ninguna otra capa.

### Estructura aprobada (Fase 0)

`inventory_app/` es el paquete principal y `agent.py`, en la raíz, es el punto de entrada del agente.

Estructura prevista (los archivos se crean progresivamente en cada fase; tras la Fase 6 existen `agent.py` en la raíz y `config.py`, `models.py`, `errors.py`, `repository.py`, `service.py`, `api.py`, `api_client.py`, `tools.py`, `conversation_log.py` y `llm.py`, además de `pytest.ini` en la raíz; `prompts.py` no se creó (el system prompt está en `agent.py`); `data/conversation_log.csv` se creará con el primer evento real):

```text
agent.py                     # Bucle del agente, historial en memoria y CLI de terminal
inventory_app/
  __init__.py
  config.py                  # Configuración desde .env / variables de entorno
  models.py                  # Modelos Pydantic
  errors.py                  # Excepciones de dominio
  repository.py              # Persistencia CSV del inventario
  service.py                 # Lógica de negocio del inventario
  api.py                     # Aplicación FastAPI y endpoints
  api_client.py              # Cliente HTTP de la API (usado por las herramientas)
  tools.py                   # Definición y ejecución de herramientas del agente
  llm.py                     # LLMClient: Chat Completions de Groq por HTTP (httpx2)
  prompts.py                 # Prompt de sistema
  conversation_log.py        # Registro append-only de conversaciones
data/                        # inventory.csv y conversation_log.csv
tests/                       # Pruebas automatizadas (pytest)
requirements.txt             # Dependencias de ejecución
requirements-dev.txt         # Dependencias de desarrollo
.env.example                 # Nombres de variables, sin credenciales
```

Separación de responsabilidades:

* API (`api.py`): endpoints finos, validación y traducción de errores a códigos HTTP.
* Lógica de negocio (`service.py`): reglas del inventario.
* Persistencia (`repository.py`): lectura y escritura del CSV.
* Modelos (`models.py`): contratos de datos.
* El agente (`agent.py`) solo conoce el cliente HTTP, las herramientas, el cliente del modelo y el registro.

Solo la API escribe en `data/inventory.csv`; solo el agente escribe en `data/conversation_log.csv`.

## Pruebas

El proyecto deberá disponer de pruebas automatizadas para validar progresivamente:

* Endpoints de la API.
* Validación de datos.
* Operaciones sobre el inventario.
* Persistencia.
* Herramientas del agente.
* Bucle principal del agente.
* Registro de conversaciones.
* Flujo completo de extremo a extremo.

Las pruebas deberán incorporarse progresivamente junto con cada funcionalidad importante.

### Decisiones aprobadas (Fase 0)

* Framework de pruebas: `pytest`.
* La API y el cliente HTTP se prueban con `TestClient` de FastAPI (compatible con `httpx.Client`), sin levantar un servidor.
* El agente se prueba con un `FakeLLM` de respuestas predefinidas, sin depender de Groq ni de la red.
* Las pruebas usan archivos CSV temporales, nunca los de `data/`.

Actualización (Fase 2):

* Con la versión de Starlette instalada, `TestClient` se basa en `httpx2` (no en `httpx`). Por eso se instaló `httpx2==2.13.1` como dependencia de desarrollo.
* `pytest.ini` con `pythonpath = .` permite ejecutar los tests con `pytest` además de con `python -m pytest`.
* `conftest.py` mantiene la salvaguarda de sesión que falla si algún test modifica `data/inventory.csv`.

Actualización (Fase 3):

* `InventoryApiClient` se prueba contra la aplicación FastAPI real mediante `TestClient`, sin Uvicorn. Solo las respuestas que la API no puede producir con sus métodos (y los errores de conexión) se simulan con `httpx2.MockTransport`, que viene con `httpx2`.
* Las herramientas se prueban con un cliente falso pequeño definido dentro del test. Solo se comprueba la delegación y la propagación de excepciones.

Actualización (Fase 5):

* `LLMClient` se prueba con respuestas de Groq simuladas mediante `httpx2.MockTransport`. Una fixture `autouse` en `test_llm.py` hace fallar cualquier conexión real (`httpx2.HTTPTransport.handle_request`), así que la suite normal no llega a Internet ni consume tokens.
* Actualización (Fase 7):
  * `tests/test_live_groq.py` incluye además los flujos F1–F5 del agente completo con el modelo real, sobre una copia del inventario inicial real. Comprueban efectos (CSV en disco y herramientas del log), no el texto exacto.
  * `tests/test_agent.py` incluye F6: `main()` contra la API servida por Uvicorn en un hilo (HTTP real, puerto asignado por el sistema), con `FakeLLM`.
* `tests/test_live_groq.py` hace dos llamadas reales (texto y tool call) y está separado de la suite normal. Se omite salvo que se ejecute explícitamente con `GROQ_LIVE=1` (`$env:GROQ_LIVE = "1"; pytest tests/test_live_groq.py`). Usa `GROQ_API_KEY` de `.env` y no la muestra.

## Dependencias

Las dependencias deberán mantenerse reducidas a las necesarias para el funcionamiento del proyecto.

Actualmente el entorno virtual contiene principalmente:

* `fastapi`
* `uvicorn`

Las nuevas dependencias deberán añadirse únicamente cuando exista una necesidad concreta y deberán quedar documentadas.

Estado verificado en Fase 0 (`.venv`, Python 3.13.15): `fastapi` 0.141.1, `uvicorn` 0.54.0, `pydantic` 2.13.5 y sus dependencias transitivas. No existe todavía archivo de dependencias.

Decisión aprobada: las dependencias se declararán en `requirements.txt` (ejecución) y `requirements-dev.txt` (desarrollo).

Dependencias aprobadas y fase en la que se instalan (no se instalan antes de la fase que las necesita):

| Dependencia | Uso | Fase |
|---|---|---|
| `python-dotenv` | Lectura de variables de entorno desde `.env` | 1 |
| `pytest` | Pruebas automatizadas (desarrollo) | 1 |
| `httpx` | Comunicación HTTP entre agente/herramientas y la API; requisito de `TestClient` | 3 (sustituida por `httpx2`, ver abajo) |
| `groq` | Integración con la API de Groq | 5 (**no se instala**: ver abajo) |

Actualización (Fase 2): en la Fase 0 se preveía que la Fase 2 no añadiría dependencias, pero `TestClient` no funciona sin un cliente HTTP. La versión instalada de Starlette (1.7.0, que trae FastAPI 0.141.1) requiere `httpx2` y solo admite `httpx` como alternativa obsoleta. Decisión aprobada:

* `httpx2==2.13.1` en `requirements-dev.txt`, solo para `TestClient`. No forma parte de la lógica del inventario.
* En la Fase 3, cuando `InventoryApiClient` lo use en ejecución, se evaluará si pasa también a `requirements.txt`. No se instalará `httpx` ni otra librería HTTP alternativa.

Actualización (Fase 3): `httpx2==2.13.1` pasa de dependencia de desarrollo a dependencia de ejecución, porque ahora `InventoryApiClient` lo usa para hablar con la API. Se quita de `requirements-dev.txt`, que lo recibe a través de `-r requirements.txt`. No se añadió ninguna otra dependencia.

Actualización (Fase 5): la integración con Groq usa directamente su API HTTP con `httpx2`. No se instala el SDK `groq` ni `openai`, y no se añade ninguna dependencia.

Estado actual de los archivos de dependencias (tras la Fase 5, sin cambios desde la Fase 3):

* `requirements.txt`: `fastapi==0.141.1`, `uvicorn==0.54.0`, `pydantic==2.13.5`, `python-dotenv==1.2.3`, `httpx2==2.13.1`.
* `requirements-dev.txt`: `-r requirements.txt`, `pytest==9.1.1`.

## Configuración prevista

Variables en `.env` (se documentarán en `.env.example` sin valores):

* `GROQ_API_KEY`: obligatoria solo para el agente.
* `GROQ_MODEL`: modelo de Groq; se elegirá en la fase de integración con Groq verificando qué modelos con soporte de herramientas están disponibles.
  * Actualización (Fase 5): no se creó esta variable. El modelo es la constante `MODEL` de `llm.py` (`openai/gpt-oss-120b`).
* Otras variables (URL de la API, rutas de los CSV, límite de pasos del agente) se definirán cuando se implementen.
  * Actualización (Fase 6): se añadió `INVENTORY_API_URL` (por defecto `http://127.0.0.1:8000`). El límite de pasos es la constante `MAX_STEPS = 8` de `agent.py` y la ruta del log, la constante `LOG_PATH`; no son variables de entorno.

## Control de versiones

El proyecto utiliza Git y está conectado a GitHub.

Los cambios deberán realizarse de forma controlada y por fases.

No se realizarán commits ni pushes automáticamente sin aprobación.

## Compatibilidad con el repositorio existente

El repositorio procede originalmente de una plantilla de 4Geeks.

Existen archivos heredados como `server.py`, `learn.json` y un README inicial que deberán analizarse antes de decidir si continúan formando parte del proyecto.

No se deben eliminar archivos heredados durante la fase inicial sin analizar previamente su función y justificar el cambio.

Decisiones tomadas en Fase 0:

* `server.py`: servidor Flask de la plantilla para servir HTML estático; no forma parte de la arquitectura. Se revisará en la fase final de limpieza. No eliminar antes.
* `main.py`: `print("Hello World")` de la plantilla. Se revisará en la fase final de limpieza. No eliminar antes.
* `learn.json`: metadatos de la plataforma 4Geeks. Se conserva por si la plataforma lo necesita.
* `README.es.md`: eliminado intencionadamente. El proyecto tendrá un único `README.md` como documentación principal.

Decisiones tomadas en la Fase 8 (limpieza final):

* `server.py` y `main.py` se eliminan. Se comprobó que ningún código, test, configuración ni documentación actual los usa: solo los mencionaban el README de la plantilla y este documento. Siguen disponibles en el historial de Git.
* `learn.json` se conserva, según la decisión de la Fase 0.
* `README.md` se reescribe con la documentación del proyecto real.

## Principio de evolución

Este documento describe el contexto técnico inicial.

Las decisiones técnicas podrán evolucionar durante el desarrollo cuando exista una razón justificada.

Cuando se tome una decisión arquitectónica relevante, deberá quedar documentada y explicada antes de aplicarse.
