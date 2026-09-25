# AST-8 — Auditoría de packaging, CI y dependencias de BytIA-KODE

**Rol:** BytIA DevOps · **Fecha:** 2026-09-25 · **Commit auditado:** `768d3ff` (rama `paperclip/review-2026-09-25`)

---

## 0. Método y entorno

- Todo lo que se afirma abajo está leído en el árbol, con cita `ruta:línea`. Nada inferido.
- **El código fuente NO se tocó.** El runner no expone `/src/BytIA-KODE` (`ls: No such file or directory`), así que la auditoría se hizo sobre el checkout de escritorio `/paperclip/instances/default/workspaces/bytia-kode` en **solo lectura** para los experimentos: el venv sandbox y la copia del repo viven en `$PAPERCLIP_SCRATCH_DIR` (`/tmp/paperclip-run-ast-8-…`), nunca en el checkout.
- Reproducciones que ejecutan código (build, tests, `pip install`) corrieron siempre sobre la **copia** `$SCRATCH/repo`, con `PYTHONDONTWRITEBYTECODE=1` y `pytest -p no:cacheprovider`.
- El runner no trae `pip`, `uv` ni `ensurepip` (`python3 -m pip → No module named pip`, `import ensurepip → ModuleNotFoundError`), por eso el venv se creó con `python3 -m venv --without-pip` + `get-pip.py`.

---

## 1. Resumen ejecutivo

| # | Sev. | Defecto | Evidencia clave |
|---|------|---------|-----------------|
| D1 | **P0** | La suite está **roja en cualquier entorno sin `TYPESAFE_API_KEY`** → la CI falla en cada push | `guardrail.py:73-76`, `test_jeval_guardrail.py:19-21` |
| D2 | **P0** | `pip install bytia-kode[mcp]` deja el subpaquete **`bytia_kode.mcp` importable cero** (`manager.py` no existe) y el wheel lo publica | `mcp/__init__.py:15-16`, `CHANGELOG.md:40` |
| D3 | P1 | `pyproject.toml` declara la dependencia **muerta `edge-tts`** y no documenta las binarias reales (`bytia-tts`, `piper`) | `pyproject.toml:31`, `audio.py:63` |
| D4 | P1 | `[project.scripts]` ignora `argv` → **`bytia-kode --bot` roto por binario** | `pyproject.toml:50`, `tui.py:1275` |
| D5 | P1 | `install.sh` instala un wrapper que **también ignora `argv`**, pero el instalador *anuncia* `bytia-kode --bot` | `install.sh:168`, `install.sh:200` |
| D6 | P1 | `install.sh` **aborta con stdin cerrado** (`set -e` + `read` sin condición) | `install.sh:2`, `install.sh:147` |
| D7 | P2 | CI sin lint, sin coverage, sin matriz de Python, sin sdist, sin smoke-test de extras, sin `check_secrets.py` | `.github/workflows/ci.yml` |
| D8 | P2 | **Tests no herméticos**: la suite crea `MagicMock/…` con ficheros SQLite **dentro del repo** | `session.py:108-114`, `agent.py:197` |
| D9 | P2 | Versión↔docs desincronizadas (`0.8.0a1` vs `0.7.8`) | `pyproject.toml:3` vs `ROADMAP.md:3`, `README.md:10,42` |
| D10 | P2 | `uv.lock` **coherente con `pyproject`**, pero ambos **obsoletos respecto al código** | `uv.lock:227-239`, `16407a0` vs `4b12ca7` |
| D11 | P3 | Los *hatch excludes* de `pyproject.toml:65-72` apuntan a **ficheros que no existen** | `find`/`git ls-files` → 0 |
| D12 | P3 | Duplicación `dev` (extra vs dependency-group), sin workflow de release, sin `dependabot.yml` | `pyproject.toml:40-44` vs `57-63` |

---

## 2. D2 — Bug latente MCP reproducido (comando + traceback)

### 2.1 Causa

`src/bytia_kode/mcp/__init__.py:15-16`:

```python
if _MCP_AVAILABLE:
    from bytia_kode.mcp.manager import McpManager
```

