# BytIA KODE — Development Log

Registro diario de sesiones de desarrollo. Cada día tiene su propio archivo en [`docs/devlog/`](docs/devlog/).

## Índice por fecha

| Fecha | Sesiones | Archivo |
|-------|----------|---------|
| 2026-04-01 | S1: Nacimiento | [`2026-04-01.md`](docs/devlog/2026-04-01.md) |
| 2026-04-02 | S2: Hardening + UX + Documentación | [`2026-04-02.md`](docs/devlog/2026-04-02.md) |
| 2026-04-03 | S3: Bot Telegram → Router + Guard sin modelo, S4: UX Avanzada + Skills System, S5: Streaming, Reasoning, Context Management, TUI v4, S6: Limpieza de peso muerto, S7: Consolidación Router + Gemma 4 + Cleanup | [`2026-04-03.md`](docs/devlog/2026-04-03.md) |
| 2026-04-04 | S8: Router Polling, ToolBlock, Auto-conocimiento | [`2026-04-04.md`](docs/devlog/2026-04-04.md) |
| 2026-04-06 | S9: Sesiones Persistentes (SQLite WAL), S10: Session Awareness + Prompt Enhancement, S11: Initial Agent (v0.1.0) | [`2026-04-06.md`](docs/devlog/2026-04-06.md) |
| 2026-04-07 | S12: Infraestructura de Debug, Bugs y Multi-Workspace C, S13: Debug, fixes y copiado, S14: TTS (Text-to-Speech) + Infra, S15: Provider System (v0.2.0) | [`2026-04-07.md`](docs/devlog/2026-04-07.md) |
| 2026-04-08 | S16: Tools & Session Persistence (v0.3.0) | [`2026-04-08.md`](docs/devlog/2026-04-08.md) |
| 2026-04-09 | S17: Telegram Bot & Skills (v0.4.0) | [`2026-04-09.md`](docs/devlog/2026-04-09.md) |
| 2026-04-10 | S18: Constitución, Comunicación y Optimización, S19: Memoria Persistente, Trusted Paths y Sandbox Expan, S20: TUI Themes & Polish (v0.5.0) | [`2026-04-10.md`](docs/devlog/2026-04-10.md) |
| 2026-04-11 | S21: BashTool Shell Operator Validation (Hotfix), S22: Panic Buttons & Native Tools (v0.6.0) | [`2026-04-11.md`](docs/devlog/2026-04-11.md) |
| 2026-04-12 | S23: file_read Sandbox Fix + Legacy Cleanup, S24: Panic Buttons, Seguridad y Auto-Skills (v0.6.0), S25: Reasoning Persistence & Docs (v0.6.1) | [`2026-04-12.md`](docs/devlog/2026-04-12.md) |
| 2026-04-15 | S26: Circuit Breaker (v0.7.0), S27: Circuit Breaker Hardening (v0.7.1) | [`2026-04-15.md`](docs/devlog/2026-04-15.md) |
| 2026-04-17 | S28: B-KODE.md Rewrite + Security Hardening | [`2026-04-17.md`](docs/devlog/2026-04-17.md) |
| 2026-04-26 | S29: DeepSeek Provider + Sticky Pinning + Claude Code M, S30: DeepSeek reasoning_content Fix (v0.7.2) | [`2026-04-26.md`](docs/devlog/2026-04-26.md) |
| 2026-04-27 | S31: Structured CoT Grammar Exploration (reverted), S32: Agent Loop Optimizations (v0.7.3), S33: Agent Loop Stagnation Fixes, S34: Fix Validation: 65% Iteration Reduction | [`2026-04-27.md`](docs/devlog/2026-04-27.md) |
| 2026-04-28 | S35: Provider Resilience Hotfixes (v0.7.4) | [`2026-04-28.md`](docs/devlog/2026-04-28.md) |
| 2026-04-29 | S36: Skills v2.0 + FIX-3/4 (v0.7.5/6), S37: Session Audit Fixes (v0.7.7) | [`2026-04-29.md`](docs/devlog/2026-04-29.md) |
| 2026-04-30 | S38: Session Metadata Persistence + v0.7.7 Closure | [`2026-04-30.md`](docs/devlog/2026-04-30.md) |

## Formato

Cada archivo diario contiene una o más entradas de sesión con **secciones semánticas según el tipo de trabajo**.

### Estructura base (obligatorio)

```markdown
# Session N — YYYY-MM-DD — Título descriptivo

**Scope:** Descripción breve del alcance. Qué se hizo, por qué, resultado principal.
```

### Separador entre sesiones

Tres líneas de `---` separadas por un salto:

```markdown

---

---

---
```

### Secciones semánticas por tipo de sesión

No hay un template único. Cada sesión elige las secciones que mejor describen el trabajo:

| Tipo | Secciones recomendadas |
|------|----------------------|
| **Feature / Nueva funcionalidad** | `### Implementación` (descripción), `### Arquitectura` (cambios clave), `### Files Changed` (tabla), `### Tests` |
| **Bug Fix** | `### Problema` (síntomas + sesión donde se detectó), `### Root Cause` (causa raíz), `### Fix` (qué se cambió y cómo), `### Files Changed` (tabla), `### Tests` |
| **Experimento / Exploración** | `### What We Built` / `### What We Tried`, `### What Stayed` (lo que se conservó), `### Root Cause: Why It Failed/Worked`, `### Key Findings`, `### Reference` |
| **Validación / Benchmark** | `### Context` (qué se valida), `### Before vs After` (tabla de métricas), `### What Worked`, `### Remaining Edge Cases` |
| **Refactor / Limpieza** | `### Cambios`, `### Archivos modificados` (tabla), `### Testing` |
| **Estándar / Mixto** | La que mejor se adapte. Si hay cambios de archivos, incluir tabla `### Files Changed` |

### Convenios

- **`### Files Changed`**: Tabla con columnas `Archivo | Cambio | Razón`
- **`### Tests`**: Siempre al final. Indicar número de tests y si hay regresiones. Ej: `142 passed — no regressions`
- **`### Commits`**: Tabla con `Commit | Descripción` para sesiones con múltiples commits
- **Los enlaces a sesiones de TUI/Telegram** van con el ID: `` `tui_a1b2c3d4` ``
- **Idioma**: El `Scope` y títulos en inglés (estándar del proyecto). Contenido interior en el idioma que mejor fluya (español para análisis, inglés para features técnicas)
