# QA-qa — Verificación del claim 174/174 y auditoría de la suite (AST-7)

- **Fecha**: 2026-09-25
- **Commit auditado**: `768d3ff` (workspace compartido `bytia-kode`, rama `paperclip/review-2026-09-25`)
- **Método**: suite ejecutada desde el workspace (no se escribió en el repo salvo este informe), `PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider`, `PYTHONPATH=src`, venv efímero en scratch. Todo lo afirmado está citado `ruta:linea` o es salida literal de pytest.

---

## 0. Resumen ejecutivo

| Afirmación | Veredicto |
|---|---|
| `HANDOFF.md:14` → "Tests: 174/174 ✅" | **Stale / falsa hoy.** El número fue exacto en `5fe9c1f` (verificado: *174 passed*), pero hoy se recogen **184** tests y **4 fallan** sin `TYPESAFE_API_KEY`. |
| Suite verde | **NO en entorno limpio**: `4 failed, 180 passed in 2.03s`. Con `TYPESAFE_API_KEY` (aunque sea un valor falso) → `184 passed in 2.01s`. |
| Directorio basura `MagicMock/mock.data_dir.__truediv__()/` | **Causa raíz localizada y reproducida byte a byte**: `tests/test_jeval_guardrail.py:93-98` construye `Agent(MagicMock())` sin `chdir` a `tmp_path`. |
| Contrato de regresión failover (`3a1b9ee`) | **Parcial**: HIGH #2 (router pineable) sí tiene contrato; HIGH #1 (pin implícito / `_provider_sync`) **no tiene ningún test**. |
| Cobertura | **0 tests** para `tui.py` (1281 L), `audio.py` (114 L), `mcp/*` (272 L), `tools/session.py` (104 L). `telegram/bot.py` (233 L) solo con 2 tests. |

---

## 1. Conteo real de la suite

Ejecución literal del comando pedido (adaptado: no existe `/src/BytIA-KODE` en este runtime; el workspace es la copia del mismo commit, por lo que se corrió allí):

```
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -m pytest -p no:cacheprovider -q
```

**Resultado (entorno limpio, sin `TYPESAFE_API_KEY`):**

```
4 failed, 180 passed in 2.03s
```

**Resultado con `TYPESAFE_API_KEY=fake-key`:**

```
184 passed in 2.01s
```

**Desglose (recogidos, `--collect-only`): 184 tests — 0 skipped, 0 xfail, 0 errores de colección.**

| Fichero | Tests |
|---|---|
| `tests/test_agentic_loop.py` | 17 |
| `tests/test_circuit_breaker.py` | 8 |
| `tests/test_context.py` | 11 |
| `tests/test_context_management.py` | 14 |
| `tests/test_exploration_tools.py` | 19 |
| `tests/test_file_edit.py` | 14 |
| `tests/test_herdr.py` | 21 |
| `tests/test_jeval_guardrail.py` | 10 |
| `tests/test_provider_health.py` | 15 |
| `tests/test_session.py` | 29 |
| `src/tests/test_basics.py` | 26 |
| **Total** | **184** |

Duración total del run completo: ~2 s (los 10 tests más lentos están por debajo de 0,1 s).

### El claim 174/174: era cierto, ya no lo es

- `HANDOFF.md:14`: `- **Tests**: 174/174 ✅ (` + "`uv run pytest -q`" + `)`.
- Verificado en el commit previo a JEVAL: checkout de `5fe9c1f` en scratch → **`174 passed in 1.94s`**. El número coincide exactamente.
- `cf66bec` añadió `tests/test_jeval_guardrail.py` (130 líneas nuevas, ver `git show --stat cf66bec`) y `ab6554b` lo extendió. Esos **10 tests** son la diferencia exacta: 174 + 10 = 184.
- Además el claim hoy es **doble-falso**: no solo hay 184, sino que **4 de esos 10 tests nuevos fallan** sin la variable de entorno (ver §5.1). Nadie actualizó `HANDOFF.md` tras `cf66bec`/`ab6554b`.

### Fallos exactos (sin `TYPESAFE_API_KEY`)

Los 4 fallan en `tests/test_jeval_guardrail.py`, siempre por el mismo motivo (gate auto-desactivado):

