# Intercom Refactoring Plan — v2.0

**Fecha:** 2026-04-30
**Autora:** BytIA Hermes
**Estado:** Borrador

---

## Diagnóstico

### Estado actual

| Aspecto | Problema |
|---------|----------|
| **Ubicaciones** | 7 copies de agent-intercom skill (`.hermes/`, `.claude/`, `.kimi/`, `.openrouter/`, `bytia/`, `bytia-claw-workspace/`, `.bytia-kode/`) |
| **Scripts vivos** | Solo en `~/.bytia-kode/intercom/scripts/` |
| **Skills** | Apuntan a `/home/asturwebs/bytia-intercom/` que NO EXISTE — copian la docs pero no funcionan |
| **Hermes** | Sin inbox, no integrada en el intercom |
| **Topología** | Rígida: OMEN + VPS, no contempla más agentes o localizaciones |
| **Telegram** | Bots hardcodeados en notify.sh — añadir 5ª hermana = modificar código |
| **Sync** | Solo OMEN↔VPS, no mesh |

### Arquitectura actual (problemas)

```
.bytia-kode/intercom/         ← Solo aquí funcionan los scripts
├── inbox/{claude,kode,claw}  ← Hermes NO existe
├── outbox/{claw/}            ← Solo claw tiene outbox
├── scripts/                  ← Solo aquí están los scripts
├── sent/
└── .env                      ← Tokens hardcodeados

Skills de Hermes/Claude/Kimi/OpenRouter:
  Apuntan a /home/asturwebs/bytia-intercom/ (NO EXISTE)
```

---

## Meta

Crear un sistema de comunicación inter-agente que:
1. Sea **compartido** — una sola instalación, todas lo usan
2. Sea **topología-agnóstico** — funcione en WSL, VPS, o lo que venga
3. Soporte **N hermanas** sin modificar código
4. Tengan **inbox propio** todas las hermanas
5. **Telegram** configurable, no hardcodeado
6. Mantenga **ACK protocol** existente

---

## Propuesta de Arquitectura v2.0

### Ubicación canónica

```
~/.bytia/intercom/                         # Un solo intercom en ~/.bytia/
├── inbox/
│   ├── hermes/
│   ├── claude/
│   ├── kode/
│   ├── claw/
│   └── <hermana-futura>/
├── outbox/
│   ├── hermes/
│   ├── claude/
│   ├── kode/
│   ├── claw/
│   └── <hermana-futura>/
├── sent/
├── config.yaml                            # Nueva: registro de hermanas + bots
├── scripts/
│   ├── check.sh
│   ├── send.sh
│   ├── ack.sh
│   ├── read.sh
│   ├── notify.sh
│   ├── sync.sh
│   └── install.sh                        # Nueva: instalador por agente
└── .env                                  # Tokens Telegram
```

### Registro de hermanas (`config.yaml`)

```yaml
agents:
  hermes:
    inbox: ~/.bytia/intercom/inbox/hermes
    outbox: ~/.bytia/intercom/outbox/hermes
    telegram_bot: @HermesBytIA_bot        # Nuevo
    endpoint: local                        # local | ssh | tunnel
    ssh_host: null
    ssh_user: null

  claude:
    inbox: ~/.bytia/intercom/inbox/claude
    outbox: ~/.bytia/intercom/outbox/claude
    telegram_bot: null                     # No tiene bot propio
    endpoint: local
    ssh_host: null
    ssh_user: null

  kode:
    inbox: ~/.bytia/intercom/inbox/kode
    outbox: ~/.bytia/intercom/outbox/kode
    telegram_bot: @AgentZero1969Bot
    endpoint: local
    ssh_host: null
    ssh_user: null

  claw:
    inbox: ~/.bytia/intercom/inbox/claw
    outbox: ~/.bytia/intercom/outbox/claw
    telegram_bot: @BytIA_bot
    endpoint: ssh
    ssh_host: 46.224.65.42
    ssh_user: pedro
    ssh_port: 22
```

