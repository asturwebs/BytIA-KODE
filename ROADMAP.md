# Roadmap - BytIA KODE

## Estado actual: v0.4.1 (Alpha estable)

### Completado

**v0.1.0 — Fundamentos**
- [x] Arquitectura agéntica con loop think → act → observe
- [x] TUI (Textual) + CLI simple + Bot Telegram
- [x] Identidad constitucional en YAML empaquetado
- [x] Multi-provider OpenAI-compatible (primary, fallback, local)
- [x] Tools: bash (allowlist), file_read, file_write
- [x] Seguridad: command injection mitigado, path traversal bloqueado, fail-secure

**v0.2.0 — Hardening**
- [x] Async I/O: subprocess y disco no bloquean el event loop
- [x] Benchmark: 4.90x speedup concurrente vs secuencial
- [x] 17 tests con pre-commit hook (validación + secret scan + pytest)
- [x] Auditoría profesional completa

**v0.3.0 — UX y build**
- [x] 9 temas con F2 cíclico y persistencia
- [x] Banner "B KODE" con colores dinámicos por tema
- [x] Bordes de chat reactivos al tema activo
- [x] Provider switching con F3 (primary → fallback → local)
- [x] `/models` lista modelos del provider activo
- [x] `/use <model>` selecciona modelo en runtime
- [x] Workflow CI/CD con GitHub Actions
- [x] Scripts de validación y secret scan

**v0.3.1 — Skills System**
- [x] Directorio `~/.bytia-kode/skills/` con auto-creación
- [x] SKILL.md con frontmatter YAML (agentskills.io compatible)
- [x] Comandos: `/skills`, `/skills save`, `/skills show`, `/skills verify`
- [x] Búsqueda por relevance (trigger keywords + description + content scoring)
- [x] Skill `skill-creator` incluida (meta-skill de bootstrap)
- [x] Progressive disclosure: metadata en lista, contenido bajo demanda

**v0.4.0 — Router, Streaming y TUI Avanzada**
- [x] Streaming token a token en la TUI (deltas SSE en tiempo real)
- [x] Reasoning/Thinking con ThinkingBlock colapsable
- [x] B-KODE.md: instrucciones de proyecto por directorio
- [x] Context window management (chars/3, compresión al 75%)
- [x] llama.cpp Router support (single port, multi-modelo, auto-detect)
- [x] Bot Telegram usa router (GPU, ~133 t/s)
- [x] Guard si no hay modelo cargado
- [x] Router polling en StatusBar (cada 5s, detecta swaps)
- [x] ctx-size dinámico desde router API
- [x] ToolBlock widget (ejecución de tools colapsable)
- [x] Agent callbacks (on_tool_call / on_tool_done)
- [x] core_identity runtime section (auto-conocimiento del agente)
- [x] Limpieza de peso muerto (3 deps, cli.py, memory/store.py)
- [x] 15 tests pasando con pre-commit hook

**v0.4.1 — Herramientas y estabilidad**
- [x] `file_edit` tool — search/replace + create con backup automático, diff unificado y diagnósticos (_no_match_help) (BytIA OpenClaw)
- [x] Context management con summarization por modelo (threshold dinámico por ctx_size, fallback a truncación) (BytIA Claude Code)
- [x] Token estimation unificado — `Agent.estimate_tokens()` como single source of truth (chars/3) (BytIA Claude Code)
- [x] ToolBlock color coding — rojo ❌ si error, verde ✅ si ok (BytIA Claude Code)
- [x] Router polling: logging en `_poll_router_info` con alertas progresivas (BytIA Claude Code)
- [x] 27 tests pasando (14 file_edit + 13 context_management)

---

## v0.4.1 — Herramientas y estabilidad (completado)

**Objetivo:** Robustez del agente y herramientas de desarrollo.

**Reparto por instancia (zero merge conflicts — cada una en archivos distintos):**

| Instancia | Plataforma | Archivos | Branch |
|-----------|-----------|----------|--------|
| **BytIA OpenClaw** | GLM-5.1 · VPS Hetzner | `tools/registry.py` | `feature/file-edit-claw` |
| **BytIA (Claude Code)** | GLM-5-Turbo · WSL2 local | `agent.py`, `tui.py` | `feature/context-bytia` |

(Ver sección "Completado" arriba para el detalle de tareas)

### Reubicado a v0.5.0 (no completado en v0.4.1)

- [ ] PromptTextArea: Shift+Enter/Ctrl+Enter = newline (Textual Key no expone modifiers de forma fiable)
- [ ] Bash allowlist diferenciada por safe_mode
- [ ] Safe mode backend real (confirmación de comandos destructivos)
- [ ] Tools de exploración: `grep`, `tree`, `glob` nativos en Python

## v0.5.0 — Contexto, Skills inteligentes y memoria

**Objetivo:** Context management real, auto-selección de skills y persistencia.

### P1 — Critical

- [x] → Promovido a v0.4.1 (BytIA Claude Code)

### P2 — High

- [ ] Auto-selección de skills (cargar solo relevantes al query actual)
  - `get_relevant()` existe en SkillLoader pero NO se invoca en `_build_system_prompt()`
  - Scoring: trigger 3pt, description 2pt, content 1pt (ya diseñado)
  - Archivo: `agent.py:120-122` → **BytIA (Claude Code)**
- [ ] Persistencia de sesiones (`/save`, `/load`, `/sessions`)
  - Almacenamiento: `~/.bytia-kode/sessions/` con timestamp
  - Actual: `/reset` pierde todo sin opción de recuperar
  - **Sin asignar** — nuevo módulo, no pisa archivos existentes

### P3 — Features

- [ ] Tools dinámicas en skills (scripts en `skills/<name>/scripts/` auto-registrados)
- [ ] `write_skill` tool para que el agente cree skills programáticamente
- [ ] Memoria vectorial con FAISS/ChromaDB (búsqueda semántica)
- [ ] Skills Hub: instalar skills desde GitHub repos
- [ ] Skill como sub-agente (SP propio dentro de la skill)
- [ ] System prompt caching optimizado
- [ ] Telegram multi-user con aislamiento por sesión

## v0.6.0 — Multi-agente

**Objetivo:** Escalar a equipo de desarrollo virtual.

- [ ] Architect Agent → desglosa tareas complejas
- [ ] Coder Agent → implementa archivo por archivo
- [ ] Reviewer Agent → revisa calidad y seguridad
- [ ] Ejecución asíncrona de tareas largas
- [ ] Generación automática de Pull Requests

## v1.0.0 — Producción

**Objetivo:** Release estable para uso diario.

- [ ] CI/CD con Docker para validación aislada
- [ ] Auto-corrección con linters (ruff, mypy)
- [ ] Web search tool integrada
- [ ] Documentación completa con ejemplos
- [ ] Cobertura de tests >= 80%
- [ ] MCP server mode (exponer KODE como tool server)

---

## Dependencias opcionales futuras

```toml
[project.optional-dependencies]
local = ["llama-cpp-python>=0.3"]
memory = ["sentence-transformers>=4.0", "faiss-cpu>=1.11"]
```
