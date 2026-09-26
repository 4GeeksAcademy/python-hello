# Progreso

## Fases

| Fase | Descripción | Dependencias nuevas | Estado |
|---|---|---|---|
| 0 | Análisis y arquitectura | — | **Completada y aprobada** |
| 1 | Base y persistencia | `python-dotenv`, `pytest` | **Completada** (commit `d465645`) |
| 2 | API FastAPI | `httpx2` (solo desarrollo, para `TestClient`) | **Completada** (commit `29d4357`) |
| 3 | Cliente HTTP de la API + herramientas | ninguna (`httpx2` pasa de desarrollo a ejecución) | **Completada** (commit `00cbe7d`) |
| 4 | Conversation log (se crea `data/conversation_log.csv`) | ninguna | **Completada** (commit `1859428`) |
| 5 | Integración con Groq (API HTTP directa con `httpx2`, sin SDK) | ninguna | **Completada** (commit `35b4076`) |
| 6 | Bucle del agente + CLI | ninguna | **Completada** (commit `ee3a918`) |
| 7 | E2E + pruebas reales con Groq | ninguna | **Completada** (commit `be4ac17`) |
| 8 | Limpieza final + README + revisión | ninguna | **Terminada; lista para commit** (auditoría final realizada) |

Orden de fases aprobado. Cada fase incluye sus propias pruebas y no se avanza a la siguiente sin indicación del usuario.

## Fase 1: resultado

Archivos creados:

* `requirements.txt`: `fastapi==0.141.1`, `uvicorn==0.54.0`, `pydantic==2.13.5`, `python-dotenv==1.2.3`.
* `requirements-dev.txt`: `-r requirements.txt` + `pytest==9.1.1`.
* `.env.example`: `GROQ_API_KEY=` vacío e `INVENTORY_CSV_PATH` comentado.
* `inventory_app/`: `__init__.py`, `config.py`, `models.py`, `errors.py`, `repository.py`, `service.py`.
* `data/inventory.csv`: inventario inicial.
* `tests/`: `conftest.py`, `test_repository.py`, `test_service.py`.

Archivo modificado: `.gitignore` (+ `.pytest_cache/`).

Contenido inicial de `data/inventory.csv`:

```text
name,quantity,unit,min_stock
Café arábica,40,bolsas,10
Café descafeinado,8,bolsas,5
Leche de avena,12,unidades,20
Leche entera,48,unidades,24
Vasos de cartón 12 oz,500,unidades,200
Tapas para vasos 12 oz,150,unidades,200
Jarabe de vainilla,4,botellas,4
Azúcar en sobres,1000,unidades,300
```

En stock bajo: Leche de avena (12 ≤ 20), Tapas para vasos 12 oz (150 ≤ 200) y Jarabe de vainilla (4 ≤ 4, caso límite).

## Pruebas realizadas (Fase 1)

Comando: `.venv/Scripts/python -m pytest -q` → **92 passed**.

* `test_repository.py` cubre: archivo inexistente, vacío o solo con cabecera; creación del archivo y del directorio; ida y vuelta; persistencia entre instancias; tipos; `low_stock` no almacenado; líneas en blanco; comas y comillas; CRLF; Unicode y UTF-8 sin BOM; UTF-8 con BOM; archivo no UTF-8; 6 cabeceras inválidas; 8 valores numéricos inválidos; 5 valores de texto inválidos; número de columnas; comilla sin cerrar; 3 variantes de duplicados; no se sobrescribe un archivo corrupto; no se escribe si la mutación falla; error de permisos en lectura; fallo en `os.replace`, en `fsync` y en la primera escritura (original intacto y sin temporales); escritura mediante temporal en el mismo directorio; 20 actualizaciones concurrentes serializadas.
* `test_service.py` cubre: listar (con datos y vacío); obtener; mayúsculas/minúsculas y espacios; los acentos no se ignoran; producto inexistente; alta y persistencia; alta sin archivo previo; limpieza de nombre y unidad; duplicados (sin modificar el CSV); 11 casos de validación del alta y sus límites; añadir y retirar stock; conservar el nombre almacenado, el orden y el resto de productos; retirar hasta cero; stock negativo rechazado sin persistir; ajuste de producto inexistente; 5 ajustes inválidos; propiedad `low_stock` y su límite; listado de stock bajo antes y después de ajustes.

