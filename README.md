# Bucle básico de agente de inventario con IA

Carla gestiona un pequeño negocio familiar de suministros para cafeterías. Este proyecto le permite consultar y modificar su inventario escribiendo en lenguaje natural desde la terminal, sin formularios ni hojas de cálculo:

```text
Tú: Acaban de llegar 30 unidades de leche de avena.
Tú: Vendimos 12 bolsas de arábica hoy.
Tú: ¿Qué productos están por agotarse?
```

Tiene dos partes:

1. **Una API REST (FastAPI)** que gestiona el inventario y lo guarda en un archivo CSV.
2. **Un agente de IA (`agent.py`)** que interpreta los mensajes con un modelo de lenguaje de **Groq** y opera sobre el inventario **solo a través de la API**, mediante herramientas.

No hay frontend: la interfaz es la terminal.

## Arquitectura

```text
Usuario (terminal)
   │
   ▼
agent.py ──────────────► LLMClient (inventory_app/llm.py) ──HTTP──► Groq
   │                        (openai/gpt-oss-120b)
   ├──► ConversationLogger ──► data/conversation_log.csv
   │
   ▼
tools.py ──► InventoryApiClient ──HTTP──► API FastAPI (inventory_app/api.py)
                                               │
                                               ▼
                                        InventoryService (service.py)
                                               │
                                               ▼
                                   CsvInventoryRepository (repository.py)
                                               │
                                               ▼
                                        data/inventory.csv
```

- **El agente nunca lee ni escribe el CSV del inventario.** Todas las operaciones pasan por la API.
- **No se usa ningún framework de agentes ni SDK de LLM.** El bucle está escrito a mano en `agent.py` y Groq se llama por HTTP directo con `httpx2`.

## La API

Los productos tienen `name`, `quantity`, `unit` y `min_stock`. Un producto está **por agotarse** (`low_stock: true`) cuando `quantity <= min_stock`.

| Método y ruta | Qué hace | Respuesta |
|---|---|---|
| `GET /health` | Comprueba que la API está en marcha | `200 {"status": "ok"}` |
| `GET /products` | Lista todos los productos | `200` |
| `GET /products/low-stock` | Lista los productos por agotarse (alertas de stock bajo) | `200` |
| `GET /products/{name}` | Devuelve un producto | `200` o `404` |
| `POST /products` | Registra un producto: `{"name", "quantity", "unit", "min_stock"}` | `201`, `409` si ya existe, `422` si los datos no son válidos |
| `POST /products/{name}/stock` | Entrada o salida de stock: `{"change": 30}` suma y `{"change": -12}` resta | `200`, `404`, `409` si el stock quedaría negativo, `422` |

- **Nombres:** no distinguen mayúsculas ni minúsculas, los acentos sí cuentan, no pueden contener `/` ni espacios dobles, y `low-stock` está reservado.
- **Errores:** siempre tienen la forma `{"code", "message", "details"}`. Los errores internos (500) no muestran rutas del sistema.
- **Documentación interactiva:** con la API en marcha, en `http://127.0.0.1:8000/docs`.

## Persistencia

- **Inventario:** se guarda en **`data/inventory.csv`**, con las columnas `name,quantity,unit,min_stock`.
  - Los cambios sobreviven a los reinicios de la API.
  - La escritura es atómica: se escribe un archivo temporal y después se sustituye el original.
  - La ruta se puede cambiar con la variable `INVENTORY_CSV_PATH` (ver configuración).
- **Inventario inicial:** 8 productos. Leche de avena, Tapas para vasos 12 oz y Jarabe de vainilla empiezan por agotarse.

## El agente

`python agent.py` abre una conversación en la terminal. Para terminar, escribe `salir` o pulsa Ctrl+C.

### Herramientas

El modelo recibe estas herramientas, con descripción y parámetros tipados en JSON Schema. Cada una llama a un endpoint de la API:

| Herramienta | Parámetros | Endpoint |
|---|---|---|
| `list_products` | — | `GET /products` |
| `get_low_stock` | — | `GET /products/low-stock` |
| `add_stock` | `name`, `quantity` (entero positivo) | `POST /products/{name}/stock` con `change` positivo |
| `remove_stock` | `name`, `quantity` (entero positivo) | `POST /products/{name}/stock` con `change` negativo |
| `create_product` | `name`, `quantity`, `unit`, `min_stock` | `POST /products` |

- **Signo de las cantidades:** el modelo nunca decide el signo. `add_stock` y `remove_stock` reciben siempre una cantidad positiva.
- **Validación:** el agente valida el nombre de la herramienta y los argumentos exactos antes de ejecutarla.
- **Productos inexistentes:** no se crean automáticamente. El agente pregunta primero a Carla.

### Bucle: observar → pensar → actuar → actualizar → repetir

Por cada mensaje, `handle_message()` en `agent.py`:

