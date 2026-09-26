# Contexto de producto

## Para quién es

Carla gestiona un pequeño negocio familiar de suministros para cafeterías. Necesita consultar y modificar el inventario escribiendo mensajes en lenguaje natural desde una terminal, sin formularios y sin editar una hoja de cálculo.

## Qué puede hacer el usuario

A través del agente, Carla puede:

* Consultar el inventario completo o un producto concreto.
* Registrar entradas de mercancía ("Acaban de llegar 30 unidades de leche de avena").
* Registrar salidas o ventas ("Vendimos 12 bolsas de arábica hoy").
* Consultar qué productos están por agotarse ("¿Qué productos están por agotarse?").
* Registrar productos nuevos, indicando nombre, cantidad inicial, unidad y stock mínimo.

## Representación de un producto

* **Nombre**: identifica al producto. "Leche de avena" y "leche de avena" son el mismo producto; los acentos sí cuentan ("Cafe" y "Café" son distintos). Tiene de 1 a 100 caracteres (sin contar los espacios exteriores, que se eliminan), no puede contener espacios dobles ni `/`, y `low-stock` es un nombre reservado.
* **Cantidad**: número entero, nunca negativo.
* **Unidad**: cómo se cuenta el producto (unidades, bolsas, kg…).
* **Stock mínimo**: umbral propio de cada producto.

Un producto está **por agotarse** cuando su cantidad es menor o igual que su stock mínimo.

## Reglas funcionales

* El stock nunca puede quedar en negativo: una salida mayor que la cantidad disponible se rechaza.
* No puede haber dos productos con el mismo nombre (sin distinguir mayúsculas/minúsculas).
* Los cambios en el inventario se conservan entre ejecuciones (persistencia en CSV).
* Si Carla menciona un producto que no existe, el agente **no lo crea automáticamente**: le informa y le pregunta si desea registrarlo y con qué datos.

## Comportamiento esperado del agente

* Interpreta la petición y decide qué herramientas usar; no depende de frases concretas.
* Opera sobre el inventario solo mediante herramientas que llaman a la API.
* Puede encadenar varias herramientas para completar una petición (por ejemplo, consultar el inventario para localizar el nombre exacto de un producto y después actualizar su stock).
* No inventa cantidades ni resultados: basa su respuesta en lo que devuelven las herramientas.
* Si una operación falla (producto inexistente, stock insuficiente, API no disponible), lo explica a Carla con claridad.
* Si la petición es ambigua, pregunta antes de modificar datos.
* Tiene un límite de pasos por mensaje; si lo alcanza, informa de que no ha podido completar la petición.
* Mantiene el historial de la conversación durante la sesión, de modo que Carla puede hacer referencia a mensajes anteriores.

## Registro de actividad

Cada conversación queda registrada en `data/conversation_log.csv`, sin sobrescribir registros anteriores: mensajes de Carla (`user`), respuestas del agente (`agent`) y herramientas ejecutadas (`tool`), con fecha y hora ISO 8601.

## Fuera de alcance

Ver `projectBrief.md`: sin frontend, sin base de datos SQL, sin autenticación y sin despliegue.