Verificaciones adicionales:

* El hash SHA-256 de `data/inventory.csv` es el mismo antes y después de los tests; además lo comprueba la salvaguarda de `conftest.py`.
* `data/inventory.csv`: UTF-8 sin BOM, sin `\r`, cabecera exacta; se carga con el servicio y devuelve 8 productos y los 3 esperados en stock bajo.
* `get_settings()` resuelve la ruta por defecto, una ruta relativa y una absoluta.
* `pip check`: sin conflictos.
* Pruebas de mutación en una copia temporal (el proyecto no se modificó): cambiar `<=` por `<` → 3 tests fallan; quitar la escritura atómica → 4 tests fallan; quitar el control de stock negativo → 1 test falla.

La Fase 1 se validó de nuevo en otro ordenador, con un `.venv` nuevo con Python 3.14.6: 92 passed.

## Fase 2: resultado

Archivos creados:

* `inventory_app/api.py`: `create_app(service=None)` con los 6 endpoints y los manejadores de errores; `app = create_app()` para `uvicorn inventory_app.api:app`.
* `pytest.ini`: `pythonpath = .`.
* `tests/test_api.py`.

Archivos modificados:

* `inventory_app/models.py`: reglas del nombre (`/`, espacios dobles, `low-stock` reservado) y modelo `StockChange`.
* `requirements-dev.txt`: + `httpx2==2.13.1`.
* `tests/conftest.py`: fixture `client`.
* `tests/test_service.py`: tests de las reglas de nombre y de `StockChange`.
* `tests/test_repository.py`: una fila inválida nueva (nombre con `/`).

`requirements.txt` no cambia. `service.py`, `repository.py`, `config.py` y `errors.py` no cambian.

## Pruebas realizadas (Fase 2)

Comandos: `pytest` y `python -m pytest` → **137 passed** (92 de la Fase 1 + 45 nuevos: 27 en `test_api.py`, 17 del modelo en `test_service.py` y 1 en `test_repository.py`).

* `test_api.py` cubre:
  * Consultas: `/health`; listar; stock bajo (y que `low-stock` no se toma como producto); obtener; nombre codificado en la URL con acentos, espacios y otras mayúsculas; producto inexistente (404).
  * Alta: crear y persistir (201); duplicado (409, CSV intacto); nombre con `/`, espacios dobles o `low-stock` (422, CSV intacto); cantidad negativa o `"10"` (422); JSON mal formado (422).
  * Stock: entrada; salida; stock insuficiente (409, con `details` y CSV intacto); `change` igual a 0 (422, `invalid_stock_change`); `change` `"5"` o ausente (422, `validation_error`); producto inexistente (404).
  * Rutas: ruta inexistente e `/` codificada como `%2F` (404, `not_found`); método no permitido (405, cabecera `Allow`).
  * Almacenamiento: error 500 (`storage_error`) en lectura y escritura, sin rutas internas en la respuesta y con el detalle en el log.
  * Creación de la aplicación: `create_app()` usa `INVENTORY_CSV_PATH` y no lee el CSV hasta recibir una petición.
  * Todos los errores se comprueban con el formato `{code, message, details}`.
* Tests del modelo: nombres rechazados (`/`, espacios dobles, `low-stock` en varias mayúsculas); nombres parecidos válidos; reglas aplicadas tras quitar los espacios exteriores; `StockChange` acepta enteros (incluido 0) y rechaza `"5"`, `1.5`, `true` y `null`.

Verificaciones adicionales:

