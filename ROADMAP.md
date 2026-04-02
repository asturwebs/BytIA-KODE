# ROADMAP - BytIA KODE

Este roadmap prioriza estabilidad, seguridad y capacidad real de “coding agent” antes de añadir features.

## Objetivos

- Experiencia fiable en TUI y Telegram
- Integración de memoria útil (persistencia y recuperación)
- Tooling seguro (evitar ejecuciones peligrosas por prompt injection)
- Base de tests que permita iterar sin romper producción

## Fase 0: Estabilización (Now)

- TUI estable
  - Asegurar que el layout siempre monta `#input-field`, `#chat-area` y `StatusBar`
  - Manejo de errores amigable (sin tracebacks en UI)
- Instalación global consistente
  - Documentar flujo `uv tool install` y reinstalación tras cambios
- Versionado consistente
  - Unificar versión mostrada (banner TUI / pyproject / telegram)

## Fase 1: Seguridad de herramientas (Next)

- Safe mode real (backend)
  - Permitir/denegar tools desde configuración
  - Confirmación obligatoria en tools “peligrosas” (bash y escritura)
- Hardening de `bash`
  - Desactivar `shell=True` o limitar comandos con allowlist
  - Limitar workdir a un sandbox o a un conjunto de rutas permitidas

## Fase 2: Memoria útil (Next)

- Definir API de memoria
  - `remember(key, value)` / `search(query)` / `summarize_context()`
- Integración BytMemory real
  - Conector a FAISS / sentence-transformers o API externa
  - Persistencia de “context snippets” relevantes por sesión/proyecto

## Fase 3: Skills iniciales (Later)

- Paquete de skills base
  - “devops”, “python”, “refactor”, “testing”, “docs”
- Carga y priorización
  - Convención de naming y niveles de prioridad

## Fase 4: Tools de productividad (Later)

- `grep/search` tipo `rg`
- `web_search` (si se habilita)
- `file_tree`/`ls` con límites

## Fase 5: Streaming y UX avanzada (Later)

- Streaming real en el loop agéntico
  - Deltas de texto + ejecución de tools sin bloquear UI
- Mejoras de TUI
  - Historial mejorado, copiado de bloques de código, panel de estado

## Métricas de éxito

- 0 crashes en arranque TUI
- Tests mínimos: agent loop, provider parsing, tools críticas, telegram handlers
- Safe mode bloquea efectivamente tools peligrosas
- Memoria devuelve resultados relevantes y reduce repetición
