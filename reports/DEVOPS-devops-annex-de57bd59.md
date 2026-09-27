## Anexo: pasada independiente de verificación (2ª ejecución DevOps)

**Contexto de coordinación — léelo primero.** Hay dos ejecuciones simultáneas de *BytIA DevOps* sobre AST-8:

| run | issue vinculada | rol |
|---|---|---|
| `41962dab-71fc-4101-8596-6666f530b1eb` | AST-8 (**checkout activo**) | dueña del entregable: `reports/DEVOPS-devops.md` + comentario final + estado |
| `de57bd59-224e-4891-94f5-36f9356fee36` (esta) | ninguna | verificación estática independiente |

Yo **no escribo `reports/DEVOPS-devops.md` ni cambio el estado** de la issue — eso es del run con el checkout, para no pisar su fichero ni abrir una carrera de estados. Todo lo que sigue es material para **fusionar en su informe**. Si algo contradice su síntesis, manda la suya. La issue queda **`in_progress`** con camino de continuación vivo (el run con checkout).

---

### 1. Bug MCP latente — REPRODUCIDO

`src/bytia_kode/mcp/__init__.py`:
```
15: if _MCP_AVAILABLE:
16:     from bytia_kode.mcp.manager import McpManager
```
`src/bytia_kode/mcp/` sólo contiene `__init__.py`, `client.py`, `config.py`, `tool.py` → **no existe `manager.py`**.

La importación está **dentro** del `if`, así que *sólo* explota cuando el extra `[mcp]` está instalado (`pyproject.toml:46` → `mcp>=1.28.1,<2`). Sin el extra, `_MCP_AVAILABLE=False` y se usa el stub de `:19`.

**Comando y traceback** (repro aislado de dependencias en scratch propio, con el SDK `mcp` simulado — NO toco `/src` ni el repo; la instalación `pip install -e '…[mcp]'` completa la está haciendo el run con checkout para no duplicar un venv de cientos de MB):

```python
# scratch/repro_mcp.py — ejecutado con PYTHONDONTWRITEBYTECODE=1
parent = types.ModuleType("bytia_kode")
parent.__path__ = ["…/workspace/bytia-kode/src/bytia_kode"]   # evita bytia_kode/__init__ (requiere httpx)
sys.modules["bytia_kode"] = parent
# stub de "mcp.client.stdio.stdio_client" → exactamente lo que mcp/__init__.py:8 importa
import bytia_kode.mcp
```

```
Traceback (most recent call last):
  File "scratch/repro_mcp.py", line 26, in <module>
    import bytia_kode.mcp
  File "…/src/bytia_kode/mcp/__init__.py", line 16, in <module>
    from bytia_kode.mcp.manager import McpManager
ModuleNotFoundError: No module named 'bytia_kode.mcp.manager'
mcp SDK importable (stubbed): OK -> _MCP_AVAILABLE will be True
bytia_kode/mcp/manager.py exists: False
REPRODUCED
```

**Control sin SDK** (simula instalación base): `import bytia_kode.mcp` → `OK, McpManager stub … | _MCP_AVAILABLE: False`. Es decir: el extra `[mcp]` **invierte** el comportamiento y lo rompe.

**Alcance real (matiz importante):**
- `grep -rn "mcp" src/bytia_kode/agent.py src/bytia_kode/tools/ tests/` → **vacío**. Nada importa `bytia_kode.mcp`: la feature está **sin cablear** (el propio `docs/ARCHITECTURE.md:277` la lista como `mcp/manager.py — lifecycle manager (pendiente)`).
- `docs/ARCHITECTURE.md:328` sólo documenta el caso "SDK no instalado → stub"; **el caso instalado está roto y no está documentado**.
- Cero tests cubren el extra `[mcp]` → por eso la CI sale verde.

### 2. `edge-tts` es peso muerto — confirmado

- `pyproject.toml:31` → `edge-tts>=7.2.8` en `dependencies`.
- `grep -rn "edge_tts" src/ tests/` → **cero apariciones** (no hay import en ningún sitio). Único `edge-tts` en código: prosa en `src/bytia_kode/audio.py:3` (docstring: "la era WSL usaba `edge-tts`").
- `uv.lock` lo arrastra: entrada `[[package]] name = "bytia-kode"` → `dependencies` incluye `{ name = "edge-tts" }`.

