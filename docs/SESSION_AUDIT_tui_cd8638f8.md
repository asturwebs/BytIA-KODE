# Session Audit: tui_cd8638f8

**Fecha:** 2026-04-19 | **Duración:** 16:04 → 17:55 (~2h) | **Mensajes:** 250
**Source:** TUI B-KODE | **Modelo:** (provider fallback, ver notas)
**Auditor:** BytIA (Claude Code) | **Fecha auditoría:** 2026-04-19

---

## Resumen Ejecutivo

Sesión de consultoría + ejecución para refactorizar asturwebs.es (WordPress → Astro + Docker). La fase de consultoría (msgs 1-30) fue excelente, pero la fase de ejecución (msgs 31-250) colapsó en un bucle de ~70 mensajes por desconocimiento de las limitaciones del propio sandbox del agente.

**Veredicto global: 4/10** — Consultoría brillante destruida por fallo ejecutivo severo.

---

## Timeline por Fases

### Fase 1: Consultoría Web (msgs 1-21) — 9/10

| Msg | Acción | Resultado |
|-----|--------|-----------|
| 1 | Pedro pregunta si puede navegar internet/repos | Confirmación clara de capacidades y límites |
| 3 | Análisis de asturwebs.es via `web_fetch` | Diagnóstico brutal: copywriting pobre, Divi lento, erratas |
| 9 | Propuesta de refactorización completa | WP → Astro + Docker + TypeScript, bien argumentado |
| 11 | Pedro aporta info del VPS Hetzner ARM | B-KODE adapta el plan a infraestructura propia |
| 13 | Resumen del stack tecnológico | Tabla clara: Astro, TS, Tailwind, MDX, SQLite, Docker |
| 15 | Req: mantenimiento por agente + interactividad | Ajuste con MDX para agente, React Islands para UX |
| 17 | Pedro comparte plan validado por Gemini PRO | B-KODE audita: 3 puntos ciegos detectados |
| 21 | Respuesta de Gemini a la auditoría | B-KODE mantiene criterio propio, no se doblega |

**Puntos fuertes:**
- Comunicación directa, cero relleno
- Análisis técnico preciso y honesto
- Adaptación inmediata al contexto del VPS
- Auditoría independiente del plan de Gemini (no consenso, criterio propio)

### Fase 2: Setup (msgs 23-37) — 7/10

| Msg | Acción | Resultado |
|-----|--------|-----------|
| 23-24 | Pedro pregunta por Docker local | Explicación correcta del flujo espejo + HMR |
| 25-27 | Discusión de ubicación del proyecto | Propone `~/Proyectos/asturwebs-v2` |
| 29 | Pedro pregunta si puede crear la carpeta | B-KODE dice "sí" pero el sandbox lo bloquea |
| 31-37 | Intenta crear carpeta + escribe archivos | `mkdir` con brace expansion falla (no hay shell) |

**Problemas:**
- Afirmación incorrecta: "Sí, puedo crearla" → sandbox block
- `mkdir -p ~/Proyectos/asturwebs-v2/{src/content,...}` → brace expansion no funciona en subprocess.exec

### Fase 3: Generación de Código (msgs 38-84) — 6/10

18 archivos generados correctamente via `file_write`, pero todos en el CWD del workspace de BytIA-KODE (contaminación).

**Archivos generados (todos correctos en contenido):**

| Archivo | Chars | Notas |
|---------|-------|-------|
| `.gitignore` | 195 | OK |
| `astro.config.mjs` | 423 | OK |
| `package.json` | 599 | OK |
| `docker-compose.yml` | 1,646 | Reescrito con 3 contenedores |
| `Dockerfile.dev` | 250 | OK |
| `Dockerfile.prod` | 416 | OK |
| `Dockerfile.api` | 258 | OK |
| `nginx.conf` | 1,329 | OK |
| `tailwind.config.mjs` | 608 | OK |
| `Layout.astro` | 9,787 | OK |
| `index.astro` | 11,830 | OK |
| `contacto/index.astro` | 5,935 | OK |
| `servicios/index.astro` | 20,201 | OK |
| `ContactForm.jsx` | 7,013 | OK |
| `api-server.js` | 7,087 | OK |
| `global.css` | 1,407 | OK |
| `env.d.ts` | 85 | OK |
| `favicon.svg` | 250 | OK |

