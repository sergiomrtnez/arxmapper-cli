"""ai_engine.py - Motor de IA local para análisis arquitectónico mediante Ollama.

Proporciona utilidades asíncronas para interactuar con Ollama, verificar el entorno,
gestionar modelos locales, descargar modelos recomendados y formular consultas
estructuradas para documentar la arquitectura de componentes de software.
"""

from __future__ import annotations

import asyncio
import os
import platform
import shutil
import subprocess
from typing import Any, Callable, Dict, List, Optional, Tuple
import urllib.error
import urllib.request

import ollama


DEFAULT_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# Catálogo de modelos recomendados para análisis de código y arquitectura
RECOMMENDED_MODELS: List[Tuple[str, str, str]] = [
    (
        "qwen2.5-coder:1.5b",
        "~1.0 GB",
        "Ultrarrápido y liviano. Ideal para equipos con recursos moderados o CPU pura.",
    ),
    (
        "qwen2.5-coder:7b",
        "~4.7 GB",
        "Excelente balance entre velocidad y profundidad analítica de código.",
    ),
    (
        "llama3.2:3b",
        "~2.0 GB",
        "Muy ágil, bajo consumo de memoria y sólida capacidad de síntesis.",
    ),
    (
        "codellama:7b",
        "~3.8 GB",
        "Especializado en lenguajes de programación y patrones de diseño.",
    ),
    (
        "qwen3:8b",
        "~5.2 GB",
        "Modelo avanzado con amplio contexto y precisión técnica.",
    ),
]

SYSTEM_PROMPT = """Eres un Arquitecto de Software Senior y analista de código de alto nivel.
Tu misión es analizar el archivo de código fuente provisto y generar un informe conciso, riguroso y en formato Markdown estructurado en viñetas.

Debes ceñirte estrictamente a estas tres secciones obligatorias:

### 🎯 1. Responsabilidad del Módulo
- Describe en 2 a 3 viñetas el propósito principal del archivo.
- Qué problema resuelve y cuál es su rol dentro del sistema global.

### 📦 2. Dependencias Clave
- Enumera las librerías externas esenciales que utiliza.
- Identifica acoplamientos internos críticos o servicios con los que interactúa.

### 🏛️ 3. Patrones Arquitectónicos y de Diseño
- Menciona los patrones detectados (ej. MVC, Factory, Repository, Observer, Singleton, Clean Architecture, Dependency Injection, Event-Driven, etc.).
- Comenta brevemente aspectos destacables de mantenibilidad o diseño (cohesión, acoplamiento, principios SOLID).

Mantén las explicaciones concisas, altamente técnicas y orientadas a la arquitectura. Si el archivo está vacío o es solo configuración, descríbelo acorde."""


def is_ollama_installed() -> bool:
    """Comprueba si el binario de Ollama está presente en el sistema."""
    if shutil.which("ollama"):
        return True

    # Comprobación de rutas habituales en Windows
    if platform.system() == "Windows":
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        if local_appdata:
            candidate = os.path.join(local_appdata, "Programs", "Ollama", "ollama.exe")
            if os.path.exists(candidate):
                return True
    return False


