# structured-cot — Grammar-Constrained Chain-of-Thought

**Repo:** https://github.com/andthattoo/structured-cot
**Autor:** andthattoo | **Creado:** 2026-04-23 | **90⭐** en 3 días

## Idea Central

Grammar-constrained CoT usando gramáticas GBNF (GGML BNF) aplicadas en **tiempo de inferencia**, sin entrenamiento, fine-tuning ni RL. Un archivo de ~10 líneas fuerza al modelo a pensar en formato estructurado compacto en lugar del verbose prose thinking nativo.

## Resultados Clave

### HumanEval+ (164 problemas, Qwen3.6-35B-A3B, 1×H100)

| Mode | pass@1 | Think tokens | Total tokens |
|---|---|---|---|
| FREE (natural `<think>`) | 92.1% | 3087 | 3410 |
| FSM (grammar GOAL/APPROACH/EDGE) | 92.7% | **138** | **408** |
| PROMPT_TERSE (solo prompt, sin grammar) | 93.3% | 2298 | 2764 |
| **FSM vs FREE Δ** | **+0.6 pp** | **22× menos** | **8× menos** |

### LiveCodeBench v6 (50 problemas LeetCode recientes)

| Mode | pass@1 | Think tokens | Total tokens | Fallos silenciosos |
|---|---|---|---|---|
| FREE | 50% | 11553 | 13632 | 18 empty_code |
| FSM_PLAN | **64%** | **267** | **2743** | **0** |
| **Δ** | **+14 pp** | **43× menos** | **5× menos** | — |

## Cómo Funciona

```gbnf
root  ::= think code
think ::= "<think>\n" "GOAL: " line "APPROACH: " line "EDGE: " line "</think>\n\n"
line  ::= [^\n]+ "\n"
code  ::= [\x09\x0A\x0D\x20-\x7E]+
```

En cada paso de generación dentro de `<think>`, los logits de tokens que violan la gramática se enmascaran a -∞. Después de `</think>`, el código es sin restricciones.

### Gramática enriquecida para tareas difíciles (LiveCodeBench)
```
GOAL → STATE → ALGO → EDGE → VERIFY
```

## Aplicabilidad a B-KODE

### 1. Integración con llama.cpp (provider local)

Si algún provider de B-KODE usa llama.cpp como backend, se puede pasar la gramática vía parámetro `grammar` en el request:

```python
extra_body={"grammar": grammar_string}
```

### 2. Concepto generalizable

El principio de "structured thinking" va más allá de coding:
- **Protocolos BytIA (P20-P25):** gramática para structured jailbreak detection
- **Decisiones de arquitectura:** GOAL/CONTEXT/TRADEOFFS/DECISION/VERIFY
- **Debugging:** ERROR/HYPOTHESIS/TEST/FIX/VERIFY

### 3. Ahorro de tokens

Con ~2B tokens/mes de consumo, si el 50% del thinking se puede comprimir → ~1B tokens ahorrados/mes. Aplicable a cualquier provider que acepte el parámetro `grammar`.

### 4. Circuit breaker + grammar

La gramática podría integrarse en el `ProviderManager` como una capa opcional:
- Si el provider soporta grammars → aplicar structured thinking
- Si no → fallback a modo normal
- Podría ser un toggle en el TUI (`/grammar on/off`)

## Limitaciones

1. **Contaminación de benchmarks.** HumanEval es de 2021, el modelo pudo memorizar soluciones.
2. **Un solo modelo testeado.** Qwen3.6-35B-A3B (MoE, 256 expertos, 9 activos). No verificado en otros.
3. **Solo coding tasks.** Sin evidencia en math, lógica, planificación multi-step.
4. **Reasoning displacement.** En problemas difíciles, el modelo mueve razonamiento del `<think>` a comentarios de código.
5. **Grammar specificity.** Cada dominio puede necesitar su propia gramática.

## Archivos del Repo

| Archivo | Descripción |
|---|---|
| `fsm_vs_free_eval.py` | Evaluador completo (~1250 líneas) |
| `make_tps_animation.py` | Animación HTML side-by-side de generaciones |
| `grammars/fsm_grammar.gbnf` | Gramática compacta GOAL/APPROACH/EDGE |
| `grammars/fsm_grammar_lcb_plan.gbnf` | Gramática enriquecida GOAL/STATE/ALGO/EDGE/VERIFY |

## Antecedente

[Coconut (Hao et al., 2024)](https://arxiv.org/abs/2412.06769) — comprime CoT en latentes continuos vía fine-tuning. Este trabajo prueba que una gramática en inferencia (sin entrenamiento) captura gran parte del mismo beneficio.

## Siguientes Pasos (para B-KODE)

- [ ] Verificar si llama.cpp (provider local) expone el parámetro `grammar` en su API OpenAI-compatible
- [ ] Diseñar gramáticas para protocolos BytIA (P20-P25)
- [ ] Añadir toggle `/grammar` en el TUI de B-KODE
- [ ] Medir compresión de thinking tokens en uso real (no benchmarks)
- [ ] Testear con DeepSeek V4 (si el endpoint acepta grammars)
