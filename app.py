"""app.py - Punto de entrada interactivo y TUI de ArxMapper.

Configura la interfaz visual Textual con vista dividida:
- Panel izquierdo: Árbol interactivo del repositorio (scanner.py).
- Panel derecho: Visor Markdown con documentación arquitectónica generada por Ollama (ai_engine.py).

Implementa la regla crítica de Carga Perezosa (Lazy Loading): el árbol arranca
instantáneamente y los archivos se procesan mediante un worker asíncrono
únicamente cuando el usuario los selecciona en la interfaz.
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, DownloadColumn, Progress, TextColumn, TimeRemainingColumn, TransferSpeedColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Footer, Header, Markdown, Static, Tree

import ai_engine
from ai_engine import AIEngine, RECOMMENDED_MODELS
from scanner import RepoScanner


console = Console()

WELCOME_MARKDOWN = """# 🏛️ ArxMapper - Arquitectura con IA Local

Bienvenido al analizador interactivo de arquitectura de repositorios.

### 🚀 Instrucciones de Navegación:
1. **Explora el árbol** en el panel izquierdo utilizando las teclas de dirección `↑` y `↓`.
2. Pulsa `Enter` o haz **click** sobre cualquier carpeta para expandirla o colapsarla.
3. Pulsa `Enter` o haz **click** sobre un archivo para iniciar su **análisis arquitectónico bajo demanda**.

### ⚡ Características:
- **Carga Perezosa (Lazy Loading):** Los archivos solo se envían al modelo local cuando los seleccionas.
- **100% Privado y Gratuito:** El procesamiento se ejecuta íntegramente en tu máquina mediante Ollama.
- **Resúmenes Técnicos:** Cada análisis detalla responsabilidades, dependencias clave y patrones de diseño.