def is_service_running(host: str = DEFAULT_HOST) -> bool:
    """Verifica si el servidor de Ollama está activo y respondiendo solicitudes HTTP."""
    try:
        req = urllib.request.Request(f"{host.rstrip('/')}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            return resp.status == 200
    except Exception:
        return False


def start_service_background() -> bool:
    """Intenta iniciar el servidor de Ollama en segundo plano."""
    try:
        cmd = "ollama"
        if platform.system() == "Windows" and not shutil.which("ollama"):
            local_appdata = os.environ.get("LOCALAPPDATA", "")
            candidate = os.path.join(local_appdata, "Programs", "Ollama", "ollama.exe")
            if os.path.exists(candidate):
                cmd = candidate

        if platform.system() == "Windows":
            # Iniciar proceso independiente sin bloquear la consola
            subprocess.Popen(
                [cmd, "serve"],
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            subprocess.Popen(
                [cmd, "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        return True
    except Exception:
        return False


def install_ollama_windows() -> Tuple[bool, str]:
    """Intenta instalar Ollama en Windows utilizando winget."""
    if shutil.which("winget") is None:
        return False, "winget no está disponible en este sistema."
    try:
        proc = subprocess.run(
            ["winget", "install", "--id", "Ollama.Ollama", "-e", "--accept-source-agreements", "--accept-package-agreements"],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0:
            return True, "Ollama instalado correctamente."
        return False, f"Error al ejecutar winget: {proc.stderr or proc.stdout}"
    except Exception as exc:
        return False, f"Excepción durante la instalación: {exc}"


def list_local_models(host: str = DEFAULT_HOST) -> List[str]:
    """Obtiene la lista de nombres de modelos descargados localmente en Ollama."""
    try:
        client = ollama.Client(host=host)
        resp = client.list()
        # ollama python client retorna un diccionario con clave 'models' o lista de objetos
        models = resp.get("models", []) if isinstance(resp, dict) else getattr(resp, "models", [])
        names: List[str] = []
        for m in models:
            if isinstance(m, dict):
                names.append(m.get("name") or m.get("model", ""))
            else:
                names.append(getattr(m, "model", "") or getattr(m, "name", ""))
        return [n for n in names if n]
    except Exception:
        return []


def pull_model_sync(
    model_name: str,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    host: str = DEFAULT_HOST,
) -> bool:
    """Descarga un modelo de Ollama sincronamente emitiendo eventos de progreso."""
    try:
        client = ollama.Client(host=host)
        stream = client.pull(model=model_name, stream=True)
        for chunk in stream:
            data = chunk if isinstance(chunk, dict) else chunk.__dict__
            if progress_callback:
                progress_callback(data)
        return True
    except Exception as exc:
        if progress_callback:
            progress_callback({"status": "error", "error": str(exc)})
        return False


class AIEngine:
    """Motor de análisis arquitectónico asíncrono sobre Ollama."""

    def __init__(self, model: str = "qwen2.5-coder:7b", host: str = DEFAULT_HOST) -> None:
        self.model = model
        self.host = host
        self._async_client = ollama.AsyncClient(host=self.host)

    async def analyze_code(self, code: str, file_path: str, repo_root: str = "") -> str:
        """Envía el código de forma asíncrona a Ollama con el prompt estructurado."""
        if not code.strip():
            return (
                f"### ℹ️ Archivo vacío\n\n"
                f"El archivo `{file_path}` no contiene líneas de código para analizar."
            )

        user_content = (
            f"Por favor analiza el siguiente archivo del proyecto:\n"
            f"- **Ruta**: `{file_path}`\n\n"
            f"```\n{code}\n```"
        )

        try:
            response = await self._async_client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                options={"temperature": 0.2},
            )

            # Extraer contenido de la respuesta
            if isinstance(response, dict):
                content = response.get("message", {}).get("content", "")
            else:
                content = response.message.content

            header = f"# 🏛️ Análisis Arquitectónico: `{file_path}`\n\n*Modelo activo:* `{self.model}`\n\n---\n\n"
            return header + content

        except ollama.ResponseError as err:
            return (
                f"# ⚠️ Error de Ollama ({err.status_code})\n\n"
                f"**Mensaje:** {err.error}\n\n"
                f"> **Sugerencia:** Comprueba que el modelo `{self.model}` esté descargado localmente.\n"
                f"> Puedes ejecutar en tu terminal: `ollama pull {self.model}`"
            )
        except Exception as exc:
            return (
                f"# ❌ Error de Conexión con Ollama\n\n"
                f"No fue posible comunicarse con el servicio de Ollama en `{self.host}`.\n\n"
                f"**Detalle técnico:** `{exc}`\n\n"
                f"### Pasos para solucionarlo:\n"
                f"1. Abre una nueva terminal.\n"
                f"2. Ejecuta el comando: `ollama serve`\n"
                f"3. Verifica que el modelo `{self.model}` esté disponible con `ollama list`."
            )
