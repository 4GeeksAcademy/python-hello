# Project Brief

## Nombre del proyecto

Bucle Básico de Agente de Inventario con IA

## Objetivo

Construir una primera versión funcional y mantenible de un sistema de gestión de inventario controlado mediante lenguaje natural.

El sistema estará pensado para que Carla, responsable de un pequeño negocio familiar de suministros para cafeterías, pueda consultar y modificar el inventario mediante mensajes escritos de forma natural, sin tener que utilizar formularios o editar directamente una hoja de cálculo.

El sistema estará compuesto por:

1. Una API REST desarrollada con FastAPI para gestionar el inventario.
2. Persistencia de los datos mediante archivos CSV.
3. Un agente de IA desarrollado en Python.
4. Integración con un modelo de lenguaje mediante Groq.
5. Un sistema de herramientas que permita al agente utilizar las operaciones de la API.
6. Un bucle de agente capaz de interpretar una petición, decidir qué herramienta utilizar, ejecutarla, analizar el resultado y continuar hasta generar una respuesta final.
7. Un registro de las conversaciones y acciones realizadas por el agente mediante `conversation_log.csv`.

## Alcance funcional

La API debe permitir como mínimo:

* Consultar los productos existentes.
* Registrar nuevos productos.
* Actualizar las cantidades de productos.
* Detectar productos con stock bajo.
* Persistir la información del inventario en CSV.

El agente debe poder recibir peticiones en lenguaje natural como:

* "Acaban de llegar 30 unidades de leche de avena."
* "Vendimos 12 bolsas de arábica hoy."
* "¿Qué productos están por agotarse?"

El agente deberá interpretar estas peticiones y utilizar las herramientas disponibles para realizar las operaciones necesarias.

## Flujo general

El flujo principal será:

1. Carla escribe una petición.
2. El agente recibe el mensaje.
3. El mensaje se incorpora al historial de conversación.
4. El agente envía el contexto al modelo de lenguaje.
5. El modelo determina si necesita utilizar una herramienta.
6. El agente ejecuta la herramienta correspondiente mediante la API.
7. El resultado de la herramienta se incorpora al contexto.
8. El agente vuelve a consultar al modelo si todavía necesita realizar alguna acción.
9. El proceso continúa hasta obtener una respuesta final.
10. El agente responde a Carla.
11. Los pasos relevantes de la conversación se registran en `conversation_log.csv`.

El historial completo de la conversación debe mantenerse en memoria durante la sesión del agente.

## Persistencia

La información del inventario se almacenará en un archivo CSV.

El registro de conversaciones se almacenará en otro archivo CSV denominado:

`conversation_log.csv`

El registro deberá ser acumulativo y no sobrescribir las conversaciones anteriores.

## Registro de conversaciones

Cada registro de `conversation_log.csv` deberá contener:

* `actor`: `user`, `agent` o `tool`.
* `message`: mensaje o resultado producido.
* `tool_call`: nombre de la herramienta utilizada cuando corresponda.
* `timestamp`: fecha y hora en formato ISO 8601.

## Interfaz

La primera versión utilizará una interfaz de terminal.

No se desarrollará frontend web, React, HTML ni CSS en esta versión.

La presentación visual no forma parte del alcance funcional del proyecto.

## Principios del proyecto

* Mantener una arquitectura sencilla y mantenible.
* Evitar sobreingeniería.
* Separar claramente API, lógica del agente, herramientas y persistencia.
* No introducir dependencias innecesarias.
* Priorizar código legible y fácil de mantener.
* Validar cada fase mediante pruebas.
* No considerar una fase terminada únicamente porque el código funciona aparentemente; debe existir una validación adecuada.
* Mantener los secretos fuera del código y del repositorio.
* No modificar partes del proyecto que no sean necesarias para la funcionalidad que se está desarrollando.

## Fuera de alcance

No se desarrollará:

* Frontend web.
* Aplicación móvil.
* Base de datos SQL.
* Sistema de usuarios o autenticación.
* Despliegue en producción.
* Sistema avanzado de permisos.
* Panel administrativo.
* Integraciones externas distintas de Groq.
* Automatizaciones no relacionadas con el funcionamiento del agente.