El flag `_MCP_AVAILABLE` se pone a `True` en `mcp/__init__.py:7-10` si `from mcp.client.stdio import stdio_client` funciona. Es decir: **instalar el extra `[mcp]` es exactamente lo que activa el import roto.**

`ls src/bytia_kode/mcp/` → `__init__.py`, `client.py`, `config.py`, `tool.py`. **No hay `manager.py`.**

Está reconocido como pendiente en `CHANGELOG.md:38-40`:

```
### Pending (próxima sesión)
- `mcp/manager.py` — lifecycle manager
```

…pero `HANDOFF.md:61` ya lo describe como hecho («MCP (v0.8.0a1): `mcp/manager.py` lifecycle, wiring bootstrap en agent+tui»), y el módulo sigue sin existir.

### 2.2 Reproducción (ejecutada, sandbox propio)

```bash
S="$PAPERCLIP_SCRATCH_DIR"
python3 -m venv --without-pip "$S/venv"
curl -fsSL https://bootstrap.pypa.io/get-pip.py -o "$S/get-pip.py"
"$S/venv/bin/python" "$S/get-pip.py" -q

# copia del repo para no ensuciar el checkout
tar -C <workspace> --exclude=.git -cf - . | tar -C "$S/repo" -xf -

"$S/venv/bin/python" -m pip install -e "$S/repo[mcp]"
"$S/venv/bin/python" -c "import bytia_kode.mcp"
```

`pip install` → `Successfully built bytia-kode` / `Successfully installed … mcp-1.30.0 … bytia-kode-0.8.0a1` (**exit 0**).

```text
Traceback (most recent call last):
  File "<string>", line 1, in <module>
    import bytia_kode.mcp
  File "/tmp/paperclip-run-ast-8-41962dab-71f-qaliuj/repo/src/bytia_kode/mcp/__init__.py", line 16, in <module>
    from bytia_kode.mcp.manager import McpManager
ModuleNotFoundError: No module named 'bytia_kode.mcp.manager'
```

| Comando | Exit |
|---|---|
| `python -c "import bytia_kode.mcp"` | **1** |
| `python -c "import bytia_kode"` → `ok 0.8.0a1` | 0 |
| `python -c "import mcp, mcp.client.stdio"` | 0 |

### 2.3 Alcance

- **Se publica.** Wheel construido en el sandbox: `bytia_kode-0.8.0a1-py3-none-any.whl`, 41 entradas. Contiene `bytia_kode/mcp/__init__.py`, `client.py`, `config.py`, `tool.py` y **no** `manager.py`. Cualquier usuario que instale el extra cae en el mismo traceback.
- **`bytia_kode.mcp.client` y `.tool` también revientan**: Python ejecuta `mcp/__init__.py` antes que el submódulo. `mcp/tool.py:3` y `mcp/client.py:13` importan entre sí dentro de ese paquete.
- **Hoy es latente, no activo**: `grep -rn "mcp" src/ tests/` fuera de `src/bytia_kode/mcp/` → **0 resultados**. Ni `agent.py` ni `tui.py` ni ningún test lo tocan.
- **La CI no puede cazarlo**: `.github/workflows/ci.yml:21` instala `pip install -e ".[dev]"` — sin `[mcp]` — y ningún paso importa `bytia_kode.mcp`.

---

## 3. D1 — La suite está roja sin `TYPESAFE_API_KEY` (CI rojo)

### 3.1 Causa

`src/bytia_kode/guardrail.py:73-76`:

```python
self._key = _load_key() if self.mode != "off" else None
if self.mode != "off" and not self._key:
    logger.warning("JEVAL_MODE=%s but no TYPESAFE_API_KEY found -> disabling", self.mode)
    self.mode = "off"
```

`_load_key()` (`guardrail.py:50-60`) mira `os.getenv("TYPESAFE_API_KEY")` y, si falla, `~/.config/typesafe/env`.

El fixture de test `tests/test_jeval_guardrail.py:19-21` solo hace:

```python
def _gate(mode, monkeypatch):
    monkeypatch.setenv("JEVAL_MODE", mode)
    return guardrail.JevalGate()
```

**Nunca fija la key** → el gate se apaga solo → los tests que esperan bloqueo fallan.

### 3.2 Evidencia (ejecutada, sandbox)