| Test | Línea | Error literal |
|---|---|---|
| `TestJevalModes::test_shadow_never_blocks_and_is_fire_and_forget` | `tests/test_jeval_guardrail.py:55` | `KeyError: 'task'` |
| `TestJevalModes::test_enforce_blocks_risky` | `tests/test_jeval_guardrail.py:64` | `assert False is True` |
| `TestJevalModes::test_fail_open_on_error` | `tests/test_jeval_guardrail.py:83` | `assert 'fail-open' in 'off'` |
| `TestAgentIntegration::test_enforce_mode_blocks_risky_tool` | `tests/test_jeval_guardrail.py:123` | `assert 1 == 0` |

---

## 2. Matriz de cobertura por módulo

`src/bytia_kode` ≈ 6.315 L (incl. `src/tests`); los tests (~1.994 L en `tests/` + 484 L en `src/tests/test_basics.py`) se reparten así:

| Módulo (L) | Tests que lo cubren | Nivel |
|---|---|---|
| `tui.py` (1281) | **ninguno** — ningún test importa `bytia_kode.tui` | **SIN COBERTURA** |
| `agent.py` (1047) | `test_agentic_loop.py` (17), `test_context_management.py` (14), `test_jeval_guardrail.py` (4 de integración), `test_session.py` (persistencia), `test_exploration_tools.py:185-204` (panic), `src/tests/test_basics.py:405-447` | medio-alto |
| `tools/registry.py` (759) | `test_exploration_tools.py` (19), `test_file_edit.py` (14), `test_agentic_loop.py` (tool errors), `test_context.py:74-82`, `src/tests/test_basics.py:33-62,107-168,373-391` | medio-alto |
| `providers/client.py` (356) | `src/tests/test_basics.py:10-51,64-70` (Message/ToolDef/chat_stream flag); indirecto vía mocks de provider | bajo-medio (sin HTTP real) |
| `skills/loader.py` (332) | `src/tests/test_basics.py:170-353` (7 tests: capas, prioridad, YAML multiline) | medio |
| `session.py` (307) | `test_session.py` (29) | alto |
| `providers/manager.py` (236) | `test_provider_health.py` (15) | medio-alto |
| `telegram/bot.py` (233) | `src/tests/test_basics.py:393-403` (`_is_allowed` con allowlist vacía) y `:449+` (errores internos ocultos) | **bajo** (2 tests; 0 sobre handlers/flujos de mensaje) |
| `config.py` (187) | `src/tests/test_basics.py:355-371` (`extra_binaries`); resto indirecto vía `load_config()`/`AppConfig` | bajo |
| `guardrail.py` (171) | `test_jeval_guardrail.py` (10) | medio (pero **no hermético**, §5.1) |
| `herdr.py` (169) | `test_herdr.py` (21) | medio-alto |
| `context.py` (152) | `test_context.py` (11) | medio-alto |
| `mcp/client.py` (148) | **ninguno** | **SIN COBERTURA** |
| `audio.py` (114) | **ninguno** | **SIN COBERTURA** |
| `tools/session.py` (104) | **ninguno** (`SessionListTool`/`SessionLoadTool`/`SessionSearchTool` no aparecen en ningún test; solo se registran en `src/bytia_kode/agent.py:58-60`) | **SIN COBERTURA** |
| `mcp/config.py` (57) | **ninguno** | **SIN COBERTURA** |
| `providers/circuit.py` (52) | `test_circuit_breaker.py` (8) | alto |
| `mcp/__init__.py` (38), `mcp/tool.py` (29) | **ninguno** | **SIN COBERTURA** |

**Respuesta directa a las preguntas del issue:**
- `tui.py` (1281 L) → **nadie**. Cero referencias a `bytia_kode.tui` en `tests/` ni `src/tests/`.
- `telegram/bot.py` (233 L) → solo `src/tests/test_basics.py:393-403` y `:449-484` (2 tests).
- `audio.py` (114 L) → **nadie**. Cero matches de `audio`/`tts` en la suite.
- `mcp/*` (272 L) → **nadie**. Cero matches de `mcp` en la suite.
- `config.py` (187 L) → parcial e indirecto (`src/tests/test_basics.py:355-371`); sin tests de validación/carga de secretos.
- `skills/loader.py` (332 L) → `src/tests/test_basics.py:170-353` (7 tests), la mejor cubierta de las preguntadas.

