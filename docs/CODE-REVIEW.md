# Code Review — BytIA-KODE v0.7.7

**Fecha:** 2026-04-30
**Revisor:** BytIA (Hermes Agent)
**Commit:** `v0.7.7-2-g3576cb4`
**Tests:** 144 passing / 0 failing

---

## Resumen ejecutivo

Arquitectura sólida con decisiones correctas en los puntos que importan (seguridad, threading SQLite, circuit breaker, stream handling). Tech debt mínima pero presente: la TUI a 46KB y una allowlist bash incompleta son los únicos flags reales. El resto son observations para tener en el radar.

**Puntuación: 7.5/10**

---

## Lo que está bien

| Patrón | Archivo | Por qué importa |
|--------|---------|----------------|
| `subprocess.exec` + `shlex.split` (no `shell=True`) | `registry.py:208` | Previene command injection de forma arquitectónica, no solo con sanitización |
| `SessionMetadata.__slots__` | `session.py:55` | Rechaza Pydantic deliberadamente para 11 campos lightweight. Zero overhead. |
| `CircuitBreaker` en 52 líneas | `circuit.py` | CLOSED→OPEN→HALF_OPEN correcto. Sin sobreingeniería. |
| `get_healthy()` siempre reinicia desde priority[0] | `manager.py:156` | Tras recovery vuelve a primary automáticamente. Muchas implementaciones se quedan sticky en fallback. |
| `_stream_with_timeout()` | `agent.py:589` | Timeout por chunk (60s), no por request total. Detecta SSE zombies sin bloquear 60s completos. |
| `file_edit` rollback on failure | `registry.py:494` | Restore from backup si el write falla. Previene archivos medio-escritos. |
| `_deep_merge()` en identity loading | `agent.py:80` | User overrides mergean sobre defaults sin reemplazar el bloque entero. |
| `append_message` + metadata update en transacción SQL atómica | `session.py:156` | No puede quedar `message_count` desincronizado. |
| `trusted_paths` configurados antes de registrar tools | `agent.py:169` | El sandbox existe antes de que cualquier tool pueda ejecutarse. |
| LoopDetector con herramienta + args como key | `agent.py:900` | Detecta bucles de la misma operación, no solo del mismo tool. |
| Batch compression 5-by-5 con keep-last-4 | `agent.py:537` | Strategy documentada: comprime historial antiguo, preserva reciente. |

---

## Flags reales

### 1. Allowlist bash incompleta

**Severidad:** Bug real (ha causado reintentos repetidos en sesiones documentadas)
**Archivo:** `registry.py:43`
**Estado:** Pendiente

```python
_DEFAULT_BINARIES = {
    "ls", "pwd", "echo", "git", "grep", "find", "mkdir", "rmdir", "touch",
    "mv", "cp", "rm", "wc", "date", "chmod", "df", "du", "head", "tail",
    "curl", "wget", "scp", "ssh",
    "uv", "python", "python3", "pip", "pip3",
    "wsl",
}
```

**Faltan binarios disponibles en el stack de Pedro:**
- `rg` (ripgrep) — el agente podría buscar con grep nativo pero no con `rg`
- `bat`, `eza` — lectura de archivos con syntax highlighting
- `z` (zoxide) — navegación inteligente
- `tokei`, `shellcheck` — análisis de código
- `gh` — GitHub CLI
- `tmux` — multiplexor

**Impacto:** El agente tiene que recurrir a `python -c` como workaround, aumentando el riesgo de errores.

**Fix sugerido:** Añadir a `_DEFAULT_BINARIES`:
```python
"rg", "bat", "eza", "z", "tokei", "shellcheck", "gh", "tmux",
```

---

### 2. TUI a 46KB

**Severidad:** Tech debt (47.8KB, crece sin límite)
**Archivo:** `tui.py`
**Estado:** Warn

Textual TUI grande no es automáticamente un problema, pero sin límite crece hasta ser inmanejable. Conviene splitear en widgets separados cuando sea práctico.