```
$ $venv/bin/python -m pytest -q -p no:cacheprovider            # sin TYPESAFE_API_KEY
4 failed, 180 passed in 2.05s          # 184 tests coleccionados, exit 1
FAILED tests/test_jeval_guardrail.py::TestJevalModes::test_shadow_never_blocks_and_is_fire_and_forget
FAILED tests/test_jeval_guardrail.py::TestJevalModes::test_enforce_blocks_risky
FAILED tests/test_jeval_guardrail.py::TestJevalModes::test_fail_open_on_error
FAILED tests/test_jeval_guardrail.py::TestAgentIntegration::test_enforce_mode_blocks_risky_tool

$ TYPESAFE_API_KEY=dummy $venv/bin/python -m pytest -q -p no:cacheprovider tests/test_jeval_guardrail.py
10 passed, exit 0
```

El warning capturado lo confirma: `JEVAL_MODE=enforce but no TYPESAFE_API_KEY found -> disabling` (`guardrail.py:75`).

### 3.3 Consecuencia

- `.github/workflows/ci.yml` **no define `env:`** (`grep -n "env:\|TYPESAFE\|secrets\." .github/workflows/ci.yml` → sin resultados) → el paso *Run tests* (`ci.yml:24-25`) **falla en cada push** desde `cf66bec`/`ab6554b` (guardrail JEVAL).
- En la máquina del autor pasa porque `~/.config/typesafe/env` existe (`guardrail.py:54-59`), lo que explica `HANDOFF.md:14` («Tests: 174/174 ✅») — hoy son **184 tests: 180 passed + 4 failed**.
- El hook local `.githooks/pre-commit:8` ejecuta los mismos tests → mismo fallo en clones limpios.

---

## 4. D3 — `pyproject.toml`: dependencia muerta y dependencias reales ausentes

### 4.1 `edge-tts>=7.2.8` es peso muerto

- `pyproject.toml:31` → `"edge-tts>=7.2.8"`.
- `src/bytia_kode/audio.py:63` lanza el binario `"bytia-tts"`; `audio.py:71` («Habla el texto con bytia-tts (piper local)»).
- `grep -rn "edge_tts|edge-tts" src/` → **solo** el comentario histórico `audio.py:3` («la era WSL usaba `edge-tts`»). Ningún `import edge_tts` en el paquete.
- Migración en `4b12ca7` (2026-09-21). **Última vez que se tocó `pyproject.toml`/`uv.lock`: `16407a0` (2026-09-15)** → el packaging no se actualizó tras la migración.

### 4.2 Lo que sí se necesita, no está declarado ni documentado

- `bytia-tts` **no está en PyPI** → `https://pypi.org/pypi/bytia-tts/json` → **HTTP 404**. No puede ser una dependencia de `pip`; hay que tratarla como binario externo.
- `piper` (voz `es_AR-daniela-high`) — requerido por `bytia-tts`, según `audio.py:38` («PATH con `~/.local/bin` garantizado (`bytia-tts` llama a `piper` sin ruta)») y `audio.py:5-6`.
- `grep -rn "bytia-tts" pyproject.toml install.sh README.md` → **0 resultados**.
- `README.md:490` sigue listando `[mpv]` como dependencia de sistema y `README.md:132`/`README.md:237` siguen describiendo «`es-MX-DaliaNeural` … con mpv» y «`audio.py ← TTS: edge-tts + mpv`» — obsoleto desde `4b12ca7`.

### 4.3 Fallo silencioso

`audio.py:82-86` captura cualquier excepción de lanzamiento y hace `logger.error(...); return None`. Con una instalación limpia (sin `bytia-tts`), el botón 🔊 **no hace nada y no avisa al usuario**.

---

## 5. D4 — `[project.scripts]` ignora `argv`

