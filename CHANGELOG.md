# Changelog

Todos los cambios relevantes del proyecto se documentan en este archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/) y [Semantic Versioning](https://semver.org/lang/es/).

## [Unreleased]

- Sin cambios publicados todavía después de `0.3.0`.

## [0.3.0] - 2026-04-02
### v0.3.0 - Arquitectura Constitucional Modular y Empaquetado de Recursos

### Added
- Directorio `src/bytia_kode/prompts/` con la identidad constitucional `core_identity.yaml`.
- Subpaquete `bytia_kode.prompts` para distribuir recursos internos del proyecto.
- Script `scripts/validate_metadata.py` para validar versión, autoría, documentación y limpieza mínima.
- Hook versionado en `.githooks/pre-commit`.
- Workflow de GitHub Actions para validación, tests, build y verificación del wheel.
- Código de conducta del proyecto.

### Changed
- Refactor completo de `agent.py` para cargar la identidad con `importlib.resources`.
- Metadatos del paquete alineados en `pyproject.toml` con versión `0.3.0`.
- README reescrito para documentar instalación oficial por wheel y formato YAML de identidad.
- Documentación técnica actualizada para reflejar la arquitectura modular y el empaquetado de recursos.
- `.gitignore` reforzado para evitar reintroducción de backups y scripts de parcheo temporales.

### Fixed
- Eliminación de advertencias `Duplicate name` durante la construcción del wheel.
- Corrección de errores recientes en el manejo del prompt multilinea de la TUI.
- Corrección de la carga del system prompt para que funcione tanto en editable como en wheel instalado.

### Validation
- `pytest` pasando en modo editable.
- `pytest` pasando sobre el wheel instalado en entorno limpio.
- `python -m build --wheel` completado sin warnings duplicados.
- `python -m twine check dist/*` completado correctamente.

### Cleanup
- Eliminación de backups, scripts temporales `fix_*` y `patch_*`, y directorios efímeros de pruebas.
- Depuración del árbol del paquete para publicación y mantenimiento futuro.
