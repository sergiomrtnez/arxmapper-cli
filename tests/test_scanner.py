"""Pruebas unitarias e integración para arxmapper.scanner."""

from __future__ import annotations

import os
from pathlib import Path
import pytest

from arxmapper.scanner import (
    BINARY_EXTENSIONS,
    CONFIG_EXTENSIONS,
    CONFIG_FILENAMES,
    DB_EXTENSIONS,
    DOC_EXTENSIONS,
    DOC_FILENAMES,
    IGNORE_DIRS,
    MAX_FILE_READ_BYTES,
    TEST_INDICATORS,
    RepoScanner,
)


class TestRepoScannerInit:
    """Pruebas de inicialización y configuración del scanner."""

    def test_default_initialization(self):
        scanner = RepoScanner()
        assert scanner.root_path == Path.cwd().resolve()
        assert IGNORE_DIRS.issubset(scanner.ignore_dirs)

    def test_custom_root_and_ignore_dirs(self, tmp_path: Path):
        custom_ignore = {"custom_build", "temp_data"}
        scanner = RepoScanner(root_path=tmp_path, custom_ignore_dirs=custom_ignore)
        assert scanner.root_path == tmp_path.resolve()
        assert "custom_build" in scanner.ignore_dirs
        assert "temp_data" in scanner.ignore_dirs
        assert ".git" in scanner.ignore_dirs


class TestIgnoredDirs:
    """Pruebas de detección de directorios excluidos."""

    @pytest.mark.parametrize(
        "dir_name, expected",
        [
            (".git", True),
            ("node_modules", True),
            (".venv", True),
            ("venv", True),
            ("__pycache__", True),
            (".idea", True),
            (".vscode", True),
            (".hidden_dir", True),
            ("__internal__", True),
            ("my_package.egg-info", True),
            ("src", False),
            ("app", False),
            ("core", False),
            ("utils", False),
        ],
    )
    def test_is_ignored_dir(self, dir_name: str, expected: bool):
        scanner = RepoScanner()
        assert scanner.is_ignored_dir(dir_name) is expected

    def test_custom_ignored_dir(self, tmp_path: Path):
        scanner = RepoScanner(root_path=tmp_path, custom_ignore_dirs={"build_cache"})
        assert scanner.is_ignored_dir("build_cache") is True
        assert scanner.is_ignored_dir("normal_dir") is False


class TestIsTextFile:
    """Pruebas de detección de archivos analizables."""

    @pytest.mark.parametrize("ext", [".exe", ".png", ".jpg", ".zip", ".tar", ".pyc", ".db"])
    def test_binary_extensions_rejected(self, tmp_path: Path, ext: str):
        scanner = RepoScanner(root_path=tmp_path)
        dummy_file = tmp_path / f"test{ext}"
        dummy_file.write_bytes(b"dummy")
        assert scanner.is_text_file(dummy_file) is False

    def test_null_byte_detected_as_binary(self, tmp_path: Path):
        scanner = RepoScanner(root_path=tmp_path)
        binary_file = tmp_path / "unknown_format"
        binary_file.write_bytes(b"some text before \x00 binary data")
        assert scanner.is_text_file(binary_file) is False

    def test_valid_text_file_accepted(self, tmp_path: Path):
        scanner = RepoScanner(root_path=tmp_path)
        py_file = tmp_path / "main.py"
        py_file.write_text("print('Hello, world!')\n", encoding="utf-8")
        assert scanner.is_text_file(py_file) is True

    def test_empty_text_file_accepted(self, tmp_path: Path):
        scanner = RepoScanner(root_path=tmp_path)
        empty_file = tmp_path / "empty.txt"
        empty_file.touch()
        assert scanner.is_text_file(empty_file) is True

    def test_nonexistent_file_returns_false(self, tmp_path: Path):
        scanner = RepoScanner(root_path=tmp_path)
        missing_file = tmp_path / "does_not_exist.txt"
        assert scanner.is_text_file(missing_file) is False

    def test_directory_passed_as_file_returns_false(self, tmp_path: Path):
        scanner = RepoScanner(root_path=tmp_path)
        assert scanner.is_text_file(tmp_path) is False