- `pyproject.toml:50` → `bytia-kode = "bytia_kode.tui:run_tui"`.
- `src/bytia_kode/tui.py:1275-1277` → `def run_tui():` sin parámetros; `grep -c "sys.argv" src/bytia_kode/tui.py` → **0**.
- `src/bytia_kode/tui.py:1280-1281` → `if __name__ == "__main__": run_tui()`.
- El wheel lo confirma: `entry_points.txt` → `bytia-kode = bytia_kode.tui:run_tui`.
- La vía `python -m bytia_kode` sí enruta: `src/bytia_kode/__main__.py:4-9` comprueba `sys.argv[1] == "--bot"`.
- Documentado en `HANDOFF.md:76-78` («el binario del venv (`bytia-kode`) apunta a `tui:run_tui` e IGNORA argv (por eso `--help` lanza la TUI)»).
- `README.md:189` usa la vía correcta (`uv run python -m bytia_kode --bot`); `README.md:174` y `README.md:188` usan el binario (válido solo sin argumentos).

---

## 6. D5 — `install.sh` instala un wrapper roto y aun así anuncia `--bot`

`install.sh:164-169` escribe `~/.local/bin/bytia-kode`:

```bash
cat > "$BIN_DIR/bytia-kode" << WRAPPER
#!/usr/bin/env bash
set -euo pipefail
cd "$INSTALL_DIR"
exec uv run python -m bytia_kode.tui "$@"
WRAPPER
```

`python -m bytia_kode.tui --bot` ejecuta `tui.py` como `__main__` → `tui.py:1280-1281` llama `run_tui()` **sin leer argv** → se lanza la TUI.

Pero `install.sh:200` imprime: `bytia-kode --bot    Start Telegram bot`. **Promesa incumplida.**

Además `HANDOFF.md:19` describe el lanzador como «wrapper bash → `.venv/bin/bytia-kode`», que no coincide con lo que `install.sh:168` escribe realmente.

**Fix de una línea:** `install.sh:168` → `exec uv run python -m bytia_kode "$@"`.

### 6.1 D6 — El instalador aborta con stdin cerrado

- `install.sh:2` → `set -euo pipefail`.
- `install.sh:139` → `if [ -d "$HOME/bytia/skills" ]; then` … `install.sh:147` → `read -p "  Create symlink to ~/bytia/skills? [y/N]: " BYTIA_LINK`.

Ese `read` **no está en contexto de condición**, así que `set -e` mata el script.

Repro con el mismo constructo y `</dev/null`:

```bash
bash -c 'set -euo pipefail
if [ -d /usr ]; then
  read -p "  Create symlink? [y/N]: " BYTIA_LINK
  echo "after read: $BYTIA_LINK"
fi
echo "DONE"' </dev/null ; echo "exit=$?"
# → exit=1  (no imprime "after read" ni "DONE")
```

Falla en `curl | bash`, CI y cualquier no-tty **siempre que exista `~/bytia/skills`**, y mata el resto del instalador (`install.sh:162-211`: wrapper, PATH, hooks, resumen).

### 6.2 Otras notas de `install.sh`

- `install.sh:42` → `curl -fsSL … | sh` (pipe de script remoto a shell).
- `install.sh:73` → `uv sync --quiet`: sin `--extra`, sin comprobación de binarias (`bytia-tts`/`piper`), e instala por defecto el *dependency group* `dev` (`pyproject.toml:56-63`: `pytest`, `build`, `twine`, `textual-dev`) en el entorno del usuario final.
- `install.sh:65` clona `main` sin tag → instala código «EN PROGRESO», no la última release (última tag: `v0.7.8`; `git tag | wc -l` → 9, ninguna `v0.8.0a1`).
- `install.sh:199` promete alias `bkode` pero no lo crea (solo lo sugiere).

---

## 7. D7 — CI: qué valida y qué falta

### 7.1 Qué valida hoy (`.github/workflows/ci.yml`, único workflow)

| Paso | Línea | Qué hace (verificado) |
|---|---|---|
| Install deps | `ci.yml:18-21` | `pip install -e ".[dev]" build twine pytest` (el extra `dev` es `pyproject.toml:40-44`; `build`/`twine` van aparte porque solo están en el dependency-group `pyproject.toml:57-63`) |
| Validate metadata | `ci.yml:22-23` | `scripts/validate_metadata.py` → autores (`:19-20`), versión no vacía (`:21-22`), YAML de identidad (`:23-24`), README contiene `uv run bytia-kode` (`:27-28`), CHANGELOG contiene `## [version]` (`:30-32`), cero temporales `*.bak|*.backup.*|fix_*.py|patch_*.py` (`:34-37`). **Ejecutado: `metadata validation OK`** |
| Run tests | `ci.yml:24-25` | `python -m pytest -q` → **hoy: 4 failed / 180 passed (§3)** |
| Build wheel | `ci.yml:26-27` | `python -m build --wheel` → **OK, wheel 105 033 bytes, 41 entradas** |
| Twine check | `ci.yml:28-29` | `python -m twine check dist/*` → **PASSED** |
| Verify packaged resource | `ci.yml:30-51` | Crea un venv limpio, instala el wheel y comprueba `bytia_kode.prompts/kernel.default.yaml` vía `importlib.resources` |

