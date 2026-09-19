"""Fixtures compartidas para los tests de ArxMapper."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Generator
import pytest


@pytest.fixture
def sample_repo(tmp_path: Path) -> Path:
    """Crea una estructura de repositorio realista para pruebas."""
    repo = tmp_path / "mock_project"
    repo.mkdir()

    # Directorios de código fuente
    src = repo / "src"
    src.mkdir()
    core = src / "core"
    core.mkdir()
    api = src / "api"
    api.mkdir()

    # Componentes de código
    (core / "engine.py").write_text("class Engine:\n    pass\n", encoding="utf-8")
    (core / "utils.py").write_text("def helper():\n    return True\n", encoding="utf-8")
    (api / "routes.py").write_text("def get_routes():\n    return []\n", encoding="utf-8")

    # Manifiestos y configuraciones
    (core / "settings.json").write_text('{"debug": true}\n', encoding="utf-8")
    (repo / "pyproject.toml").write_text('[project]\nname = "mock"\n', encoding="utf-8")
    (repo / "Dockerfile").write_text("FROM python:3.11\n", encoding="utf-8")

    # Pruebas
    tests_dir = repo / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_engine.py").write_text("def test_engine(): pass\n", encoding="utf-8")
    (tests_dir / "api_test.py").write_text("def test_api(): pass\n", encoding="utf-8")

    # Documentación
    (repo / "README.md").write_text("# Mock Project\nDocumentación básica.\n", encoding="utf-8")
    docs_dir = repo / "docs"
    docs_dir.mkdir()
    (docs_dir / "architecture.md").write_text("# Arquitectura\nDetalles del diseño.\n", encoding="utf-8")

    # Base de datos
    (repo / "schema.sql").write_text("CREATE TABLE users (id INT);\n", encoding="utf-8")

    # Directorios que deben ser ignorados
    git_dir = repo / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text("[core]\n", encoding="utf-8")

    node_modules = repo / "node_modules"
    node_modules.mkdir()
    (node_modules / "dummy.js").write_text("console.log(1);", encoding="utf-8")

    venv_dir = repo / ".venv"
    venv_dir.mkdir()
    (venv_dir / "pyvenv.cfg").write_text("home = /usr/bin\n", encoding="utf-8")

    egg_dir = repo / "mock.egg-info"
    egg_dir.mkdir()
    (egg_dir / "PKG-INFO").write_text("Metadata-Version: 2.1\n", encoding="utf-8")

    # Archivos binarios
    (repo / "binary.exe").write_bytes(b"\x4d\x5a\x90\x00\x03")
    (repo / "corrupt.bin").write_bytes(b"hello\x00world")

    return repo
