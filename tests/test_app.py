"""Pruebas unitarias e integración para arxmapper.app (TUI y CLI)."""

from __future__ import annotations

import asyncio
from pathlib import Path
import sys
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from textual.widgets import Markdown, Tree

from arxmapper.app import (
    LOGO_ART,
    WELCOME_MARKDOWN,
    LoadingScreen,
    RepoMapperApp,
    ScolopendraLogo,
    main,
    run_ollama_wizard,
)
from arxmapper.scanner import RepoScanner


class TestScolopendraLogo:
    """Pruebas del widget animado de la escolopendra."""

    def test_logo_initial_state(self):
        logo = ScolopendraLogo()
        assert len(logo.art_lines) > 0
        assert logo.current_line_idx == 0
        assert logo.is_completed is False

    def test_logo_step_draw_progresses(self):
        logo = ScolopendraLogo()
        logo._step_draw()
        assert logo.current_line_idx == 1
        assert logo.is_completed is False

    def test_logo_step_draw_completes(self):
        logo = ScolopendraLogo()
        mock_timer = MagicMock()
        logo._timer = mock_timer

        # Avanzar hasta el final de las líneas
        for _ in range(len(logo.art_lines) + 2):
            logo._step_draw()

        assert logo.is_completed is True
        mock_timer.stop.assert_called_once()


class TestRepoMapperApp:
    """Pruebas de la aplicación Textual interactiva."""

    @pytest.mark.asyncio
    async def test_app_compose_and_initial_widgets(self, sample_repo: Path):
        app = RepoMapperApp(repo_path=sample_repo, active_model="qwen2.5-coder:7b")
        with patch.object(LoadingScreen, "run_background_scan"):
            async with app.run_test() as pilot:
                tree = app.query_one("#repo-tree", Tree)
                markdown_pane = app.query_one("#markdown-content", Markdown)
                assert tree is not None
                assert markdown_pane is not None
                assert "ArxMapper" in WELCOME_MARKDOWN

    @pytest.mark.asyncio
    async def test_app_on_scan_completed_populates_tree(self, sample_repo: Path):
        app = RepoMapperApp(repo_path=sample_repo, active_model="test-model")
        scanner = RepoScanner(root_path=sample_repo)
        hierarchy = scanner.get_hierarchy()

        with patch.object(LoadingScreen, "run_background_scan"):
            async with app.run_test() as pilot:
                app.on_scan_completed(hierarchy)
                tree = app.query_one("#repo-tree", Tree)
                assert tree.root.data == hierarchy
                assert len(tree.root.children) > 0

    @pytest.mark.asyncio
    async def test_app_actions(self, sample_repo: Path):
        app = RepoMapperApp(repo_path=sample_repo, active_model="test-model")
        scanner = RepoScanner(root_path=sample_repo)
        hierarchy = scanner.get_hierarchy()

        with patch.object(LoadingScreen, "run_background_scan"):
            async with app.run_test() as pilot:
                app.on_scan_completed(hierarchy)

                # Probar alternancia de tema
                initial_theme = app.theme
                app.action_toggle_theme()
                assert app.theme != initial_theme

                # Probar expandir y colapsar
                app.action_expand_all()
                app.action_collapse_all()

                # Probar recarga de esquema (refresh_tree)
                with patch.object(app, "push_screen") as mock_push:
                    app.action_refresh_tree()
                    mock_push.assert_called_once()

    @pytest.mark.asyncio
    async def test_node_selected_directory(self, sample_repo: Path):
        app = RepoMapperApp(repo_path=sample_repo, active_model="test-model")
        scanner = RepoScanner(root_path=sample_repo)
        hierarchy = scanner.get_hierarchy()

        with patch.object(LoadingScreen, "run_background_scan"):
            async with app.run_test() as pilot:
                app.on_scan_completed(hierarchy)

                # Crear evento para nodo de directorio
                mock_event = MagicMock()
                mock_node = MagicMock()
                mock_node.data = hierarchy
                mock_event.node = mock_node

                app.on_tree_node_selected(mock_event)
                mock_node.toggle.assert_called_once()

                markdown_widget = app.query_one("#markdown-content", Markdown)
                assert "Métricas de Composición" in markdown_widget.source

    @pytest.mark.asyncio
    async def test_node_selected_file_triggers_analysis(self, sample_repo: Path):
        app = RepoMapperApp(repo_path=sample_repo, active_model="test-model")
        file_path = sample_repo / "src" / "core" / "engine.py"

        mock_event = MagicMock()
        mock_node = MagicMock()
        mock_node.data = {
            "name": "engine.py",
            "path": file_path,
            "is_dir": False,
        }
        mock_event.node = mock_node

        with patch.object(LoadingScreen, "run_background_scan"), \
             patch.object(app, "analyze_file_task") as mock_analyze:
            async with app.run_test() as pilot:
                app.on_tree_node_selected(mock_event)
                mock_analyze.assert_called_once()
                markdown_widget = app.query_one("#markdown-content", Markdown)
                assert "Generando análisis arquitectónico" in markdown_widget.source

    @pytest.mark.asyncio
    async def test_node_selected_no_path_returns_early(self, sample_repo: Path):
        app = RepoMapperApp(repo_path=sample_repo, active_model="test-model")
        mock_event = MagicMock()
        mock_node = MagicMock()
        mock_node.data = {}
        mock_event.node = mock_node

        with patch.object(LoadingScreen, "run_background_scan"), \
             patch.object(app, "analyze_file_task") as mock_analyze:
            async with app.run_test() as pilot:
                app.on_tree_node_selected(mock_event)
                mock_analyze.assert_not_called()

    @pytest.mark.asyncio
    async def test_node_selected_path_not_relative(self, sample_repo: Path, tmp_path: Path):
        app = RepoMapperApp(repo_path=sample_repo, active_model="test-model")
        outside_file = tmp_path / "outside.py"
        outside_file.write_text("print(1)", encoding="utf-8")

        mock_event = MagicMock()
        mock_node = MagicMock()
        mock_node.data = {"name": "outside.py", "path": outside_file, "is_dir": False}
        mock_event.node = mock_node

        with patch.object(LoadingScreen, "run_background_scan"), \
             patch.object(app, "analyze_file_task") as mock_analyze:
            async with app.run_test() as pilot:
                app.on_tree_node_selected(mock_event)
                mock_analyze.assert_called_once_with(outside_file, str(outside_file))

    @pytest.mark.asyncio
    async def test_analyze_file_task_execution(self, sample_repo: Path):
        app = RepoMapperApp(repo_path=sample_repo, active_model="test-model")
        file_path = sample_repo / "src" / "core" / "engine.py"

        mock_ai_engine = MagicMock()
        mock_ai_engine.analyze_code = AsyncMock(return_value="# Análisis arquitectónico de prueba")
        app.ai_engine = mock_ai_engine

        with patch.object(LoadingScreen, "run_background_scan"):
            async with app.run_test() as pilot:
                worker = app.analyze_file_task(file_path, "src/core/engine.py")
                await worker.wait()
                markdown_widget = app.query_one("#markdown-content", Markdown)
                assert "Análisis arquitectónico de prueba" in markdown_widget.source

    @pytest.mark.asyncio
    async def test_analyze_file_task_with_truncated_file(self, sample_repo: Path):
        app = RepoMapperApp(repo_path=sample_repo, active_model="test-model")
        file_path = sample_repo / "src" / "core" / "engine.py"

        mock_scanner = MagicMock()
        mock_scanner.read_file_content.return_value = ("large code", True)
        app.scanner = mock_scanner

        mock_ai_engine = MagicMock()
        mock_ai_engine.analyze_code = AsyncMock(return_value="# Análisis de código extenso")
        app.ai_engine = mock_ai_engine

        with patch.object(LoadingScreen, "run_background_scan"):
            async with app.run_test() as pilot:
                worker = app.analyze_file_task(file_path, "src/core/engine.py")
                await worker.wait()
                markdown_widget = app.query_one("#markdown-content", Markdown)
                assert "El archivo supera el umbral de tamaño" in markdown_widget.source