Comprobado además: el wheel **sí** incluye `bytia_kode/tui.css`, `prompts/*.yaml` y `vendor/skills/**`, y **no** incluye `tests/` (solo `packages = ["src/bytia_kode"]`, `pyproject.toml:74-75`).

`scripts/check_secrets.py` → `secret scan OK`, pero **no está en CI**: solo en `.githooks/pre-commit:7`.

### 7.2 Qué falta

1. **Lint.** `grep tool.ruff|tool.black|tool.mypy|tool.coverage pyproject.toml` → nada; `find` por `.ruff.toml`, `.flake8`, `setup.cfg`, `tox.ini`, `.pre-commit-config.yaml`, `mypy.ini` → **0 ficheros**.
2. **Coverage.** Sin `pytest-cov`, sin `.coveragerc`, sin umbral.
3. **Matriz de Python.** `ci.yml:17` fija `python-version: '3.11'`, pero `pyproject.toml:17-19` declara 3.11/3.12/3.13 y `pyproject.toml:8` exige `>=3.11`. Nunca se prueba 3.12/3.13.
4. **sdist.** `ci.yml:27` solo `--wheel` → `twine check dist/*` solo revisa el wheel; el sdist (que es lo que instala `pip install git+…`/PyPI source) no se construye ni se valida.
5. **Smoke-test de extras.** No se instala `[mcp]`, `[local]`, `[memory]` ni se importa `bytia_kode.mcp` → **D2 es invisible para CI**.
6. **`check_secrets.py`** existe y pasa, pero no corre en CI.
7. **Docs.** No hay build de docs: `find` por `mkdocs.yml`/`conf.py` → 0; `docs/` es Markdown suelto. Tendría sentido añadir un link-check (`lychee` / `markdown-link-check`), no un build.
8. **Supply chain.** `ci.yml:14-15` usan `actions/checkout@v4` y `actions/setup-python@v5` por tag, no por SHA; `ci.yml:3-5` `on: push` sin filtro de rama (corre en todas las ramas).
9. **Release.** `.github/workflows/` solo contiene `ci.yml` → no hay publicación automática, pese a `build`+`twine` en `pyproject.toml:60-61` y `README.md:181`.
10. **Dependabot.** No existe `.github/dependabot.yml` (aunque `16407a0` habla de «cerrar las 36 alertas de Dependabot»).

---

## 8. D10 — `uv.lock` (576 306 bytes)

**Consistente con `pyproject.toml`:**

| Campo | `pyproject.toml` | `uv.lock` |
|---|---|---|
| versión | `0.8.0a1` (`:3`) | `0.8.0a1` (`uv.lock:228`) |
| `requires-python` | `>=3.11` (`:8`) | `>=3.11` (`uv.lock:3`) |
| dependencias | 8 (`:23-32`) | 8 idénticas incl. `edge-tts` (`uv.lock:230-239`) |
| extras | `dev/local/mcp/memory` (`:39-47`) | `provides-extras = ["dev", "local", "mcp", "memory"]` |
| dependency-group `dev` | `:56-63` | `[package.metadata.requires-dev] dev` idéntico |
| requires-dist | — | coincide 1:1 con especificadores y markers |

Versiones fijadas relevantes: `mcp 1.30.0` (`uv.lock:1166`), `edge-tts 7.2.8` (`uv.lock:637`).

**Pero:** el lock está al día respecto a `pyproject`, y **ambos están obsoletos respecto al código** (ver §4.1): `edge-tts` sigue declarado y fijado seis días después de que `4b12ca7` lo dejara sin uso.

