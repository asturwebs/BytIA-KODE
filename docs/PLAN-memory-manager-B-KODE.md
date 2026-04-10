# Plan: Sistema de Memoria Persistente para Kode

## Objetivo

Crear un sistema de memoria persistente que permita a Kode almacenar, buscar y recuperar conocimiento entre sesiones.

## Hallazgos de Investigación

### Sandbox (PROBLEMA CRÍTICO)

`_resolve_workspace_path()` sandboxea contra `Path.cwd()`:
- CWD = `/home/asturwebs/proyectos/mi-proyecto/` → `~/.bytia-kode/memoria/` BLOQUEADO
- CWD = `/home/asturwebs/` → `~/.bytia-kode/memoria/` PERMITIDO

**Solución:** Añadir `data_dir` como trusted path en `_resolve_workspace_path()`, igual que `SkillLoader.save_skill()` ya escribe fuera del sandbox. La `data_dir` es un directorio propio del agente, no código del usuario.

### BashTool inconsistency

BashTool sandboxea el `workdir` pero NO los argumentos de los comandos. `cat > /tmp/file` funciona aunque `/tmp/` esté fuera del workspace. Esto ya es así y no lo cambiamos ahora, pero es relevante: Kode puede usar BashTool como workaround.

### Skills no se filtran

`get_relevant()` existe en SkillLoader pero NO se invoca en `_build_system_prompt()`. Todas las skills se inyectan como resumen. Esto es aceptable para <10 skills pero escalará mal.

## Cambios Necesarios

### 1. Sandbox: Trusted Paths (registry.py)

Modificar `_resolve_workspace_path()` para aceptar una lista de trusted paths adicionales:

```python
_TRUSTED_PATHS: list[Path] = []

def set_trusted_paths(paths: list[Path]):
    _TRUSTED_PATHS.extend(p.resolve() for p in paths)

def _resolve_workspace_path(path: str) -> Path:
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    resolved = candidate.resolve()
    workspace = Path.cwd().resolve()
    if workspace == resolved or workspace in resolved.parents:
        return resolved
    for trusted in _TRUSTED_PATHS:
        if trusted == resolved or trusted in resolved.parents:
            return resolved
    raise PermissionError(f"Security violation: path escapes workspace: {path}")
```

En `Agent.__init__()`, añadir `data_dir` como trusted path:

```python
from bytia_kode.tools.registry import set_trusted_paths
set_trusted_paths([config.data_dir])
```

### 2. Estructura de Directorios (crear en ~/.bytia-kode/)

```
~/.bytia-kode/memoria/
├── procedimientos/     # How-tos, workflows, pasos repetibles
├── contexto/           # Decisiones importantes, hitos, contexto histórico
├── tecnologia/         # Stacks, arquitecturas, docs técnicos
├── decisiones/        # ADRs: por qué X sobre Y
└── index.md            # Índice auto-generado
```

### 3. Skill: memory-manager (SKILL.md)

Ubicación: `~/.bytia-kode/skills/memory-manager/SKILL.md`

Procedimientos:
- **memory_store**: file_write a `~/.bytia-kode/memoria/<categoria>/<nombre>.md`
- **memory_search**: grep recursivo en `~/.bytia-kode/memoria/`
- **memory_index**: regenerar index.md listando todos los archivos .md
- **memory_read**: file_read de un archivo específico

Formato estándar de archivos:
```yaml
---
created: 2026-04-10
category: procedimientos
tags: tag1, tag2
---
# Título
Contenido...
```

### 4. Tests

- Test: trusted paths permiten escritura en data_dir
- Test: paths fuera de workspace Y fuera de trusted siguen bloqueados
- Test: memory-manager skill se carga correctamente

## Ejecución (orden)

1. Modificar `registry.py`: añadir `_TRUSTED_PATHS` + `set_trusted_paths()`
2. Modificar `agent.py`: llamar a `set_trusted_paths([config.data_dir])` en init
3. Crear estructura de directorios `~/.bytia-kode/memoria/`
4. Crear `index.md` inicial
5. Crear skill `memory-manager/SKILL.md`
6. Añadir tests
7. Ejecutar tests
8. Reinstalar: `uv tool install --force --reinstall .`
9. Actualizar B-KODE.md y CONTEXT.md
10. Commit y push

## Riesgos

- **Trusted paths amplían la superficie de ataque.** Mitigación: solo `data_dir` (directorio propio del agente), no paths arbitrarios del usuario.
- **BashTool ya puede escribir fuera.** No empeoramos la situación, solo hacemos explícito lo que ya es posible vía bash.