class TestRunOllamaWizard:
    """Pruebas del asistente interactivo de terminal."""

    def test_wizard_existing_single_model_auto_selects(self):
        with patch("arxmapper.app.ai_engine.is_ollama_installed", return_value=True), \
             patch("arxmapper.app.ai_engine.is_service_running", return_value=True), \
             patch("arxmapper.app.ai_engine.list_local_models", return_value=["qwen2.5-coder:7b"]), \
             patch("arxmapper.app.Confirm.ask", return_value=True):
            model = run_ollama_wizard()
            assert model == "qwen2.5-coder:7b"

    def test_wizard_existing_multiple_models_user_picks(self):
        with patch("arxmapper.app.ai_engine.is_ollama_installed", return_value=True), \
             patch("arxmapper.app.ai_engine.is_service_running", return_value=True), \
             patch("arxmapper.app.ai_engine.list_local_models", return_value=["qwen2.5-coder:7b", "llama3.2:3b"]), \
             patch("arxmapper.app.Confirm.ask", return_value=True), \
             patch("arxmapper.app.Prompt.ask", return_value="2"):
            model = run_ollama_wizard()
            assert model == "llama3.2:3b"

    def test_wizard_not_installed_declines_install_exits(self):
        with patch("arxmapper.app.ai_engine.is_ollama_installed", return_value=False), \
             patch("arxmapper.app.Confirm.ask", return_value=False), \
             pytest.raises(SystemExit) as exc_info:
            run_ollama_wizard()
        assert exc_info.value.code == 1

    def test_wizard_not_installed_install_fails_exits(self):
        with patch("arxmapper.app.ai_engine.is_ollama_installed", return_value=False), \
             patch("arxmapper.app.Confirm.ask", return_value=True), \
             patch("arxmapper.app.ai_engine.install_ollama_windows", return_value=(False, "winget error")), \
             pytest.raises(SystemExit) as exc_info:
            run_ollama_wizard()
        assert exc_info.value.code == 1

    def test_wizard_service_not_running_timeout_exits(self):
        with patch("arxmapper.app.ai_engine.is_ollama_installed", return_value=True), \
             patch("arxmapper.app.ai_engine.is_service_running", return_value=False), \
             patch("arxmapper.app.ai_engine.start_service_background", return_value=True), \
             patch("arxmapper.app.time.sleep"), \
             pytest.raises(SystemExit) as exc_info:
            run_ollama_wizard()
        assert exc_info.value.code == 1

    def test_wizard_existing_models_invalid_prompt_falls_back(self):
        with patch("arxmapper.app.ai_engine.is_ollama_installed", return_value=True), \
             patch("arxmapper.app.ai_engine.is_service_running", return_value=True), \
             patch("arxmapper.app.ai_engine.list_local_models", return_value=["model-a", "model-b"]), \
             patch("arxmapper.app.Confirm.ask", return_value=True), \
             patch("arxmapper.app.Prompt.ask", return_value="invalid_number"):
            model = run_ollama_wizard()
            assert model == "model-a"

    def test_wizard_decline_download_with_local_models(self):
        with patch("arxmapper.app.ai_engine.is_ollama_installed", return_value=True), \
             patch("arxmapper.app.ai_engine.is_service_running", return_value=True), \
             patch("arxmapper.app.ai_engine.list_local_models", return_value=["existing-model"]), \
             patch("arxmapper.app.Confirm.ask", side_effect=[False, False]):
            model = run_ollama_wizard()
            assert model == "existing-model"

    def test_wizard_decline_download_no_local_models_exits(self):
        with patch("arxmapper.app.ai_engine.is_ollama_installed", return_value=True), \
             patch("arxmapper.app.ai_engine.is_service_running", return_value=True), \
             patch("arxmapper.app.ai_engine.list_local_models", return_value=[]), \
             patch("arxmapper.app.Confirm.ask", return_value=False), \
             pytest.raises(SystemExit) as exc_info:
            run_ollama_wizard()
        assert exc_info.value.code == 1

    def test_wizard_download_recommended_model_success_with_progress(self):
        def fake_pull(model, progress_callback=None):
            if progress_callback:
                progress_callback({"status": "downloading", "completed": 500, "total": 1000})
                progress_callback({"status": "verifying"})
            return True

        with patch("arxmapper.app.ai_engine.is_ollama_installed", return_value=True), \
             patch("arxmapper.app.ai_engine.is_service_running", return_value=True), \
             patch("arxmapper.app.ai_engine.list_local_models", return_value=[]), \
             patch("arxmapper.app.Confirm.ask", return_value=True), \
             patch("arxmapper.app.Prompt.ask", return_value="1"), \
             patch("arxmapper.app.ai_engine.pull_model_sync", side_effect=fake_pull):
            model = run_ollama_wizard()
            assert model == "qwen2.5-coder:1.5b"

    def test_wizard_download_fails_with_fallback(self):
        with patch("arxmapper.app.ai_engine.is_ollama_installed", return_value=True), \
             patch("arxmapper.app.ai_engine.is_service_running", return_value=True), \
             patch("arxmapper.app.ai_engine.list_local_models", return_value=["fallback-model"]), \
             patch("arxmapper.app.Confirm.ask", side_effect=[False, True]), \
             patch("arxmapper.app.Prompt.ask", return_value="1"), \
             patch("arxmapper.app.ai_engine.pull_model_sync", return_value=False):
            model = run_ollama_wizard()
            assert model == "fallback-model"


