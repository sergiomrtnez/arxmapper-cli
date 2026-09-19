"""Pruebas unitarias para arxmapper.ai_engine."""

from __future__ import annotations

import os
import platform
import subprocess
from unittest.mock import AsyncMock, MagicMock, patch
import urllib.error

import ollama
import pytest

from arxmapper.ai_engine import (
    DEFAULT_HOST,
    RECOMMENDED_MODELS,
    SYSTEM_PROMPT,
    AIEngine,
    install_ollama_windows,
    is_ollama_installed,
    is_service_running,
    list_local_models,
    normalize_ollama_host,
    pull_model_sync,
    start_service_background,
)


class TestNormalizeOllamaHost:
    """Pruebas de normalización de URLs para Ollama."""

    def test_empty_host_defaults_to_localhost(self, monkeypatch):
        monkeypatch.delenv("OLLAMA_HOST", raising=False)
        assert normalize_ollama_host("") == "http://127.0.0.1:11434"
        assert normalize_ollama_host("   ") == "http://127.0.0.1:11434"
        assert normalize_ollama_host(None) == "http://127.0.0.1:11434"

    def test_host_from_environment_variable(self, monkeypatch):
        monkeypatch.setenv("OLLAMA_HOST", "http://remote:11434")
        assert normalize_ollama_host(None) == "http://remote:11434"

    def test_colon_port_format(self):
        assert normalize_ollama_host(":11434") == "http://127.0.0.1:11434"
        assert normalize_ollama_host(":8080") == "http://127.0.0.1:8080"

    def test_zero_zero_zero_zero_mapped_to_127_0_0_1(self):
        assert normalize_ollama_host("0.0.0.0:11434") == "http://127.0.0.1:11434"
        assert normalize_ollama_host("http://0.0.0.0:11434") == "http://127.0.0.1:11434"

    def test_explicit_valid_hosts(self):
        assert normalize_ollama_host("localhost:11434") == "http://localhost:11434"
        assert normalize_ollama_host("http://192.168.1.100:11434") == "http://192.168.1.100:11434"
        assert normalize_ollama_host("https://ollama.internal.net:8443") == "https://ollama.internal.net:8443"


class TestIsOllamaInstalled:
    """Pruebas de detección del ejecutable de Ollama."""

    def test_detected_via_which(self):
        with patch("shutil.which", return_value="/usr/local/bin/ollama"):
            assert is_ollama_installed() is True

    def test_missing_on_non_windows(self):
        with patch("shutil.which", return_value=None), patch("platform.system", return_value="Linux"):
            assert is_ollama_installed() is False

    def test_windows_localappdata_exists(self, monkeypatch):
        with patch("shutil.which", return_value=None), \
             patch("platform.system", return_value="Windows"), \
             patch("os.path.exists", return_value=True):
            monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\test\AppData\Local")
            assert is_ollama_installed() is True

    def test_windows_localappdata_not_exists(self, monkeypatch):
        with patch("shutil.which", return_value=None), \
             patch("platform.system", return_value="Windows"), \
             patch("os.path.exists", return_value=False):
            monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\test\AppData\Local")
            assert is_ollama_installed() is False


class TestIsServiceRunning:
    """Pruebas de verificación de salud del servicio Ollama."""

    def test_service_running_returns_true_on_200(self):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__.return_value = mock_response

        with patch("urllib.request.urlopen", return_value=mock_response):
            assert is_service_running("http://127.0.0.1:11434") is True

    def test_service_running_returns_false_on_connection_error(self):
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")):
            assert is_service_running("http://127.0.0.1:11434") is False

    def test_service_running_returns_false_on_non_200(self):
        mock_response = MagicMock()
        mock_response.status = 500
        mock_response.__enter__.return_value = mock_response

        with patch("urllib.request.urlopen", return_value=mock_response):
            assert is_service_running() is False


