# BytIA KODE - Development Log

## 2026-04-01 - Sesion 1: Nacimiento

### Contexto
- Pedro vio explotar el repo `instructkr/claw-code` en GitHub (~100K estrellas en horas)
- Investigamos: clean-room rewrite en Python+Rust del source filtrado de Claude Code
- Se decide crear BytIA-KODE desde cero en Python, inspirándose en arquitectura de tools, skills y loop agéntico

### Arquitectura base implementada

```text
src/bytia_kode/
├── config.py
├── agent.py
├── tui.py
├── cli.py
├── providers/
│   ├── client.py
│   └── manager.py
├── tools/
│   └── registry.py
├── skills/
│   └── loader.py
├── memory/
│   └── store.py
└── telegram/
    └── bot.py
```

### Testeo inicial
- Tests unitarios: 4/4 passing

---

## 2026-04-02 - Sesion 2: Hardening + UX + Documentación

### Fixes técnicos aplicados

1. `file_write` ya soporta rutas relativas sin romper (`os.makedirs("")` evitado)
2. Cliente provider robustecido ante respuestas parciales/malformadas
3. `chat(stream=True)` ahora falla explícitamente con mensaje claro para usar `chat_stream()`
4. Loop del agente tolera tool-calls incompletas y evita duplicar texto en llamadas múltiples
5. Bot de Telegram con guardas defensivas en handlers y logging menos sensible

### Fix crítico TUI (reportado en producción)

- Error observado por usuario:
  - `NoMatches: No nodes match '#input-field' on Screen(id='_default')`
- Causa raíz:
  - faltaba el `compose()` en `BytIAKODEApp`, por lo que no se montaban `#input-field`, `#chat-area` y `StatusBar`
- Solución:
  - se restauró `compose()` con la estructura completa de widgets

### Verificación

- `uv run pytest -q` -> `6 passed`
- `uv run python -m compileall -q src/bytia_kode` -> OK

### Nota operativa para instalación global

Si se ejecuta con `uv tool install`, hay que reinstalar tras fixes para evitar binario desfasado:

```bash
uv tool uninstall bytia-kode
uv tool install /home/asturwebs/bytia/proyectos/BytIA-KODE
```

### Documentación actualizada

- `README.md` actualizado (estado real, troubleshooting, comandos, verificación)
- `ROADMAP.md` creado como fuente canónica de planificación

### Pendientes priorizados

- Integración de memoria semántica real (FAISS/BytMemory API)
- Bloqueo real de herramientas peligrosas en safe mode (backend)
- Mejorar cobertura de tests en TUI y flujo de tools
- Versionado consistente entre banner TUI y paquete
