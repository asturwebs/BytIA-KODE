# HANDOFF — BytIA-KODE (B-KODE)

> Memoria transferible del repo. Leer ANTES de asumir contexto. Actualizar al cerrar sesión significativa.
> Última actualización: 2026-10-03 (v0.8.6 — parcheo de seguridad: 17 alertas Dependabot cerradas + suelos en extras. Antes: v0.8.5 — anexo DEVOPS §5: la versión nunca se inventa. Antes: v0.8.4 — AST-33: gate CI de verdad ejecutable del README + fix `--bot` y `TELEGRAM_API_BASE` de AST-32; antes: v0.8.3 — AST-30: política de workspace de AST-26 y blindaje content-plane de AST-27, **publicada en PyPI** 2026-09-28 desde main `2521890`; v0.8.2 — AST-25: blindaje de cancelación de AST-24; v0.8.1 — AST-23: README profesional + estreno del flujo OIDC + `--version` + `.vendor-version` real)
>
> Cambios del **2026-09-21** incorporados: guardarraíl **JEVAL** (`cf66bec`, modos `off`/`shadow`/`enforce`, default `off`), modo **shadow** fire-and-forget (`ab6554b`), TTS local vía **`bytia-tts` + piper** — sustituye al TTS en la nube de la era WSL (`4b12ca7`), y botón de audio que vuelve a "Escuchar" al terminar (`768d3ff`). Sesiones anteriores a esta oleada: ver `docs/devlog/` y `reports/`.

## Qué es

Agente CLI propio (Python 3.11+ / Textual): agente + skills + terminal.
"Efectividad > Coste. Zero Hype. Truth > Comfort."

## Estado

