# Roadmap - BytIA KODE

## Estado actual: v0.3.0 (Alpha estable)

### Completado en v0.3.0

- [x] Arquitectura agéntica con loop think → act → observe
- [x] TUI (Textual) + CLI simple + Bot Telegram
- [x] Identidad constitucional en YAML empaquetado
- [x] Multi-provider OpenAI-compatible (primary, fallback, local)
- [x] Tools: bash (allowlist), file_read, file_write
- [x] Seguridad: command injection mitigado, path traversal bloqueado, fail-secure
- [x] Async I/O: subprocess y disco no bloquean el event loop
- [x] Benchmark: 4.90x speedup concurrente vs secuencial
- [x] 17 tests con pre-commit hook (validación + secret scan + pytest)
- [x] Auditoría profesional completa

---

## v0.4.0 — Estabilidad y herramientas

**Objetivo:** Mejorar la experiencia de desarrollo y la robustez del agente.

- [ ] Streaming token a token en la TUI (deltas del provider en tiempo real)
- [ ] Safe mode backend real (confirmación de comandos destructivos)
- [ ] Tools de exploración: `grep`, `tree`, `glob` nativos en Python
- [ ] Integración Git autónoma (diffs, branches, commits desde la TUI)
- [ ] Auto-fallback de providers con circuit breaker
- [ ] Cobertura de tests >= 60%
- [ ] Rate limiting en Telegram

## v0.5.0 — Memoria y plugin system

**Objetivo:** Memoria semántica y extensibilidad.

- [ ] Tool auto-discovery (plugin system dinámico)
- [ ] Memoria vectorial con FAISS/ChromaDB (búsqueda semántica)
- [ ] Telegram multi-user con aislamiento por sesión
- [ ] System prompt caching optimizado
- [ ] Soporte para custom tools vía directorio de usuario

## v0.6.0 — Multi-agente

**Objetivo:** Escalar a equipo de desarrollo virtual.

- [ ] Architect Agent → desglosa tareas complejas
- [ ] Coder Agent → implementa archivo por archivo
- [ ] Reviewer Agent → revisa calidad y seguridad
- [ ] Ejecución asíncrona de tareas largas
- [ ] Generación automática de Pull Requests

## v1.0.0 — Producción

**Objetivo:** Release estable para uso diario.

- [ ] CI/CD con Docker para validación aislada
- [ ] Auto-corrección con linters (ruff, mypy)
- [ ] Web search tool integrada
- [ ] Documentación completa con ejemplos
- [ ] Cobertura de tests >= 80%

---

## Dependencias opcionales futuras

```toml
[project.optional-dependencies]
local = ["llama-cpp-python>=0.3"]
memory = ["sentence-transformers>=4.0", "faiss-cpu>=1.11"]
```
