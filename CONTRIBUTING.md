# Contribuir a BytIA KODE

## Validación obligatoria

```bash
python scripts/validate_metadata.py
python -m pytest -q
python -m build --wheel
python -m twine check dist/*
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
