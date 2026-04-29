---
name: skills-manager
description:  Gestión del sistema de skills unificado BytIA.
  Trigger: skills, skill, configurar, importar, registry.
license: MIT
author: bytia
version: "1.0.0"
scope: [root]
auto_invoke: "skills, skill, configurar, importar, registry"
# BytIA Skills Manager

Sistema unificado de skills para todos los AI assistants del ecosistema BytIA.

## Comandos Principales

### setup-all.sh - Distribución de skills

```bash
cd ~/bytia

# Configurar todos
./scripts/setup-all.sh --all

# Auto-detectar CLIs instaladas
./scripts/setup-all.sh --detect

# Preview sin ejecutar
./scripts/setup-all.sh --all --dry-run

# Solo CLIs o solo KODE
./scripts/setup-all.sh --cli
./scripts/setup-all.sh --kode
```

### Gestión dinámica de CLIs

```bash
# Ver CLIs configuradas
./scripts/setup-all.sh --list-clis

# Añadir nueva CLI
./scripts/setup-all.sh --add-cli openrouter --path ~/.openrouter/skills
./scripts/setup-all.sh --add-cli cursor --path ~/.cursor/skills --symlink

# Eliminar CLI personalizada
./scripts/setup-all.sh --remove-cli openrouter
```

### list-skills.sh - Listar skills

```bash
./scripts/list-skills.sh              # Propios + external
./scripts/list-skills.sh --all        # Todo incluyendo registry
./scripts/list-skills.sh --registry   # Solo registry
./scripts/list-skills.sh --kode       # Skills de BytIA-KODE
```

### import-skill-from-registry.sh - Importar del registry

```bash
./scripts/import-skill-from-registry.sh --list     # Ver disponibles
./scripts/import-skill-from-registry.sh fastapi    # Importar
./scripts/import-skill-from-registry.sh --update   # Actualizar
```

## CLIs Soportadas

| CLI | Path | Método |
|-----|------|--------|
| Kimi | `~/.kimi/skills/` | rsync |
| Claude Code | `.claude/skills/` | symlink |
| Gemini CLI | `.gemini/skills/` | symlink |
| OpenAI Codex | `.codex/skills/` | symlink |
| OpenCode | `.config/opencode/skill/` | symlink |
| Hermes Agent | `~/.hermes/skills/` | rsync |
| BytIA-KODE | `~/.bytia-kode/skills/` | symlink |

## Añadir Nueva CLI

```bash
# 1. Añadir al sistema
./scripts/setup-all.sh --add-cli openrouter --path ~/.openrouter/skills

# 2. Configurar
./scripts/setup-all.sh --openrouter

# 3. O configurar todos
./scripts/setup-all.sh --all
```

## Flujo Completo

```bash
# 1. Detectar CLIs instaladas
./scripts/setup-all.sh --detect

# 2. Importar skills del registry
./scripts/import-skill-from-registry.sh fastapi
./scripts/import-skill-from-registry.sh pytest

# 3. Configurar todo
./scripts/setup-all.sh --all

# 4. Verificar
./scripts/list-skills.sh --all
```

## Recursos

- **Documentación:** `docs/SKILLS_SYSTEM.md`
- **Registry:** https://autoskills.sh
