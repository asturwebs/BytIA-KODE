# Auditoría de Seguridad — BytIA-KODE v0.3.0

**Fecha:** 2026-04-02
**Auditor:** BytIA (agente especializado)
**Alcance:** Todos los archivos fuente del proyecto

---

## Resumen Ejecutivo

| Métrica | Valor |
|---------|-------|
| Hallazgos CRITICAL | 1 |
| Hallazgos HIGH | 3 |
| Hallazgos MEDIUM | 4 |
| Hallazgos INFO | 2 |
| **Recomendación** | **NO desplegar en producción hasta mitigar SEC-001, SEC-002, SEC-003** |

---

## SEC-001: Command Injection en BashTool — CRITICAL (95/100)

**Impacto:** Ejecución arbitraria de comandos del SO con privilegios del usuario que ejecuta la aplicación.

**Evidence:** `src/bytia_kode/tools/registry.py:61-70`

```python
result = subprocess.run(
    command,
    shell=True,  # <-- VULNERABLE
    ...
)
```

**Cadena de ataque:**
1. Usuario envía mensaje → `telegram/bot.py:85`
2. Mensaje pasa al Agent → `agent.py:86-88`
3. Proveedor LLM responde con `tool_calls` → `agent.py:115-118`
4. Argumentos del tool call van directos a `BashTool.execute()` → `agent.py:140`
5. Comando ejecutado con `shell=True` sin validación → `registry.py:63-65`

**Vectores:** Proveedor LLM malicioso, prompt injection indirecta vía archivos, MITM si endpoint no usa HTTPS.

**Fix:** Usar allowlist de comandos + `shell=False` + sandbox de directorio.

---

## SEC-002: Path Traversal en FileReadTool — HIGH (88/100)

**Impacto:** Lectura de archivos arbitrarios del sistema (SSH keys, configs, DBs).

**Evidence:** `src/bytia_kode/tools/registry.py:95-102`

```python
p = os.path.expanduser(path)  # Sin validación
with open(p, "r") as f:
    lines = f.readlines()
```

**Fix:** Validar que `path.resolve()` esté dentro de directorios permitidos. Bloquear patrones como `.ssh`, `.gnupg`, `.env`.

---

## SEC-003: Path Traversal en FileWriteTool — HIGH (90/100)

**Impacto:** Escritura de archivos arbitrarios. Sobrescribir `~/.bashrc`, `~/.ssh/authorized_keys`, inyectar código en proyectos.

**Evidence:** `src/bytia_kode/tools/registry.py:122-129`

**Fix:** Misma validación de paths que SEC-002 + límite de tamaño de archivo.

---

## SEC-004: API Key Expuesta en .env — HIGH (85/100)

**Impacto:** Credenciales en `.env` que puede ser commiteado por error.

**Evidence:** `.env:1-22`, `.env.example`

**Fix:** Pre-commit hook que bloquee commits de `.env` + escaneo de secrets en git history.

---

## SEC-005: Telegram Bot Open by Default — MEDIUM (82/100)

**Impacto:** Si `TELEGRAM_ALLOWED_USERS` está vacío, el bot acepta mensajes de CUALQUIER usuario.

**Evidence:** `src/bytia_kode/telegram/bot.py:32-36`

```python
if not allowed:
    return True  # No filter = open to all  <-- INSEGURO
```

**Fix:** Cambiar a fail-secure: denegar por defecto si no hay allowlist configurada.

---

## SEC-006: Input Validation Insuficiente en Tool Arguments — MEDIUM (80/100)

**Impacto:** Argumentos de tools pasados directamente desde respuesta LLM sin validación de tipo, rango o formato.

**Evidence:** `src/bytia_kode/agent.py:116-129`

**Fix:** Validar con Pydantic: tipos, rangos (timeout 1-300s), formatos.

---

## SEC-007: Sin Rate Limiting en Bot Telegram — MEDIUM (75/100)

**Impacto:** Abuso de API del proveedor por usuario autorizado con muchos mensajes rápidos.

**Evidence:** `src/bytia_kode/telegram/bot.py:78-102` — sin mecanismo de rate limiting.

**Fix:** Implementar rate limiting por usuario (ej: 10 msg/minuto).

---

## SEC-008: Sin Validación de Respuestas del Proveedor — MEDIUM (78/100)

**Impacto:** Proveedor LLM malicioso puede enviar respuestas manipuladas.

**Evidence:** `src/bytia_kode/providers/client.py:94-118`

**Fix:** Validar tamaño máximo de respuesta, límite de tool_calls, caracteres de control.

---

## SEC-009: Logging Insuficiente para Incident Response — INFO (60/100)

**Impacto:** Dificulta detección y respuesta a incidentes.

**Fix:** Structured logging con context (tool, command_hash, user_id, timestamp).

---

## SEC-010: Dependencias Sin Análisis de Vulnerabilidades — INFO (55/100)

**Impacto:** Deps con vulnerabilidades conocidas pueden comprometer la app.

**Evidence:** `pyproject.toml:23-34` — versiones sin pin exacto.

**Fix:** `pip-audit`/`safety` en CI + dependabot configurado.

---

## Acciones Prioritarias

| # | Issue | Acción |
|---|-------|--------|
| 1 | SEC-001 | Deshabilitar BashTool o implementar allowlist INMEDIATAMENTE |
| 2 | SEC-002/003 | Implementar validación de paths antes del próximo release |
| 3 | SEC-004 | Escanear historial git + pre-commit hooks |
| 4 | SEC-005 | Cambiar default a fail-secure en Telegram |
| 5 | SEC-006-008 | Validación de input + rate limiting |

## Estado Post-Mitigación

- **SEC-001 — MITIGADO** en commit `b36f7d8` mediante allowlist de binarios, eliminación de `shell=True` y ejecución segura del tool `bash`.
- **SEC-002 — MITIGADO** en commit `b36f7d8` mediante validación de rutas resueltas dentro de `Path.cwd()` para lectura de archivos.
- **SEC-003 — MITIGADO** en commit `b36f7d8` mediante validación de rutas resueltas dentro de `Path.cwd()` para escritura de archivos.
- **SEC-005 — MITIGADO** en commit `b36f7d8` aplicando política fail-secure en Telegram: denegación por defecto sin allowlist.