class TestMainCLI:
    """Pruebas de la función de entrada CLI main()."""

    def test_main_invalid_path_exits(self, tmp_path: Path):
        invalid_path = tmp_path / "non_existent_folder"
        test_args = ["arxmapper", "-p", str(invalid_path)]
        with patch.object(sys, "argv", test_args), \
             pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    def test_main_with_model_and_no_wizard(self, sample_repo: Path):
        test_args = ["arxmapper", "-p", str(sample_repo), "-m", "custom:7b", "--no-wizard"]
        with patch.object(sys, "argv", test_args), \
             patch("arxmapper.app.time.sleep"), \
             patch.object(RepoMapperApp, "run") as mock_run:
            main()
            mock_run.assert_called_once()

    def test_main_no_wizard_uses_available_local_model(self, sample_repo: Path):
        test_args = ["arxmapper", "-p", str(sample_repo), "--no-wizard"]
        with patch.object(sys, "argv", test_args), \
             patch("arxmapper.app.ai_engine.list_local_models", return_value=["local-model:latest"]), \
             patch("arxmapper.app.time.sleep"), \
             patch.object(RepoMapperApp, "run") as mock_run:
            main()
            mock_run.assert_called_once()

    def test_main_triggers_wizard_when_no_flags(self, sample_repo: Path):
        test_args = ["arxmapper", "-p", str(sample_repo)]
        with patch.object(sys, "argv", test_args), \
             patch("arxmapper.app.run_ollama_wizard", return_value="wizard-model:7b") as mock_wiz, \
             patch("arxmapper.app.time.sleep"), \
             patch.object(RepoMapperApp, "run") as mock_run:
            main()
            mock_wiz.assert_called_once()
            mock_run.assert_called_once()

