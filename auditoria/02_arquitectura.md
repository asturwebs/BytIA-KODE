# Auditoría de Arquitectura — BytIA-KODE v0.3.0

**Fecha:** 2026-04-02
**Auditor:** BytIA (análisis directo)
**Alcance:** Arquitectura, módulos, coupling, extensibilidad, agent loop

---

## Resumen Ejecutivo

| Métrica | Valor |
|---------|-------|
| Módulos analizados | 11 archivos fuente |
| Líneas de código (src/) | ~900 LOC |
| Hallazgos HIGH | 3 |
| Hallazgos MEDIUM | 5 |
| Hallazgos LOW | 3 |

**Veredicto general:** Arquitectura modular y funcional para su etapa (Alpha v0.3.0). Buen diseño de paquete, separation of concerns razonable, pero con deuda técnica en estado compartido, manejo de errores, y features declaradas pero no implementadas.

---

## 1. Estructura del Proyecto

```
src/bytia_kode/
├── __init__.py          # Version management
├── __main__.py          # python -m entry point
├── agent.py             # Agentic loop (core brain)
├── cli.py               # CLI con prompt_toolkit + Rich
├── config.py            # Config con dotenv + dataclasses
├── tui.py               # TUI con Textual
├── tui.css              # Textual stylesheet
├── providers/
│   ├── client.py        # OpenAI-compatible async HTTP client
│   └── manager.py       # Multi-provider con fallback
├── tools/
│   └── registry.py      # Tool registry + Bash/FileRead/FileWrite
├── skills/
│   └── loader.py        # SKILL.md parser + trigger matching
├── memory/
│   └── store.py         # JSON flat memory store
├── prompts/
│   └── core_identity.yaml  # SP constitucional embebido
└── telegram/
    └── bot.py           # Telegram bot interface
```

### Evaluación: BUENA

- Separación clara por dominio: providers, tools, skills, memory, telegram
- `core_identity.yaml` embebido como package resource (no file path hardcodeado)
- Entry points múltiples: CLI, TUI, Telegram — todos usan el mismo `Agent`

---

## 2. Dependency Graph

```
cli.py ──→ Agent ──→ ProviderManager ──→ ProviderClient
tui.py ──→ Agent ──→ ToolRegistry ──→ Tool (Bash/FileRead/FileWrite)
bot.py ──→ Agent ──→ SkillLoader
                  ──→ BytMemoryConnector
                  ──→ load_system_prompt() ← core_identity.yaml
```

### Evaluación: LIMPIA

- **No hay dependencias circulares.** Flujo unidireccional.
- **Acoplamiento bajo.** Cada módulo puede testearse independientemente.
- **Issue:** `Agent` es una "god class" que instancia todo. No hay dependency injection — los componentes se crean en `__init__`.

---

## 3. Agent Loop (agent.py)

### Flujo: think → act → observe → repeat

```
chat(user_message) → loop(max_iterations=50):
  1. build system_prompt (identity + skills + memory)
  2. send to provider with tool_defs
  3. if response has tool_calls → execute tools → append results → loop
  4. if no tool_calls → yield content → break
```

### Hallazgos

| ID | Severidad | Issue | Línea |
|----|-----------|-------|-------|
| ARC-001 | HIGH | `chat()` es generador async (`yield`) que también muta estado (`self.messages`). Patrón impuro — difícil de testear | agent.py:86-150 |
| ARC-002 | HIGH | No hay manejo de errores del provider dentro del loop. Si `provider_client.chat()` falla, la excepción propaga sin limpiar `self.messages` | agent.py:96-97 |
| ARC-003 | MEDIUM | `_build_system_prompt()` se reconstruye en CADA iteración del loop. Los skills y memory no cambian entre iteraciones — desperdicio de tokens | agent.py:76-84, 94 |
| ARC-004 | MEDIUM | `max_iterations = 50` es hardcodeado. Debería ser configurable | agent.py:73 |
| ARC-005 | LOW | `chat_stream()` es un método separado que no soporta tools. Duplicación parcial de lógica con `chat()` | agent.py:152-165 |

### Evaluación: FUNCIONAL pero frágil

El agentic loop está bien concebido pero la implementación mezcla side effects con generación. Un refactor a patrón state machine mejoraría testabilidad y mantenibilidad.

---

## 4. Provider Architecture

### Multi-provider con fallback

```
ProviderManager
├── primary   (Z.AI, OpenRouter, etc.)
├── fallback  (opcional)
└── local     (llama.cpp, Ollama)
```

### Hallazgos

| ID | Severidad | Issue | Línea |
|----|-----------|-------|-------|
| ARC-006 | MEDIUM | No hay auto-fallback. Si el provider primario falla, no intenta automáticamente con el fallback | manager.py |
| ARC-007 | MEDIUM | No hay timeout/retry con backoff en `ProviderClient`. Un provider lento bloquea indefinidamente hasta el timeout HTTP (120s) | client.py:46 |
| ARC-008 | LOW | El endpoint es hardcoded a `/chat/completions`. Algunos providers usan rutas diferentes | client.py:91 |

### Evaluación: BUENA base, necesita resiliencia

La arquitectura de multi-provider es correcta. Falta implementar circuit breaker y retry logic.

---

## 5. Tool System

### Registry pattern

```python
ToolRegistry._register_defaults()  # BashTool, FileReadTool, FileWriteTool
```