**Approach:** Extraer widgets reutilizables (`ToolBlock`, `ThinkingBlock`, `StatusBar`) a `src/bytia_kode/tui/widgets/` y reimportarlos en `tui.py`.

---

### 3. Race condition potencial en interrupt/kill

**Severidad:** Baja (unlikely en práctica)
**Archivo:** `agent.py:1017-1029`
**Estado:** Observation

```python
async def kill(self) -> None:
    self._cancel_event.set()
    if self._active_subprocess and self._active_subprocess.returncode is None:
        ...
        self._active_subprocess.terminate()
```

`_active_subprocess` se asigna en el callback `on_subprocess` que pasa el process. Si otra tool call llega mientras `kill()` está ejecutando, el callback podría sobrescribir `_active_subprocess` antes del check de `returncode`.

**Fix sugerido:** Capturar `_active_subprocess` en variable local antes del if, o usar un lock.

---

### 4. Summary de contexto usa el mismo modelo provider

**Severidad:** UX / coste
**Archivo:** `agent.py:560-577`
**Estado:** Pendiente

```python
summary = await self._summarize_messages(batch, provider_client)
```

Consume tokens del mismo modelo que se usa para generar. En sesiones largas con mucha context compression, suma.

**Fix sugerido:** Usar un segundo provider barato (ej: GLM-4-flash como summarizer) o fallback a truncación pura sin LLM call.

---

### 5. System messages — enforcement verificado

**Severidad:** Verification passed
**Archivo:** `agent.py:538`
**Estado:** Confirmado

~~Originalmente marcado como "bug potencial". Verificación contra código real demuestra que el enforcement SÍ existe:~~

```python
non_system = [
    (i, m) for i, m in enumerate(self.messages) if m.role != "system"
]
```

El filtro excluye explícitamente `role="system"` del batch de compresión. Los system messages sobreviven en cualquier posición de `self.messages`. Los resúmenes generados también se insertan como `role="system"` (línea 554), por lo que sobreviven a compresiones futuras.

**Acción:** Añadir test de regresión para proteger este comportamiento contra cambios futuros.

---

## Observations (sin acción inmediata)

### Token estimation heurística
`chars/3` (o `chars/3.5` para ASCII-heavy) es una aproximación, no un conteo real. Si `token_count` se conecta a billing en el futuro, desviará. Documentado, pero hay que recordarlo.

### Symlink attack surface
`_resolve_workspace_path()` usa `resolve()` que sigue symlinks. Un attacker que cree `/workspace/link -> /etc/` podría escapar el sandbox. No crítico porque solo se permiten `workspace` y `trusted_paths`, pero ampliable.

### Panic Buttons incompletos (ROADMAP)
- `AgentCancelledError` con cleanup parcial — pendiente
- Tests de cancelación: interrupt mid-stream, mid-tool, kill durante bash — pendientes
- Textual TUI tests con `pytest-textual` — pendiente

---

## v0.7.8 — Propuesta de contenido (actualizada tras triple review)

Priorización fusionada de Hermes + Peke + Claude:

| Item | Severidad | Esfuerzo |
|------|-----------|----------|
| Ampliar allowlist bash (`rg`, `bat`, `eza`, `tokei`, `shellcheck`) — NO `z`/`tmux`/`gh` | Bug real | 10min |
| Test regresión: system message preservation | Verificación | 20min |
| Fix race condition interrupt/kill | Baja | 15min |
| tui.py refactor: extraer widgets a subdir | Tech debt | Medio |

**No recomendado para v0.7.8** (fuera de scope):
- Summary con modelo separado (trade-off deliberado, no bug — requiere redesign del provider manager)
- `z`/`tmux`/`gh` en allowlist (sin valor real para el agente)
- Symlink attack surface fix (bajo riesgo, alto esfuerzo)
- Panic button cleanup + cancelación tests (v0.7.9)
- LSP integration, hashline edits (v0.8.0 según ROADMAP)

---

## Tests

```
144 passed in 1.26s
0 failed
```

Suite estable sin regresiones.

---

*Generado por BytIA (Hermes Agent) — 2026-04-30*