Consecuencia: cada instalación arrastra una **dependencia de red** (edge-tts habla con Azure TTS) que el producto ya no usa → coste, superficie de red y ruido en auditoría de dependencias.

### 3. Dependencias runtime NO declaradas — confirmado

- `audio.py:71` invoca `bytia-tts` (piper local); `audio.py:38` fuerza `~/.local/bin` en PATH porque "bytia-tts llama a `piper` sin ruta"; `audio.py:4` menciona `mpv`.
- Presencia en packaging: `bytia-tts` → **no** en `pyproject.toml`, **no** en `uv.lock`; `piper` → ninguno de los dos; `mpv` → ninguno de los dos.
- Consecuencia: `uv sync` / `pip install bytia-kode` termina **OK con el altavoz roto** — fallo silencioso en runtime, no en instalación.

### 4. `bytia-kode --bot` roto por DOS rutas de entrada

| ruta | fichero | ¿respeta `--bot`? |
|---|---|---|
| console script `bytia-kode` | `pyproject.toml:50` → `bytia_kode.tui:run_tui` (`tui.py:1275`, sin argv) | **NO** |
| wrapper de `install.sh` | `install.sh:168` → `python -m bytia_kode.tui "$@"` (`tui.py:1280` corre `run_tui()`) | **NO** |
| `python -m bytia_kode` | `src/bytia_kode/__main__.py:4` → `sys.argv[1] == "--bot"` | **SÍ** |

Ya reconocido en `HANDOFF.md:77-78` y con workaround en `README.md:189`. Pero `README.md:188` sigue enseñando `uv run bytia-kode` como mando principal y **`install.sh:200` anuncia `bytia-kode --bot` como si funcionara** — anuncio falso dentro del propio instalador.

### 5. Consistencia versión ↔ docs

| sitio | valor | ¿ok? |
|---|---|---|
| `pyproject.toml:3` | `0.8.0a1` | base |
| `uv.lock` (paquete `bytia-kode`) | `0.8.0a1` | ✅ |
| `CHANGELOG.md:3` | `## [0.8.0a1] - 2026-05-24 (EN PROGRESO)` | ✅ |
| `ROADMAP.md:3` | `Estado actual: v0.7.8 (Alpha estable)` | ❌ |
| `README.md:10` badge / `README.md:42` | `release-0.7.8` / `Release actual: 0.7.8` | ❌ |
| `git tag` (último) | `v0.7.8` — no existe `v0.8.0a1` | ❌ |
| `src/bytia_kode/__init__.py:18` | fallback hardcodeado `"0.3.0"` | ❌ |

**Matiz sobre el enunciado de la issue:** `__init__.py` **no fija** la versión. Usa `importlib.metadata.version("bytia-kode")` (`:22`) con fallback a leer `pyproject.toml` (`:10-18`). El único valor obsoleto es el fallback `"0.3.0"`, visible sólo si el paquete no está instalado y no hay `pyproject` (p.ej. dentro de un wheel instalado sin fuentes). Menos grave de lo que sugiere la issue, pero sigue siendo un número muerto.

**Por qué la CI no lo ve:** `scripts/validate_metadata.py:31` sólo exige que `CHANGELOG.md` contenga `## [{version}]` (pasa). No valida README, ROADMAP ni tags → la deriva pasa en verde.

### 6. Excludes de hatch: configuración muerta

`pyproject.toml:65-72` excluye `src/bytia_kode/*.backup.*`, `*.bak` y `agent_new.py`.
`find $R \( -name agent_new.py -o -name '*.backup.*' -o -name '*.bak' \)` → **cero coincidencias**. Son restos de ficheros ya borrados.

Además han **divergido**: `scripts/validate_metadata.py:11` usa `["*.bak", "*.backup.*", "fix_*.py", "patch_*.py"]` — patrones distintos y **sin** `agent_new.py`. Dos listados de "ficheros prohibidos" que ya no concuerdan.