* El hash de `data/inventory.csv` es el mismo antes y después de los tests y el archivo no tiene cambios respecto al commit; además lo vigila la salvaguarda de `conftest.py`.
* El `data/inventory.csv` real sigue siendo válido con las nuevas reglas de nombre (8 productos).
* Uvicorn importa `inventory_app.api:app` (con `uvicorn.importer.import_from_string`) y la aplicación expone los 6 endpoints.
* No quedan referencias a `APIRouter`, `Depends`, `get_service` ni `app.state`.
* `pip check`: sin conflictos.

## Fase 3: resultado

Se implementó en dos partes (3A: cliente HTTP; 3B: herramientas), cada una revisada y aprobada por separado.

Archivos creados:

* `inventory_app/api_client.py`: `InventoryApiClient` con `list_products`, `get_low_stock`, `add_stock` y `remove_stock`.
* `inventory_app/tools.py`: las 4 herramientas (`list_products`, `get_low_stock`, `add_stock`, `remove_stock`), que delegan en `InventoryApiClient`.
* `tests/test_api_client.py` y `tests/test_tools.py`.

Archivos modificados:

* `requirements.txt`: + `httpx2==2.13.1` (pasa a ser dependencia de ejecución).
* `requirements-dev.txt`: se quita la línea de `httpx2` (lo recibe a través de `-r requirements.txt`).

No cambia ningún archivo de las Fases 1 y 2 (`api.py`, `service.py`, `repository.py`, `models.py`, `errors.py`, `config.py` ni sus tests).

## Pruebas realizadas (Fase 3)

Comandos: `pytest` y `python -m pytest` → **163 passed** (137 de las Fases 1 y 2 + 18 de `InventoryApiClient` + 8 de las herramientas).

* `test_api_client.py` (18):
  * Contra la API real con `TestClient`:
    * Listar productos y consultar stock bajo.
    * Añadir stock (cambio positivo) y retirar stock (cambio negativo), comprobando que se guarda.
    * Nombre con espacios, Unicode, `?`, `#`, `%` y otras mayúsculas.
    * Producto inexistente → `ProductNotFound`; stock insuficiente → `InsufficientStock` con sus datos.
    * Error de almacenamiento → `StorageError` sin rutas internas.
    * Ruta inexistente (nombre con `/`) → `InventoryError`, no `ProductNotFound`.
  * Sin petición: cantidades `0` y negativas rechazadas en `add_stock` y `remove_stock` (4 casos).
  * Con `httpx2.MockTransport`:
    * Traducción de `product_already_exists`, `invalid_stock_change` y `validation_error`.
    * Respuesta que no es de nuestra API (sin exponer su cuerpo).
    * Error de conexión → `InventoryError`.
* `test_tools.py` (8), con un cliente falso dentro del test:
  * Cada herramienta llama al método correcto con los mismos argumentos (en `remove_stock`, la cantidad positiva) y devuelve el resultado del cliente.
  * Cada herramienta deja pasar la excepción del cliente sin convertirla.

Verificaciones adicionales:

* `data/inventory.csv`: mismo hash antes y después de los tests y sin cambios respecto al commit de la Fase 2 (`29d4357`).
* Pruebas de mutación en memoria (el proyecto no se modificó):
  * No codificar `/`, `?`, `#` y `%` hace fallar el test del nombre Unicode.
  * Traducir todo 404 a `ProductNotFound` hace fallar el test de ruta inexistente.
* Revisión de imports:
  * `tools.py` solo importa `InventoryApiClient`.
  * `api_client.py` solo importa `urllib.parse.quote`, `httpx2` e `inventory_app.errors`.
  * Ninguno importa el servicio, el repositorio ni FastAPI, ni accede al CSV.
  * `tools.py` no tiene condicionales, bucles ni `try`, y no hay registro de herramientas.

## Fase 4: resultado

Archivos creados:

* `inventory_app/conversation_log.py`: `ConversationLogger(path)` con `log(actor, message, tool_call="")`.
* `tests/test_conversation_log.py`.