**Riesgo de drift (D12):** `dev` está definido **dos veces con contenido distinto** — extra en `pyproject.toml:40-44` (`pytest`, `pytest-asyncio`, `textual-dev`) y dependency-group en `pyproject.toml:57-63` (los mismos + `build`, `twine`). `pip install ".[dev]"` (CI, `ci.yml:21`) usa el extra; `uv sync` (`install.sh:73`) usa el group. Pueden desviarse sin que nada lo detecte.

---

## 9. D9 — Consistencia versión ↔ docs

| Fuente | Valor | ¿OK? |
|---|---|---|
| `pyproject.toml:3` | `0.8.0a1` | referencia |
| `uv.lock:228` | `0.8.0a1` | OK |
| `CHANGELOG.md:3` | `## [0.8.0a1] - 2026-05-24 (EN PROGRESO)` | OK (es lo que exige `validate_metadata.py:31`) |
| `HANDOFF.md:13` | `0.8.0a1` | OK |
| `docs/ARCHITECTURE.md:3` | `0.8.0a1` | OK |
| `bytia_kode.__version__` (runtime) | `0.8.0a1` | OK — `__init__.py:22` usa `importlib.metadata`, `__init__.py:24` cae a leer `pyproject` |
| **`ROADMAP.md:3`** | **`## Estado actual: v0.7.8 (Alpha estable)`** | **DESAFASE** |
| **`README.md:10`** | badge `release-0.7.8` | **DESAFASE** |
| **`README.md:42`** | «Release actual: `0.7.8`» | **DESAFASE** |
| `HANDOFF.md:14` | «Tests: 174/174 ✅» | **DESAFASE** (hoy 184: 180 pass + 4 fail) |
| `README.md:132,237,490` | edge-tts + mpv | **OBSOLETO** desde `4b12ca7` |

Por qué el CI no lo ve: `scripts/validate_metadata.py:27-28` solo exige que el README contenga la cadena literal `uv run bytia-kode` — **no valida el badge ni la versión del README**.

Tags: `git tag` → 9 (`v0.5.3` … `v0.7.8`), **ninguna de `0.8.0a1`** → `pyproject` está adelantado respecto a lo publicado.

---

## 10. D11 — Hatch excludes apuntan a ficheros inexistentes

`pyproject.toml:65-72`:

```toml
[tool.hatch.build]
exclude = [
    "src/bytia_kode/*.backup.*",
    "src/bytia_kode/**/*.backup.*",
    "src/bytia_kode/*.bak",
    "src/bytia_kode/**/*.bak",
    "src/bytia_kode/agent_new.py",
]
```

Comprobado sobre el árbol:

```bash
find . -path ./.git -prune -o -type f \( -name 'agent_new.py' -o -name '*.backup.*' -o -name '*.bak' \) -print
# → (vacío)

git ls-files | grep -E 'agent_new|\.backup\.|\.bak$'
# → (vacío)
```

**No existe ninguno**, ni trackeado ni sin trackear. La regla es muerta (inofensiva). `scripts/validate_metadata.py:11,34-37` vigila además `*.bak`, `*.backup.*`, `fix_*.py`, `patch_*.py` a todo el repo — también sin coincidencias hoy. El wheel construido no los contiene (41 entradas, ninguna de esas).

---

## 11. D8 — Los tests ensucian el working tree del repo

### 11.1 Evidencia

Tras cualquier `pytest`, el árbol queda con un directorio **sin trackear** `MagicMock/` (no está en `.gitignore`):

```text
MagicMock/mock.data_dir.__truediv__()/138477722887104   (fichero SQLite)
MagicMock/mock.data_dir.__truediv__()/138477721214256   (fichero SQLite)
MagicMock/mock.data_dir.__truediv__()/138477721213584   (fichero SQLite)
```

Bisect fichero a fichero en el sandbox (`rm -rf MagicMock` antes de cada uno):

```text
POLLUTA: tests/test_jeval_guardrail.py      (único)
```

### 11.2 Cadena causal