**Problemas:**
- Escritos en CWD (workspace BytIA-KODE) en lugar de `~/Proyectos/asturwebs-v2/`
- Primer intento de escritura directa en destino: `Security violation: path escapes workspace`
- No se proponen alternativas proactivas tras el primer fallo

### Fase 4: El Bucle (msgs 85-158) — 1/10

**Bucle de ~70 mensajes** intentando copiar archivos del CWD a `~/Proyectos/asturwebs-v2/`.

**Cronología del bucle:**

| Rango msgs | Estrategia | Resultado | Veces repetida |
|------------|-----------|-----------|----------------|
| 86-96 | `bash` con pipes/redirects | `Security policy: output redirection not allowed` | ~8 |
| 96-108 | Script bash (`install.sh`) | `Security policy violation: command 'bash' is not allowed` | ~3 |
| 108-124 | "Reconstruir desde cero" + mismo `cp` con pipes | Mismo error | ~5 |
| 124-142 | `cp` individual archivo por archivo | Parcialmente funciona, pero se atasca | ~6 |
| 142-158 | Repite "Tienes razón, Socio" + misma estrategia | No avanza | ~10 |

**Mensaje prototipo del bucle (repetido 30+ veces):**
> "Tienes toda la razón, Socio. Estoy repitiendo el mismo comando sin avanzar. El problema real es que las herramientas de archivo están sandboxeadas al CWD..."

**Patrón observable:** Reconoce el problema → lo verbaliza → no cambia de estrategia → repite.

**Falta de auto-detección:** No hay mecanismo de "he fallado 5 veces seguidas con el mismo error, debo escalar".

### Fase 5: Limpieza (msgs 159-197) — 4/10

| Msg | Acción | Resultado |
|-----|--------|-----------|
| 159 | Pedro: "revisa bien tu workspace, regaste archivos" | B-KODE usa `tree` para diagnosticar |
| 161-180 | Intenta limpiar con `rm` + `rmdir` | Parcialmente exitoso, vuelve a atascarse |
| 183 | Segundo `tree` | Workspace raíz limpio |
| 185-189 | Intenta verificar `~/Proyectos/asturwebs-v2/` | `Security violation: path escapes workspace` |
| 191 | Pedro elimina `(src` manualmente | Correcto |
| 196 | B-KODE confirma: proyecto incompleto en destino | Solo configs raíz, sin código fuente |

### Fase 6: Reconstrucción (msgs 197-250) — 3/10

| Msg | Acción | Resultado |
|-----|--------|-----------|
| 199-221 | Re-genera todos los archivos en CWD | file_write funciona, 12 archivos escritos |
| 223-235 | Intenta `cp` al destino | Archivos raíz OK, subdirectorios fallan |
| 237-249 | `mkdir` + `cp` separados | Algunos directorios no se crean anidados |
| 250 | Escala a Pedro: comando manual | Finalmente pide ayuda |

**Resultado final del proyecto:** Incompleto. Faltan archivos en subdirectorios de `~/Proyectos/asturwebs-v2/`.

---

## Análisis de Causas Raíz

### CR-1: Desconocimiento de las Limitaciones del Propio Sandbox (SEVERO)

**Síntoma:** El agente intenta repetidamente comandos que el sistema rechaza.

**Errores del bash tool documentados en la sesión:**

| Error | Ocurrencias | Tipo |
|-------|-------------|------|
| `output redirection not allowed` | ~20 | Pipes, >, >> |
| `command chain not allowed` | ~10 | &&, ;, || |
| `command 'bash' is not allowed` | 1 | bash script.sh |
| `Security violation: path escapes workspace` | ~5 | file_write/tree fuera de CWD |

**Causa:** El agente no tiene en su system prompt una descripción explícita de que `bash` usa `subprocess.exec` sin shell. No sabe que `{a,b,c}`, `&&`, `|`, `>` son caracteres literales en ese contexto.

**Impacto:** 70+ mensajes de bucle (~28% de la sesión).

### CR-2: Falta de Self-Loop Detection (SEVERO)

**Síntoma:** El agente reconoce verbalmente que está en un bucle pero no toma acción correctiva.

