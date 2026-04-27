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

## Formato

Cada archivo diario contiene una o más entradas de sesión con el formato:

```markdown
# Session N — YYYY-MM-DD — Título

**Scope:** Descripción breve del alcance.
```

Múltiples sesiones en el mismo día se separan con `---`.