1. **Observar:** añade el mensaje del usuario al historial y lo registra.
2. **Pensar:** envía el historial y las herramientas al modelo.
3. **Actuar:** si el modelo pide herramientas, el agente las ejecuta en orden a través de la API.
4. **Actualizar:** añade al historial la respuesta del modelo y el resultado de cada herramienta (mensajes `role="tool"`). Los errores, por ejemplo por stock insuficiente, también se devuelven al modelo para que se los explique a Carla.
5. **Repetir:** vuelve a consultar al modelo hasta que responde sin pedir herramientas.

Tres límites de seguridad:
- **Límite de pasos:** como máximo 8 llamadas al modelo por mensaje (`MAX_STEPS`).
- **Memoria de la sesión:** el historial completo se mantiene en memoria durante toda la sesión, así que se puede hacer referencia a mensajes anteriores.
- **Errores de Groq:** si Groq falla, el agente muestra un mensaje claro y la sesión continúa.

### Registro de conversaciones

Cada evento se añade a **`data/conversation_log.csv`**, que se crea con el primer mensaje:

```text
actor,message,tool_call,timestamp
```

| `actor` | `message` | `tool_call` |
|---|---|---|
| `user` | Lo que escribe el usuario | vacío |
| `tool` | Resultado de la herramienta en JSON (`{"result": ...}` o `{"error": ...}`) | `{"name": ..., "arguments": {...}}` en JSON |
| `agent` | Respuesta que ve el usuario | vacío |

- **Formato:** `timestamp` sigue ISO 8601 con zona horaria.
- **Solo añade (append-only):** nunca se sobrescriben los registros anteriores, tampoco entre sesiones distintas.

## Estructura

```text
agent.py                       Agente: bucle, herramientas para el modelo y CLI
inventory_app/
  api.py                       API FastAPI (endpoints y errores)
  service.py                   Reglas de negocio del inventario
  repository.py                Lectura y escritura del CSV
  models.py                    Modelos Pydantic y reglas de los nombres
  errors.py                    Excepciones del inventario
  api_client.py                Cliente HTTP de la API (lo usa el agente)
  tools.py                     Herramientas del agente
  llm.py                       Cliente HTTP de Groq (LLMClient)
  conversation_log.py          Registro append-only de conversaciones
  config.py                    Configuración desde el entorno y .env
data/
  inventory.csv                Inventario
  conversation_log.csv         Registro de conversaciones (se crea al usar el agente)
tests/                         Tests (pytest)
memory-bank/                   Contexto y decisiones del proyecto
requirements.txt               Dependencias de ejecución
requirements-dev.txt           Dependencias de desarrollo (añade pytest)
.env.example                   Plantilla de configuración, sin secretos
```

## Requisitos

- Python 3.13 o superior (probado con 3.14.6).
- Una clave de API de Groq para usar el agente. La API y los tests normales no la necesitan.

## Instalación

```bash
python -m venv .venv
```

Activa el entorno:
- Windows (PowerShell): `.venv\Scripts\Activate.ps1`
- Linux y macOS: `source .venv/bin/activate`

Después instala las dependencias:

```bash
pip install -r requirements-dev.txt
```

## Configuración

Copia `.env.example` como `.env` y rellena la clave. `.env` está en `.gitignore` y nunca se sube al repositorio.

| Variable | Obligatoria | Por defecto | Uso |
|---|---|---|---|
| `GROQ_API_KEY` | Sí, para el agente | — | Clave de la API de Groq |
| `INVENTORY_CSV_PATH` | No | `data/inventory.csv` | CSV del inventario. Una ruta relativa se resuelve desde la raíz del proyecto |
| `INVENTORY_API_URL` | No | `http://127.0.0.1:8000` | Dirección de la API que usa el agente |

## Uso

Necesitas dos terminales, las dos con el entorno virtual activado.

**Terminal 1: arrancar la API**

```bash
uvicorn inventory_app.api:app
```

**Terminal 2: arrancar el agente**

```bash
python agent.py
```

```text
Carla: ¡Hola! ¿En qué puedo ayudarte? (escribe "salir" para terminar)
Tú: ¿Qué productos están por agotarse?
Carla: ...
```

Si la API no está en marcha, el agente lo explica en su respuesta en lugar de fallar.

## Tests

```bash
pytest
```

- **Qué cubren:** el repositorio CSV, el servicio, la API, el cliente HTTP, las herramientas, el registro, el cliente de Groq y el agente completo, incluida una prueba de extremo a extremo con la API servida por Uvicorn.
- **Groq falso:** los tests normales usan un modelo falso. No necesitan clave, no se conectan a Groq y no modifican `data/inventory.csv`.

**Pruebas reales con Groq (opcionales).** `tests/test_live_groq.py` contiene pruebas que llaman al modelo real y consumen tokens. Se omiten salvo que se activen de forma explícita.

PowerShell:

```powershell
$env:GROQ_LIVE = "1"; pytest tests/test_live_groq.py
```

Linux y macOS:

```bash
GROQ_LIVE=1 pytest tests/test_live_groq.py
```

Si se ejecutan muchas seguidas, Groq puede responder `HTTP 429` (límite por minuto). En ese caso, repite la prueba afectada pasado un minuto.