### Hallazgos

| ID | Severidad | Issue | Línea |
|----|-----------|-------|-------|
| ARC-009 | HIGH | Tools se registran solo en `__init__`. No hay mecanismo de auto-discovery ni plugin system para tools custom | registry.py:146-148 |
| ARC-010 | MEDIUM | Solo 3 tools implementados. Faltan tools esenciales: glob/find, web search, code search | registry.py |

### Evaluación: Extensible pero mínima

El patrón registry es correcto y fácil de extender. Agregar nuevos tools requiere solo heredar de `Tool` y registrar.

---

## 6. Memory System

### JSON flat store

```python
BytMemoryConnector → data_dir/memory/store.json
search() → keyword matching (no embeddings)
```

### Hallazgos

| ID | Severidad | Issue | Línea |
|----|-----------|-------|-------|
| ARC-011 | MEDIUM | Búsqueda es keyword-based. El pyproject.toml declara deps opcionales de FAISS/sentence-transformers pero no están integrados | store.py:49-57 |
| ARC-012 | LOW | `get_context()` vuelca TODA la memoria al system prompt. Sin límite de tamaño, puede exceder el context window | store.py:60-67 |

### Evaluación: Placeholder funcional

El memory connector funciona pero es un stub. La integración con QHMC/FAISS está declarada pero no implementada.

---

## 7. Skills System

### SKILL.md pattern (Hermes-like)

```python
SkillLoader → scan dirs → parse frontmatter → trigger matching
```

### Evaluación: BIEN diseñado

- Frontmatter parsing manual (sin librería) — funciona, pero frágil
- `get_relevant()` usa keyword matching — aceptable para v0.3.0
- `skill_dirs` no se configura desde config — requiere instanciación manual
- No hay auto-loading desde `~/.bytia-kode/skills/`

---

## 8. Telegram Bot

### Hallazgos

| ID | Severidad | Issue |
|----|-----------|-------|
| ARC-013 | MEDIUM | Un solo `Agent` por bot. Todas las conversaciones comparten estado. No hay aislamiento por chat/user | bot.py:20-21 |
| ARC-014 | LOW | No hay soporte para mensajes largos con Markdown formatting | bot.py:93-98 |

### Evaluación: Funcional para single-user

El bot funciona pero no escala a múltiples usuarios simultáneos.

---

## 9. Configuration

### .env + dataclasses

- `ProviderConfig`: base_url, api_key, model + fallback + local
- `TelegramConfig`: bot_token, allowed_users
- `AppConfig`: log_level, data_dir

### Evaluación: LIMPIA

- Carga en orden correcto: CWD `.env` primero, luego global `~/.bytia-kode/.env`
- Uso de dataclasses + field(default_factory) para lazy loading
- **Falta:** Validación con Pydantic. No hay verificación de que api_key no esté vacía al usar provider primario

---

## 10. TUI vs CLI

| Aspecto | CLI (cli.py) | TUI (tui.py) |
|---------|-------------|-------------|
| Complejidad | 87 líneas | 458+ líneas |
| Dependencias | prompt_toolkit + Rich | Textual |
| Funcionalidad | Chat básico + comandos | Chat + herramientas + safe_mode visual |
| Madurez | Funcional | En desarrollo |

### Issue: `safe_mode` es solo visual

El toggle de safe_mode en la TUI no tiene efecto en el backend. Los tools se ejecutan igualmente.

---

## 11. Testing

```python
# src/tests/test_basics.py — único archivo de tests
# Coverage: mínima (solo tests básicos)
```

**Cobertura estimada:** <10% del código fuente

Módulos sin tests:
- agent.py (agentic loop)
- providers/client.py (HTTP client)
- tools/registry.py (tool execution)
- telegram/bot.py (bot interface)
- memory/store.py (persistence)

---

## Componentes Faltantes para Producción

| Componente | Prioridad | Descripción |
|------------|-----------|-------------|
| Dependency Injection | Alta | Agent crea todo en `__init__`. Necesita DI para testing y extensibilidad |
| Error Recovery | Alta | No hay recovery en el agent loop si el provider falla |
| Session Persistence | Media | Historial se pierde al cerrar. Falta JSONL o SQLite |
| Plugin System | Media | Tools custom sin auto-discovery |
| Semantic Memory | Media | FAISS/sentence-transformers declarados pero no integrados |
| Observability | Baja | Sin métricas de tokens, latencia, o coste |
| Multi-user Isolation | Baja | Telegram comparte Agent entre todos los usuarios |

---

## Fortalezas

1. **Paquete bien estructurado** — src layout, pyproject.toml, hatch build
2. **SP embebido como resource** — no depende de file paths externos
3. **Multi-provider** — arquitectura limpia para switching/fallback
4. **Extensible** — agregar tools/skills es straightforward
5. **Async-first** — httpx, async/await en todo el stack
6. **Standard compliance** — OpenAI-compatible API (cualquier provider funciona)

## Debilidades

1. **Agent como god class** — mezcla estado, IO, y lógica de negocio
2. **Sin DI** — testing requiere mocking manual
3. **Errores silenciados** — try/except que devuelven ToolResult(error=True) sin recovery
4. **Features declaradas sin implementar** — safe_mode, semantic memory, auto-fallback
5. **Tests insuficientes** — <10% coverage