No cambia ningún archivo existente ni las dependencias. `data/conversation_log.csv` todavía no existe: se creará con el primer evento que registre el agente.

Tras la revisión del usuario se ajustó el diseño:

* Se quitó la regla que exigía `tool_call` en los eventos `tool`: el logger valida el formato del evento, no cómo lo usará el agente.
* Se añadió la validación de la cabecera de un archivo existente.
* El formato interno de `tool_call` y el manejo de errores de escritura quedan para el agente.

## Pruebas realizadas (Fase 4)

Comandos: `pytest` y `python -m pytest` → **181 passed** (163 de las Fases 1–3 + 18 del registro).

* `test_conversation_log.py` (18), sobre un archivo temporal:
  * El primer evento crea el archivo (y su directorio) con la cabecera exacta.
  * Registro de eventos `user`, `agent` y `tool`; el evento `tool` se registra con y sin `tool_call`.
  * Los eventos nuevos conservan los anteriores, también desde otra instancia del logger, y la cabecera aparece una sola vez.
  * Comas, comillas y saltos de línea se escapan y se leen igual.
  * UTF-8 (acentos, `ñ`, caracteres chinos, emoji) sin BOM.
  * Se rechazan actores inválidos (`system`, `User`, vacío) y valores que no son texto; en esos casos no se crea el archivo.
  * Un archivo existente cuya primera línea no es exactamente la cabecera se rechaza con `ValueError` y queda byte a byte igual. Casos probados: otro CSV, una columna menos, cabecera sin salto de línea y datos sin cabecera.
  * El timestamp es ISO 8601, tiene zona horaria y está entre la hora anterior y la posterior al registro.
* La propagación de `OSError` no tiene test propio (decisión del usuario): el logger no captura excepciones de escritura.

Verificaciones adicionales:

* `data/inventory.csv`: mismo hash antes y después de los tests.
* `data/conversation_log.csv` real: los tests no lo crean ni lo modifican. El logger exige una ruta explícita y los tests usan `tmp_path`.
* `conversation_log.py` solo importa `csv`, `datetime` y `pathlib`.

## Fase 5: resultado

Archivos creados:

* `inventory_app/llm.py`: `LLMClient(api_key, http=None)` con `complete(messages, tools=None)`, y `LLMError`.
* `tests/test_llm.py`: tests con respuestas simuladas.
* `tests/test_live_groq.py`: prueba real opcional, fuera de la suite normal.

Archivo modificado:

* `inventory_app/config.py`: `Settings.groq_api_key` (lee `GROQ_API_KEY`).

Sin dependencias nuevas: no se instalan `groq` ni `openai`. Se reutiliza `httpx2`.

## Pruebas realizadas (Fase 5)

Comandos: `pytest` y `python -m pytest` → **198 passed, 2 skipped** (181 de las Fases 1–4 + 17 de `LLMClient`; los 2 omitidos son los tests reales).

* `test_llm.py` (17), sin red:
  * Construcción: se rechaza una clave ausente o vacía. `get_settings()` lee `GROQ_API_KEY` y trata una clave en blanco como ausente.
  * Sin cliente inyectado se usaría la red real, que la fixture bloquea en los tests.
  * Petición: `POST` a la URL de Groq, `Authorization: Bearer <clave>` y cuerpo con `model`, `messages` y `tools`. `tools` no se envía si no se pasa.
  * Respuesta de texto y respuesta con dos tool calls (argumentos convertidos a `dict` y `message` listo para el historial).
  * Errores HTTP 401 (con código de Groq) y 500 (sin JSON), error de conexión y timeout: todos dan `LLMError` sin la clave, sin `Bearer` y sin el mensaje interno.
  * Respuestas inesperadas (5 casos: no es JSON, sin `choices`, `content` no textual, argumentos que no son JSON o que no son un objeto) dan `LLMError`.
