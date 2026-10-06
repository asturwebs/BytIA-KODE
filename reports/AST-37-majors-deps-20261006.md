# AST-37 — Evaluación de majors pendientes de dependencias

**Fecha:** 2026-10-06 · **Autor:** BytIA CTO · **Base:** commit `50b6b15@ws` (sobre `9fb57bd@ws`; hashes del workspace de Paperclip — el contenido de `50b6b15@ws` vive en main como `432c085`)
**Alcance:** SOLO evaluación y recomendación. Cero cambios de dependencias: al cierre de este
informe `pyproject.toml` y `uv.lock` están INALTERADOS (verificación pegada en §6). La
ejecución de cualquier upgrade se decide por el Socio y se hace en issue propia.

Los cuatro paquetes pedidos: `twine 7` (dev), `sentence-transformers 6` (extra memory),
`faiss-cpu 1.15` (extra memory), `llama-cpp-python 0.3.36` (extra local). `mcp<2` NO se
toca: cap deliberado del Socio.

---

## 1. Estado de partida (verificado en este run)

| Paquete | Pin pyproject | Resuelto en uv.lock | Call sites en src/tests |
| --- | --- | --- | --- |
| twine | `>=6.2.0` (dev group, sin tope) | **6.2.0** | 0 (es CLI: CI/RELEASING) |
| sentence-transformers | `>=4.0` (extra `memory`) | **5.3.0** | **0** |
| faiss-cpu | `>=1.11` (extra `memory`) | **1.13.2** | **0** |
| llama-cpp-python | `>=0.3` (extra `local`) | **0.3.19** | **0** |
| mcp | `>=1.28.1,<2` (extra `mcp`) | 1.30.0 | (fuera de alcance) |

- **Cero call sites** para st/faiss/llama-cpp: `grep -rn 'sentence_transformers|faiss|llama_cpp'
  src/ tests/` → vacío. El extra `memory` corresponde a la memoria vectorial del ROADMAP v1.0
  (aún sin implementar) y el extra `local` a inferencia GGUF embebida (hoy el router llama.cpp
  se consume por HTTP en `:8080`, no vía binding Python).
- El árbol pesado del extra memory YA está resuelto en el lock en versión moderna:
  transformers **5.17.0**, huggingface-hub **1.8.0**, torch **2.14.0**, numpy **2.4.4**,
  scikit-learn **1.8.0**, scipy **1.17.1** (todos ≥ floors de st 6 — ver §3.2).
- CI **ya usa twine flotante (7.x)** sin decirlo: `ci.yml` instala `twine` sin pin
  (`pip install ... twine`) y `release.yml` verifica con `uvx twine check` — desde que 7.0.0
  salió (2026-07-27), cada CI verde ha sido verde **con twine 7**. El pin 6.2.0 solo vive en
  el lock/venv local.
- Artefacto local de referencia: `dist/bytia_kode-0.8.4-py3-none-any.whl`, cuyo METADATA
  real estampa **`Metadata-Version: 2.5`** (leído del wheel en este run).

## 2. Probe empírico twine 6.2.0 vs 7.0.0 (este run, venv de scratch)

```
$ PYTHONPATH=.../t62 python3 -m twine --version && python3 -m twine check dist/bytia_kode-0.8.4-py3-none-any.whl
twine version 6.2.0 (keyring: 25.7.0, packaging: 26.3, ...)
Checking dist/bytia_kode-0.8.4-py3-none-any.whl: ERROR InvalidDistribution:
  Invalid distribution metadata: '2.5' is not a valid metadata version        rc=1

$ PYTHONPATH=.../t70 python3 -m twine --version && python3 -m twine check dist/bytia_kode-0.8.4-py3-none-any.whl
twine version 7.0.0 (readme-renderer: 46.0, ...)
Checking dist/bytia_kode-0.8.4-py3-none-any.whl: PASSED                      rc=0
```

Mismo artefacto, dos veredictos. El twine del lock **no puede verificar el paquete que hoy
publicamos**; el de CI (flotante) sí. Esto convierte el "major pendiente" en deuda con
síntoma activo, no teórica.

## 3. Evaluación por paquete

### 3.1 twine 6.2.0 → 7.0.0 (dev)

