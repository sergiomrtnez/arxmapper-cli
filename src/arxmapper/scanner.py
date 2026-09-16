"""scanner.py - Explorador y analizador del sistema de archivos del repositorio.

Este módulo es el responsable exclusivo de inspeccionar el directorio de trabajo,
filtrar directorios ruidosos o artefactos irrelevantes, y construir una
estructura de datos jerárquica lista para ser consumida por la interfaz TUI.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


# Directorios excluidos por convención y relevancia arquitectónica
IGNORE_DIRS: Set[str] = {
    ".git",
    "node_modules",
    "target",
    "venv",
    ".venv",
    "env",
    ".env",
    "__pycache__",
    ".idea",
    ".vscode",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
    ".coverage",
    ".antigravity",
    ".tox",
    ".eggs",
    "bin",
    "obj",
}

# Extensiones binarias o no relevantes para análisis de código
BINARY_EXTENSIONS: Set[str] = {
    ".exe", ".dll", ".so", ".dylib", ".bin", ".iso",
    ".tar", ".gz", ".zip", ".7z", ".rar", ".bz2",
    ".pyc", ".pyo", ".pyd",
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp", ".svg",
    ".mp4", ".avi", ".mov", ".mp3", ".wav",
    ".pdf", ".docx", ".xlsx", ".pptx",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".db", ".sqlite", ".sqlite3",
    ".lock",
}

MAX_FILE_READ_BYTES: int = 120_000  # ~120 KB para evitar desbordar el contexto del LLM


class RepoScanner:
    """Explorador jerárquico de repositorios de código basado en pathlib."""

    def __init__(
        self,
        root_path: Optional[Path] = None,
        custom_ignore_dirs: Optional[Set[str]] = None,
    ) -> None:
        self.root_path = (root_path or Path.cwd()).resolve()
        self.ignore_dirs = set(IGNORE_DIRS)
        if custom_ignore_dirs:
            self.ignore_dirs.update(custom_ignore_dirs)

    def is_ignored_dir(self, dir_name: str) -> bool:
        """Verifica si un directorio debe ser excluido."""
        return dir_name in self.ignore_dirs or dir_name.startswith((".", "__"))

    def is_text_file(self, file_path: Path) -> bool:
        """Determina si un archivo es de texto analizable."""
        if file_path.suffix.lower() in BINARY_EXTENSIONS:
            return False
        try:
            # Inspección rápida de los primeros 1024 bytes buscando bytes nulos
            with file_path.open("rb") as f:
                chunk = f.read(1024)
                if b"\x00" in chunk:
                    return False
            return True
        except (OSError, PermissionError):
            return False

    def get_hierarchy(self, current_path: Optional[Path] = None) -> Dict[str, Any]:
        """Construye una estructura de datos jerárquica en forma de diccionario."""
        target = current_path or self.root_path
        data: Dict[str, Any] = {
            "name": target.name or str(target),
            "path": target,
            "is_dir": target.is_dir(),
            "children": [],
        }

        if not target.is_dir():
            return data

        try:
            entries = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
            for entry in entries:
                if entry.is_dir():
                    if not self.is_ignored_dir(entry.name):
                        data["children"].append(self.get_hierarchy(entry))
                elif entry.is_file():
                    if self.is_text_file(entry):
                        data["children"].append({
                            "name": entry.name,
                            "path": entry,
                            "is_dir": False,
                            "children": [],
                        })
        except (PermissionError, OSError):
            pass

        return data

    def populate_textual_tree(self, tree_node: Any, current_path: Optional[Path] = None) -> None:
        """Puebla un nodo Tree de Textual de forma recursiva con la estructura del proyecto."""
        target = current_path or self.root_path
        try:
            entries = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
            for entry in entries:
                if entry.is_dir():
                    if not self.is_ignored_dir(entry.name):
                        sub_node = tree_node.add(
                            f"📁 {entry.name}",
                            data={"path": entry, "is_dir": True},
                            expand=False,
                        )
                        self.populate_textual_tree(sub_node, entry)
                elif entry.is_file():
                    if self.is_text_file(entry):
                        icon = self._get_file_icon(entry.suffix.lower())
                        tree_node.add_leaf(
                            f"{icon} {entry.name}",
                            data={"path": entry, "is_dir": False},
                        )
        except (PermissionError, OSError):
            pass

    @staticmethod
    def _get_file_icon(ext: str) -> str:
        """Retorna un icono representativo según el tipo de archivo."""
        icons = {
            ".py": "🐍",
            ".js": "🟨",
            ".ts": "🟦",
            ".tsx": "⚛️",
            ".jsx": "⚛️",
            ".html": "🌐",
            ".css": "🎨",
            ".scss": "🎨",
            ".json": "📋",
            ".yaml": "⚙️",
            ".yml": "⚙️",
            ".toml": "⚙️",
            ".md": "📝",
            ".rst": "📝",
            ".txt": "📄",
            ".sh": "🐚",
            ".bash": "🐚",
            ".rs": "🦀",
            ".go": "🐹",
            ".java": "☕",
            ".kt": "🟣",
            ".xml": "📜",
            ".properties": "⚙️",
            ".gradle": "🐘",
            ".c": "🅲",
            ".cpp": "➕",
            ".h": "📑",
            ".sql": "🗄️",
            ".dockerfile": "🐳",
        }
        return icons.get(ext, "📄")

    def read_file_content(self, file_path: Path) -> Tuple[str, bool]:
        """Lee el contenido de un archivo de texto de forma segura.

        Retorna:
            (contenido_str, fue_truncado)
        """
        try:
            size = file_path.stat().st_size
            is_truncated = size > MAX_FILE_READ_BYTES

            with file_path.open("r", encoding="utf-8", errors="replace") as f:
                content = f.read(MAX_FILE_READ_BYTES)

            return content, is_truncated
        except Exception as exc:
            return f"Error al leer el archivo {file_path.name}: {exc}", False
