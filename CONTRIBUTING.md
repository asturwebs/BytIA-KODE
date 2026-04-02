# Contribuir a BytIA KODE

## Validación obligatoria

```bash
uv run python scripts/validate_metadata.py
uv run pytest -q
uv run python -m build --wheel
uv run python -m twine check dist/*
```

## Hook local versionado

```bash
git config core.hooksPath .githooks
```

## Criterios

- Cambios pequeños y verificables.
- Documentación sincronizada con el comportamiento real.
- Sin secretos ni credenciales en el repositorio.
- Sin archivos temporales, backups ni scripts de parcheo.