1. `tests/test_jeval_guardrail.py:94-98` construye `cfg = MagicMock()` y solo fija `cfg.provider` y `cfg.skills_dir` → **`cfg.data_dir` es un `MagicMock`**.
2. `src/bytia_kode/agent.py:197` → `config.data_dir / "sessions.db"` → devuelve un `MagicMock`.
3. `src/bytia_kode/session.py:108` → `self.db_path = Path(db_path)`. `str()` de ese mock da `MagicMock/mock.data_dir.__truediv__()/138477722887104`.
4. `src/bytia_kode/session.py:109` → `self.db_path.parent.mkdir(parents=True, exist_ok=True)` → crea el directorio **en el cwd del repo**.
5. `src/bytia_kode/session.py:114` → `sqlite3.connect(str(self.db_path))` → crea el fichero SQLite de verdad.

Repro mínimo de los pasos 3-4 (ejecutado):

```python
cfg = MagicMock(); db = cfg.data_dir / "sessions.db"
p = Path(db); print(str(p))        # MagicMock/mock.data_dir.__truediv__()/129919280584016
p.parent.mkdir(parents=True, exist_ok=True)   # crea ./MagicMock/… en el cwd
```

### 11.3 Consecuencias

- `git status` deja de estar limpio tras cada suite → rompe flujos que asumen árbol limpio.
- No está cubierto por `.gitignore` (revisado: no hay entrada `MagicMock/`).
- Es un síntoma de que **`SessionStore` no valida su `db_path`** (`session.py:107-110` acepta cualquier cosa Path-able y la materializa).

*(Nota: se observó un `MagicMock/` aparecer en el checkout compartido a las 19:02 UTC, en paralelo a la ejecución concurrente de [AST-9](/AST/issues/AST-9); no se borró para no interferir con esa run.)*

---

## 12. Plan de fix priorizado

### P0 — desbloquear CI y la publicación

1. **Hacer hermético el gate JEVAL en tests** — `tests/test_jeval_guardrail.py:19-21`: añadir `monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")` dentro de `_gate()` (o inyectar la key en `JevalGate`), de modo que los 4 tests pasen **sin** red ni secretos. Alternativa: añadir un modo `JevalGate` sintético. *Verifica:* `pytest -q` → `184 passed` en entorno sin la variable.
2. **Cerrar D2** — una de dos en `src/bytia_kode/mcp/__init__.py:15-16`:
   - (a) implementar `mcp/manager.py` (lo promete `HANDOFF.md:61`), o
   - (b) envolver el import en `try/except ModuleNotFoundError` y caer al stub de `mcp/__init__.py:19-38`, marcando `[mcp]` como experimental en `CHANGELOG.md:40`.
   Mientras tanto, no documentar `[mcp]` como funcional.
3. **Añadir smoke-test de extras a CI** — paso nuevo en `.github/workflows/ci.yml` tras el wheel: crear venv, `pip install "dist/*.whl[mcp]"` y `python -c "import bytia_kode.mcp"`. Sin esto, (2) regresará sin que nadie lo vea.

### P1 — corrección de packaging

4. **Quitar `edge-tts>=7.2.8`** de `pyproject.toml:31` y regenerar `uv lock` (mantiene `uv.lock:231` y `uv.lock:637` al día).
5. **Preflight de binarias** — `bytia-tts` (404 en PyPI, no es instalable vía pip) y `piper`:
   - comprobación en `install.sh` con mensaje claro antes de `uv sync` (`install.sh:72-74`);
   - sección «Requisitos de voz» en `README.md` sustituyendo lo de `README.md:132,237,490`;
   - opcional: degradar explícitamente en `audio.py:82-86` (hoy silencioso).
6. **Arreglar el entry point** — `pyproject.toml:50`: apuntar a un `main()` que reenvíe `argv` (p.ej. reutilizar la lógica de `src/bytia_kode/__main__.py:4-9`) en lugar de `bytia_kode.tui:run_tui`.
7. **Arreglar el wrapper de `install.sh`** — `install.sh:168` → `exec uv run python -m bytia_kode "$@"`; mantener `install.sh:200` ya que entonces será cierto. Sincronizar `HANDOFF.md:19`.
8. **Tolerar stdin cerrado** — `install.sh:147` → `read -r -p "…" BYTIA_LINK || BYTIA_LINK=n`.

### P2 — calidad de CI

