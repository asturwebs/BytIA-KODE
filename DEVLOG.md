# BytIA KODE - Development Log

## 2026-04-01 - Sesión 1: Nacimiento

### Contexto

BytIA KODE nace como un agente de código autónomo con arquitectura agéntica: tools, skills, loop de iteración y memoria persistente. Inspirado en la idea de tener un asistente de código personal con identidad constitucional propia.

### Arquitectura base implementada

```text
src/bytia_kode/
├── config.py
├── agent.py
├── tui.py
├── cli.py
├── providers/
│   ├── client.py
│   └── manager.py
├── tools/
│   └── registry.py
├── skills/
│   └── loader.py
├── memory/
│   └── store.py
└── telegram/
    └── bot.py
```

### Verificación

- Tests unitarios iniciales: 4/4 passing
- Compilación limpia con `compileall`

---

## 2026-04-02 - Sesión 2: Hardening + UX + Documentación

### Fixes técnicos

1. `file_write` soporta rutas relativas sin romper
2. Cliente provider robustecido ante respuestas parciales/malformadas
3. `chat(stream=True)` falla explícitamente con mensaje claro para usar `chat_stream()`
4. Loop del agente tolera tool-calls incompletas
5. Bot de Telegram con guardas defensivas en handlers

### Fix crítico TUI

- Error: `NoMatches: No nodes match '#input-field' on Screen(id='_default')`
- Causa: faltaba `compose()` en `BytIAKODEApp`
- Solución: restaurar `compose()` con la estructura completa de widgets

### Verificación

- `uv run pytest -q` → 6 passed

---

## 2026-04-02 - Sesiones 3-6: Auditoría y Hardening (4 fases)

### Fase 1: Seguridad crítica

- SEC-001: BashTool con allowlist + `shell=False` + `shlex.split()`
- SEC-002/003: Path traversal bloqueado con `_resolve_workspace_path()`
- SEC-005: Telegram fail-secure por defecto
- Resultado: 11 tests passing

### Fase 2: Estabilidad

- Async I/O: `asyncio.create_subprocess_exec` + `asyncio.to_thread`
- Error recovery con excepciones específicas
- Input sanitizado
- Resultado: 14 tests passing

### Fase 3: Producción

- Memory con carga estricta y contexto acotado (20 entries / 2000 chars)
- Telegram oculta errores internos al usuario
- Pre-commit hook con secret scan
- Resultado: 17 tests passing

### Fase 4: Cierre

- Refactor: `_handle_tool_calls()` extraído del agente
- Benchmark: 4.90x speedup secuencial vs concurrente
- Documentación: CHANGELOG, auditoría, history.json

### Verificación final

- `uv run pytest -v` → 17 passed in 0.30s
- Pre-commit hook: metadata OK + secret scan OK + pytest OK
- Repo publicado en GitHub: https://github.com/asturwebs/BytIA-KODE