---

## 3. Directorio basura `MagicMock/mock.data_dir.__truediv__()/` — causa raíz

**Culpable: `tests/test_jeval_guardrail.py:93-98`** (`TestAgentIntegration._agent`), el único constructor de `Agent` con config mock que **no** hace `monkeypatch.chdir(tmp_path)`.

Cadena causal completa (reproducida):

1. `tests/test_jeval_guardrail.py:94-98`:
   ```python
   def _agent(self, tmp_path):
       cfg = MagicMock()
       cfg.provider = MagicMock()
       cfg.skills_dir = tmp_path / "skills"
       ...
       return Agent(cfg)          # <- sin monkeypatch.chdir(tmp_path)
   ```
2. `src/bytia_kode/agent.py:196-197`: `self._session_store = session_store or SessionStore(config.data_dir / "sessions.db")` — con `cfg` MagicMock, `cfg.data_dir / "sessions.db"` devuelve otro `MagicMock` (magia `__truediv__`).
3. `src/bytia_kode/session.py:108-109`:
   ```python
   self.db_path = Path(db_path)
   self.db_path.parent.mkdir(parents=True, exist_ok=True)
   ```
   `Path(MagicMock)` invoca `os.fspath()`, y el `__fspath__` auto-generado de `MagicMock` devuelve exactamente `MagicMock/mock.data_dir.__truediv__()/<id>`.

**Reproducción literal** (pytest desde un directorio limpio sobre `tests/test_jeval_guardrail.py`):

```
./MagicMock
./MagicMock/mock.data_dir.__truediv__()
./MagicMock/mock.data_dir.__truediv__()/128888860609904
./MagicMock/mock.data_dir.__truediv__()/128888842159840
./MagicMock/mock.data_dir.__truediv__()/128888842172944
```

Un directorio por cada `Agent(cfg)` construido (3 tests de `TestAgentIntegration`), creado **relativo al CWD** — por eso aparece en la raíz del repo al lanzar pytest desde ahí.

**Contraste**: los otros dos fixtures con el mismo patrón sí se protegen — `tests/test_agentic_loop.py:13` y `tests/test_context_management.py:12` hacen `monkeypatch.chdir(tmp_path)` antes de `Agent(cfg)`, así que su basura cae en el tmp de pytest y nadie la ve. `tests/test_jeval_guardrail.py` (añadido en `cf66bec`) es el único que se saltó esa convención.

**Por qué no se pilló**: los 4 tests de ese fichero fallan antes de que la basura moleste (o fallan *por* el mismo mock), y el directorio no está en `.gitignore` (`git status` lo mostraría como untracked al correr desde la raíz).

**Arreglo mínimo sugerido** (no aplicado — este issue es auditoría): añadir `monkeypatch.chdir(tmp_path)` a `_agent` (o pasar `cfg.data_dir = tmp_path`), y opcionalmente blindar `SessionStore.__init__` con un `TypeError` claro si `db_path` no es `str|Path`.

---

## 4. Regresiones del failover (`3a1b9ee`)

`3a1b9ee` arregló 2 bugs HIGH. Estado del contrato de regresión:

| Bug HIGH (según `3a1b9ee`) | ¿Contrato? | Dónde |
|---|---|---|
| **#1 Pin implícito**: `_auto_detect_model` reasignaba `active_provider` → `_on_provider_changed` pineaba el primer motor → failover desactivado. Fix: guard `_provider_sync` (sync display-only; pin solo con F3). | **NO** | El guard vive en `src/bytia_kode/tui.py:456` (`_provider_sync: bool = False`) y `tui.py:552-558` / `tui.py:586-590` / `tui.py:1014-1018`. **Ningún test importa `bytia_kode.tui`** → regresión indetectable. |
| **#2 Router no pineable**: `primary` fuera de `_priority_order` → F3 no lo ofrecía. Fix: `list_pinnable()`. | **SÍ** | `tests/test_provider_health.py:58-62` (`test_list_pinnable_includes_router`: `list_pinnable() == ["unsloth","local","fallback","deepseek","primary"]` y `list_available()` sin `primary`) y `tests/test_provider_health.py:64-69` (`test_pinned_router_is_served_directly`). |