**Qué aporta** (changelog oficial, 2026-07-27; único release entre 6.2.0 y 7.0.0):
- **"Fix uploading packages with metadata version 2.5" (#1317)** — el caso exacto de
  nuestro wheel; elimina soporte de metadata 2.0 (nunca estandarizada).
- Bugfixes: `.pypirc` leído en UTF-8 (#1268), `--version` muestra subdependencias (#1275),
  bump de `rich` que evita un hang en algunos entornos (#1308), gestión elegante de códigos
  HTTP no estándar de índices (#1309).
- `requires-python >=3.10` (nuestro floor es 3.11): sin impacto.

**Riesgos de breaking contra NUESTRO código:** ninguno. Es herramienta dev, se invoca como
CLI (`twine check dist/*` en ci.yml/release.yml/RELEASING/README — el comando no cambia);
cero imports en `src/`. El único contrato roto (metadata 2.0) es irrelevante: hatchling nos
estampa 2.4/2.5.

**Coste de migración:** re-lock de 1 entrada + sus floors (`rich>=14.3.3`, `packaging>=26.1`,
`id`, `rfc3986` — **todos ya resueltos en el lock**: rich 15.0.0, packaging 26.2, id 1.6.1,
rfc3986 2.0.0). 0 líneas de código, 0 tests tocados. Wheel py3-none-any: riesgo 3.13 nulo.
Para CI es literalmente noop (ya corre 7).

**Recomendación: SUBIR** en issue propia de re-lock. Prioridad dentro de la deuda:
media-alta — el estado actual obliga a recordar "twine-check siempre en venv virgen" como
parche de proceso (lección AST-30); subir borra el parche.

### 3.2 sentence-transformers 5.3.0 → 6.x (extra memory)

**Qué aporta** (release notes oficiales v6.0.0 2026-08-18 y v6.1.0 2026-09-18):
- **MultiVectorEncoder**: cuarto tipo de modelo (ColBERT/late-interaction) además de
  SentenceTransformer/CrossEncoder/SparseEncoder; carga checkpoints PyLate/ColBERT/colpali.
- **Moderniza floors a transformers v5** (línea transformers-5-native), fix de la clase de
  bugs silenciosos de scoring en half-precision, encoding/training más rápidos.
- 6.1.0: guías de eficiencia/benchmarks y mejoras multimodales (menor).

**Riesgos de breaking contra NUESTRO código:** **ninguno hoy** — cero call sites. Los breaks
del major (guía de migración oficial: `CrossEncoder.rank` devuelve floats Python, upcast
float32 en `predict`, `quantize_embeddings` cambia forma de salida, quantización int8
multi-proceso no bit-compatible) afectan a usos CrossEncoder/quantization que no tenemos;
un futuro módulo de memoria usaría `SentenceTransformer.encode` + índice, no esas APIs.

**Coste de migración:** re-lock de 1 entrada. **Todos los floors de st 6 ya están
satisfechos por el lock actual** (verificado contra `requires_dist` oficial de 6.1.0):
transformers `>=5.0,<6` ✓ (5.17.0), hub `>=1.3,<2` ✓ (1.8.0), torch `>=2.2` ✓ (2.14.0),
numpy `>=1.24` ✓ (2.4.4), scikit-learn `>=1.1` ✓ (1.8.0), scipy ✓, typing-extensions
`>=4.10` ✓ (4.15.0), python `>=3.10` ✓ (floor 3.11). 0 líneas, 0 tests (el extra no tiene
cobertura). Wheel py3-none-any: riesgo 3.13 nulo.

**Riesgo de NO subir (matizado):** el lock actual empareja st 5.3.0 (línea diseñada contra
transformers 4.41+) con transformers 5.17.0 — combinación fuera de la línea nativa de
upstream; st 6 es la versión hecha PARA el transformers que ya tenemos. Subir reduce
incoherencia latente, no la crea.

**Recomendación: SUBIR a 6.1.0** en el mismo re-lock. Cap 5.x interino (hasta que se
ejecute): motivo = extra sin uso y sin smoke en CI; no se salta un major sin un test de
humo del extra `memory` (instalar + `SentenceTransformer` fixture mínima), a añadir en la
issue de upgrade. Si el Socio prefiere esperar, ese motivo queda como el registrado del cap.

### 3.3 faiss-cpu 1.13.2 → 1.15.1 (extra memory)

**Qué aporta** (changelog oficial, secciones 1.14.0/1.14.1/1.15.0/1.15.1):
- 1.14.0: stubs PEP 561 (type-checking real), ARM SVE, k-means++/AFK-MC², early stopping.
- 1.14.1: **soporte Python 3.13/3.14** + fix SWIG 4.4 multi-phase init.
- 1.15.0: índices EDEN, mmap para Flat/Vamana, stubs SVS/Panorama, y una pasada grande de
  **endurecimiento de deserialización** (límites de recursión/alocación, rechazo de índices
  nulos) — relevante para quien cargue índices de terceros.
- 1.15.1: fixes de leak (OnDisk), data race NNDescent, validaciones de deserialización.

**Riesgos de breaking contra NUESTRO código:** ninguno hoy (cero call sites). Los breaks de
1.14.0 (RaBitQ qb por defecto 0→4, `ScalarQuantizer` SIMDWidth int→enum, headers RAFT
eliminados) tocan APIs que un futuro módulo de memoria básico (IndexFlat/IVF/HNSW) no usa.

**Coste de migración:** re-lock de 1 entrada. Wheels **cp310-abi3** manylinux_2_28 x86_64
(misma forma que 1.13.2 — lateral en compatibilidad) → **3.13 cubierto por abi3**;
numpy `>=1.25` ✓ (2.4.4); `requires-python >=3.10` ✓ (floor 3.11). 0 líneas, 0 tests.

**Recomendación: SUBIR a 1.15.1** en el mismo re-lock. Coste ~0, elimina un major abierto,
y la versión trae el soporte 3.13 explícito + hardening de deserialización.

### 3.4 llama-cpp-python 0.3.19 → 0.3.36 (extra local)

**Qué aporta** (compare oficial 0.3.19→0.3.36 + pyproject del tag): syncs continuos de
llama.cpp hasta 2026-10 (vendor migrado a la org ggml-org), chat handlers nuevos
(Gemma4, MTMD, NanoLlava renombrado), `chat_template_kwargs` en carga de modelo, soporte
experimental wasm/Pyodide. Nada que necesitemos hoy: consumimos llama.cpp como servicio
HTTP (router :8080), no como binding.

**Riesgos de breaking contra NUESTRO código:** ninguno hoy (cero call sites). Para uso
futuro de bajo nivel, el range trae **renombres masivos de la API C expuesta**:
`llama_token_eos/nl` → `llama_vocab_eos/nl`, `llama_n_vocab` → `llama_vocab_n_tokens`,
`llama_tokenize` cambia firma (`add_bos`→`add_special`, vocab en vez de model/ctx),
`use_mmap/use_mlock` → enums `LLAMA_LOAD_MODE_*`, sessions → `llama_state_*`. La clase
`Llama` de alto nivel sigue estable en firma pública.

**Coste de migración:** el alto de los cuatro, y no por líneas (0 hoy) sino por instalación:
**PyPI 0.3.36 publica SOLO sdist** (`llama_cpp_python-0.3.36.tar.gz`, sin wheels linux en el
índice normal) → cada install compila C++ (build-system `scikit-build-core[pyproject]>=0.9.2`
+ cmake + fuentes de llama.cpp). Sus classifiers declaran 3.13/3.14 pero su propia matriz de
CI visible cubre 3.9–3.12; el riesgo wheel en 3.13 no es de disponibilidad sino de **coste y
fragilidad de compilación** (toolchain presente, ~minutos por install). El 0.3.19 del lock
tiene exactamente el mismo perfil, así que mantener no empeora nada.

**Recomendación: APLAZAR** — mantener 0.3.19 en el lock. Re-evaluación: al abrir la feature
de inferencia embebida del ROADMAP, o a más tardar **2027-01-06**. Motivo del aplazamiento:
extra sin uso, instalación from-source cara, y el upgrade no desbloquea nada del roadmap.
Cuando se re-evalúe, decidir también si el extra pasa a instalarse con wheels del índice de
CUDA o se queda CPU-sdist.

## 4. Tabla de decisión

| Paquete | Hoy (lock) | Target | Recomendación | Justificación trazable |
| --- | --- | --- | --- | --- |
| twine | 6.2.0 | 7.0.0 | **SUBIR** (re-lock) | 6.2.0 falla `check` sobre Metadata 2.5 (probe §2 + changelog #1317); CI ya corre 7; deps del floor ya en lock |
| sentence-transformers | 5.3.0 | 6.1.0 | **SUBIR** (mismo re-lock) | floors ya satisfechos por el lock; línea transformers-5-native; 0 call sites → 0 riesgo hoy; cap interino documentado hasta smoke del extra |
| faiss-cpu | 1.13.2 | 1.15.1 | **SUBIR** (mismo re-lock) | cp310-abi3 cubre 3.13; numpy ok; soporte 3.13 explícito + hardening deserialización; 0 call sites |
| llama-cpp-python | 0.3.19 | 0.3.36 | **APLAZAR** (mantener) | sdist-only (compila cada install); renombres C API masivos; extra sin uso; re-eval: feature embebida o 2027-01-06 |
| mcp | 1.30.0 | — | **NO SE TOCA** | cap deliberado `<2` del Socio; motivo ya documentado (HANDOFF §Pendiente: "para evitar major 2.x sin tests"; pyproject extra `mcp`) |

Ejecución propuesta: **una issue única de re-lock** (twine 7.0.0 + st 6.1.0 + faiss 1.15.1,
con smoke del extra `memory` añadido a CI como parte de ella), decidida por el Socio a partir
de esta tabla. Nada de esto entra en AST-37.

## 5. Caps deliberados — documentación

- **`mcp<2`**: intacto. Motivo ya registrado en HANDOFF (§Pendiente, bloque Dependabot:
  "mcp pineado `>=1.28.1,<2` para evitar major 2.x sin tests") y visible en el propio
  `pyproject.toml` (extra `mcp`) y docs/ARCHITECTURE (tabla de optional dependencies).
- **st `5.x` (interino, solo si se decide esperar)**: motivo = extra `memory` sin uso ni
  smoke en CI; no se salta un major sin un test de humo del extra. Registrado en este
  informe y en el bloque de deuda añadido a HANDOFF en este mismo commit. El pin fino de
  st 5.x vive en uv.lock, no en pyproject (que mantiene `>=4.0`).

## 6. Verificación de criterios de aceptación (este run)

- `git diff --exit-code -- pyproject.toml uv.lock` → **vacío** (salida pegada en el
  comentario de entrega de la issue).
- Gate de citas SHA sobre `reports/` con este informe incluido → verde (salida pegada en el
  comentario de entrega).
- Suite sobre el commit final → pegada en el comentario de entrega.

## 7. Fuentes (consultadas 2026-10-06)

- twine: changelog oficial renderizado — `https://twine.readthedocs.io/en/stable/changelog.html`
  (sección 7.0.0, 2026-07-27); PyPI JSON `pypi.org/pypi/twine/7.0.0/json`.
- sentence-transformers: release notes v6.0.0/v6.1.0 —
  `github.com/UKPlab/sentence-transformers/releases/tags/v6.0.0` (y v6.1.0);
  migration guide `docs/migration_guide.md` del repo (vía API contents); PyPI JSON
  `pypi.org/pypi/sentence-transformers/6.0.0/json` y `/6.1.0/json`.
- faiss: CHANGELOG oficial — `raw.githubusercontent.com/facebookresearch/faiss/main/CHANGELOG.md`
  (secciones 1.14.0/1.14.1/1.15.0/1.15.1); PyPI JSON `pypi.org/pypi/faiss-cpu/1.15.0/json`
  y `/1.15.1/json` (lista de wheels cp310-abi3).
- llama-cpp-python: compare oficial
  `github.com/abetlen/llama-cpp-python/compare/v0.3.19...v0.3.36` (142 commits/52 ficheros)
  y `.diff`; `pyproject.toml` del tag v0.3.36 (vía API contents); PyPI JSON
  `pypi.org/pypi/llama-cpp-python/0.3.36/json` (sdist-only).
- Local: `uv.lock` y `pyproject.toml` de este repo en la base citada; probe twine §2;
  METADATA del wheel `dist/bytia_kode-0.8.4-py3-none-any.whl`.
