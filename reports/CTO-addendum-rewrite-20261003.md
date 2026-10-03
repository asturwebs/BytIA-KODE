# Addendum de trazabilidad — el corte de SHAs del rewrite de historia

**Aplica a:** todos los reports de este directorio (AST-1…AST-4 y pasadas de rol).
**Verificado:** 2026-10-03, AST-34, contra `main@c760ce7` y la API de GitHub, con corrida propia.

## Qué pasó (resumen; detalle en HANDOFF §"Rewrite de historia")

El 2026-10-03 el Socio aprobó un `git filter-repo` sobre main: 151 trailers
`Co-Authored-By` no canónicos (Claude/Opus/Paperclip y emails fuera de
`bytia@bytia.es`) + 4 trailers `Paperclip-Issue` fueron normalizados/eliminados.
Los commits tocados y los 16 tags (`v0.5.3`–`v0.8.6`) cambiaron de SHA y se
force-pushearon (con el ruleset `protect-main` bajado y rehecho alrededor).
Cada commit reescrito tiene un **gemelo**: mismo árbol, mismo mensaje, mismas
fechas, distinto hash (y ancestros distintos). La historia de la época vive
completa en el bundle pre-rewrite del Socio:
`~/Backups/bytia-kode-pre-rewrite-20261003.bundle` (no accesible desde los
runners Paperclip — declarado, no verificado aquí).

## Qué significa para estos reports

**Ningún SHA citado abajo debe usarse como base de operaciones git** contra el
repo (checkout, diff, cherry-pick, compare, bisect): parte ya no existe y parte
existe pero pertenece a un universo desvinculado de la historia de main. Citar
un SHA de estos es citar una **referencia de época**; si hay que resolverlo, la
fuente autoritativa es el bundle, no GitHub.

### Estado real, verificado contra la API el 2026-10-03

El corte no es uniforme (la línea "todos los SHAs pre-rewrite quedaron huérfanos"
de HANDOFF es cierta en espíritu pero no al SHA):

| Estado | SHAs citados en reports |
|---|---|
| **No resuelven (404)** | `2341a78` `38f2053` `5537803` `6541aba` (oleada O0) · `a2cb332` `a4f9da1` `f6143f9` (O1) · `edff66d` `28d89e6` `594098d` `3505b7b` `68cf37a` (estado-real) |
| **Resuelven hoy** | `768d3ff` `4b12ca7` `ab6554b` `cf66bec` `16407a0` `5fe9c1f` `3a1b9ee` (reports de rol) · `2521890` `91fb426` `64ce5c9` `7ee7b88` (era releases) |

Los que aún resuelven lo hacen porque cuelgan de refs de PR heredadas
(`refs/pull/4`–`refs/pull/7`) o son objetos colgantes que GitHub todavía no ha
purgado — **estado volátil, sin garantía**: pueden desaparecer en cualquier gc.
Que resuelvan NO significa que estén en la historia de main: p.ej. `7ee7b88`
(el commit que construyó 0.8.6) y `0417e76` (el tag v0.8.6 actual) son gemelos
con el mismo mensaje y fecha.

 Patrón observado: los SHAs de las oleadas O0/O1 (26–27 sep, densas en trailers
 no canónicos) cayeron todos; los de los reports de rol (15–21 sep) sobreviven
 por ahora.

### Dónde resuelve cada cosa (mapa práctico)

- **GitHub `main` post-rewrite:** los tags apuntan a los gemelos nuevos —
  `v0.8.4→e1366d1`, `v0.8.5→9e912aa`, `v0.8.6→0417e76` (peeled).
- **Workspaces Paperclip:** la historia pre-rewrite sigue viva en el checkout
  compartido (los 19 SHAs citados arriba resuelven ahí) — válida para
  arqueología local, nunca como base de entrega.
- **Bundle del Socio:** la única fuente completa y estable old→new.

## Artefactos publicados en PyPI (verificado descargándolos)

Los wheels/sdists ≤ 0.8.6 llevan estampas `_commit.txt` de época pre-rewrite:
**0.8.5 estampa `64ce5c9`** y **0.8.6 estampa `7ee7b88`**. En una instalación de
PyPI, `--version` imprime esos SHAs (p.ej. `0.8.6+7ee7b88`) que ya no casan con
la historia de main. Es cosmético y auto-corrige: la primera release construida
sobre la historia nueva (0.8.7+) volverá a estampar SHAs que resuelven.

## Regla para citas futuras

SHA + fecha + fichero del report. Un SHA sin fecha de época es una cita rota en
espera: a partir del 2026-10-03, todo SHA anterior a ese día se trata como
referencia histórica, no como puntero vivo.