### Protocolo de envío

**send.sh** lee `config.yaml` para saber:
1. Dónde está el inbox del destinatario (local o remoto)
2. Si necesita SSH/SCP para entregar
3. Qué bot usar para notificar

```bash
# Ejemplo: hermes → claw
FROM=hermes TO=claw ./send.sh mensaje.md

# send.sh:
# 1. Lee config.yaml
# 2. Destino claw = endpoint=ssh, ssh_host=46.224.65.42
# 3. SCP ~/.bytia/intercom/outbox/hermes/msg.md → claw:inbox/
# 4. Notifica vía @BytIA_bot (del config.yaml)
```

---

## Pasos de Implementación

### Fase 1: Crear infraestructura canónica

1. **Crear directorio base** `~/.bytia/intercom/`
2. **Crear config.yaml** con las 4 hermanas actuales
3. **Migrar scripts** de `.bytia-kode/intercom/scripts/` a `~/.bytia/intercom/scripts/`
4. **Crear inbox/outbox** para hermes
5. **Migrar `.env`** a `~/.bytia/intercom/.env`

### Fase 2: Actualizar scripts

6. **Refactorizar send.sh** — leer `config.yaml` en vez de hardcodear destinos
7. **Refactorizar notify.sh** — leer `config.yaml` para saber qué bot usar
8. **Refactorizar sync.sh** — genérico basado en `config.yaml`
9. **Crear install.sh** — instala symlinks/scripts para una nueva hermana

### Fase 3: Integrar sisters

10. **Crear inbox hermes** (falta completamente)
11. **Actualizar skill agent-intercom** en `.hermes/skills/` para apuntar a `~/.bytia/intercom/`
12. **Actualizar skill agent-intercom** en `.claude/skills/`, `.kimi/skills/`, `.openrouter/skills/`
13. **Desplegar en VPS** (Claw) — `install.sh` adapta rutas automáticamente

### Fase 4: Limpieza

14. **Eliminar** `~/.bytia-kode/intercom/` (redundante)
15. **Eliminar** skills duplicadas en `bytia/skills/`, `bytia-claw-workspace/skills/`
16. **Actualizar DEVLOG.md** del intercom

---

## Compatibilidad hacia atrás

- Los mensajes ya en `inbox/` de cada hermana se mantienen
- El formato YAML frontmatter no cambia
- El protocolo ACK (`mv .md .ack`) no cambia
- Solo la infraestructura (ubicación, scripts, config) cambia

---

## Nueva hermana — paso a paso

```bash
# 1. Pedro decide: "nueva hermana = Luna"
# 2. Crear inbox/outbox
mkdir -p ~/.bytia/intercom/inbox/luna
mkdir -p ~/.bytia/intercom/outbox/luna

# 3. Añadir a config.yaml
# luna:
#   inbox: ~/.bytia/intercom/inbox/luna
#   telegram_bot: @LunaBytIA_bot
#   endpoint: local

# 4. install.sh en la máquina de Luna
# 5. Skill agent-intercom de Luna apunta a ~/.bytia/intercom/
```

Sin modificar código. Solo config.

---

## Issues abiertos (requieren decisión de Pedro)

1. **Ubicación** — ¿`~/.bytia/intercom/` o prefieres otra? ¿`~/.bytia/intercom` o `~/.bytia-intercom`?
2. **Migración** — ¿mantener mensajes existentes en `.bytia-kode/intercom/inbox/` o start fresh?
3. **Skills compartidas** — ¿dónde va la skill agent-intercom? ¿en cada CLI o un repo central?
4. **Telegram bots** — ¿Hermes tiene bot propio? ¿cuál?

---

## No incluye (out of scope)

- Cambio de protocolo de mensajes (formato YAML + ACK se mantiene)
- Sistema de mensajería en tiempo real (sigue siendo filesystem-based)
- Migración de historial antiguo a la nueva estructura (start fresh, lo anterior queda en `sent/`)

---

*Generado por BytIA Hermes — 2026-04-30*