**Patrón observado:**
1. "Tienes razón, estoy repitiendo..."
2. "Voy a cambiar de estrategia..."
3. Ejecuta el mismo comando
4. Mismo error
5. Vuelve al paso 1

**No existe:** Contador de errores consecutivos, mecanismo de escalación, o detección de patrón repetitivo.

### CR-3: Sandbox Path Escapes Workspace sin Alternativa Clara (MODERADO)

**Síntoma:** `file_write` y `tree` rechazan paths fuera del CWD, pero el agente no propone cambiar de directorio de trabajo.

**Opciones no exploradas:**
1. Pedir al usuario que lance B-KODE desde `~/Proyectos/asturwebs-v2/`
2. Generar un script instalador que el usuario ejecute
3. Escribir todos los archivos relativos al CWD y pedir un `cp -r` al usuario

### CR-4: Contaminación del Workspace (MODERADO)

**Síntoma:** 18 archivos de Astro/Docker escritos en el repo de BytIA-KODE.

**Carpetas espurias creadas:**
- `(src` — brace expansion literal
- `{src` — brace expansion literal
- `content,src` — separación por comas literal

**Causa:** `mkdir -p path/{a,b,c}` en subprocess.exec sin shell.

### CR-5: Falta de Escalación Proactiva (MODERADO)

**Síntoma:** El agente sigue intentando resolver el problema durante ~100 mensajes sin pedir ayuda.

**Un agente maduro debería:** Tras 3-5 intentos fallidos, decir: "No puedo resolver esto con las herramientas disponibles. Ejecuta: `comando` en tu terminal."

---

## Fixes Propuestos para el Roadmap

### FIX-1: Bash Tool Limitations en System Prompt [Prioridad: P0]

**Archivo:** `src/bytia_kode/prompts/runtime.default.yaml` o `kernel.default.yaml`

**Qué añadir:**
```yaml
tool_constraints:
  bash:
    description: "Uses subprocess.exec without shell. Each call = single command + args."
    not_supported:
      - "Pipes: |, |&"
      - "Redirections: >, >>, <<"
      - "Chains: &&, ;, ||"
      - "Brace expansion: {a,b,c}"
      - "Shell builtins: source, bash, sh -c"
      - "Glob expansion: *, ? (use glob tool instead)"
    allowed_patterns:
      - "Single command: cp src dst"
      - "With args: mkdir -p path/to/dir"
      - "Multiple calls: call bash N times sequentially"
    escalation: "If a command needs pipes/chains, write a script with file_write and ask the user to execute it."
  file_write:
    description: "Writes files. Paths are relative to CWD (workspace root)."
    constraint: "Cannot write outside workspace root. For external paths, write locally and ask user to copy."
```

**Espera reducir:** ~90% de los errores de bash de la sesión.

### FIX-2: Self-Loop Detection [Prioridad: P0]

**Archivo:** `src/bytia_kode/agent.py`

**Mecanismo propuesto:**

```python
class LoopDetector:
    def __init__(self, max_consecutive_failures=3, window_size=5):
        self.max_failures = max_consecutive_failures
        self.window = []
        self.window_size = window_size

    def record(self, tool_name: str, success: bool, error_msg: str = ""):
        self.window.append((tool_name, success, error_msg))
        if len(self.window) > self.window_size:
            self.window.pop(0)

    def is_looping(self) -> bool:
        if len(self.window) < self.max_failures:
            return False
        last_n = self.window[-self.max_consecutive_failures:]
        return all(not success for _, success, _ in last_n)

    def get_escalation_message(self) -> str:
        errors = [f"{tool}: {err}" for tool, _, err in self.window if err]
        return (
            f"He intentado esta operación {self.max_consecutive_failures}+ veces sin éxito. "
            f"Los errores son: {'; '.join(errors[-3:])}. "
            f"Necesito que ejecutes este comando manualmente en tu terminal."
        )
```

**Integración en agent.py:**
- En el bucle de `chat()`, tras cada tool call fallida, `loop_detector.record()`
- Si `loop_detector.is_looping()` → inyectar mensaje de sistema forzando escalación
- El agente debe generar un comando que el usuario pueda ejecutar, no seguir intentando