* Prueba real (`GROQ_LIVE=1`, ejecutada explícitamente): **2 passed** con `openai/gpt-oss-120b`.
  * En la primera ejecución, el modelo pidió `get_low_stock` con argumentos `{"": {}}` en vez de `{}`. La aserción era demasiado estricta para el modelo; se cambió para comprobar solo que los argumentos llegan como `dict`, y el comportamiento queda anotado para la Fase 6.

Verificaciones adicionales:

* `data/inventory.csv` sin cambios; `data/conversation_log.csv` no se crea.
* `.env` está en `.gitignore` y no está versionado. Ningún archivo versionable contiene una clave `gsk_` real. `.env.example` solo tiene `GROQ_API_KEY=` vacío.
* `groq` y `openai` no están instalados. `llm.py` solo importa `json` y `httpx2`.

## Fase 6: resultado

Diseño revisado y aprobado por el usuario antes de implementar (decisiones en `techContext.md`).

Archivos creados:

* `agent.py`: bucle del agente (`handle_message`), ejecución y validación de herramientas (`run_tool`), system prompt, definiciones de las 5 herramientas y CLI (`main`).
* `tests/test_agent.py`.

Archivos modificados:

* `inventory_app/api_client.py`: `create_product()`; `validation_error` pasa a dar `InventoryError` con los motivos, en lugar de `InvalidStockChange`.
* `inventory_app/tools.py`: herramienta `create_product`.
* `inventory_app/config.py`: `Settings.inventory_api_url` (`INVENTORY_API_URL`, por defecto `http://127.0.0.1:8000`).
* `.env.example`: `INVENTORY_API_URL` documentada, comentada y sin secretos.
* `tests/test_api_client.py`: tests reales de `create_product` (alta, duplicado y datos inválidos). Sustituyen dos casos simulados que ahora se pueden probar contra la API.
* `tests/test_tools.py`: delegación y error de `create_product`.
* `tests/test_live_groq.py`: test real opt-in del agente completo.

Sin dependencias nuevas, sin frameworks de agentes y sin clases en `agent.py`.

## Pruebas realizadas (Fase 6)

Comandos: `pytest` y `python -m pytest` → **220 passed, 3 skipped** (198 anteriores + 22 nuevos: 19 del agente, +1 neto del cliente y +2 de las herramientas; los 3 omitidos son las pruebas reales).

* `test_agent.py` (19), con `FakeLLM` y la API real en `TestClient`:
  * Bucle y herramientas:
    * Respuesta directa: una sola llamada al modelo y fin del bucle.
    * El resultado de una herramienta vuelve al modelo con su `tool_call_id`.
    * Herramientas consecutivas (`list_products` → `add_stock` → respuesta final) con el CSV temporal actualizado.
    * `remove_stock` con cantidad positiva.
    * `create_product`.
  * Errores:
    * `InsufficientStock` llega al modelo y el stock no cambia.
    * 6 peticiones inválidas llegan al modelo como error y no cambian nada: herramienta desconocida, `{"": {}}`, argumento que falta, argumento que sobra, nombre que no es texto y cantidad negativa.
    * Producto ya existente.
  * Historial, registro y límites:
    * El historial se conserva entre turnos.
    * Filas del log `user` → `tool` (con `tool_call` en JSON y el mismo resultado que recibió el modelo) → `agent`.
    * Límite de 8 pasos: el evento se registra y el mensaje de límite no entra en el historial.
    * `LLMError`: respuesta segura y registrada; no se añade ningún `assistant` inventado al historial, y el siguiente turno continúa.
  * CLI y configuración:
    * La CLI termina con código 1 y un mensaje sin rutas internas si el log no se puede escribir, sin modificarlo.
    * `INVENTORY_API_URL` (valor por defecto y variable de entorno).
* Pruebas reales (`GROQ_LIVE=1`, ejecutadas explícitamente): **3 passed**. Incluyen el agente completo con `openai/gpt-oss-120b`: ante "¿Qué productos están por agotarse?" usa `get_low_stock` y su respuesta menciona la leche de avena.

