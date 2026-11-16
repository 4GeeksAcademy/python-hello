# Python Hello

El boilerplate más básico para comenzar un proyecto en Python en 4Geeks. Inicia tu primer proyecto en Python desde cero.

[![Abrir en GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/4GeeksAcademy/python-hello)

## Primeros pasos

### Opción 1: Codespaces o Dev Container (recomendado)

Abre este repositorio en GitHub Codespaces (o en VS Code con la extensión Dev Containers). Todo se instala automáticamente:

- Python 3.12
- [uv](https://docs.astral.sh/uv/), el gestor de paquetes y proyectos
- La extensión 4Geeks Student y las extensiones de Python para VS Code

### Opción 2: Configuración local

Asegúrate de tener Python 3.12 o superior instalado. Te recomendamos [instalar uv](https://docs.astral.sh/uv/getting-started/installation/), que también puede instalar Python por ti. Luego ejecuta:

```bash
$ uv sync
```

## ¿Qué hacer a continuación?

Abre el archivo `main.py` y comienza a escribir tu código.

Ejecuta tu código escribiendo el siguiente comando en tu terminal:

```bash
$ uv run main.py
```

Puedes crear e incluir tantos archivos de Python (también conocidos como módulos) como desees utilizando declaraciones `import`.

### Instalar paquetes

```bash
$ uv add requests
```

Esto agrega el paquete a `pyproject.toml` y `uv.lock`, para que cualquiera que clone tu proyecto obtenga las mismas versiones con `uv sync`.

## Alternativa: usando pip

Si prefieres no usar uv, puedes trabajar con las herramientas estándar `venv` y `pip`:

```bash
$ python3 -m venv .venv
$ source .venv/bin/activate      # En Windows: .venv\Scripts\activate
$ python3 main.py
```

Para instalar un paquete ejecuta `pip install requests`, y recuerda agregarlo a la lista `dependencies` en `pyproject.toml` para que tu proyecto lo registre.

### Contribuidores

Esta plantilla fue creada como parte de los [Recursos de Python de 4Geeks](https://4geeks.com/es/technology/python) para el aprendizaje en [4Geeks.com](https://4geeks.com) por [Alejandro Sanchez](https://twitter.com/alesanchezr) y [muchos otros contribuyentes](https://github.com/4GeeksAcademy/python-hello/graphs/contributors).