class TestClassifyFile:
    """Pruebas de categorización semántica arquitectónica."""

    @pytest.mark.parametrize(
        "file_name, expected_role",
        [
            ("test_scanner.py", "test"),
            ("scanner_test.py", "test"),
            ("scanner-test.py", "test"),
            ("app.test.ts", "test"),
            ("app.spec.js", "test"),
            ("UserServiceTest.java", "test"),
            ("tests.py", "test"),
            ("test.py", "test"),
            ("package.json", "config"),
            ("pyproject.toml", "config"),
            ("Dockerfile", "config"),
            ("Makefile", "config"),
            ("docker-compose.yml", "config"),
            (".env.production", "config"),
            ("pytest.ini", "config"),
            ("README.md", "docs"),
            ("CONTRIBUTING.rst", "docs"),
            ("manual.txt", "docs"),
            ("schema.sql", "database"),
            ("schema.prisma", "database"),
            ("queries.graphql", "database"),
            ("engine.py", "component"),
            ("index.ts", "component"),
            ("server.go", "component"),
            ("main.rs", "component"),
            ("latest.py", "component"),
            ("contest.py", "component"),
            ("fastest.py", "component"),
        ],
    )
    def test_semantic_classification(self, file_name: str, expected_role: str):
        path = Path(file_name)
        result = RepoScanner.classify_file(path)
        assert result["role"] == expected_role, f"Failed for {file_name}: expected {expected_role}, got {result['role']}"
        assert "badge" in result
        assert "bullet" in result
        assert "color" in result
        assert "desc" in result
        assert "icon" in result

    def test_file_inside_test_directory(self):
        path = Path("src/tests/helper.py")
        result = RepoScanner.classify_file(path)
        assert result["role"] == "test"

    def test_file_icon_lookup(self):
        assert RepoScanner._get_file_icon(".py") == "🐍"
        assert RepoScanner._get_file_icon(".ts") == "🟦"
        assert RepoScanner._get_file_icon(".js") == "🟨"
        assert RepoScanner._get_file_icon(".sql") == "🗄️"
        assert RepoScanner._get_file_icon(".unknown_ext") == "📄"


class TestClassifyDir:
    """Pruebas de clasificación jerárquica de carpetas."""

    def test_depth_zero_is_root(self):
        info = RepoScanner.classify_dir(Path("repo"), depth=0)
        assert info["role"] == "root"
        assert info["badge"] == "[SISTEMA]"

    def test_depth_one_is_module(self):
        info = RepoScanner.classify_dir(Path("repo/src"), depth=1)
        assert info["role"] == "module"
        assert info["badge"] == "[MÓDULO]"

    def test_depth_two_or_more_is_package(self):
        info_depth2 = RepoScanner.classify_dir(Path("repo/src/core"), depth=2)
        assert info_depth2["role"] == "package"
        assert info_depth2["badge"] == "[PAQUETE]"

        info_depth3 = RepoScanner.classify_dir(Path("repo/src/core/sub"), depth=3)
        assert info_depth3["role"] == "package"


