# Addendum de trazabilidad — el corte de SHAs del rewrite de historia

**Aplica a:** todos los reports de este directorio (AST-1…AST-4 y pasadas de rol).
**Verificado:** 2026-10-03, AST-34, contra `main@c760ce7` con corrida propia: inventario **por contexto** de las citas de commit de los 8 reports + orfandad `git cat-file` token a token en clon fresco post-rewrite (0/34 strings resuelven), verificación cruzada triple (terminal PI contra el bundle, terminal Claude Code, CTO), API de GitHub, y artefactos PyPI descargados. *v3 — retira el titular numérico de la v2, no reproducible (§"Historial del error"); v4 — añade la atribución causal (3 clases) y la tabla de traducción completa de las 19 citas, emparejadas y verificadas por patch-id (19/19)*.

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

### El hecho robusto (titular)

**Toda cita de commit en `reports/` es huérfana: 0 resuelven** en un clon
post-rewrite. Verificado token a token con `git cat-file` por tres vías
independientes (terminal PI contra el bundle, terminal Claude Code, CTO contra
clon fresco — mismo resultado). Este titular no depende de ningún filtro de
conteo: es cierto bajo cualquiera. Pero "huérfana" tiene **dos causas
distintas** (§"Atribución causal" abajo): solo **7** lo son *por el rewrite*;
las otras **12** nunca fueron commits de main — son hashes nacidos en el
workspace de Paperclip. Y cada una de las 19 tiene un reemplazo vivo en main
hoy (§"Tabla de traducción").

### Por qué NO hay titular numérico (desglose por forma)

Contar "SHAs citados" con regex sobre strings hex es un método roto: cada
filtro da un número distinto y ninguno clasifica. Sobre los 8 reports
originales:

| Bucket (regex, strings hex únicos de 7–40) | Nº |
|---|---|
| Strings hex únicos | 34 |
| — puros dígitos (ids de objetos mock de las tablas QA/DEVOPS: `126287905920672`, `138477722887104`…) | 11 |
| — fragmentos de UUID (pasadas DevOps `de57bd59` `41962dab` `36f9356fee36` `6666f530b1eb`; agente `d284fe7c`) | 5 |
| — candidatos a cita, filtro "con letras" | 23 |
| — candidatos a cita, filtro estricto (letras, sin UUID conocidos) | 19 |

Los numéricos y los fragmentos de UUID **no son citas de commit** — pero la
forma no clasifica en ninguna dirección: `5537803` es todo dígitos y **sí** es
una cita de commit real (tabla O0 del gates report), mientras que `d284fe7c`
tiene letras y **no** lo es (prefijo del UUID del agente Researcher).

### El inventario por contexto (el que manda)

Cita de commit = token en una línea que nombra commit/SHA/tag, o fila de tabla
con columna Commit. Con ese criterio, los 8 reports citan **19 commits**,
todos huérfanos (`git cat-file`, 0 resuelven):

- oleada O0 (clase 2): `2341a78` `38f2053` `5537803` `6541aba`
- oleada O1 (clase 2): `a2cb332` `a4f9da1` `f6143f9`
- estado-real (clase 2): `edff66d` `28d89e6` `594098d` `3505b7b` `68cf37a`
- reports de rol (clase 1): `768d3ff` `4b12ca7` `ab6554b` `cf66bec` `16407a0` `5fe9c1f` `3a1b9ee`

Más citados (nº de informes que los mencionan): `768d3ff` (6), `ab6554b` (5),
`cf66bec` (4), `4b12ca7` (4), `5fe9c1f` (3).

### Atribución causal (v4) — quién huérfanó a quién

"0 resuelven" es cierto, pero la causa no es una. Resolviendo cada token
contra las fuentes autoritarias — PI: bundle pre-rewrite del host + checkout
del workspace; CTO: checkout del workspace (las 19 resuelven ahí) + clon
post-rewrite (0 resuelven), gemelos verificados por **patch-id 19/19**:

| Clase | Nº | Qué son | ¿Las tocó el rewrite? |
|---|---|---|---|
| Commits reales del repo | **7** | los citados por las pasadas de rol: resuelven en el bundle pre-rewrite (PI) y en la rama `main` del workspace (línea pre-rewrite sincronizada, CTO: 7/7 ancestros de main); todos con gemelo de hash en la historia nueva | **Sí** — las únicas huérfanas-por-rewrite |
| Commits nacidos en el workspace de Paperclip | **12** | oleadas O0/O1 + informes estado-real: hashes creados por `git am`/commits locales en el workspace (`git am` recrea hashes propios); alcanzables solo desde ramas `paperclip/*`, jamás desde `main` (CTO: 12/12 no-ancestros) | **No — nunca fueron commits de main**: esos hashes nunca resolvieron allí; su contenido llegó por transferencia (gemelo de contenido, no de hash) |
| No son commits de nada | **15** | 10 ids de objetos MagicMock de las tablas QA/DEVOPS + 4 fragmentos UUID de pasadas DevOps + `d284fe7c` (UUID del agente Researcher) | N/A |