class TestStartServiceBackground:
    """Pruebas de inicio del servidor en segundo plano."""

    def test_start_service_windows(self):
        with patch("platform.system", return_value="Windows"), \
             patch("shutil.which", return_value="ollama"), \
             patch("subprocess.Popen") as mock_popen:
            result = start_service_background()
            assert result is True
            mock_popen.assert_called_once()
            args, kwargs = mock_popen.call_args
            assert args[0] == ["ollama", "serve"]

    def test_start_service_linux(self):
        with patch("platform.system", return_value="Linux"), \
             patch("shutil.which", return_value="ollama"), \
             patch("subprocess.Popen") as mock_popen:
            result = start_service_background()
            assert result is True
            mock_popen.assert_called_once()
            _, kwargs = mock_popen.call_args
            assert kwargs.get("start_new_session") is True

    def test_start_service_windows_localappdata_candidate(self, monkeypatch):
        monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\test\AppData\Local")
        with patch("platform.system", return_value="Windows"), \
             patch("shutil.which", return_value=None), \
             patch("os.path.exists", return_value=True), \
             patch("subprocess.Popen") as mock_popen:
            result = start_service_background()
            assert result is True
            mock_popen.assert_called_once()
            args, _ = mock_popen.call_args
            assert "ollama.exe" in args[0][0]

    def test_start_service_exception_handled(self):
        with patch("subprocess.Popen", side_effect=OSError("Exec format error")):
            assert start_service_background() is False


class TestInstallOllamaWindows:
    """Pruebas de instalación desasistida con winget."""

    def test_winget_not_found(self):
        with patch("shutil.which", return_value=None):
            success, msg = install_ollama_windows()
            assert success is False
            assert "winget no está disponible" in msg

    def test_winget_success(self):
        mock_proc = MagicMock(returncode=0, stdout="Successfully installed", stderr="")
        with patch("shutil.which", return_value=r"C:\Windows\System32\winget.exe"), \
             patch("subprocess.run", return_value=mock_proc):
            success, msg = install_ollama_windows()
            assert success is True
            assert "correctamente" in msg

    def test_winget_failure(self):
        mock_proc = MagicMock(returncode=1, stdout="", stderr="Package not found")
        with patch("shutil.which", return_value=r"C:\Windows\System32\winget.exe"), \
             patch("subprocess.run", return_value=mock_proc):
            success, msg = install_ollama_windows()
            assert success is False
            assert "Package not found" in msg

    def test_winget_exception(self):
        with patch("shutil.which", return_value=r"C:\Windows\System32\winget.exe"), \
             patch("subprocess.run", side_effect=RuntimeError("Process aborted")):
            success, msg = install_ollama_windows()
            assert success is False
            assert "Excepción durante la instalación" in msg


class TestListLocalModels:
    """Pruebas de consulta de modelos locales."""

    def test_list_models_dict_format(self):
        mock_client = MagicMock()
        mock_client.list.return_value = {
            "models": [
                {"name": "qwen2.5-coder:7b"},
                {"model": "llama3.2:3b"},
            ]
        }
        with patch("ollama.Client", return_value=mock_client):
            models = list_local_models()
            assert models == ["qwen2.5-coder:7b", "llama3.2:3b"]

    def test_list_models_object_format(self):
        m1 = MagicMock()
        m1.model = "codellama:7b"
        m1.name = None

        m2 = MagicMock()
        m2.model = None
        m2.name = "qwen3:8b"

        mock_resp = MagicMock()
        mock_resp.models = [m1, m2]

        mock_client = MagicMock()
        mock_client.list.return_value = mock_resp
        with patch("ollama.Client", return_value=mock_client):
            models = list_local_models()
            assert models == ["codellama:7b", "qwen3:8b"]

    def test_list_models_on_exception_returns_empty_list(self):
        mock_client = MagicMock()
        mock_client.list.side_effect = Exception("Ollama daemon down")
        with patch("ollama.Client", return_value=mock_client):
            assert list_local_models() == []