class TestGetHierarchy:
    """Pruebas del árbol de jerarquía y cálculo de métricas."""

    def test_get_hierarchy_structure(self, sample_repo: Path):
        scanner = RepoScanner(root_path=sample_repo)
        data = scanner.get_hierarchy()

        assert data["is_dir"] is True
        assert data["role"] == "root"
        assert data["depth"] == 0
        metrics = data["metrics"]
        assert metrics["total_files"] > 0
        assert metrics["components"] >= 3  # engine.py, utils.py, routes.py
        assert metrics["configs"] >= 3     # settings.json, pyproject.toml, Dockerfile
        assert metrics["tests"] >= 2       # test_engine.py, api_test.py
        assert metrics["docs"] >= 2        # README.md, architecture.md
        assert metrics["submodules"] >= 2   # src, tests, docs

        # Verificar que directorios ignorados no están en children
        child_names = [c["name"] for c in data["children"]]
        assert ".git" not in child_names
        assert "node_modules" not in child_names
        assert ".venv" not in child_names
        assert "mock.egg-info" not in child_names

        # Verificar que archivos binarios no están incluidos
        assert "binary.exe" not in child_names
        assert "corrupt.bin" not in child_names

    def test_get_hierarchy_on_file_returns_base(self, sample_repo: Path):
        file_path = sample_repo / "README.md"
        scanner = RepoScanner(root_path=sample_repo)
        data = scanner.get_hierarchy(file_path)
        assert data["is_dir"] is False
        assert data["children"] == []

    def test_get_hierarchy_empty_directory(self, tmp_path: Path):
        empty_dir = tmp_path / "empty_repo"
        empty_dir.mkdir()
        scanner = RepoScanner(root_path=empty_dir)
        data = scanner.get_hierarchy()
        assert data["children"] == []
        assert data["metrics"]["total_files"] == 0

    def test_get_hierarchy_permission_error(self, tmp_path: Path, monkeypatch):
        scanner = RepoScanner(root_path=tmp_path)
        def mock_iterdir(self):
            raise PermissionError("Access is denied")
        monkeypatch.setattr(Path, "iterdir", mock_iterdir)
        data = scanner.get_hierarchy()
        assert data["children"] == []
        assert data["metrics"]["total_files"] == 0


class TestGetModuleMarkdownSummary:
    """Pruebas de la generación de fichas Markdown de módulos."""

    def test_module_summary_with_children(self, sample_repo: Path):
        scanner = RepoScanner(root_path=sample_repo)
        data = scanner.get_hierarchy()

        md = scanner.get_module_markdown_summary(data, sample_repo)
        assert "# 🏛️ [SISTEMA]" in md
        assert "Métricas de Composición" in md
        assert "Componentes de código" in md
        assert "Esquema de Componentes Inmediatos" in md

    def test_module_summary_empty_children(self, tmp_path: Path):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        scanner = RepoScanner(root_path=empty_dir)
        data = scanner.get_hierarchy()

        md = scanner.get_module_markdown_summary(data, empty_dir)
        assert "Este directorio no contiene archivos directos o están excluidos." in md

    def test_module_summary_path_not_relative_to_root(self, tmp_path: Path):
        dir_a = tmp_path / "dir_a"
        dir_b = tmp_path / "dir_b"
        dir_a.mkdir()
        dir_b.mkdir()

        scanner = RepoScanner(root_path=dir_a)
        data = scanner.get_hierarchy(dir_b)

        md = scanner.get_module_markdown_summary(data, dir_a)
        assert str(dir_b) in md


class TestReadFileContent:
    """Pruebas de lectura segura de archivos de texto."""

    def test_read_small_file(self, tmp_path: Path):
        scanner = RepoScanner(root_path=tmp_path)
        test_file = tmp_path / "small.txt"
        test_file.write_text("Hello, ArxMapper!", encoding="utf-8")

        content, is_truncated = scanner.read_file_content(test_file)
        assert content == "Hello, ArxMapper!"
        assert is_truncated is False

    def test_read_truncated_large_file(self, tmp_path: Path):
        scanner = RepoScanner(root_path=tmp_path)
        large_file = tmp_path / "large.txt"
        # Escribir más de MAX_FILE_READ_BYTES
        data = "A" * (MAX_FILE_READ_BYTES + 500)
        large_file.write_text(data, encoding="utf-8")

        content, is_truncated = scanner.read_file_content(large_file)
        assert len(content) == MAX_FILE_READ_BYTES
        assert is_truncated is True

    def test_read_nonexistent_file(self, tmp_path: Path):
        scanner = RepoScanner(root_path=tmp_path)
        missing = tmp_path / "missing.txt"

        content, is_truncated = scanner.read_file_content(missing)
        assert "Error al leer el archivo" in content
        assert is_truncated is False

    def test_read_utf8_with_replacement(self, tmp_path: Path):
        scanner = RepoScanner(root_path=tmp_path)
        special_file = tmp_path / "special.txt"
        special_file.write_bytes(b"Valid ASCII \xff\xfe Invalid bytes")

        content, is_truncated = scanner.read_file_content(special_file)
        assert "Valid ASCII" in content
        assert is_truncated is False