- **Versión**: `0.8.6` (bump 2026-10-03, parcheo de dependencias: pyjwt 2.15.1, urllib3 2.8.0, sentence-transformers 5.6.1 en `uv.lock` + suelos de seguridad en los extras `mcp`/`memory`; cierra las 17 alertas Dependabot y el PR #7. Ninguna era dependencia del paquete base). Publicadas en PyPI: 0.8.1 (2026-09-27, primer OIDC), 0.8.2, 0.8.3 (2026-09-28), 0.8.4 (2026-09-29), 0.8.5 (2026-10-03). MCP sigue WIP/stub, no feature
- **Tests**: **482/482 ✅** (recuento **observado** el 2026-10-03: `python -m pytest -q` → 482 passed en 50 s. Esta línea venía diciendo 466, ya por detrás de los 477 que declaraba el ROADMAP en v0.8.4 — es exactamente la deriva que señaló el anexo DEVOPS §11; aquí queda con el número real y su fecha). Histórico: (`PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider -q`, verificado sin `TYPESAFE_API_KEY` en el entorno; AST-22 añadió `test_canonical_install` + `test_release_workflow`, AST-23 añadió `test_version_flag` + `test_vendor_version`, AST-24 añadió `test_cancellation_armor` + `test_tui_interruption` — +17: blindaje de cancelación y primeros tests de TUI; AST-26 +49 (`test_workspace_policy`: política de workspace), AST-27 +40 (blindaje content-plane) — 466). La suite fue **hermetizada en la oleada O0** (issue hermana **O0-A / AST-11**, commit `38f2053`): el gate JEVAL ya no exige `TYPESAFE_API_KEY` y desapareció la basura `MagicMock/` en el árbol (antes del fix: 180/184). Las oleadas **O1** (T1 allowlist, T2 SSRF, T4 trusted paths, T8 redacción; commits `a2cb332`+`a4f9da1`+`f6143f9`) y **O2** (7 quick wins de núcleo; commit `2341a78`) añadieron 59+18 tests de regresión sobre los 184 herméticos. Post-merge, la **ronda F** de endurecimiento de la capa 2 del BashTool añadió 53 más: tests propios del escáner de secretos (`fa9ce29`+`e98fb5b`), F1 flags de programa inline (`670b056`, AST-18) y F2 programa posicional de awk/gawk (`ddfc27d`, AST-19). El **build id** (`61604aa`, AST-20) añadió 17 tests de estampa/`version_label` sobre los 314.
- **Hotfix 2026-09-16** (`3a1b9ee`): failover vivo — pin solo en F3 (guard `_provider_sync`), router pineable de nuevo (`list_pinnable()`; F3→primary pina el router). 2 bugs HIGH hallados por OpenCodeReview revisando `ae97b37`. Detalle: `docs/devlog/2026-09-16.md`
- **Auto-sanado verificado (16-sep, auditoría)**: sin pin, cada chat camina desde la cabeza (`get_healthy`) y el half-open del breaker reintenta el Studio a los 60 s — se recupera solo, sin F3 ni reinicio (`test_self_heal_returns_to_chain_head_after_recovery`). Residual real: el reintento half-open puede costar un arranque en frío del Studio; el failover en-chat continúa y el mensaje no se pierde.
- **Selección directa de providers (2026-09-16)**: **F1 = modo AUTO** (pin(None), reversible desde cualquier pin) · F4 Studio · F5 Ollama · F6 Z.ai · F7 DeepSeek · F8 Router (pin manual, aviso de circuito) · F3 cicla. Resuelve el "slot Auto" pendiente del re-review ocr.
- **CI**: `.github/workflows/ci.yml` — validación (metadata + tests + wheel + twine). Push a main NO deploya.
- **Release**: `.github/workflows/release.yml` (AST-22) — push de tag `v*` → gates + `uv build` → `pypa/gh-action-pypi-publish` por **OIDC/Trusted Publishers** en el environment `pypi` (required reviewer = PROD GATE del Socio) → **GitHub Release automática** con notas extraídas del CHANGELOG (job `github-release`, AST-23). Cero secretos en el repo. **Fail-closed**: hasta que el Socio registre el Trusted Publisher en PyPI (owner `asturwebs`, repo `BytIA-KODE`, workflow `release.yml`, environment `pypi`), el job publish falla en el intercambio OIDC — eso es por diseño. El proceso completo, paso a paso: `RELEASING.md` (AST-23).
- **Instalación canónica (AST-22)**: `pip install bytia-kode` / `uv tool install bytia-kode` (PyPI). `install.sh` hace bootstrap de uv → instala desde PyPI → configura `~/.bytia-kode/.env`. El clone es SOLO desarrollo.
- **Lanzador**: `~/.local/bin/bytia-kode` — en **esta máquina** sigue siendo el **wrapper bash de la era clone** (143 B, 15-sep): `exec ~/Projects/BytIA-KODE/.venv/bin/bytia-kode`, y ese venv tiene el paquete en **editable** (`direct_url.json` → `"editable": true`), así que `--version` sale con SHA git (`0.8.4+91fb426`) en vez de versión pelada. Es el camino de **desarrollo**, no el canónico: en una instalación de PyPI el lanzador es el console script real (entry `bytia_kode.__main__:main`, AST-22: despacha `--bot`; AST-23: `--version` imprime `versión (+ build id)` y sale 0). Verificado 2026-10-03 — hasta hoy esta doc afirmaba que el wrapper "ya no existe", inexacto para esta máquina. Las skills vendor se re-siembran solas cuando cambia la versión instalada (`importlib.metadata`, AST-23 — antes el sello decía "unknown" en installs de PyPI y el reseed nunca disparaba).
- **Cerebro**: `~/.bytia-kode/` (config, sesiones SQLite, temas, `mcp_servers.json`)

## Arquitectura en 30 segundos

```
src/bytia_kode/
├── tui.py        # BytIAKODEApp (Textual). ActivityIndicator.set_status = choke point de estados
├── agent.py      # loop agéntico
├── providers/    # multi-provider + failover local-first + circuit breaker
├── mcp/          # cliente MCP (Adapter sobre Tool registry)
├── herdr.py      # puente herdr: auto-reporte al panel de agentes del multiplexor
├── session.py    # persistencia SQLite de sesiones
├── skills/       # loader de skills
└── telegram/     # bot (--bot)
```

## Integración herdr (2026-09-15, commit bc24e04)

Si corre en un pane de herdr (`HERDR_PANE_ID`), el TUI se auto-reporta al panel
de agentes del multiplexor (label `bytia-kode`, estados working/idle/blocked).
También ancla el id de sesión activa (`--agent-session-id`, re-ancla en /load
y /new) — herdr 0.8.2 lo acepta pero aún no lo expone (forward-compatible).
Kill-switch: `BYTIA_KODE_HERDR=0`. Detalles y gotcha del parser CLI 0.8.2
(positional antes que opciones): docstring de `src/bytia_kode/herdr.py`.

## Decisiones vivas

- **Cadena auto v3 (2026-09-15 noche, `ae97b37`)**: `unsloth(Studio bandeja) →
  local(ollama) → fallback(z.ai) → deepseek`. El ROUTER (:8080) es **BAJO DEMANDA**:
  fuera del walk de failover — no se auto-despierta nunca; solo pin manual (F3) o
  último recurso si TODO caído. El sondeo lee su catálogo (GET /v1/models no carga
  modelo) para tener el preset listo en la demanda. Evolución: v2 (`27934dc`) puso
  primary primero; el Socio migró a Studio-en-bandeja (autostart + idle-unload 300s)
  y pidió que el router no cargue solo. `active_provider` inicial = 1º de la cadena.
- **Estados → herdr**: `ready→idle`, `thinking/tool/skill→working`. Aún no hay
  prompt de aprobación nativo → `blocked` soportado en el mapa pero sin emisor.
- **CLI de herdr, no socket**: interfaz pública estable > protocolo interno.
- venv con `uv`; tests con pytest; estilo: docstrings/comentarios en español.

## Pendiente (próxima sesión)

- MCP (v0.8.0) — **WIP / experimental, NO feature de la release** (decisión del Socio, 2026-09-27):
  la optional dep **`[mcp]` YA existe** en `pyproject.toml` (`mcp>=1.28.1,<2`),
  y con ella instalada `import bytia_kode.mcp` **cae al stub** en lugar de romper
  (fix de la issue hermana **O0-B / AST-12**, commit `5537803`, cerrada +
  smoke de extras `[mcp]` en CI). Quedan pendientes `mcp/manager.py` lifecycle,
  wiring bootstrap en agent+tui y `McpTool.execute()` (`TODO(human)`).
  La TUI no depende del paquete mcp.
- Dependabot: ✅ **36 vulns cerradas (2026-09-15, `uv lock` quirúrgico de 12
  paquetes; `mcp` pineado `>=1.28.1,<2` para evitar major 2.x sin tests)** —
  verificar que GitHub cierra las alerts tras el re-escaneo
- Emisor de estado `blocked` cuando exista flujo de aprobación de tools
- Upstream herdr: que exponga/persista sesiones self-reported (hoy las traga)

## Telegram bot (2026-09-15, servicio activado por el Socio)

- **Servicio**: `bytia-kode-telegram.service` (systemd USER, enabled — arranca al
  boot vía Linger). Activo y polleando (`api.telegram.org` ESTABLISHED, 0 restarts).
- **Invocación correcta**: `.venv/bin/python -m bytia_kode --bot` — el binario del
  venv (`bytia-kode`) apunta a `tui:run_tui` e IGNORA argv (por eso `--help` lanza
  la TUI). Un solo poller: lanzar `--bot` a mano en otra máquina/proceso da 409.
- Token + allowed_users en `~/.bytia-kode/.env` (600). PATH del unit incluye shims
  mise + `~/.local/bin` (tools del agente).

## Gotchas

- **Bump de versión en el clon editable ⇒ `uv sync` obligatorio**: `--version` lee la versión del `dist-info` **instalado**, no del `pyproject.toml` del árbol. Si bumpeas y no re-sincronizas el venv, el gate de claims del README se pone rojo (`--version` imprime la vieja) y bloquea el commit. Pasó al preparar v0.8.5 (2026-10-03). En CI no ocurre porque reinstala el paquete en cada corrida. Si `uv sync` no basta, el síntoma es siempre el mismo: `ls .venv/lib/python3.*/site-packages/bytia_kode-*.dist-info`.
- `git pull` antes de trabajar: otras sesiones de Claude pueden commitear en paralelo (ha pasado).
- El parser del CLI `herdr` 0.8.2 exige `<PANE_ID>` antes que las `--opciones`.
