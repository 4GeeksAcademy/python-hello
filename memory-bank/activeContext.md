# Contexto activo

## Trabajo actual

Fase 8 (limpieza final + README + revisión): **terminada y lista para commit**. Hecho: auditoría contra los criterios de evaluación, pruebas de los criterios 8 y 9, README reescrito, archivos de la plantilla eliminados, Memory Bank actualizado, **prueba manual real con Groq completada** (3 escenarios correctos y datos restaurados) y **auditoría final realizada** (resultado en `progress.md`). Pendiente: commit y push.

## Estado de las fases

* Fase 0 y Fase 1: completadas, commit `d465645`.
* Fase 2 (API FastAPI): completada, commit `29d4357`.
* Fase 3 (cliente HTTP + herramientas): completada, commit `00cbe7d`.
* Fase 4 (registro de conversaciones): completada, commit `1859428`.
* Fase 5 (integración con Groq): completada, commit `35b4076`.
* Fase 6 (bucle del agente + CLI): completada, commit `ee3a918`.
* Fase 7 (E2E + pruebas reales): completada, commit `be4ac17`.
* Fase 8 (limpieza final + README + revisión): terminada y lista para commit.
* `data/conversation_log.csv` todavía no existe: se creará con el primer mensaje en una sesión real de `python agent.py`.

Rama de trabajo: `fase-1-base-persistencia`, sincronizada con GitHub (`origin`) hasta la Fase 7 (`be4ac17`). `main` sigue en el commit de la plantilla (`142f2a9`).

## Hecho recientemente (Fase 8, sin commit)

* Auditoría contra los 10 criterios de evaluación. Los criterios 8 (append-only entre sesiones) y 9 (interacción de varios pasos) tienen ahora pruebas deterministas en `tests/test_agent.py`. Suite normal: **223 passed, 7 skipped**.
* `README.md` reescrito con la documentación del proyecto real.
* `server.py` y `main.py` (plantilla, sin uso) eliminados.
* El archivo de persistencia sigue siendo `data/inventory.csv` (no se renombra a `products.csv`); el README lo explica junto con `INVENTORY_CSV_PATH`.
* Auditoría final: 8 criterios CUBIERTOS (3–10), 1 PARCIAL (criterio 2) y 1 NO VERIFICABLE (criterio 1). Las dos excepciones son limitaciones de verificación o de coincidencia literal, no fallos confirmados; están documentadas en `progress.md`:
  * criterio 1: no se pueden comprobar las rutas y métodos literales sin el enunciado original;
  * criterio 2: se usa `data/inventory.csv` y no `products.csv`, y no hay un test de reinicio literal del proceso servidor.

## Hecho en la Fase 7

* Solo tests; sin cambios en el código de producción ni dependencias nuevas.
* `tests/test_agent.py`: F6, la CLI completa con `FakeLLM` contra la API servida por Uvicorn en un hilo (HTTP real) sobre una copia del inventario, con el CSV y el log comprobados en disco.
* `tests/test_live_groq.py`: F1–F5 con Groq real sobre una copia del inventario inicial real (entrada, venta con nombre aproximado, stock bajo, producto inexistente y stock insuficiente). Comprueban efectos, no el texto exacto.
* Suite normal: **221 passed, 7 skipped**. Pruebas reales: las 7 pasan. F5 tuvo que repetirse a mano por un límite `HTTP 429` de Groq al lanzar las 7 seguidas.

## Entorno

`.venv` con **Python 3.14.6** (en el ordenador actual). Dependencias instaladas desde `requirements-dev.txt`.

Para usar el agente:

1. En una terminal: `uvicorn inventory_app.api:app`.
2. En otra terminal: `python agent.py` (requiere `GROQ_API_KEY` en `.env`).

## Hecho recientemente (Fase 6)

* `agent.py` con `run_tool`, `handle_message` (el bucle) y `main` (CLI), sin clases.
* Quinta herramienta `create_product`: `InventoryApiClient.create_product()` y `tools.create_product()`.
* `INVENTORY_API_URL` en `config.py` (por defecto `http://127.0.0.1:8000`) y en `.env.example`.
* `tests/test_agent.py` (19 tests). Tests nuevos de `create_product` en el cliente y las herramientas. Test real opt-in del agente completo.
* Suite normal: **220 passed, 3 skipped** con `pytest` y con `python -m pytest`. Pruebas reales ejecutadas explícitamente: 3 passed.

## Decisiones tomadas durante la Fase 6 (aprobadas por el usuario)

* Se añade `create_product` como quinta herramienta, porque registrar productos es un requisito funcional. El contrato de la API no cambia.
* `validation_error` pasa a dar `InventoryError` con los motivos de la API, en lugar de `InvalidStockChange`: con `create_product`, un dato inválido no es un cambio de stock.
* `INVENTORY_API_URL` en `config.py`, con valor por defecto.
* El agente es el orquestador. El modelo solo pide herramientas, y `run_tool` valida el nombre y los argumentos exactos antes de ejecutar:
  * Rechaza con `InvalidArguments` los argumentos que faltan o que sobran, y también `{"": {}}`.
  * Rechaza con `UnknownTool` las herramientas que no existen.
  * Devuelve los errores como resultado para el modelo, y la cantidad se pasa tal cual (el agente no cambia el signo).
* Bucle secuencial con un único historial `list[dict]` por sesión. Se conserva `tool_call_id` y los resultados se envían como mensajes `role="tool"`.
* Termina con la respuesta final del modelo, o en `MAX_STEPS = 8` con un mensaje claro.
* Registro:
  * `user`: el texto del usuario.
  * `tool`: el resultado en JSON y `tool_call` con el nombre y los argumentos en JSON.
  * `agent`: el texto que ve el usuario.
* `LLMError`: mensaje seguro, registrado como `agent`; la sesión continúa.
* Si el log no se puede escribir, la sesión termina de forma controlada con un mensaje claro.
* `SYSTEM_PROMPT` dentro de `agent.py`; no se crea `prompts.py`.
* Detalle completo en `techContext.md`.

## Cuestiones abiertas

* La prueba manual se hizo sobre los archivos reales y después se restauraron: el repositorio no incluye un `data/conversation_log.csv` de ejemplo. Se crea con la primera sesión real del agente.
* Cómo integrar el trabajo en `main` (pull request o merge): se decidirá después del commit de la Fase 8.
* La CLI etiqueta al asistente como "Carla:" y al usuario como "Tú:", según el ejemplo del usuario. En el resto del proyecto, Carla es la usuaria.

## Siguiente paso

Commit y push de la Fase 8 cuando el usuario lo indique. Después, decidir la integración de la rama `fase-1-base-persistencia` con `main`.
