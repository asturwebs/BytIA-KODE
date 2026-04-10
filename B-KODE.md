# BytIA-KODE — Project Instructions

## Rutas Críticas

| Recurso | Ruta |
|---------|------|
| Skills | `~/.bytia-kode/skills/` |
| Memoria | `~/.bytia-kode/memoria/` |
| Contextos | `~/.bytia-kode/contexts/` |
| Intercom | `/home/asturwebs/bytia-intercom/` |
| Logs | `~/.bytia-kode/logs/bytia-kode.log` |
| Sesiones | `~/.bytia-kode/sessions.db` |
| Config | `~/.bytia-kode/.env` |

## Skills Disponibles (5)

Cargadas al inicio desde `~/.bytia-kode/skills/*/SKILL.md`:

| Skill | Propósito |
|-------|-----------|
| `agent-intercom` | Comunicación inter-agente (Claude, Claw, Kode) |
| `graphify` | Construcción de grafos de conocimiento |
| `memory-manager` | Memoria persistente entre sesiones |
| `skill-creator` | Plantilla para crear nuevas skills |
| `web-fetch` | Lectura de URLs (HTML a texto) |

Cuando una petición coincida con un skill trigger, carga y sigue el procedimiento del SKILL.md.

## Protocolo Intercom

- **Tu inbox:** `/home/asturwebs/bytia-intercom/inbox/kode/`
- **NUNCA leas** de `inbox/claude/` ni `inbox/claw/`
- **Enviar a Claude:** copiar `.md` a `/home/asturwebs/bytia-intercom/inbox/claude/`
- **Enviar a Claw:** copiar `.md` a `/home/asturwebs/bytia-intercom/outbox/claw/`
- **ACK:** renombrar mensaje a `.ack` después de leerlo
- **Telegram:** usar `$TELEGRAM_BOT_TOKEN` del entorno (NUNCA hardcodear tokens)
- **Check inbox:** `ls /home/asturwebs/bytia-intercom/inbox/kode/*.md | grep -v '\.ack$'`

## Sistema de Memoria

Persistir conocimiento en `~/.bytia-kode/memoria/<categoria>/<nombre>.md`.

Categorías: `procedimientos/`, `contexto/`, `tecnologia/`, `decisiones/`

Formato obligatorio: YAML frontmatter + contenido markdown:
```yaml
---
created: YYYY-MM-DD
category: <categoria>
tags: [tag1, tag2]
---
# Título
Contenido aquí.
```

Operaciones: `memory_store` (escribir), `memory_search` (grep), `memory_index` (reconstruir index.md), `memory_read`.

## Runtime

- **Router:** llama.cpp en `localhost:8080`, auto-detección de modelo
- **Providers:** primary (router) / fallback (Z.AI) / local (Ollama) — cambiar con F3
- **Sandbox:** tools restringidos a CWD + `~/.bytia-kode/`
- **Bash:** solo binarios en allowlist (ver `EXTRA_BINARIES` en `.env`)

## Seguridad

- **NUNCA** hardcodear tokens, API keys o secrets en código, skills o este archivo
- Usar **variables de entorno** para todos los secrets (`TELEGRAM_BOT_TOKEN`, `PROVIDER_API_KEY`, etc.)
- Este repo es **PÚBLICO** (asturwebs/BytIA-KODE) — todo lo commiteado es visible
- Si un tool falla, reportar error exacto — NUNCA simular éxito (P20)
