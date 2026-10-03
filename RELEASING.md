# RELEASING — cómo se publica BytIA-KODE

> El proceso real. Se aprendió publicando v0.8.0 a mano (AST-21) y se
> automatizó con Trusted Publishers/OIDC en v0.8.1 (AST-22/AST-23).
> Cero secretos en el repo: el publish se autentica por OIDC.

## El flujo (canónico, estrenado en v0.8.1)

### 1. Preparación (en main, antes de taggear)

- `CHANGELOG.md`: entrada `## [X.Y.Z] - YYYY-MM-DD` (la entrada `## [Unreleased]` se convierte; no se reescribe el histórico).
- `pyproject.toml` **y** `uv.lock` bumpados a `X.Y.Z` — el lock arrastra su propia entrada `version` y el residuo rompe el gate (lección AST-21).
- README/badges al día. Los badges dinámicos (PyPI, CI) no requieren toque; cualquiera hardcodeado es drift.
- Gates verdes **en el commit final** (skill gates-de-entrega): suite completa, `scripts/validate_metadata.py`, `scripts/check_readme_claims.py`, `scripts/check_report_citations.py`, secret scan. Un gate corrido antes del último cambio es un gate no corrido.

### 2. Tag

```bash
git tag vX.Y.Z
git push origin vX.Y.Z
```

El tag dispara `.github/workflows/release.yml` (sólo tags `v*`, nunca branches).

### 3. Gates + build (job `build`)

Secret scan full-tree → `validate_metadata.py` (falla si README/CHANGELOG/pyproject divergan) → `check_readme_claims.py` (gate de claims del README, fail cerrado) → `check_report_citations.py` (gate de citas SHA de `reports/`, fail cerrado) → suite → `uv build` → `twine check`. Sobre `ci.yml` también corre en el tag (`on: push` incluye tags).

### 4. PROD GATE — aprobación del Socio (job `publish`)

El job `publish` corre en el GitHub **environment `pypi`**, que tiene required reviewer. GitHub pausa ahí hasta que el Socio aprueba con un clic en la UI (Actions → run → jobs → Review deployments). Sin aprobación, no hay publish. Éste es el homólogo GitHub del `prod-go` del Socio.

### 5. OIDC → PyPI

`pypa/gh-action-pypi-publish` intercambia el token OIDC del runner por un token de publicación corto (Trusted Publisher registrado en PyPI: owner `asturwebs`, repo `BytIA-KODE`, workflow `release.yml`, environment `pypi`). No hay token persistente en el repo ni en GitHub Settings.

> **Fail-closed por diseño**: si el Trusted Publisher no está registrado, el intercambio OIDC falla y no se publica nada. Eso ES la validación de que no publica por accidente.

### 6. GitHub Release (job `github-release`)

Tras publicar, el job crea la **GitHub Release del tag** con las notas **extraídas de `CHANGELOG.md`** (sección `## [X.Y.Z]`). Fuente única de verdad: nada de notas escritas a mano ni PR-lists de GitHub. Si el CHANGELOG no tiene la entrada del tag, el job falla antes de crear una Release vacía.

> Contexto: v0.7.8 siguió de "Latest" cinco horas después de publicar 0.8.0 porque la Release se creaba a mano. Desde v0.8.1 nace sola.

### 7. Verificación post-publish

- [ ] `pip install bytia-kode==X.Y.Z` en un venv limpio funciona.
- [ ] `bytia-kode --version` imprime `X.Y.Z` (+ build id si el build estampó commit).
- [ ] `~/.bytia-kode/skills/vendor/.vendor-version` contiene `X.Y.Z` (auto-reseed de skills vendor detectó la nueva versión).
- [ ] La ficha de PyPI (https://pypi.org/project/bytia-kode/) renderiza el README nuevo.
- [ ] La GitHub Release del tag existe y sus notas son la entrada del CHANGELOG.

## Camino manual de emergencia (el de v0.8.0)

Sólo si OIDC no está disponible. Requiere un API token del Socio (never stored en el repo):

```bash
uv build && uvx twine check dist/*
uvx twine upload dist/* --verbose   # pide credenciales por prompt
```

Después: **rotar o borrar el token usado**. PyPI no admite re-subir la misma versión — un fix obliga a `X.Y.Z+1`.

## Reglas

- **El publish lo aprueba el Socio** (environment `pypi`). Ninguna automatización publica sin ese clic.
- **CHANGELOG es la única fuente de notas** — la GitHub Release no se edita a mano.
- **Un tag se publica una vez.** PyPI es inmutable por versión.
- **No se taggea desde el clone de trabajo sin remote**: el bundle lo aplica el Socio en el repo real (ver HANDOFF.md).