*Selecciona un archivo del panel izquierdo para comenzar.*
"""


class RepoMapperApp(App):
    """Aplicación Textual con vista dividida y carga perezosa para análisis de repositorios."""

    TITLE = "ArxMapper"
    SUB_TITLE = "Analizador de Arquitectura con IA Local"

    CSS = """
    Screen {
        background: $surface;
    }

    #main-container {
        height: 1fr;
        width: 100%;
    }

    #left-pane {
        width: 32%;
        min-width: 28;
        height: 100%;
        border-right: tall $accent;
        background: $panel;
        padding: 0 1;
    }

    #right-pane {
        width: 68%;
        height: 100%;
        background: $surface;
        padding: 1 2;
    }

    #tree-title {
        text-style: bold;
        color: $accent-lighten-2;
        padding: 1 0;
        border-bottom: solid $primary;
    }

    #repo-tree {
        height: 1fr;
        scrollbar-gutter: stable;
        background: $panel;
    }

    #markdown-scroll {
        height: 100%;
        scrollbar-gutter: stable;
    }

    #markdown-content {
        margin: 0;
        padding: 0;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Salir", priority=True),
        Binding("r", "refresh_tree", "Recargar Árbol"),
        Binding("t", "toggle_theme", "Alternar Tema"),
    ]

    def __init__(
        self,
        repo_path: Optional[Path] = None,
        active_model: str = "qwen2.5-coder:7b",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.repo_path = (repo_path or Path.cwd()).resolve()
        self.active_model = active_model
        self.scanner = RepoScanner(root_path=self.repo_path)
        self.ai_engine = AIEngine(model=self.active_model)
        self.sub_title = f"Modelo: {self.active_model} | {self.repo_path.name}"

    def compose(self) -> ComposeResult:
        """Configura la estructura visual de dos paneles."""
        yield Header(show_clock=True)
        with Horizontal(id="main-container"):
            with Vertical(id="left-pane"):
                yield Static(f"📁 {self.repo_path.name}", id="tree-title")
                tree: Tree[Dict[str, Any]] = Tree(f"/{self.repo_path.name}", id="repo-tree")
                tree.show_root = True
                yield tree
            with Vertical(id="right-pane"):
                with VerticalScroll(id="markdown-scroll"):
                    yield Markdown(WELCOME_MARKDOWN, id="markdown-content")
        yield Footer()

    def on_mount(self) -> None:
        """Monta el árbol visual al instante sin llamar al LLM (Lazy Loading estricto)."""
        self.load_tree()

    def load_tree(self) -> None:
        """Carga o recarga la jerarquía de archivos en el componente Tree."""
        tree = self.query_one("#repo-tree", Tree)
        tree.clear()
        tree.root.data = {"path": self.repo_path, "is_dir": True}
        tree.root.label = f"📁 {self.repo_path.name}"
        self.scanner.populate_textual_tree(tree.root, self.repo_path)
        tree.root.expand()

    def action_refresh_tree(self) -> None:
        """Acción de atajo 'r' para recargar el árbol del repositorio."""
        self.load_tree()
        self.notify("Árbol de directorios actualizado.", title="ArxMapper")

    def action_toggle_theme(self) -> None:
        """Acción de atajo 't' para alternar temas visuales."""
        self.theme = "textual-light" if self.theme == "textual-dark" else "textual-dark"

    def on_tree_node_selected(self, event: Tree.NodeSelected[Dict[str, Any]]) -> None:
        """Captura la selección de un nodo en el árbol.

        Si es un directorio: expande o contrae.
        Si es un archivo: activa el análisis perezoso con el LLM.
        """
        node = event.node
        node_data = node.data or {}
        is_dir = node_data.get("is_dir", False)
        target_path: Optional[Path] = node_data.get("path")

        if not target_path:
            return

        if is_dir:
            node.toggle()
            return

        # Es un archivo -> Iniciar flujo de análisis perezoso (Lazy Loading)
        try:
            rel_path = target_path.relative_to(self.repo_path)
        except ValueError:
            rel_path = target_path

        markdown_widget = self.query_one("#markdown-content", Markdown)
        loading_text = (
            f"# ⏳ Generando análisis arquitectónico...\n\n"
            f"> **Archivo seleccionado:** `{rel_path}`  \n"
            f"> **Modelo activo:** `{self.active_model}`  \n\n"
            f"---\n\n"
            f"Leyendo código fuente y enviando consulta al modelo local de Ollama. "
            f"El tiempo de respuesta dependerá de la complejidad del archivo y la velocidad de tu hardware."
        )
        markdown_widget.update(loading_text)

        # Ejecutar análisis en un worker asíncrono para mantener la TUI 100% reactiva
        self.analyze_file_task(target_path, str(rel_path))

    @work(exclusive=True)
    async def analyze_file_task(self, file_path: Path, rel_path: str) -> None:
        """Worker exclusivo en segundo plano que consulta Ollama y actualiza la UI."""
        code, is_truncated = self.scanner.read_file_content(file_path)
        markdown_widget = self.query_one("#markdown-content", Markdown)

        # Llamada asíncrona no bloqueante
        analysis_markdown = await self.ai_engine.analyze_code(
            code=code,
            file_path=rel_path,
            repo_root=str(self.repo_path),
        )

        if is_truncated:
            analysis_markdown += (
                "\n\n---\n"
                "> ℹ️ **Nota:** El archivo supera el umbral de tamaño para análisis seguro. "
                "Se procesó un bloque inicial representativo para no sobrecargar la ventana de contexto."
            )

        # Actualización reactiva del visor Markdown
        markdown_widget.update(analysis_markdown)


# ==============================================================================
# Asistente de Configuración de Ollama (Terminal Onboarding Wizard)
# ==============================================================================

def run_ollama_wizard() -> str:
    """Flujo interactivo previo en terminal para comprobar, instalar y seleccionar modelos Ollama."""
    console.print()
    console.print(
        Panel.fit(
            "[bold cyan]ArxMapper 🏛️[/bold cyan] - Analizador de Arquitectura con IA Local\n"
            "[dim]Verificando entorno Ollama y modelos disponibles...[/dim]",
            border_style="cyan",
        )
    )

    # 1. Comprobar instalación de Ollama
    if not ai_engine.is_ollama_installed():
        console.print("[bold yellow]⚠️ No se detectó una instalación de Ollama en tu sistema.[/bold yellow]")
        want_install = Confirm.ask(
            "¿Deseas intentar instalar Ollama automáticamente ahora con winget?",
            default=True,
        )
        if want_install:
            console.print("[cyan]Iniciando instalación de Ollama mediante winget...[/cyan]")
            success, msg = ai_engine.install_ollama_windows()
            if success:
                console.print(f"[bold green]✓ {msg}[/bold green]")
                console.print("[dim]Iniciando servicio de Ollama...[/dim]")
                ai_engine.start_service_background()
                time.sleep(4)
            else:
                console.print(f"[bold red]✗ No se pudo instalar automáticamente:[/bold red] {msg}")
                console.print("Por favor descarga e instala Ollama manualmente desde: [link=https://ollama.com]https://ollama.com[/link]")
                sys.exit(1)
        else:
            console.print("[red]Ollama es necesario para la ejecución local de IA. Abortando.[/red]")
            sys.exit(1)

    # 2. Comprobar servicio activo
    if not ai_engine.is_service_running():
        console.print("[yellow]El servidor de Ollama no parece estar corriendo. Intentando iniciarlo...[/yellow]")
        ai_engine.start_service_background()
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]Esperando a que Ollama responda...[/cyan]", total=10)
            for _ in range(10):
                time.sleep(1)
                progress.update(task, advance=1)
                if ai_engine.is_service_running():
                    break

        if not ai_engine.is_service_running():
            console.print("[bold red]✗ No se pudo conectar con Ollama en localhost:11434.[/bold red]")
            console.print("Por favor inicia el servicio manualmente ejecutando [bold]ollama serve[/bold] en otra terminal.")
            sys.exit(1)

    console.print("[bold green]✓ Servidor Ollama activo y respondiendo.[/bold green]\n")

    # 3. Listar modelos locales disponibles
    local_models = ai_engine.list_local_models()

    if local_models:
        table = Table(title="📦 Modelos Disponibles en tu Sistema", border_style="green")
        table.add_column("#", justify="center", style="bold cyan")
        table.add_column("Nombre del Modelo", style="bold white")
        for idx, m in enumerate(local_models, start=1):
            table.add_row(str(idx), m)
        console.print(table)
        console.print()

        # Preguntar si desea usar uno local o descargar uno nuevo
        use_existing = Confirm.ask("¿Deseas utilizar uno de tus modelos ya instalados?", default=True)
        if use_existing:
            if len(local_models) == 1:
                chosen_model = local_models[0]
                console.print(f"[green]Seleccionado automáticamente el modelo:[/green] [bold]{chosen_model}[/bold]\n")
                return chosen_model

            choice_str = Prompt.ask(
                f"Selecciona el número del modelo a usar (1-{len(local_models)})",
                default="1",
            )
            try:
                idx = int(choice_str) - 1
                if 0 <= idx < len(local_models):
                    chosen_model = local_models[idx]
                    console.print(f"[green]Modelo seleccionado:[/green] [bold]{chosen_model}[/bold]\n")
                    return chosen_model
            except ValueError:
                pass
            return local_models[0]

    # 4. Catálogo de modelos recomendados para descarga
    console.print("\n[bold cyan]📚 Catálogo de Modelos Recomendados para Análisis de Código:[/bold cyan]\n")
    cat_table = Table(border_style="cyan")
    cat_table.add_column("#", justify="center", style="bold yellow")
    cat_table.add_column("Modelo", style="bold white")
    cat_table.add_column("Tamaño", style="dim")
    cat_table.add_column("Descripción", style="italic")

    for idx, (name, size, desc) in enumerate(RECOMMENDED_MODELS, start=1):
        cat_table.add_row(str(idx), name, size, desc)
    console.print(cat_table)
    console.print()

    want_download = Confirm.ask("¿Deseas descargar uno de estos modelos recomendados?", default=True)
    if not want_download:
        if local_models:
            return local_models[0]
        console.print("[bold red]Es indispensable contar con al menos un modelo para operar. Abortando.[/bold red]")
        sys.exit(1)

    sel_idx_str = Prompt.ask(
        f"Elige el número de modelo a descargar (1-{len(RECOMMENDED_MODELS)})",
        default="1",
    )
    try:
        idx = int(sel_idx_str) - 1
        model_to_pull = RECOMMENDED_MODELS[idx][0]
    except (ValueError, IndexError):
        model_to_pull = RECOMMENDED_MODELS[0][0]

    console.print(f"\n[bold cyan]Iniciando descarga de {model_to_pull}...[/bold cyan]")

    # Descarga interactiva con Progress
    with Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        download_task = progress.add_task(f"Descargando {model_to_pull}", total=None)

        def on_progress(chunk: Dict[str, Any]) -> None:
            status = chunk.get("status", "")
            completed = chunk.get("completed", 0)
            total = chunk.get("total", 0)
            if total > 0:
                progress.update(download_task, completed=completed, total=total, description=f"{status}: {model_to_pull}")
            elif status:
                progress.update(download_task, description=f"{status}")

        success = ai_engine.pull_model_sync(model_to_pull, progress_callback=on_progress)

    if success:
        console.print(f"[bold green]✓ Modelo {model_to_pull} descargado con éxito.[/bold green]\n")
        return model_to_pull
    else:
        console.print(f"[bold red]✗ Falló la descarga de {model_to_pull}.[/bold red]")
        if local_models:
            console.print(f"[yellow]Utilizando modelo existente como alternativa: {local_models[0]}[/yellow]")
            return local_models[0]
        sys.exit(1)