Verificaciones adicionales:

* `data/inventory.csv` sin cambios; `data/conversation_log.csv` no se crea en los tests.
* `.env` sin versionar; ninguna clave real en archivos versionables.
* Dependencias sin cambios; ni `groq`, ni `openai`, ni frameworks de agentes instalados.

## Fase 7: resultado

Diseño revisado y aprobado por el usuario antes de implementar. No hay archivos nuevos, dependencias nuevas ni cambios en el código de producción.

Archivos modificados:

* `tests/test_agent.py`: fixture `http_api_server` (Uvicorn real en un hilo, puerto asignado por el sistema, sobre una copia de `data/inventory.csv`) y el test F6.
* `tests/test_live_groq.py`:
  * F1–F5 con el modelo real sobre una copia del inventario inicial real, con la API en `TestClient`.
  * Fixture `real_inventory` y funciones `run_turn` y `quantities`, que usan los 5 flujos.
  * Sustituye el test del agente con `sample_products` de la Fase 6, que ahora es F3.

Flujos cubiertos:

| # | Flujo | Tipo | Qué se comprueba |
|---|---|---|---|
| F1 | "Acaban de llegar 30 unidades de leche de avena." | Groq real | CSV en disco: Leche de avena +30 y el resto igual; `add_stock` con resultado |
| F2 | "Vendimos 12 bolsas de arábica hoy." | Groq real | CSV: Café arábica −12 y el resto igual; `remove_stock` con resultado. No se exige una secuencia de herramientas |
| F3 | "¿Qué productos están por agotarse?" | Groq real | La respuesta menciona avena, tapas y vainilla (inventario inicial real); se usó `get_low_stock` o `list_products`; CSV intacto |
| F4 | "Acaban de llegar 10 unidades de leche de almendras." | Groq real | No se llama a `create_product`; CSV intacto |
| F5 | "Vendimos 50 bolsas de café arábica." (hay 40) | Groq real | No se vende más de lo disponible y la decisión se basa en datos reales. Hay dos caminos válidos: el modelo consulta el stock (`list_products`) y se niega, o intenta `remove_stock` y recibe `InsufficientStock` de la API real. Es obligatorio que use al menos una de esas dos herramientas y que el CSV no cambie. En las ejecuciones observadas el modelo siempre consultó `list_products` y se negó, sin llamar a `remove_stock`. El camino técnico `remove_stock` → `InsufficientStock` → modelo lo cubre de forma determinista `test_agent.py::test_tool_error_is_sent_to_the_model` |
| F6 | CLI completa: `main()` → `INVENTORY_API_URL` → HTTP real → Uvicorn → CSV | `FakeLLM` | Salida de la CLI, resultado del servidor recibido por el modelo, CSV en disco (leído con un repositorio nuevo), filas del log `user` → `tool` → `agent` y una sola cabecera |

En las pruebas reales no se compara el texto de la respuesta. Solo se exige que sea una respuesta final real (no vacía, distinta de `LIMIT_REPLY` y sin error del modelo), salvo las palabras clave de F3.

## Pruebas realizadas (Fase 7)

* `pytest` y `python -m pytest` → **221 passed, 7 skipped** (220 anteriores + F6; los 7 omitidos son las pruebas reales).
* `GROQ_LIVE=1 pytest tests/test_live_groq.py` → **6 passed, 1 failed** en la primera ejecución:
  * F5 falló con `Groq rechazó la petición (HTTP 429, rate_limit_exceeded)`: las 7 pruebas se lanzaron seguidas y superaron el límite por minuto del plan de Groq. No es un fallo del agente, que gestionó el `LLMError` con un mensaje seguro y sin traceback.
  * Al repetir F5 a mano pasado un minuto: **1 passed**. No se añadieron reintentos al código.
* `data/inventory.csv`: mismo hash antes y después de todas las ejecuciones. `data/conversation_log.csv` no se crea.

## Fase 8 (terminada, lista para commit): criterios de evaluación