### 7. CI (`.github/workflows/ci.yml`) — qué valida y qué falta

**Sí valida:** `pip install -e ".[dev]" build twine pytest` (`:21`) → `scripts/validate_metadata.py` (`:23`) → `pytest -q` (`:25`) → `python -m build --wheel` (`:27`) → `twine check dist/*` (`:29`) → **smoke del recurso empaquetado en venv limpio** (`:31-50`). Este último paso es lo mejor del fichero: instala el wheel real y comprueba `prompts/kernel.default.yaml`.

**Falta:**
1. **Sin lint**: ni `ruff`/`black`/`flake8`/`mypy` en `pyproject.toml`, ni `.ruff.toml`/`.flake8`/`.pre-commit-config.yaml` en el árbol. `.githooks/pre-commit` tampoco linta.
2. **Sin coverage** (ni tool, ni threshold, ni report).
3. **Sin build de docs** (no hay mkdocs/sphinx en el repo).
4. **Matrix de un solo Python**: `ci.yml:17` = `3.11`, pero `pyproject.toml:17-19` declara 3.11/3.12/3.13 y `requires-python = ">=3.11"` (`:8`). **3.12 y 3.13 nunca se prueban.**
5. **`uv.lock` no se valida en CI**: la CI usa `pip install -e` (`:21`), nunca `uv sync --locked` / `uv lock --check`. Un lock desincronizado pasaría verde.
6. **`scripts/check_secrets.py` no está en CI** — sólo en `.githooks/pre-commit:13`. Quien no ejecute `git config core.hooksPath .githooks` (`README.md:449`) no escanea secretos en absoluto. El escaneo de secretos es opt-in local.
7. **Sólo wheel**: `python -m build --wheel` (`:27`) → `twine check` nunca revisa un sdist; no existe job de publicación de release.
8. Sin `concurrency`/cancelación de runs duplicados ni path filters: `on: push` + `pull_request` (`:4-5`) duplica ejecuciones en PRs.

### 8. `uv.lock` (576 KB): consistente… con un `pyproject` defectuoso

- Entrada `bytia-kode`: `version = "0.8.0a1"`, `dependencies` = exactamente las 8 de `pyproject.toml:23-32`, `[package.optional-dependencies]` = `dev/local/mcp/memory` y `[package.dev-dependencies] dev` = `pyproject.toml:56-63`. `requires-python = ">=3.11"` = `pyproject.toml:8`. → **sincronizado, sin drift.**
- El problema **no es el lock**: es que es fiel a un `pyproject` que arrastra `edge-tts` (§2) y no declara `bytia-tts`/`piper` (§3).
- **Duplicidad de grupo dev:** `[project.optional-dependencies] dev` (`pyproject.toml:40-44`) y `[dependency-groups] dev` (`:56-63`) se llaman igual y **difieren** (éste añade `build>=1.4.2` y `twine>=6.2.0`). `pip install -e ".[dev]"` (CI) usa el primero, `uv sync` (`install.sh:73`) usa el segundo → por eso la CI repite `build twine` a mano en `ci.yml:21`.

### 9. `install.sh` (7,4 KB)

**Qué instala:** deps git/uv/python3 (`:35-53`) → clone o `git pull --ff-only` (`:57-67`) → `uv sync --quiet` (`:73`) → `.env` desde `.env.example` (`:78-104`) → skills vendor (`:110-135`) → wrapper en `~/.local/bin` (`:162-171`) → `core.hooksPath .githooks` (`:186-189`).

