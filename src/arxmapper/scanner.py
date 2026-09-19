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

# Categorización semántica arquitectónica de archivos
CONFIG_EXTENSIONS: Set[str] = {
    ".toml", ".json", ".yaml", ".yml", ".xml", ".properties",
    ".cfg", ".ini", ".conf", ".gradle", ".env",
}
CONFIG_FILENAMES: Set[str] = {
    "dockerfile", "makefile", "license", "gemfile", "pipfile",
    "cmakelists.txt", "pom.xml", ".gitignore", ".gitattributes",
    "requirements.txt", "package.json", "tsconfig.json",
}

DOC_EXTENSIONS: Set[str] = {".md", ".rst", ".txt", ".adoc"}
DOC_FILENAMES: Set[str] = {"readme", "contributing", "changelog", "license"}

DB_EXTENSIONS: Set[str] = {".sql", ".prisma", ".graphql", ".gql"}

TEST_INDICATORS: Set[str] = {"test", "tests", "spec", "__tests__"}

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
        return (
            dir_name in self.ignore_dirs
            or dir_name.startswith((".", "__"))
            or dir_name.endswith(".egg-info")
        )

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

    @classmethod
    def classify_file(cls, file_path: Path) -> Dict[str, str]:
        """Clasifica semánticamente un archivo según su rol arquitectónico."""
        name_lower = file_path.name.lower()
        suffix = file_path.suffix.lower()
        stem_lower = file_path.stem.lower()

        # 1. Pruebas / Tests
        parts_lower = [p.lower() for p in file_path.parts]
        is_test = (
            any(t in parts_lower for t in TEST_INDICATORS)
            or name_lower.startswith(("test_", "test-"))
            or name_lower.endswith(("_test.py", "-test.py"))
            or ".test." in name_lower
            or ".spec." in name_lower
            or stem_lower in ("test", "tests")
            or stem_lower.endswith(("_test", "-test", ".test", "_tests", "-tests"))
            or (
                (stem_lower.endswith("test") or stem_lower.endswith("tests"))
                and not stem_lower.endswith(("latest", "contest", "fastest", "protest", "attest", "detest", "pytest"))
            )
        )
        if is_test:
            return {
                "role": "test",
                "badge": "[TEST]",
                "bullet": "🧪",
                "color": "yellow",
                "desc": "Archivo de prueba unitaria o integración",
                "icon": cls._get_file_icon(suffix),
            }

        # 2. Configuración y Manifiestos
        if suffix in CONFIG_EXTENSIONS or name_lower in CONFIG_FILENAMES or name_lower.startswith(".env"):
            return {
                "role": "config",
                "badge": "[CONFIG]",
                "bullet": "⚙️",
                "color": "magenta",
                "desc": "Manifiesto o configuración del sistema",
                "icon": cls._get_file_icon(suffix),
            }

        # 3. Documentación
        if suffix in DOC_EXTENSIONS or any(name_lower.startswith(d) for d in DOC_FILENAMES):
            return {
                "role": "docs",
                "badge": "[DOCS]",
                "bullet": "📝",
                "color": "cyan",
                "desc": "Documentación o guía del proyecto",
                "icon": cls._get_file_icon(suffix),
            }

        # 4. Bases de datos / Esquemas
        if suffix in DB_EXTENSIONS:
            return {
                "role": "database",
                "badge": "[DATA]",
                "bullet": "🗄️",
                "color": "blue",
                "desc": "Esquema o consulta de base de datos",
                "icon": cls._get_file_icon(suffix),
            }

        # 5. Componente de código fuente
        return {
            "role": "component",
            "badge": "[COMPONENTE]",
            "bullet": "●",
            "color": "green",
            "desc": "Componente ejecutable de código fuente",
            "icon": cls._get_file_icon(suffix),
        }

    @classmethod
    def classify_dir(cls, dir_path: Path, depth: int) -> Dict[str, str]:
        """Clasifica un directorio como Módulo, Submódulo o Paquete arquitectónico."""
        if depth == 0:
            return {
                "role": "root",
                "badge": "[SISTEMA]",
                "bullet": "🏛️",
                "color": "bold cyan",
                "desc": "Raíz del repositorio y arquitectura global",
            }
        if depth == 1:
            return {
                "role": "module",
                "badge": "[MÓDULO]",
                "bullet": "◈",
                "color": "bold yellow",
                "desc": "Módulo principal del sistema",
            }
        return {
            "role": "package",
            "badge": "[PAQUETE]",
            "bullet": "◆",
            "color": "bold blue",
            "desc": "Sub-paquete o subsistema interno",
        }

    def get_hierarchy(self, current_path: Optional[Path] = None, depth: int = 0) -> Dict[str, Any]:
        """Construye una estructura de datos jerárquica y semántica del repositorio."""
        target = (current_path or self.root_path).resolve()
        dir_class = self.classify_dir(target, depth)

        data: Dict[str, Any] = {
            "name": target.name or str(target),
            "path": target,
            "is_dir": target.is_dir(),
            "depth": depth,
            "role": dir_class["role"],
            "badge": dir_class["badge"],
            "bullet": dir_class["bullet"],
            "color": dir_class["color"],
            "children": [],
            "metrics": {
                "total_files": 0,
                "components": 0,
                "configs": 0,
                "tests": 0,
                "docs": 0,
                "submodules": 0,
            },
        }

        if not target.is_dir():
            return data

        try:
            entries = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
            for entry in entries:
                if entry.is_dir():
                    if not self.is_ignored_dir(entry.name):
                        sub_data = self.get_hierarchy(entry, depth=depth + 1)
                        data["children"].append(sub_data)
                        data["metrics"]["submodules"] += 1
                        data["metrics"]["total_files"] += sub_data["metrics"]["total_files"]
                        data["metrics"]["components"] += sub_data["metrics"]["components"]
                        data["metrics"]["configs"] += sub_data["metrics"]["configs"]
                        data["metrics"]["tests"] += sub_data["metrics"]["tests"]
                        data["metrics"]["docs"] += sub_data["metrics"]["docs"]
                elif entry.is_file():
                    if self.is_text_file(entry):
                        file_class = self.classify_file(entry)
                        role = file_class["role"]
                        data["metrics"]["total_files"] += 1
                        if role == "component":
                            data["metrics"]["components"] += 1
                        elif role == "config":
                            data["metrics"]["configs"] += 1
                        elif role == "test":
                            data["metrics"]["tests"] += 1
                        elif role == "docs":
                            data["metrics"]["docs"] += 1

                        data["children"].append({
                            "name": entry.name,
                            "path": entry,
                            "is_dir": False,
                            "classification": file_class,
                            "size": entry.stat().st_size if entry.exists() else 0,
                            "children": [],
                        })
        except (PermissionError, OSError):
            pass

        return data

    def get_module_markdown_summary(self, module_data: Dict[str, Any], root_path: Path) -> str:
        """Genera una ficha arquitectónica detallada en Markdown para un módulo o paquete."""
        mod_path: Path = module_data.get("path", root_path)
        try:
            rel_path = mod_path.relative_to(root_path)
            rel_path_str = str(rel_path) if str(rel_path) != "." else "/"
        except ValueError:
            rel_path_str = str(mod_path)

        metrics = module_data.get("metrics", {})
        total_files = metrics.get("total_files", 0)
        components = metrics.get("components", 0)
        configs = metrics.get("configs", 0)
        tests = metrics.get("tests", 0)
        docs = metrics.get("docs", 0)
        submodules = metrics.get("submodules", 0)

        badge = module_data.get("badge", "[MÓDULO]")
        bullet = module_data.get("bullet", "◈")
        name = module_data.get("name", mod_path.name)

        md = [
            f"# {bullet} {badge} `{name}`\n",
            f"> **Ubicación en el sistema:** `{rel_path_str}`  ",
            f"> **Nivel de Abstracción:** Nivel {module_data.get('depth', 1)}  ",
            f"> **Complejidad del Módulo:** {total_files} archivos ({components} componentes de código, {submodules} submódulos)\n",
            "---\n",
            "### 📊 Métricas de Composición",
            f"- 🧩 **Componentes de código:** `{components}`",
            f"- 📁 **Submódulos / Paquetes internos:** `{submodules}`",
            f"- ⚙️ **Configuraciones / Manifiestos:** `{configs}`",
            f"- 🧪 **Suites de prueba:** `{tests}`",
            f"- 📝 **Documentación:** `{docs}`\n",
            "### 📋 Esquema de Componentes Inmediatos",
        ]

        direct_children = module_data.get("children", [])
        if not direct_children:
            md.append("*Este directorio no contiene archivos directos o están excluidos.*")
        else:
            for child in direct_children:
                c_name = child.get("name", "")
                if child.get("is_dir"):
                    c_badge = child.get("badge", "[MÓDULO]")
                    c_bullet = child.get("bullet", "◈")
                    c_files = child.get("metrics", {}).get("total_files", 0)
                    md.append(f"- {c_bullet} **{c_badge} `{c_name}/`** [dim]({c_files} archivos)[/dim]")
                else:
                    c_class = child.get("classification", {})
                    c_badge = c_class.get("badge", "[CMP]")
                    c_bullet = c_class.get("bullet", "●")
                    c_desc = c_class.get("desc", "")
                    size_kb = round(child.get("size", 0) / 1024, 1)
                    md.append(f"- {c_bullet} **`{c_name}`** `{c_badge}` — *{c_desc}* (~{size_kb} KB)")

        md.append("\n---\n")
        md.append("💡 *Haz clic en cualquiera de los componentes en el árbol para generar su análisis arquitectónico profundo con IA.*")
        return "\n".join(md)

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