Se auditó el proyecto contra los 10 criterios de evaluación facilitados por el usuario. Los criterios 8 y 9 estaban solo parcialmente cubiertos y ahora tienen una prueba determinista cada uno, en `tests/test_agent.py`, con `FakeLLM`, sin Groq real y sin cambios en el código de producción:

* **Criterio 8 (registro append-only en varias sesiones):** `test_log_is_append_only_across_two_agent_sessions`.
  * Ejecuta `main()` dos veces sobre el mismo `conversation_log.csv` temporal. Cada ejecución crea su propio logger, historial y modelo, como dos arranques del programa.
  * Comprueba que el contenido de la primera sesión queda intacto byte a byte, que la segunda solo añade filas, que la cabecera aparece una sola vez, que las 4 filas quedan en orden y que la segunda sesión no recibe el historial de la primera.
  * Prueba de mutación: si el logger reescribiera el archivo, el test falla.
* **Criterio 9 (interacción de varios pasos):** `test_multi_step_create_product_then_ask_for_low_stock`.
  * Dos turnos de la misma sesión, con una única lista `messages` y la API real de la prueba (`TestClient` sobre el CSV temporal).
  * Turno 1: `create_product` registra "Leche de coco" con stock bajo (2 ≤ 5), y se comprueba en el CSV en disco.
  * Turno 2: `get_low_stock`. Se comprueba que la primera llamada al modelo de ese turno recibe el historial completo del turno 1 y que el resultado real de la API incluye el producto recién creado.

Suite normal tras añadirlas: **223 passed, 7 skipped**.

Documentación y limpieza (sin cambios en el código de producción, las dependencias ni los datos):

* `README.md` reescrito: sustituye al de la plantilla "Python Hello" por la documentación del proyecto (arquitectura, endpoints, persistencia en `data/inventory.csv` con `INVENTORY_CSV_PATH`, agente con Groq, bucle, registro append-only, estructura, instalación, `.env`, cómo arrancar la API y el agente y cómo ejecutar los tests, incluidos los opt-in).
* `server.py` y `main.py` eliminados: eran de la plantilla y no los usaba ningún código, test ni configuración.
* Memory Bank: la Fase 7 figura como cerrada en `be4ac17`.

Prueba manual real, completada correctamente:

* **Montaje:** una única sesión de `python agent.py` contra la API real (`uvicorn inventory_app.api:app`), Groq real (`openai/gpt-oss-120b`) y el `data/inventory.csv` real. Los mensajes se enviaron por la entrada estándar y el agente los leyó con el mismo `input()` de la CLI. No hubo errores de Groq.
* **Escenarios:**
  * **Entrada:** "Acaban de llegar 30 unidades de leche de avena". El modelo llamó a `list_products` (`GET /products`) y a `add_stock` con `{"name": "Leche de avena", "quantity": 30}` (`POST /products/Leche%20de%20avena/stock`). Leche de avena pasó de 12 a 42 en el CSV.
  * **Consulta en la misma sesión:** "¿Qué productos están por agotarse?". El modelo llamó a `get_low_stock` (`GET /products/low-stock`) y respondió con Tapas para vasos 12 oz y Jarabe de vainilla; la leche de avena ya no aparece, porque tiene 42 > 20.
  * **Producto inexistente:** "Acaban de llegar 10 unidades de un producto que no existe llamado Producto de prueba". El modelo no lo creó y pidió la unidad y el stock mínimo. No llamó a ninguna herramienta: usó la lista de productos del turno 1, que estaba en el historial.
* **`data/conversation_log.csv`:**
  * 9 filas (`user`/`tool`/`agent`) con la cabecera exacta.
  * `tool_call` en JSON válido en las 3 filas `tool` y timestamps ISO 8601 con zona horaria.
  * Sin la API key, `gsk_` ni `Bearer`.
  * La primera fila empezaba con un BOM (`\ufeff`) que añadió PowerShell al enviar el texto por la entrada estándar. No es del programa.