Sobre el test pedido explícitamente, **`test_self_heal_returns_to_chain_head_after_recovery` existe y es un contrato real** — `tests/test_provider_health.py:43-56`:
- tras 3 fallos de `unsloth` → circuito `open` y `get_healthy()[1] == "local"` (`:47-50`);
- simula expiración del half-open (`_last_failure_time -= 61`, `:53`) → el walk **vuelve a la cabeza** (`== "unsloth"`, `:54`);
- `report_success` → circuito `closed` (`:55-56`).

Es un test white-box (manipula `_last_failure_time`, `:53`, y usa `_circuits` internos, `:49`), pero fija exactamente el comportamiento que `HANDOFF.md:15` promete. **Resumen: 1 de los 2 HIGH está protegido; el HIGH del pin implícito no tiene ninguna red de seguridad.**

---

## 5. Calidad de aserciones y mocks

### 5.1 Tests no herméticos — dependen del entorno del ejecutador (hallazgo más serio)

Los tests de JEVAL fijan `JEVAL_MODE` pero **no fijan la API key**. El helper `tests/test_jeval_guardrail.py:19-21` solo hace `monkeypatch.setenv("JEVAL_MODE", mode)`, y `src/bytia_kode/guardrail.py:73-77` auto-desactiva el gate si `_load_key()` devuelve `None`:

```python
self._key = _load_key() if self.mode != "off" else None
if self.mode != "off" and not self._key:
    logger.warning("JEVAL_MODE=%s but no TYPESAFE_API_KEY found -> disabling", ...)
    self.mode = "off"
```

`_load_key` (`guardrail.py:50-60`) mira `TYPESAFE_API_KEY` o `~/.config/typesafe/env`. Solo `test_no_key_disables` (`tests/test_jeval_guardrail.py:84-88`) parchea `_load_key`; los otros 4 tests que necesitan el gate activo **no**. Consecuencia: la suite pasa o falla según el portátil del que la lances — el desarrollador con la key en el shell ve "todo verde" y en CI sin secretos ve 4 rojos. **Esto explica cómo el claim 174/174 pudo publicarse "verde"**.

*Arreglo mínimo*: en `_gate()` poner `monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")` (o `monkeypatch.setattr(guardrail, "_load_key", lambda: "k")`).

### 5.2 Efectos secundarios sobre `$HOME` real (suite no hermética, 2ª parte)

Ejecutar la suite escribe fuera de `tmp_path`, verificado en este runtime tras un run completo:

- `~/.bytia-kode/{sessions.db,skills/,logs/}` — creado por `AppConfig.__post_init__` (`src/bytia_kode/config.py:95-96` default `~/.bytia-kode`, mkdir en `config.py:118-120`) vía `src/tests/test_basics.py:92,409,432` (`Agent(load_config())`) y `:397-401,475-479` (`TelegramBot(AppConfig(...))` → `src/bytia_kode/telegram/bot.py:21` crea `sessions.db`).
- `~/.local/state/jev-router/kode-guardrail.jsonl` — escrito por `guardrail._log` (`src/bytia_kode/guardrail.py:34`, `:81-88`) cada vez que los tests de JEVAL ejercitan `_classify`.

Consecuencias: un CI con home de solo-lectura fallaría tests que "no deberían tocar disco", y dos máquinas con `~/.bytia-kode` distinto pueden dar resultados distintos (p.ej. `skills/` ya poblado cambia el `SkillLoader`).

### 5.3 Test sin ninguna aserción

- `tests/test_herdr.py:144-152` `test_fallo_del_cli_no_propaga`: ejecuta `bridge._process(...)` con `_run = boom` y **no tiene ni un `assert`**. Solo fallaría si se levanta una excepción (smoke test legítimo pero incompleto: no verifica qué devuelve ni qué registra en el log).

El resto (183 tests) tiene `assert` o `pytest.raises`. Los "assert débiles" detectados (`X is True/False`, `not result.error`) son en su mayoría aserciones conductuales correctas (propiedades del breaker, `ToolResult.error`), no ruido.