# ==============================================================================
# Función Principal
# ==============================================================================

def main() -> None:
    """Punto de entrada CLI de la aplicación."""
    parser = argparse.ArgumentParser(
        description="ArxMapper - Herramienta TUI interactiva para análisis de arquitectura de repositorios con Ollama."
    )
    parser.add_argument(
        "-p", "--path",
        type=str,
        default=".",
        help="Ruta al directorio del repositorio a explorar (por defecto: directorio actual).",
    )
    parser.add_argument(
        "-m", "--model",
        type=str,
        default="",
        help="Nombre del modelo Ollama a utilizar (omite el asistente si ya está disponible).",
    )
    parser.add_argument(
        "--no-wizard",
        action="store_true",
        help="Inicia directamente la TUI sin el asistente previo de comprobación de Ollama.",
    )

    args = parser.parse_args()
    target_repo = Path(args.path).resolve()

    if not target_repo.exists() or not target_repo.is_dir():
        console.print(f"[bold red]Error:[/bold red] La ruta especificada no es un directorio válido: {target_repo}")
        sys.exit(1)

    chosen_model = args.model
    if not chosen_model and not args.no_wizard:
        chosen_model = run_ollama_wizard()
    elif not chosen_model:
        # Modo rápido: elegir el primer modelo disponible o fallback
        available = ai_engine.list_local_models()
        chosen_model = available[0] if available else "qwen2.5-coder:7b"

    console.print(f"[cyan]Iniciando TUI para [bold]{target_repo}[/bold] con modelo [bold]{chosen_model}[/bold]...[/cyan]")
    time.sleep(1)

    app = RepoMapperApp(repo_path=target_repo, active_model=chosen_model)
    app.run()


if __name__ == "__main__":
    main()
