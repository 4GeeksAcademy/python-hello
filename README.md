# Python Hello

The most basic boilerplate to start a Python project at 4Geeks: start your very first Python project from scratch.

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/4GeeksAcademy/python-hello)

## Getting started

### Option 1: Codespaces or Dev Container (recommended)

Open this repository in GitHub Codespaces (or in VS Code with the Dev Containers extension). Everything is installed for you automatically:

- Python 3.15
- [uv](https://docs.astral.sh/uv/), the package and project manager
- The 4Geeks Student extension and the Python extensions for VS Code

### Option 2: Local setup

Make sure you have Python 3.15 or newer installed. We strongly recommend [installing uv](https://docs.astral.sh/uv/getting-started/installation/), which can also install Python for you. Then run:

```bash
$ uv sync
```

## What to do next?

Open the `main.py` file and start writing your code.

Execute your code by typing the following command on your terminal:

```bash
$ uv run main.py
```

You can create and include as many Python files (a.k.a. modules) as you want using `import` statements.

### Installing packages

```bash
$ uv add requests
```

This adds the package to `pyproject.toml` and `uv.lock`, so anyone who clones your project gets the same versions with `uv sync`.

## Alternative: using pip

If you prefer not to use uv, you can work with the standard `venv` and `pip` tools:

```bash
$ python3 -m venv .venv
$ source .venv/bin/activate      # On Windows: .venv\Scripts\activate
$ python3 main.py
```

To install a package, run `pip install requests`, and remember to add it to the `dependencies` list in `pyproject.toml` so your project keeps track of it.

### Contributors

This template was built as part of the [4Geeks Python Resources](https://4geeks.com/technology/python) for learning at [4Geeks.com](https://4geeks.com) by [Alejandro Sanchez](https://twitter.com/alesanchezr) and [many other contributors](https://github.com/4GeeksAcademy/python-hello/graphs/contributors).
