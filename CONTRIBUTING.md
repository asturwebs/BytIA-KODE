# Contribuir a BytIA KODE

Consulta [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) para la guía completa: estructura del proyecto, cómo crear tools y skills, testing, build y release.

## Resumen rápido

```bash
uv run pytest -q                          # Tests
uv run python scripts/validate_metadata.py # Metadata check
uv build                                   # Build wheel
uv pip install ./dist/*.whl --force-reinstall  # Instalar
```

Hook de pre-commit:

```bash
git config core.hooksPath .githooks
```

## Criterios

- Cambios pequeños y verificables.
- Documentación sincronizada con el comportamiento real.
- Sin secretos ni credenciales en el repositorio.
- Sin archivos temporales, backups ni scripts de parcheo.
