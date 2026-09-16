"""ArxMapper - Herramienta TUI interactiva para analizar y documentar arquitectura de código.

Analiza repositorios locales con modelos LLM locales mediante Ollama,
ofreciendo interfaz TUI reactiva y carga perezosa bajo demanda.
"""

__version__ = "0.1.0"

from .ai_engine import AIEngine, RECOMMENDED_MODELS
from .scanner import RepoScanner

__all__ = ["AIEngine", "RECOMMENDED_MODELS", "RepoScanner", "__version__"]
