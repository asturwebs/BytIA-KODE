# Addendum de trazabilidad — el corte de SHAs del rewrite de historia

**Aplica a:** todos los reports de este directorio (AST-1…AST-4 y pasadas de rol).
**Verificado:** 2026-10-03, AST-34, contra `main@c760ce7` con corrida propia: conteo y orfandad `git cat-file` en clon fresco post-rewrite (verificación cruzada con la del Socio, idéntico resultado), API de GitHub, y artefactos PyPI descargados.

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

**Ningún SHA citado debe usarse como base de operaciones git** contra el repo
(checkout, diff, cherry-pick, compare, bisect): **ninguno resuelve**. Citar un
SHA de estos es citar una **referencia de época**; si hay que resolverlo, la
fuente autoritativa es el bundle, no GitHub.

### La cuenta exacta (verificación cruzada Socio + CTO, 2026-10-03)

Los `reports/*.md` citan **34 strings con forma de SHA** (incluido el fragmento
del nombre del anexo DevOps). De ellos, **32 son SHAs de commit reales y los 32
son huérfanos — 0 resuelven**: verificación del Socio contra el bundle (terminal
PI, `git cat-file` uno a uno), reproducida por el CTO en un clon fresco
post-rewrite con idéntico resultado (0/34). Los otros 2 (`de57bd59`, en el
nombre del anexo, y `41962dab`) son fragmentos de UUID de las pasadas DevOps,
no commits. Citas más frecuentes: `768d3ff` (6 informes), `ab6554b` (5),
`cf66bec` (4), `4b12ca7` (4), `5fe9c1f` (3).

**Los 32, por origen** (todos huérfanos, `git cat-file` en clon): oleada O0
`2341a78` `38f2053` `5537803` `6541aba` · oleada O1 `a2cb332` `a4f9da1`
`f6143f9` · estado-real `edff66d` `28d89e6` `594098d` `3505b7b` `68cf37a` ·
reports de rol `768d3ff` `4b12ca7` `ab6554b` `cf66bec` `16407a0` `5fe9c1f`
`3a1b9ee` · era releases `2521890` `91fb426` `64ce5c9` `7ee7b88`.

> **Nota para quien use la API/web de GitHub:** el día de la verificación, 11
> de estos commits (`768d3ff` `4b12ca7` `ab6554b` `cf66bec` `16407a0`
> `5fe9c1f` `3a1b9ee` `2521890` `91fb426` `64ce5c9` `7ee7b88`) aún eran
> **visibles en el servidor** — la web los muestra — porque cuelgan de refs de
> PR heredadas (`refs/pull/4`–`refs/pull/7`) o de objetos aún no purgados.
> Es visibilidad volátil del lado servidor: en ningún clon resuelven y no
> forman parte de la historia de main — `7ee7b88` (el commit que construyó
> 0.8.6) y `0417e76` (el tag v0.8.6 actual) son gemelos con el mismo mensaje
> y fecha. No confundir "la web lo muestra" con "resuelve".

### Dónde resuelve cada cosa (mapa práctico)

- **GitHub `main` post-rewrite:** los tags apuntan a los gemelos nuevos —
  `v0.8.4→e1366d1`, `v0.8.5→9e912aa`, `v0.8.6→0417e76` (peeled).
- **Workspaces Paperclip:** la historia pre-rewrite sigue viva en el checkout
  compartido (los SHAs de commit citados arriba resuelven ahí) — válida para
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
