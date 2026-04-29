---
name: bytia-memory
description:  claude-mem v10.6.1 3-Layer workflow for semantic memory retrieval (O13).
  Trigger: When asking about historical context, past sessions, "what did we do before", or "context from previous work".
license: MIT
author: bytia
version: "10.6.1"
scope: [root]
auto_invoke: "Historical queries, past context, 'what did we do before'"

# claude-mem 3-Layer Workflow (O13)

## REGLA CRÍTICA

**SIEMPRE** sigue este orden. **NUNCA** saltes pasos.

```
Layer 1: search(query) → IDs (~50-100 tokens/result)
Layer 2: timeline(anchor=ID) → Contexto (~50 tokens)
Layer 3: get_observations([IDs]) → Detalles (~500/obs)
```

PROHIBIDO: `get_observations` sin `search`/`timeline` primero. 10× ahorro de tokens.


## LAYER 1: SEARCH

**Tool**: `mcp__plugin_claude-mem_mcp-search__search`

Devuelve candidatos con IDs. ~50-100 tokens por resultado.

Parámetros útiles:
- `query`: Término de búsqueda o pregunta
- `limit`: Máximo resultados (default: 10)
- `type`: Filtrar por tipo (opcional)


## LAYER 2: TIMELINE

**Tool**: `mcp__plugin_claude-mem_mcp-search__timeline`

Contexto alrededor de un ID ancla. Usa el ID más relevante del Layer 1.

Parámetros útiles:
- `anchor`: Observation ID del Layer 1
- `depth_before`: Items antes del ancla (default: 3)
- `depth_after`: Items después del ancla (default: 3)


## LAYER 3: GET_OBSERVATIONS

**Tool**: `mcp__plugin_claude-mem_mcp-search__get_observations`

Detalles completos. **SOLO** para IDs filtrados en Layers 1-2.

Parámetros:
- `ids`: Array de observation IDs


## EJEMPLO

```
1. search(query="telegram bot architecture", limit=5)

2. timeline(anchor=1525, depth_before=2, depth_after=2)

3. get_observations(ids=[1523, 1524, 1525, 1526, 1527])
```

Coste total con 3-layer: ~650 tokens (5 obs)
Coste sin filtrar: ~10,000 tokens. **Ahorro: 93%**


## DECISION TREE

```
Usuario pregunta sobre contexto histórico?
├─ Específico? ("qué decidimos sobre X")
│   └─ search(query específica, limit=5) → timeline → get_observations
└─ Amplio? ("en qué trabajamos")
```


## CITACIÓN

```markdown
Según observación #1525 (2026-01-29), elegimos Arquitectura B para el Telegram Bot.
```


## QUICK REFERENCE

| Layer | Tool | Propósito | Coste |
|-------|------|-----------|-------|
| 1 | `search` | Candidatos con IDs | ~50-100/result |
| 2 | `timeline` | Contexto alrededor de IDs | ~50/timeline |
| 3 | `get_observations` | Detalles completos | ~500/obs |


## RECURSOS

- **Protocolo O13**: `@bytia.kernel.yaml`
- **Sesiones**: `~/.claude/projects/*/sessions/*.jsonl`
- **Web UI**: http://localhost:37777
