# 🗺️ Roadmap y Tareas Pendientes de ArxMapper

Este documento recopila el estado actual del proyecto, las mejoras técnicas implementadas y las tareas pendientes priorizadas para versiones posteriores de **ArxMapper CLI**.

---

## ✅ Funcionalidades Implementadas y Validadas

- [x] **Empaquetado modular estándar:** Reestructuración bajo `src/arxmapper/` con soporte de empaquetado PEP 621 en `pyproject.toml` y puntos de entrada (`arxmapper`, `python -m arxmapper`).
- [x] **Conectividad robusta con Ollama:** Normalización automática de variables de entorno (`OLLAMA_HOST`), resolviendo enlaces `0.0.0.0` a destinos válidos de cliente en Windows (`127.0.0.1:11434`), con soporte de IPv4, IPv6 y hosts remotos.
- [x] **Esquema arquitectónico de módulos:** Representación visual basada en nodos con viñetas semánticas (`🏛️ [SISTEMA]`, `◈ [MÓDULO]`, `◆ [PAQUETE]`, `● [COMPONENTE]`, `⚙️ [CONFIG]`, `🧪 [TEST]`, `📝 [DOCS]`).
- [x] **Navegación recursiva sin bloqueos:** Corrección del error de doble toggle en `Tree` mediante `auto_expand = False` y apertura inicial por niveles (profundidad $\le 2$).
- [x] **Ficha arquitectónica de módulo:** Panel interactivo en Markdown que muestra métricas, resumen de composición y desglose de componentes directos al seleccionar directorios.
- [x] **Diseño reactivo y responsivo:** Eliminación de anchos fijos y porcentajes rígidos; uso de proporciones dinámicas (`1fr` y `2fr`) para que los paneles izquierdo y derecho se adapten automáticamente a cualquier ancho de ventana sin cortes ni desbordamientos.
- [x] **Controles globales de árbol:** Atajos `e` (expandir todo), `c` (colapsar todo), `r` (recargar), `t` (alternar tema), `q` (salir).

---

## 📋 Tareas y Mejoras Pendientes

### 🔴 Prioridad Alta (Próxima versión / v0.2.0)

1. **Streaming de respuestas en tiempo real en la TUI**
   - **Descripción:** Actualmente la TUI espera a que Ollama complete toda la respuesta del análisis para renderizar el Markdown.
   - **Objetivo:** Utilizar el modo streaming (`stream=True` en `AsyncClient.chat`) y actualizar progresivamente el panel derecho token a token.
   - **Beneficio:** Menor tiempo percibido de espera (primer token visible en menos de 1 segundo).

2. **Caché local de análisis por hash de archivo (SHA-256)**
   - **Descripción:** Si el usuario selecciona repetidamente el mismo archivo en una sesión o en ejecuciones posteriores, se vuelve a invocar a Ollama.
   - **Objetivo:** Guardar en `.arxmapper/cache/` el hash del contenido del archivo y su análisis generado. Si el archivo no ha cambiado, recuperar la respuesta inmediatamente sin consultar al LLM.

3. **Exportación de documentación arquitectónica**
   - **Descripción:** Posibilidad de guardar los informes generados en el disco.
   - **Objetivo:** Añadir atajo de teclado (ej. `s` / `Ctrl+S`) o flag CLI (`--export docs/`) para exportar:
     - El informe del archivo o módulo actual a Markdown.
     - Un documento consolidado `ARCHITECTURE.md` de todo el proyecto.

4. **Buscador y filtro interactivo en el esquema (Fuzzy Search)**
   - **Descripción:** En repositorios grandes con cientos de archivos, desplazarse por el árbol puede resultar lento.
   - **Objetivo:** Atajo `/` para abrir una barra de búsqueda rápida que filtre nodos y componentes por nombre en tiempo real.

---

### 🟡 Prioridad Media (v0.3.0)

5. **Análisis holístico de módulo completo**
   - **Descripción:** Actualmente las carpetas muestran métricas numéricas y resumen de archivos, pero no un análisis narrativo del rol del módulo completo generado por el LLM.
   - **Objetivo:** Botón o atajo en la ficha de módulo para pedir a Ollama un análisis sintético del paquete combinando las cabeceras de sus archivos internos.

6. **Generación automática de diagramas Mermaid**
   - **Descripción:** Solicitar en el prompt del sistema que Ollama genere un diagrama `mermaid` (diagrama de flujo o secuencia) cuando el archivo implemente lógica entre múltiples clases.
   - **Objetivo:** Renderizado visual o textual compatible con herramientas de previsualización Markdown.

7. **Soporte de archivo de exclusiones personalizadas (`.arxignore`)**
   - **Descripción:** Permitir al usuario definir patrones glob adicionales de exclusión específicos de su proyecto sin modificar `scanner.py`.

8. **Selector interactivo de modelo en caliente dentro de la TUI**
   - **Descripción:** Permitir cambiar de modelo de Ollama desde la propia interfaz con una tecla (ej. `m`), sin tener que salir y relanzar el CLI.

---

### 🟢 Prioridad Baja / Mantenimiento y Calidad

9. **Suite de pruebas unitarias y de integración**
   - **Descripción:** Configurar `pytest` y `pytest-asyncio` con cobertura para `scanner.py`, `ai_engine.py` y `app.py`.
   - **Snapshot testing:** Pruebas visuales de la TUI Textual mediante `run_test()`.

10. **Automatización CI/CD con GitHub Actions**
    - Configurar workflow para linting con `ruff`, comprobación estática con `mypy` y matriz de pruebas en Windows, Linux y macOS.

11. **Publicación y distribución en PyPI**
    - Configurar metadatos finales y automatización para publicar el paquete en PyPI, permitiendo su instalación sencilla con `pip install arxmapper` o `pipx run arxmapper`.
