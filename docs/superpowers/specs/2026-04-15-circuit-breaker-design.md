# Circuit Breaker para Provider Auto-Fallback

**Fecha:** 2026-04-15
**Versión:** 1.0
**Estado:** Diseño aprobado
**Sesión:** 24

## Resumen

Implementar un Circuit Breaker estándar (CLOSED/OPEN/HALF_OPEN) por provider que permite fallback automático cuando el provider primario falla. El usuario recibe un aviso cuando se cambia de provider. Auto-recuperación tras 60s.

## Motivación

Actualmente, si el provider primario falla, el agente muestra un error y para. El usuario tiene que cambiar manualmente con F3. Con 3 providers configurados (primary, fallback, local), el sistema debería ser capaz de usar un provider alternativo automáticamente.

## Arquitectura

```
Agent.chat() → ProviderManager.get_healthy(preferred) → ProviderClient
                    ↓ si circuit OPEN
              prueba siguiente provider (fallback → local)
              → callback on_provider_switch(from, to)
              → yield ("system", aviso)
```

### Orden de prioridad

primary → fallback → local

### Auto-recuperación

- Provider en OPEN durante >60s → pasa a HALF_OPEN
- Se permite 1 petición de prueba
- Si funciona → CLOSED (disponible)
- Si falla → OPEN de nuevo

### Mid-stream

Si el provider falla *durante* el streaming (después de recibir tokens), NO se reintenta con otro provider. Se pierde esa respuesta parcial y se muestra error. El retry solo ocurre antes de empezar a recibir tokens. Razón: una respuesta a medias puede tener tool calls parciales que dejarían el estado del agentic loop inconsistente.

## Componentes

### 1. CircuitBreaker (nuevo archivo: `providers/circuit.py`)

Patrón estándar con 3 estados: CLOSED, OPEN, HALF_OPEN.

**Atributos:**
- `_failure_count: int` — fallos consecutivos (resetea en success)
- `_state: str` — CLOSED | OPEN | HALF_OPEN
- `_last_failure_time: float` — timestamp del último fallo
- `_half_open_allowed: bool` — si se permite la petición de prueba en HALF_OPEN

**Parámetros configurables:**
- `failure_threshold: int = 3` — fallos consecutivos antes de abrir
- `recovery_timeout: float = 60.0` — segundos hasta HALF_OPEN

**Métodos:**
- `state -> str` — estado actual
- `is_available -> bool` — True si CLOSED o HALF_OPEN (tras check_recovery)
- `record_success() -> None` — resetea counters, HALF_OPEN → CLOSED
- `record_failure() -> None` — incrementa failures, si >= threshold → OPEN
- `_check_recovery() -> None` — si OPEN y timeout pasado → HALF_OPEN

**Tabla de transiciones:**

| Evento | CLOSED | OPEN | HALF_OPEN |
|--------|--------|------|-----------|
| `record_success()` | No-op | No-op | → CLOSED, reset |
| `record_failure()` | count++ | No-op | → OPEN |
| count >= threshold | → OPEN | — | — |
| `is_available` | True | `_check_recovery()` | True |

### 2. ProviderManager (modificado: `providers/manager.py`)

**Atributos nuevos:**
- `_circuits: dict[str, CircuitBreaker]` — 1 CB por provider configurado
- `_on_provider_switch: Callable[[str, str], None] | None` — callback de notificación

**Métodos nuevos:**
- `get_healthy(preferred: str = "primary") -> tuple[ProviderClient, str]` — devuelve (client, name) del primer provider disponible. Orden: preferred → resto por prioridad. Si todos OPEN → devuelve preferred como último recurso.
- `report_success(provider: str) -> None` — registra éxito en el CB
- `report_failure(provider: str) -> None` — registra fallo en el CB
- `get_status() -> dict[str, dict]` — estado de todos los circuits para UI/debug

**Métodos modificados:**
- `list_available() -> list[str]` — ahora solo devuelve providers con circuit CLOSED o HALF_OPEN

### 3. Agent (modificado: `agent.py`)

**Métodos nuevos:**
- `_try_with_fallback(preferred: str, stream_fn: Callable) -> AsyncIterator` — intenta stream_fn con el provider preferido, si falla prueba siguientes

**Métodos modificados:**
- `chat()` — usa `providers.get_healthy()` en lugar de `providers.get()`. Si el provider cambia, yield `("system", aviso)`. Tras éxito/fallo en streaming, llama `report_success/report_failure`.

### 4. TUI (modificado: `tui.py`)

**Cambio mínimo:** Conectar case `"system"` en `_process_message()`. `ChatMessage` ya tiene variante `"system"` con estilo diferenciado.

### 5. Telegram Bot (modificado: `telegram/bot.py`)

**Cambio mínimo:** Añadir case `"system"` en event handler → mensaje informativo con prefijo informativo.

## Archivos afectados

| Archivo | Acción | Líneas estimadas |
|---------|--------|-----------------|
| `src/bytia_kode/providers/circuit.py` | **Nuevo** | ~60 |
| `src/bytia_kode/providers/manager.py` | Modificado | ~50 nuevas |
| `src/bytia_kode/agent.py` | Modificado | ~30 |
| `src/bytia_kode/tui.py` | Modificado | ~3 |
| `src/bytia_kode/telegram/bot.py` | Modificado | ~3 |
| `tests/test_circuit_breaker.py` | **Nuevo** | ~80 |
| `tests/test_agentic_loop.py` | Modificado | ~40 (tests de integración) |

## Tests

### CircuitBreaker unitarios (~8 tests)

| Test | Verifica |
|------|----------|
| `test_starts_closed` | Estado inicial es CLOSED |
| `test_success_keeps_closed` | `record_success()` no cambia estado |
| `test_failures_open_circuit` | 3 fallos → OPEN |
| `test_open_is_not_available` | OPEN → `is_available == False` |
| `test_recovery_to_half_open` | OPEN + timeout → HALF_OPEN |
| `test_half_open_success_closes` | Éxito en HALF_OPEN → CLOSED |
| `test_half_open_failure_reopens` | Fallo en HALF_OPEN → OPEN |
| `test_failure_count_resets_on_success` | Éxito resetea contador |

### ProviderManager (~5 tests)

| Test | Verifica |
|------|----------|
| `test_get_healthy_returns_preferred` | Primary CLOSED → devuelve primary |
| `test_get_healthy_skips_open` | Primary OPEN → devuelve fallback |
| `test_get_healthy_all_open_returns_preferred` | Todos OPEN → devuelve primary |
| `test_report_success_resets` | `report_success()` → circuit CLOSED |
| `test_report_failure_increments` | `report_failure()` → incrementa failures |

### Integración Agent (~4 tests)

| Test | Verifica |
|------|----------|
| `test_fallback_on_provider_failure` | Mock primary falla → Agent usa fallback |
| `test_system_message_on_switch` | Provider switch → yield ("system", ...) |
| `test_no_fallback_mid_stream` | Error durante stream → error, no retry |
| `test_all_providers_fail` | Todos caen → yield ("error", ...) |

**Total: ~17 tests nuevos** (106 actuales → 123)

## Fuera de alcance

- Estado del circuit en ActivityIndicator (opcional, pospuesta)
- TUI tests (siguiente feature)
- Health check periódico activo (el recovery es pasivo, on-demand)
- Métricas/Prometheus
- Persistencia del estado del circuit entre sesiones

## Dependencias

Sin dependencias nuevas. Usa `time.monotonic()` (stdlib) para timeouts y el `httpx` existente.