### FIX-3: Tool Error Memory por Sesión [Prioridad: P1]

**Archivo:** `src/bytia_kode/agent.py`

**Qué:** El agente debe recordar qué comandos fueron rechazados por security policy y no volver a intentarlos.

```python
class ToolErrorMemory:
    def __init__(self):
        self.blocked_patterns: dict[str, str] = {}  # tool_name -> error_pattern

    def record_block(self, tool_name: str, command: str, error: str):
        key = f"{tool_name}:{self._normalize(command)}"
        self.blocked_patterns[key] = error

    def is_blocked(self, tool_name: str, command: str) -> bool:
        key = f"{tool_name}:{self._normalize(command)}"
        return key in self.blocked_patterns

    def _normalize(self, command: str) -> str:
        import re
        return re.sub(r'[\'"\s]+', '', command)[:50]
```

**Efecto:** Si `bash: cp file | ...` fue rechazado, no volver a intentar ningún comando con `|`.

### FIX-4: Workspace Context Awareness [Prioridad: P1]

**Archivo:** `src/bytia_kode/agent.py` + `src/bytia_kode/tools/registry.py`

**Qué:** Añadir al system prompt dinámico información sobre paths escribibles:

```python
def _build_workspace_context(self) -> str:
    return (
        f"Workspace: {os.getcwd()}\n"
        f"Writable: file_write works relative to CWD only.\n"
        f"External paths: Write locally, then provide user with cp/mv commands.\n"
        f"Trusted paths: {self.config.trusted_paths}"
    )
```

### FIX-5: Proactive Escalation Threshold [Prioridad: P2]

**Archivo:** `src/bytia_kode/agent.py`

**Qué:** Si el agente falla N veces con herramientas, forzar un mensaje tipo:

> "⚠️ **Escalación automática:** No puedo completar esta operación tras {N} intentos.
> Ejecuta en tu terminal:
> ```bash
> {comando_generado}
> ```"

**N propuesto:** 3 fallos consecutivos con el mismo tool.

### FIX-6: Post-Generation Workspace Validation [Prioridad: P2]

**Archivo:** `src/bytia_kode/tools/registry.py` (FileWriteTool)

**Qué:** Tras un batch de escrituras, verificar que los archivos están en paths que pertenecen al proyecto actual:

```python
def _validate_project_boundary(self, path: str) -> bool:
    project_markers = ["pyproject.toml", "package.json", ".git"]
    # Check if path's directory or any parent has project markers
    # If writing would create files outside the known project tree, warn
```

---

## Acciones Inmediatas Requeridas (Post-Audit)

### Acción 1: Verificar estado de `~/Proyectos/asturwebs-v2/`
```bash
tree ~/Proyectos/asturwebs-v2/ -L 4
```
Confirmar qué archivos llegaron correctamente y cuáles faltan.

### Acción 2: Verificar limpieza del workspace BytIA-KODE
```bash
git status
```
Confirmar que no quedan residuos de AsturWebs en el repo.

### Acción 3: Decidir destino del proyecto asturwebs-v2
- Opción A: Completar la copia a `~/Proyectos/asturwebs-v2/`
- Opción B: Regenerar desde cero lanzando B-KODE desde el directorio destino
- Opción C: Ejecutar desde este Claude Code con acceso completo al filesystem

---

## Métricas de la Sesión

| Métrica | Valor |
|---------|-------|
| Mensajes totales | 250 |
| User | 22 (8.8%) |
| Assistant | 125 (50%) |
| Tool calls | 103 (41.2%) |
| Tool calls exitosos | ~40 (38.8%) |
| Tool calls fallidos (security) | ~40 (38.8%) |
| Tool calls fallidos (otros) | ~23 (22.3%) |
| Mensajes en bucle productivo | ~30 (12%) |
| Mensajes en bucle improductivo | ~70 (28%) |
| Intervenciones manuales de Pedro | 4 |
| Archivos generados | 18 |
| Archivos copiados a destino | ~12 (parcial) |
| Duración total | ~2 horas |
| Tiempo en bucle | ~50 min (42%) |

---

*Documento generado por BytIA (Claude Code) — Auditoría de sesión B-KODE tui_cd8638f8*
*Fecha: 2026-04-19 20:30 GMT+2*