class TestPullModelSync:
    """Pruebas de descarga síncrona de modelos."""

    def test_pull_model_success_with_callback(self):
        events = []
        chunks = [
            {"status": "pulling manifest"},
            {"status": "downloading", "completed": 50, "total": 100},
            {"status": "success"},
        ]
        mock_client = MagicMock()
        mock_client.pull.return_value = iter(chunks)

        with patch("ollama.Client", return_value=mock_client):
            result = pull_model_sync("qwen2.5-coder:1.5b", progress_callback=lambda d: events.append(d))
            assert result is True
            assert len(events) == 3
            assert events[1]["completed"] == 50

    def test_pull_model_failure_triggers_error_callback(self):
        events = []
        mock_client = MagicMock()
        mock_client.pull.side_effect = Exception("Network timeout")

        with patch("ollama.Client", return_value=mock_client):
            result = pull_model_sync("invalid-model", progress_callback=lambda d: events.append(d))
            assert result is False
            assert len(events) == 1
            assert events[0]["status"] == "error"
            assert "Network timeout" in events[0]["error"]


class TestAIEngine:
    """Pruebas del motor asíncrono AIEngine."""

    @pytest.mark.asyncio
    async def test_empty_code_returns_empty_notification(self):
        engine = AIEngine(model="qwen2.5-coder:7b")
        result = await engine.analyze_code(code="", file_path="empty.py")
        assert "Archivo vacío" in result
        assert "empty.py" in result

    @pytest.mark.asyncio
    async def test_whitespace_code_returns_empty_notification(self):
        engine = AIEngine(model="qwen2.5-coder:7b")
        result = await engine.analyze_code(code="   \n\n\t  ", file_path="spaces.py")
        assert "Archivo vacío" in result

    @pytest.mark.asyncio
    async def test_successful_analysis_dict_response(self):
        engine = AIEngine(model="qwen2.5-coder:7b")
        mock_client = AsyncMock()
        mock_client.chat.return_value = {
            "message": {
                "content": "### 🎯 1. Responsabilidad del Módulo\n- Módulo principal."
            }
        }
        engine._async_client = mock_client

        result = await engine.analyze_code(
            code="def main(): pass",
            file_path="src/main.py",
        )

        assert "# 🏛️ Análisis Arquitectónico: `src/main.py`" in result
        assert "*Modelo activo:* `qwen2.5-coder:7b`" in result
        assert "Responsabilidad del Módulo" in result

    @pytest.mark.asyncio
    async def test_successful_analysis_object_response(self):
        engine = AIEngine(model="llama3.2:3b")
        mock_msg = MagicMock()
        mock_msg.content = "### 📦 2. Dependencias Clave\n- Textual y Ollama."
        mock_response = MagicMock()
        mock_response.message = mock_msg

        mock_client = AsyncMock()
        mock_client.chat.return_value = mock_response
        engine._async_client = mock_client

        result = await engine.analyze_code(
            code="import textual\nimport ollama",
            file_path="src/app.py",
        )

        assert "# 🏛️ Análisis Arquitectónico: `src/app.py`" in result
        assert "*Modelo activo:* `llama3.2:3b`" in result
        assert "Dependencias Clave" in result

    @pytest.mark.asyncio
    async def test_ollama_response_error_handling(self):
        engine = AIEngine(model="nonexistent-model")
        mock_client = AsyncMock()
        mock_client.chat.side_effect = ollama.ResponseError(
            error="model 'nonexistent-model' not found",
            status_code=404,
        )
        engine._async_client = mock_client

        result = await engine.analyze_code(code="print(1)", file_path="test.py")
        assert "Error de Ollama (404)" in result
        assert "ollama pull nonexistent-model" in result

    @pytest.mark.asyncio
    async def test_generic_connection_error_handling(self):
        engine = AIEngine(model="qwen2.5-coder:7b")
        mock_client = AsyncMock()
        mock_client.chat.side_effect = ConnectionRefusedError("No connection could be made")
        engine._async_client = mock_client

        result = await engine.analyze_code(code="print(1)", file_path="test.py")
        assert "Error de Conexión con Ollama" in result
        assert "ollama serve" in result
        assert "No connection could be made" in result