### 5.4 Densidad de mocks — razonable, con un caso frágil

| Fichero | `MagicMock`/`AsyncMock` | `patch*` | Valoración |
|---|---|---|---|
| `tests/test_agentic_loop.py` | 44 | 1 | Justificado: aisla el loop del provider de red. |
| `tests/test_jeval_guardrail.py` | 8 | 8 | Justificado (evita red), pero el config mock es el culpable de §3. |
| `tests/test_context_management.py` | 8 | 1 | OK. |
| `tests/test_provider_health.py` | 6 | 0 | Casi todo contra objetos reales (`ProviderManager`, circuitos). Bien. |
| Resto | 0–2 | 0–4 | Bien. |

Único caso frágil: `tests/test_provider_health.py:106-111` (`test_unsloth_slot_registered_when_configured`) pasa **porque los atributos de un `MagicMock` son truthy por defecto** (lo admite el propio comentario en `:107`). Si alguien cambiara el fixture a `AppConfig` real sin `unsloth_url`, el test rompería por motivos ajenos al comportamiento probado.

---

## 6. Huecos priorizados

1. **P0 — Suite roja / no hermética (§5.1)**: 4 tests de JEVAL dependen de `TYPESAFE_API_KEY` ambiente. Arreglo de 1 línea en `tests/test_jeval_guardrail.py:19-21`. Sin esto, el "todo verde" de cualquier futura entrega es ambiental, no verificado.
2. **P0 — Basura `MagicMock/mock.data_dir.__truediv__()/` (§3)**: añadir `monkeypatch.chdir(tmp_path)` en `tests/test_jeval_guardrail.py:93`. 1 línea.
3. **P1 — `tui.py` (1281 L, 0 tests)**: es el módulo más grande del repo y contiene el choke point de estados (`ActivityIndicator.set_status`, `HANDOFF.md:28`) y el fix del HIGH #1 de `3a1b9ee` (`_provider_sync`, `tui.py:456`). Cobertura mínima recomendada: extraer `_provider_sync`/`_on_provider_changed` a una unidad testeable y fijar el contrato "el sync reactivo nunca pinea".
4. **P1 — `telegram/bot.py` (233 L, 2 tests)**: sin tests de handlers, dedup de procesado (`bot.py:23-24`), ni aislamiento por chat (`_get_agent`, `bot.py:28-33`).
5. **P2 — `mcp/*` (272 L, 0 tests) y `audio.py` (114 L, 0 tests)**: `mcp/config.py:24-25` parsea `mcp_servers.json` (superficie de config con input de usuario) es el candidato más barato; `audio.py` es TTS/altavoz (recién cambiado en `4b12ca7` — justo lo que convendría tener cubierto).
6. **P2 — `tools/session.py` (104 L, 0 tests)**: las 3 tools de sesión (`SessionListTool`/`SessionLoadTool`/`SessionSearchTool`) solo se registran en `agent.py:58-60`, nunca se ejercitan.
7. **P2 — Hermeticidad de `$HOME` (§5.2)**: fixture de sesión que monkeypatchee `DATA_DIR`/`HOME` para `src/tests/test_basics.py` (`Agent(load_config())` en `:92,409,432`) y para el log de `guardrail`.
8. **P3 — `tests/test_herdr.py:144`**: añadir aserción de resultado/log al test sin asserts.
9. **P3 — Actualizar `HANDOFF.md:14`** con el conteo real del commit actual y matizar el comando (requiere `TYPESAFE_API_KEY` hasta que se arregle P0#1).

---

## 7. Cómo reproducir

```bash
# 1) Conteo real (entorno limpio → 4 failed, 180 passed)
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -p no:cacheprovider -q

# 2) Con la key (→ 184 passed)
TYPESAFE_API_KEY=fake-key PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -p no:cacheprovider -q

# 3) Basura MagicMock (desde un directorio limpio)
cd $(mktemp -d) && PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=<repo>/src python -m pytest -p no:cacheprovider -q <repo>/tests/test_jeval_guardrail.py
ls -R | grep MagicMock

# 4) El claim 174 histórico
git archive 5fe9c1f | tar -x -C <scratch> && cd <scratch> && python -m pytest -p no:cacheprovider -q   # → 174 passed
```

---

## 8. Evidencia adicional (re-auditoría independiente, misma issue)

Una segunda pasada sobre el mismo commit reprodujo todos los hallazgos anteriores y añade lo siguiente.

### 8.1 La basura NO son directorios: son bases SQLite reales fuera de `tmp_path`

Las entradas numéricas de `MagicMock/mock.data_dir.__truediv__()/` son **archivos de 36.864 bytes**, no directorios:

```
d        MagicMock/
d        MagicMock/mock.data_dir.__truediv__()
f  36864  MagicMock/mock.data_dir.__truediv__()/126287907513280
f  36864  MagicMock/mock.data_dir.__truediv__()/126287905920672
f  36864  MagicMock/mock.data_dir.__truediv__()/126287906441936
```

La cadena es más grave de lo que dice §3: `session.py:108-109` crea los dos directorios vía `mkdir(parents=True)`, y después `src/bytia_kode/session.py:114` (`sqlite3.connect(str(self.db_path))`) **escribe una base SQLite real con esquema completo** en el tercer nivel, nombrada con el `id()` del mock. Un solo test → un archivo; los 3 tests de `TestAgentIntegration` → 3 archivos. Con `session.py:118` (`PRAGMA journal_mode=WAL`) además se habría generado `-wal`/`-shm` de no cerrarse limpio.

**Corrección al §3 sobre el arreglo:** `monkeypatch.chdir(tmp_path)` solo *reubica* la basura, no la elimina — los tres fixtures (`test_agentic_loop.py:13`, `test_context_management.py:12`, `test_jeval_guardrail.py:93`) escriben igualmente una SQLite real desde un mock; dos caen en el tmp de pytest y solo uno se ve en la raíz. El arreglo de fondo es **`cfg.data_dir = tmp_path`** (o `AppConfig(data_dir=tmp_path)`, patrón ya correcto en `tests/test_session.py:172`), más un `TypeError` explícito en `SessionStore.__init__` (`session.py:107-109`) si `db_path` no es `str | Path`.

### 8.2 Sonda de mutación: ¿hay tests que siempre pasan?

Se aplicaron 6 mutaciones al código de producto, **verificando que cada una llegaba a aplicarse** y restaurando tras cada prueba (`TYPESAFE_API_KEY=k`, suite completa):

| Mutación | Detectada por |
|---|---|
| `guardrail.py:122` — `blocked = False` (enforce nunca bloquea) | **2** tests |
| `session.py:162` — todo mensaje con `seq_num` 0 | 15 tests |
| `session.py:196` — `ORDER BY seq_num DESC` | 9 tests |
| `providers/circuit.py:34` — el breaker nunca abre | **1** test |
| `providers/manager.py:201` — `get_healthy` ignora el pin | **1** test |
| `skills/loader.py` — prioridad de capas invertida | 13 tests + 28 errores |

**6/6 detectadas → la suite tiene dientes; no hay tests vacíos en el sentido fuerte.** Pero tres zonas son finas: el umbral del circuit breaker y el pin de `get_healthy` se sostienen sobre **un único test cada uno**, y el bloqueo de `guardrail` sobre dos. Esas tres son las primeras candidatas a reforzarse si se refactoriza.

*(Nota de método: una mutación no aplicada por patrón inexistente se descarta como inválida en lugar de contarse como "no detectada" — de ahí verificar la aplicación.)*

### 8.3 Líneas exactas del guard `_provider_sync` (HIGH #1)

Para el contrato de regresión pendiente del §4/§6, el guard está en **`src/bytia_kode/tui.py`**, en 10 sitios y sin un solo test:

| Línea | Uso |
|---|---|
| `tui.py:456` | declaración `_provider_sync: bool = False` + comentario del contrato |
| `tui.py:558` | `_on_provider_changed` — `if self._provider_sync: return` (**el núcleo del fix**) |
| `tui.py:586-590`, `1014-1018`, `1028-1032`, `1108-1112` | los 4 puntos de sync display-only (`try/finally`) |

El test mínimo que faltaría: provocar un cambio de `active_provider` con `_provider_sync = True` y afirmar que `agent.providers.pinned` **no** cambia.