9. **Lint**: añadir `ruff` (config en `pyproject.toml`) + paso en CI. Hoy no hay ni config ni paso.
10. **Coverage**: `pytest-cov` con umbral declarado + badge/informe.
11. **Matriz 3.11/3.12/3.13** en `ci.yml:17` (coherente con `pyproject.toml:17-19`).
12. **sdist + twine check completo**: `python -m build` (sdist y wheel) en `ci.yml:27`.
13. **Mover `scripts/check_secrets.py` a CI** (ya existe y pasa; solo está en `.githooks/pre-commit:7`).
14. **Link-check de docs** (`docs/` es Markdown puro, no hay build posible).
15. **Hardening**: pin de actions por SHA (`ci.yml:14-15`), `on.push` acotado a ramas (`ci.yml:3-5`).

### P2 — consistencia de docs/config

16. **Versiones**: `ROADMAP.md:3`, `README.md:10` y `README.md:42` → `0.8.0a1`; `HANDOFF.md:14` → 184 tests.
17. **TTS en docs**: `README.md:132`, `README.md:237`, `README.md:490` → `bytia-tts` + `piper`; eliminar `mpv` si ya no se usa.
18. **`.env.example`**: documentar `JEVAL_MODE`, `JEVAL_THRESHOLD`, `JEVAL_TIMEOUT` y `TYPESAFE_API_KEY` (hoy `grep JEVAL|TYPESAFE .env.example README.md docs/DEVELOPMENT.md` → 0), incluida la ruta alternativa `~/.config/typesafe/env` de `guardrail.py:54`.
19. **Endurecer `validate_metadata.py:27-28`** para que compare la versión del badge/README contra `pyproject.toml:3` — así D9 no vuelve a pasar en silencio.
20. **Unificar `dev`**: elegir extra (`pyproject.toml:40-44`) *o* dependency-group (`pyproject.toml:56-63`) como única fuente de verdad.

### P3 — higiene

21. **Hatch excludes** (`pyproject.toml:65-72`): eliminarlos o documentarlos como red de seguridad — hoy no excluyen nada porque los ficheros no existen (§10).
22. **Test pollution**: corregir el fixture de `tests/test_jeval_guardrail.py:94-98` (fijar `cfg.data_dir = tmp_path / "data"`) y, mientras tanto, añadir `MagicMock/` a `.gitignore`. Reforzar `session.py:107-110` validando el `db_path`.
23. **Workflow de release** a PyPI y **`.github/dependabot.yml`** (no existen; `.github/workflows/` solo tiene `ci.yml`).

---

## 13. Anexo — comandos ejecutados

```bash
# entorno
ls /src/BytIA-KODE                       # No such file or directory
command -v uv virtualenv pip pip3        # (vacío)
python3 -m pip --version                 # No module named pip
python3 -c "import ensurepip"            # ModuleNotFoundError

# D2
"$S/venv/bin/python" -m pip install -e "$S/repo[mcp]"     # exit 0, mcp-1.30.0
"$S/venv/bin/python" -c "import bytia_kode.mcp"           # exit 1, ModuleNotFoundError (ver §2.2)
"$S/venv/bin/python" -c "import bytia_kode"               # exit 0, ok 0.8.0a1

# D1
"$S/venv/bin/python" -m pytest -q -p no:cacheprovider     # 4 failed, 180 passed (184), exit 1
TYPESAFE_API_KEY=dummy "$S/venv/bin/python" -m pytest -q -p no:cacheprovider \
    tests/test_jeval_guardrail.py                          # 10 passed, exit 0

# build (ambos OK)
"$S/venv/bin/python" -m build --wheel                      # bytia_kode-0.8.0a1-py3-none-any.whl, 105033 B, 41 entradas
"$S/venv/bin/python" -m twine check dist/*                 # PASSED

# CI local
python3 scripts/validate_metadata.py                       # metadata validation OK
python3 scripts/check_secrets.py                           # secret scan OK

# D8 (bisect)
for f in tests/*.py src/tests/*.py; do rm -rf MagicMock; pytest "$f"; [ -d MagicMock ] && echo "POLLUTA: $f"; done
# → POLLUTA: tests/test_jeval_guardrail.py

# deps externas
curl -s https://pypi.org/pypi/bytia-tts/json                # HTTP 404
git tag                                                      # 9 tags, última v0.7.8
```