Es la diferencia entre "no resuelven" (cierto para las 19) y "el rewrite las
huérfanó" (falso para 12): el rewrite no les quitó a las 12 nada que hubieran
tenido en main.

### Tabla de traducción — las 19 citas con reemplazo vivo en main (patch-id 19/19)

Cada par verificado por identidad de parche (`git diff-tree -p <c> | git
patch-id --stable`, CTO); los 7 de clase 1 emparejados además por PI contra
el bundle (asunto + fecha de autor):

**Clase 1 — gemelos de hash** (el rewrite cambió el hash; mismo árbol,
mensaje y fechas):

`768d3ff→f40eeb1` · `ab6554b→7fe27ba` · `cf66bec→548753a` ·
`4b12ca7→b38f0aa` · `5fe9c1f→9048a32` · `3a1b9ee→d55ab10` ·
`16407a0→df71ffe`

**Clase 2 — transferencias de contenido** (el hash citado nació en el
workspace; el gemelo de main nació del apply del parche — mismo asunto, fecha
de autor y parche):

`2341a78→99cda61` · `38f2053→6ccb601` · `5537803→669b343` ·
`6541aba→d4af06f` · `a2cb332→57cff55` · `a4f9da1→1f93520` ·
`f6143f9→c041256` · `edff66d→d199bf2` · `28d89e6→0dd41a4` ·
`594098d→2781b19` · `3505b7b→ab135ce` · `68cf37a→b6df33c`

Quien cite estos commits en el futuro: usar el hash nuevo de la derecha.

### Historial del error (para el registro)

La v2 de este addendum tituló "32 SHAs de commit reales, 32 huérfanos". Ese
número era 34 menos 2 fragmentos UUID conocidos, sin auditar el filtro:
dejaba dentro 10 ids de mock y 2 fragmentos más, y su propia lista enumeraba
23 — de los cuales 4 (`2521890` `91fb426` `64ce5c9` `7ee7b88`) ni siquiera
aparecen en los reports (llegaron importados del contexto PyPI/HANDOFF).
El "32" nació en la terminal PI, la terminal Claude Code lo retransmitió como
verificado, y el CTO lo reprodujo fielmente heredando el defecto. Tres
agentes, un mismo error — **el fallo era del método, no de la ejecución**:
reproducir la aritmética de un conteo no audita su filtro. Corregido en v3:
inventario por contexto y titular = hecho verificable.

> **Nota para quien use la API/web de GitHub:** el día de la verificación, 7 de
> las 19 citas (`768d3ff` `4b12ca7` `ab6554b` `cf66bec` `16407a0` `5fe9c1f`
> `3a1b9ee`) seguían **visibles en el servidor** — la web las muestra — porque
> cuelgan de refs de PR heredadas (`refs/pull/4`–`refs/pull/7`) o de objetos
> aún no purgados; ídem los stamps de release `2521890` `91fb426` `64ce5c9`
> `7ee7b88` (§ PyPI abajo). Es visibilidad volátil del lado servidor: en
> ningún clon resuelven y no forman parte de la historia de main — `7ee7b88`
> (el commit que construyó 0.8.6) y `0417e76` (el tag v0.8.6 actual) son
> gemelos con el mismo mensaje y fecha. No confundir "la web lo muestra" con
> "resuelve".

### Dónde resuelve cada cosa (mapa práctico)

- **GitHub `main` post-rewrite:** los tags apuntan a los gemelos nuevos —
  `v0.8.4→e1366d1`, `v0.8.5→9e912aa`, `v0.8.6→0417e76` (peeled).
- **Workspaces Paperclip:** la historia pre-rewrite sigue viva en el checkout
  compartido — las 19 citas resuelven ahí (las 12 de clase 2 nacieron en el
  workspace; las 7 de clase 1 viven en su rama `main`, línea pre-rewrite
  sincronizada) — válida para arqueología local, nunca como base de entrega.
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

**Regla de método (heredada de la corrección v3):** ningún conteo de "SHAs
citados" por regex sobre strings hex — a los ids de mock y fragmentos de UUID
se cuelan, y las citas casualmente numéricas se caen. El inventario se hace
por contexto (token que nombra commit/SHA/tag, o fila con columna Commit), y
el titular numérico se sustituye por el hecho verificable — aquí: "todas las
citas de commit son huérfanas, 0 resuelven".

## Historial de versiones de este addendum

v1 — matriz de visibilidad API (retirada: confundía visibilidad del servidor
con resolución). v2 — titular "32/32 huérfanos" (retirado: número no
reproducible, ver §"Historial del error"). v3 — inventario por contexto, 19
citas, todas huérfanas. v4 — esta: atribución causal (7 huérfanas-por-rewrite
+ 12 hashes de workspace) y tabla de traducción completa (patch-id 19/19).
