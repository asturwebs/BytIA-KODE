# Escalation Orchestrator — modo multi-agente

> **Estado:** en `main` desde 2026-10-26 (merge `2f68fed`). Sin release en PyPI.
> **Diseño completo:** [`PLAN-escalation-orchestrator-B-KODE.md`](PLAN-escalation-orchestrator-B-KODE.md) (Anexos C y D: decisiones y requisitos).
> **Origen:** adaptación de [GVS5H](https://github.com/slee-persis/GVS5H) (MIT) a repos reales, multi-provider y router llama.cpp.

## Qué es

Un modo opt-in en el que varias instancias **frescas** del modelo resuelven una tarea de código coordinadas por un **ledger en disco** (plan, notas, tareas, registro) en lugar de por un único hilo de conversación:

```
manager (texto)  ── plan + tareas
     │
     ├── ideación (enfoques alternativos)
     │
     └── ronda: worker (Agent con tools) → verificación real → manager
                        │                        │
                        └── edita scratch/       └── pytest/build
```

La diferencia con el agente normal: cada rol arranca con contexto corto y lee el estado del ledger, la verificación es el **ground truth** (no la opinión del modelo) y los presupuestos son duros.

## Cuándo usarlo (y cuándo no)

**Úsalo cuando:**
- La tarea es de código, hay un repo git con tests (o build) ejecutables.
- El agente normal se atasca o da vueltas en una tarea dura.
- Quieres un artefacto revisable (`patch.diff`) sin que el worker toque tu árbol de trabajo.

**No lo uses cuando:**
- La tarea es trivial (el camino normal es más rápido y barato).
- **La tarea consiste en modificar tests** (refactor de suite, subir cobertura): no es elegible por diseño (C8).
- El repo no tiene tests ni build: no hay ground truth.
- El repo tiene cambios sin commitear que quieres incluir: el scratch parte del **HEAD**, no del working tree.
- El repo es de un cliente y el manager no es local (ver Privacidad).

## Requisitos

1. Repo **git** (el scratch es un `git worktree`).
2. Suite de tests o build ejecutable en el repo (`pytest` por defecto).
3. Provider local: el **router llama.cpp** (`:8080`) o `unsloth`; el default `local` apunta a Ollama.
4. `KODE_ESCALATION_ENABLED=true` (kill-switch, apagado por defecto).

## Activación y uso

### TUI

```bash
cd /ruta/al/repo
KODE_ESCALATION_ENABLED=true \
LOCAL_BASE_URL=http://localhost:8080/v1 \
LOCAL_MODEL=qwen38-160k \
bytia-kode
```

Dentro:

```
/escalate Corrige el bug de src/calc.py: add debe sumar
```

### Telegram

```
/escalate Corrige el bug de src/calc.py: add debe sumar
```

El repo es el **cwd del proceso del bot**. Si no es git, responde `ineligible`.

### Qué verás

Progreso por fase (`scratch listo`, `baseline: N fallos preexistentes`, `resultado: done`), el estado final, rondas, tokens y el **patch** (`patch.diff`). El patch **no se aplica solo**: lo revisas y lo aplicas tú.

## Qué hace por dentro

1. **Scratch**: `git worktree` desechable del HEAD del repo en `~/.bytia-kode/workspaces/...`. Tu repo no se toca; al terminar se elimina (también en error).
2. **Baseline**: corre la suite en el scratch **antes** de empezar y registra los fallos preexistentes.
3. **Ciclo**: plan → ideación → `[worker (Agent con tools) → verificación → manager]` hasta `done` o presupuesto.
4. **Verificación real**: `pytest`/build en el scratch. Solo los fallos **nuevos** invalidan la ronda; exit 2/3/4/5 (conftest roto, sin tests…) **no** es verde.
5. **Anti-tamper**: si el worker toca tests, la ronda se invalida, los tests se restauran desde el SHA base (incluidos tests nuevos, ignorados y renames) y dos rondas inválidas consecutivas abortan con `protocol: test-tamper`.
6. **Cierre por ground truth**: tests verdes + worker `solved` → `done`, aunque el manager no lo marque.
7. **Patch**: `git diff` contra el SHA base, sin artefactos (`__pycache__`, `.pytest_cache`, `*.bak`, `*.backup-*`).

## Estados

| Estado | Significado |
|---|---|
| `done` | Tests verdes y tarea cerrada. Patch listo. |
| `budget` | Se agotó un presupuesto (rondas, tokens o wall-clock). El patch puede ser parcial o incluso correcto. |
| `protocol` | El modelo no respetó el protocolo tras el reintento correctivo, o evasión de tests (`test-tamper`). |
| `infra` | Fallo de infraestructura: provider, circuit breaker, timeout del worker, bug del propio runner (`bug:`). |
| `ineligible` | No se puede escalar: kill-switch apagado, repo no-git, marcador de cliente. |

## Seguridad y privacidad

- **Tu repo no se modifica**: todo ocurre en un worktree; el patch se propone, no se aplica.
- **Jail del worker (R5)**: el `Agent` corre con `confined`, root = `scratch/` y trusted paths **vacíos** (no hereda `~/.bytia-kode`). Al terminar se restaura el jail de la sesión.
- **Tests protegidos (C1/R2)**: restauración desde el SHA base con status limpio; un worker que toque tests no puede falsear el veredicto.
- **Privacidad (C2)**: manager **local** por defecto. El modo cloud exige opt-in explícito y está **prohibido en repos de cliente**: el contenido del repo se enviaría al proveedor.
- **VRAM**: workers **secuenciales**; no caben dos instancias del 27B en la 4090.

## Configuración

| Clave | Default | Descripción |
|---|---|---|
| `KODE_ESCALATION_ENABLED` | `false` | Kill-switch global. Sin esto, `ineligible: disabled`. |
| `KODE_ESCALATION_MANAGER_PROVIDER` | `local` | Provider del manager. Cloud solo opt-in. |
| `KODE_ESCALATION_WORKER_PROVIDER` | `local` | Provider del worker (Agent). |
| `KODE_ESCALATION_WORKER_MAX_ITER` | `12` | Techo de iteraciones del Agent worker. |
| `KODE_ESCALATION_MAX_ROUNDS` | `4` | Rondas worker→verify→manage. |
| `KODE_ESCALATION_MAX_TASKS` | `8` | Tareas máximas por plan (truncado registrado). |
| `KODE_ESCALATION_MAX_WALLCLOCK_MIN` | `20` | Tiempo máximo por tarea. |
| `KODE_ESCALATION_MAX_TOKENS` | `200000` | Presupuesto agregado de tokens. |
| `KODE_ESCALATION_PROTOCOL_RETRIES` | `1` | Reintentos correctivos por respuesta inválida. |
| `KODE_ESCALATION_VERIFY_CMD` | `pytest -q --tb=no` | Comando de verificación en el scratch. |
| `KODE_ESCALATION_AUTO_TRIGGER` | `false` | Auto-trigger por estancamiento (fase futura). |

`LOCAL_BASE_URL` / `LOCAL_MODEL` deciden a qué endpoint va el provider `local` (por defecto Ollama `:11434`; para el router, `http://localhost:8080/v1` + `qwen38-160k`).

## Límites conocidos

- **Tareas que tocan tests** no son elegibles (C8).
- **El manager puede no cerrar** aunque los tests estén verdes; el cierre por ground truth lo cubre, pero un `budget` puede dejar trabajo útil sin marcar `done`.
- **Un worker por ronda, secuencial** (VRAM).
- **El patch no se aplica automáticamente**; no hay `git apply` desde el chat.
- **`pyproject.toml`**: solo se restaura la sección `[tool.pytest.ini_options]`; otros cambios legítimos del worker se conservan.
- **Builds no-pytest**: el parser de veredicto está orientado a pytest (`FAILED`, `N passed`); para builds solo cuenta el exit code y el tail.
- **Thinking**: el 80% de los tokens de respuesta del modelo local es traza `<think>` y entra en el presupuesto (F0).

## Troubleshooting

| Síntoma | Causa / solución |
|---|---|
| `ineligible: disabled` | Falta `KODE_ESCALATION_ENABLED=true`. |
| `ineligible: not-a-git-repo` | El cwd no es un repo git. |
| `protocol` con `unexpected section` | El modelo no respeta el protocolo; el reintento correctivo ya actuó. Revisa el modelo/quant. |
| `protocol: test-tamper` | El worker tocó tests dos rondas seguidas; el sistema lo bloqueó (por diseño). |
| `budget` con patch correcto | El manager no cerró o el presupuesto era corto; sube `MAX_ROUNDS`/`MAX_TOKENS`. |
| `infra` | Provider caído, circuit breaker o bug del runner (`bug:` en el detail). |
| `/escalate` → "Unknown command" | Versión anterior a F2; actualiza el CLI. |
| Va a `gemma4` en vez del router | Configura `LOCAL_BASE_URL`/`LOCAL_MODEL`. |

## Números medidos

E2E real (2026-10-26, qwen38-160k, repo con `add` que restaba):

```
status=done  rounds=1  tokens=5870  segundos=163.6
patch: src/calc.py  a - b -> a + b   (limpio)
```

F0 (protocolo textual de GVS5H, 30 llamadas): conformidad 30/30, peor ciclo 9,72 min, peor 19.494 tokens; 79,8% del output es `<think>`.

## Referencias

- Diseño y decisiones: [`PLAN-escalation-orchestrator-B-KODE.md`](PLAN-escalation-orchestrator-B-KODE.md) (Anexo C: C1-C8; Anexo D: R1-R9 + M1-M4).
- Código: `src/bytia_kode/orchestrator/` (protocol, ledger, specs, prompts, runner, verify, workspace, jail, agent_worker, providers, service).
- Tests: `tests/test_orchestrator_*.py`.
