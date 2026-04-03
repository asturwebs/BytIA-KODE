# Changelog

Todos los cambios relevantes del proyecto se documentan en este archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/) y [Semantic Versioning](https://semver.org/lang/es/).

## [Unreleased]

### Changed

- Banner ASCII actualizado a "B KODE" con crédito "by AsturWebs & BytIA".
- Colores del banner y session info panel ahora son dinámicos, adaptándose al tema activo.
- Borde del banner dinámico (cambia con el tema).
- Añadidos 3 temas claros: `catppuccin-latte`, `solarized-light`, `rose-pine-dawn` (total: 9 temas).
- Tema por defecto cambiado de `monokai` a `gruvbox`.

### Added

- Atajo `F2` para cambiar de tema cíclicamente (con `priority=True` para WSL).
- Método `_get_theme_colors()` para extraer colores del tema activo.
- Método `_render_banner()` para inyección dinámica de color en el banner.
- `watch_theme()` actualiza banner e info panel en tiempo real al cambiar tema.
- Persistencia del tema seleccionado en `~/.bytia-kode/theme.json`.
- Bordes de mensajes de chat (user, assistant, tool, error) reaccionan en tiempo real al cambiar tema.

### Added

- `F3` para cambiar entre providers configurados (primary → fallback → local → primary).
- Comando `/models` para listar modelos disponibles del provider activo (Ollama/llama.cpp).
- Comando `/use <model>` para seleccionar un modelo del provider activo.
- `ProviderClient.list_models()` — consulta Ollama `/api/tags` y fallback a `/v1/models`.
- `ProviderManager.list_available()` y `set_model()` para switching en runtime.
- TUI usa `active_provider` para routing de chat (antes hardcodeado a "primary").

## [0.3.0] - 2026-04-02

### Added

- Directorio `src/bytia_kode/prompts/` con la identidad constitucional `core_identity.yaml`.
- Subpaquete `bytia_kode.prompts` para distribuir recursos internos del proyecto.
- Script `scripts/validate_metadata.py` para validar versión, autoría, documentación y limpieza mínima.
- Script `scripts/check_secrets.py` para escaneo de secrets en pre-commit.
- Script `scripts/benchmark_io.py` para benchmark comparativo secuencial vs concurrente.
- Hook versionado en `.githooks/pre-commit` con validación, secret scan y tests.
- Workflow de GitHub Actions para validación, tests, build y verificación del wheel.
- Sección de seguridad y rendimiento en auditoría profesional.

### Changed

- Refactor completo de `agent.py` para cargar la identidad con `importlib.resources`.
- Extracción de `_handle_tool_calls()` desde `chat()` para mejorar legibilidad.
- BashTool migrado a `asyncio.create_subprocess_exec` (I/O no bloqueante).
- FileReadTool y FileWriteTool migrados a `asyncio.to_thread` para I/O de disco.
- Input sanitizado: `_sanitize_user_message()` filtra caracteres no imprimibles.
- Error recovery: `chat()` captura `TimeoutError`, `ConnectionError`, `RuntimeError`, `httpx.HTTPError` y preserva historial.
- Memoria con carga estricta (error en JSON corrupto) y contexto acotado (20 entries / 2000 chars).
- Telegram en modo fail-secure (denegar por defecto sin allowlist).
- Errores internos ocultos al usuario de Telegram (solo en logs).
- Metadatos del paquete alineados en `pyproject.toml` con versión `0.3.0`.

### Security

- **SEC-001**: Mitigado — BashTool con allowlist de binarios, `shell=False`, `shlex.split()`.
- **SEC-002/003**: Mitigado — `_resolve_workspace_path()` impide path traversal.
- **SEC-005**: Mitigado — Telegram fail-secure por defecto.

### Performance

- Motor I/O asíncrono validado con benchmark: **4.90x speedup** (79.6% mejora) en ejecución concurrente vs secuencial.

### Fixed

- Eliminación de advertencias `Duplicate name` durante la construcción del wheel.
- Corrección de errores en el manejo del prompt multilinea de la TUI.
- Corrección de la carga del system prompt para editable y wheel instalado.
- `python3` añadido al allowlist de BashTool (`sys.executable` resuelve a `python3`).
- Eliminación de imports y logger duplicados en `registry.py`.

### Validation

- 17 tests pasando.
- Pre-commit hook: validación de metadatos + secret scan + pytest.
- `uv build` completado sin warnings.