**Fallos:**
1. `install.sh:168` → `exec uv run python -m bytia_kode.tui "$@"` ignora argv ⇒ **`install.sh:200` anuncia un `bytia-kode --bot` que no funciona** (§4).
2. `install.sh:164-171` escribe `~/.local/bin/bytia-kode`, que en la mayoría de setups **se interpone al console-script** de igual nombre instalado por pip/uv → dos binarios distintos compitiendo por el mismo nombre, y además el wrapper hace `cd "$INSTALL_DIR"` fijo (`:167`), atando la ejecución al clon.
3. `install.sh:73` `uv sync --quiet` **sin `--extra`** → no instala `[mcp]`, `[local]` ni `[memory]`. **Ningún camino del installer habilita el extra MCP.**
4. `install.sh:147` `read -p` bajo `set -euo pipefail` (`:2`): en un shell no interactivo (`CI`, `curl | sh`) `read` devuelve ≠0 en EOF y **aborta el script en mitad de la instalación**. Sólo se alcanza si existe `~/bytia/skills` (`:139`), pero es un fallo real de robustez.
5. `install.sh:124` renombra a `*.backup.<timestamp>` y `:127` hace `rm -rf "$dest"` sobre el destino ya movido → esos backups **se acumulan indefinidamente** en `~/.bytia-kode/skills/vendor/`.
6. `install.sh:42` `curl … | sh` sin checksum ni versión fijada; `:61` un `git pull` fallido degrada a aviso y la instalación sigue **desactualizada en verde**.

### 10. Despliegue: no existe en el repo (ángulo fuera de la lista del issue)

- `find` por `Dockerfile*`, `docker-compose*`, `*.service`, `Procfile`, `fly.toml`, `render.yaml`, `Makefile` → **cero resultados**.
- Pero `HANDOFF.md:74-75` documenta un servicio **real en producción**: `bytia-kode-telegram.service` (systemd user, `Linger`, "activo y polleando"). **El fichero del unit no está en el árbol.**
- Consecuencia: la "cadena de despliegue" del proyecto es `git clone` + `install.sh` + un unit que vive sólo en la máquina del operador. **No es reproducible desde el repositorio**, y un `install.sh:61` fallido no lo detecta. Tampoco hay job de release ni tag `v0.8.0a1`.

### 11. Deriva de recuento de tests (señal cruzada a AST-7)

`README.md:11` badge `tests-145 passing` vs `README.md:57` "los 144 tests". Ambos desfasados del 174/174 que audita AST-7. Tres números distintos en dos ficheros.

---

## Plan de fix priorizado (para que el informe con checkout lo adopte)

**P0 — rompe al usuario final**
1. `pyproject.toml:50` → punto de entrada que respete argv: extraer el dispatch de `__main__.py` a un `main()` y apuntar `bytia-kode = "bytia_kode.__main__:main"`.
2. `install.sh:168` → `exec uv run python -m bytia_kode "$@"`; y alinear `README.md:188`.
3. **MCP**: hoy publicar `pyproject.toml:46` `[mcp]` sólo garantiza un `ModuleNotFoundError`. Corto: **no publicar el extra** hasta que exista `mcp/manager.py`. *No* envolver la línea 16 en `try/except ImportError` — dejaría un `McpManager` stub **con el SDK instalado**, que aparenta funcionar y es peor que el error.
4. Declarar runtime: quitar `edge-tts` (`pyproject.toml:31`) y añadir `bytia-tts`; documentar `piper`/`mpv` como prerequisitos de SO con chequeo en `install.sh`.

**P1 — la CI es ciega justo donde duele**
5. Añadir lint (ruff) + `uv lock --check` + matrix `3.11/3.12/3.13` + `scripts/check_secrets.py` + `python -m build` (sdist **y** wheel).
6. Test de regresión `import bytia_kode.mcp` **con** el SDK presente: fallaría hoy y es exactamente la red que falta.

**P2 — higiene**
7. Versiones: badge `README.md:10`, línea `README.md:42`, `ROADMAP.md:3`, tag `v0.8.0a1`, fallback `__init__.py:18`.
8. Borrar los excludes muertos (`pyproject.toml:65-72`) o sincronizarlos con `scripts/validate_metadata.py:11`.
9. Commitar `bytia-kode-telegram.service` (o documentar de dónde se obtiene).
10. Fusionar `[project.optional-dependencies] dev` y `[dependency-groups] dev`.

---

**Estado de esta ejecución:** `de57bd59…` queda **sin deliverable de fichero a propósito** (ver cabecera). AST-8 → **`in_progress`**, dueño del cierre = run con checkout `41962dab…`.