* **Restauración:** `data/inventory.csv` se restauró desde una copia y quedó byte a byte igual al estado versionado. `data/conversation_log.csv` se eliminó, porque no existía antes. La prueba no dejó cambios en los datos entregables.
* **Suite después de la prueba:** **223 passed, 7 skipped**.

Auditoría final contra los 10 criterios de evaluación, **realizada**. No se encontró ninguna modificación de producción justificada:

| Estado | Criterios |
|---|---|
| CUBIERTO | 3, 4, 5, 6, 7, 8, 9 y 10 (**8 criterios**) |
| PARCIAL | 2 |
| NO VERIFICABLE | 1 |

Las dos excepciones son limitaciones de verificación o de coincidencia literal con el texto del criterio disponible, no fallos de implementación confirmados:

1. **Criterio 1 (los cuatro endpoints requeridos):** las operaciones del brief tienen su endpoint funcional (`GET /products`, `POST /products`, `POST /products/{name}/stock` y `GET /products/low-stock`, más `GET /health` y `GET /products/{name}`), probado en `tests/test_api.py`. Sin el enunciado original completo no se puede comprobar si coinciden literalmente con las cuatro rutas y métodos que espera el evaluador.
2. **Criterio 2 (persistencia en `products.csv` que sobrevive a un reinicio):**
   * El proyecto usa `data/inventory.csv`, configurable con `INVENTORY_CSV_PATH`, mientras que el criterio menciona `products.csv`. Se mantiene el nombre por decisión del usuario: no hay enunciado que confirme que ese nombre sea obligatorio. El README explica el nombre actual.
   * La persistencia está demostrada con instancias nuevas del repositorio y del servicio sobre el mismo archivo, F6 con Uvicorn y la prueba manual. No existe un test que detenga y vuelva a arrancar literalmente el proceso del servidor.

Pendiente después del commit de la Fase 8: decidir cómo integrar el trabajo en `main`, que sigue en el commit de la plantilla (pull request o merge).

## Problemas conocidos

* `data/inventory.csv` se escribe con fin de línea `\n`. Con `core.autocrlf=true`, Git puede avisar de la conversión a CRLF; la lectura acepta ambos formatos.
* `openai/gpt-oss-120b` puede enviar argumentos inesperados (por ejemplo `{"": {}}` para una herramienta sin parámetros).
  * En la Fase 6, `run_tool` los rechaza con `InvalidArguments` y el system prompt indica que las herramientas sin parámetros se llaman con `{}`.
  * Si el modelo insistiera, el bucle acabaría en `MAX_STEPS`. Las pruebas reales del agente de la Fase 7 (F1–F5) terminaron con una respuesta final, sin llegar al límite.
* Las pruebas reales pueden fallar por el límite por minuto de Groq (`HTTP 429, rate_limit_exceeded`) si se ejecutan muchas seguidas. Conviene repetir la que falle pasado un minuto. No se reintenta automáticamente.
* Para usar el agente, la API debe estar arrancada en otra terminal (`uvicorn inventory_app.api:app`). Si no lo está, las herramientas devuelven "No se puede conectar con la API de inventario" y el modelo se lo explica al usuario.
* `LLMClient` crea un `httpx2.Client` que no se cierra explícitamente. Para una sesión de terminal no es un problema.
* La URL base de la API se configura desde la Fase 6 con `INVENTORY_API_URL` (entorno o `.env`), con valor por defecto `http://127.0.0.1:8000`. Debe coincidir con la dirección en la que se arranca Uvicorn.
* Si un CSV editado a mano contiene un nombre que incumple las nuevas reglas (por ejemplo, con `/`), la carga falla con `StorageError` (500 en la API). Es intencionado: se prefiere un error explícito a un producto al que no se puede acceder.
* `data/conversation_log.csv` se versionará y el agente le añadirá filas en cada ejecución, así que cada sesión real generará cambios en Git. Es una consecuencia aceptada.
