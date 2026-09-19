"""Pruebas del paquete arxmapper, exports y puntos de entrada."""

from __future__ import annotations

import runpy
import subprocess
import sys
from unittest.mock import patch
import pytest

import arxmapper
from arxmapper import AIEngine, RECOMMENDED_MODELS, RepoScanner, __version__


class TestPackageMetadata:
    """Pruebas de metadatos y exportaciones de la biblioteca."""

    def test_version_defined(self):
        assert isinstance(__version__, str)
        assert len(__version__.split(".")) >= 3

    def test_all_exports(self):
        assert "AIEngine" in arxmapper.__all__
        assert "RECOMMENDED_MODELS" in arxmapper.__all__
        assert "RepoScanner" in arxmapper.__all__
        assert "__version__" in arxmapper.__all__
        assert arxmapper.AIEngine is AIEngine
        assert arxmapper.RepoScanner is RepoScanner

    def test_recommended_models_structure(self):
        assert len(RECOMMENDED_MODELS) > 0
        for item in RECOMMENDED_MODELS:
            assert len(item) == 3
            name, size, desc = item
            assert ":" in name
            assert "B" in size
            assert len(desc) > 10


class TestMainModuleExecution:
    """Pruebas de ejecución mediante python -m arxmapper."""

    def test_main_module_runs_main(self):
        with patch("arxmapper.app.main") as mock_main:
            # Ejecutar __main__.py como si fuera `python -m arxmapper`
            runpy.run_module("arxmapper", run_name="__main__")
            mock_main.assert_called_once()
