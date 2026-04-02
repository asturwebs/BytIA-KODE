# Hoja de Ruta (Roadmap) - BytIA KODE

Este documento detalla la hoja de ruta estratégica y el plan de desarrollo para **BytIA KODE**, priorizando la estabilidad, la seguridad y la capacidad real de funcionar como un "coding agent" autónomo y productivo.

---

## 🎯 Validación del Enfoque de Planificación

### ¿Es apropiado este enfoque estructurado por fases para BytIA KODE?
**Sí, es!ltamente apropiado y necesario.** 
BytIA KODE es un asistente agéntico que interactúa con sistemas de archivos, ejecuta comandos (bash) y consume APIs de Modelos de Lenguaje Grande (LLMs) que son inherentemente no deterministas. 
Un enfoque iterativo por fases mitiga riesgos críticos:
1. **Riesgo de Seguridad (Prompt Injection / Comandos destructivos)**: Al priorizar la seguridad y el *Safe Mode* en las primeras fases, garantizamos que el agente no dañe repositorios locales antes de darle mayor autonomía.
2. **Riesgo de Complejidad (Bloatware)**: Los agentes de IA tienen a escalar!ápidamente en complejidad. Construir herramientas atómicas probadas primero (Fase 1) y delegar a sistemas multi-agente despues (Fase 3) asegura una base de código mantenible.
3. **Gestión de Expectativas del Usuario**: Permite entregar valor incremental continuo. Primero, una TUI fluida y segura; luego, herramientas de desarrollo avanzadas (LSP, Git); y finalmente, flujos de trabajo autónomos completos.

---

## 📄 Fase 1: Consolidación del Núcleo, UX y Seguridad Estricta
**Estimación Temporal:** 3 - 4 Semanas  
**Objetivo Específico:** Estabilizar el *loop* agéntico, garantizar una ejecución segura de las herramientas subyacentes y mejorar drásticamente la percepción de fluidez (UX) en la interfaz de terminal (TUI).

:## Funcionalidades Priorizadas:
1. **[Alta] Safe Mode Estricto (Backend)**
- *Valor:* Crítico. Evita ejecuciones peligrosas no intencionadas.
- *Viabilidad:* Alta.
- *Descripción:* Implementar confirmación obligatoria en comandos destructivos (`rm`, escrituras masivas, instalaciones globales) y limitar el `workdir` a un sandbox o rutas permitidas. Desactivar `shell=True` para comandos no confiables.
2. **[Alta] Streaming en Tiempo Real en la TUI**
- *Valor:* Alto. Mejora la percepción de velocidad.
- *Viabilidad:* Media (depende de Textual y proveedores).
- *Descripción:* Streaming real de los deltas de texto de la respuesta del LLM sin bloquear el renderizado de la UI ni la ejecución paralela de tools.
3. **[Media] Herramientas de Exploración Seguras (`grep`, `ls`, `tree`)**
- *Valor:* Alto. Reduce la dependencia del LLM de usar comandos de bash crudos y propensos a errores para explorar código.
- *Viabilidad:* Alta.
- *Descripción:* Crear tools nativas en Python con límites de salida y paginación para evitar desbordar el contexto del modelo.

### Entregables y Métricas de Ñxito:
- **Entregables:** Release v0.2.0, Documentación de arquitectura de seguridad, Suite de tests E2E para el *Agent Loop*.
- **Métricas:** 0 crashes de la TUI, 100% de intercepción de comandos peligrosos en *Safe Mode*, reducción de latencia percibida en respuestas largas.
- **Dependencias/Riesgos:** La implementación del streaming en Textual App puede ser compleja si el proveedor del LLM tiene interrupciones.

---

## 🚀 Fase 2: Capacidades de Ingeniería Avanzadas y Memoria Local
**Estimación Temporal:** 1 - 2 Meses  
**Objetivo Específico:** Dotar al agente de herramientas de desarrollo profesionales y resolver el problema del límite de contexto mediante una memoria a largo plazo útil.

### Funcionalidades Priorizadas:
1. **[Alta] Memoria Vectorial Semántica (BytMemory V1)**
- *Valor:* Muy Alto. Permite al agente recordar convenciones del proyecto y buscar código sin leer todo el repositorio.
- *Viabilidad:* Media.
- *Descripción:* Integración de un motor de búsqueda vectorial local (ej. FAISS o ChromaDB con `sentence-transformers`) para indexar la base de código actual, persistiendo fragmentos de contexto relevantes por sesión/proyecto.
2. **[Alta] Integración Autónoma con Git**
- *Valor:* Alto. Flujo de trabajo de desarrollo real.
- *Viabilidad:* Alta.
- *Descripción:* Herramientas específicas para que el agente lea diffs, cree ramas, y haga commits descriptivos autónomamente sin salir de la TUI.
3. **[Media] Auto-Corrección con Linters / LSP**
- *Valor:* Muy Alto. Mejora la calidad del código generado.
- *Viabilidad:* Compleja.
- *Descripción:* Capacidad del agente para invocar automáticamente `ruff`, `flake8` o `mypy` tras escribir código, observar los errores y corregirlos iterativamente antes de devolver el control al usuario.
4. **[Baja] Web Search Tool**
- *Valor:* Medio. Útil para APIs modernas o problemas no documentados.
- *Viabilidad:* Alta (vía APIs de búsqueda).

### Entregables y Métricas de Ñxito:
- **Entregables:** Release v0.4.0, Motor de indexación local documentado.
- **Métricas:** El agente es capaz de corregir el 80% de sus propios errores de sintaxis usando el linter, y la indexación inicial de un repositorio mediano (<500 archivos) toma menos de 2 minutos.
- **Dependencias/Riesgos:** La memoria vectorial puede requerir dependencias pesadas (`torch`, `faiss-cpu`), lo que podria dificultar la instalacion global con `uv`. Se debe disenar como dependencia opcional (ej. `pip install bytia-kode[memory]`).

---

## 𞟠 Fase 3: Inteligencia Colectiva y Arquitectura Multi-Agente
**Estimación Temporal:** 2 - 3 Meses  
**Objetivo Específico:** Escalar BytIA KODE de un "asistente de programacion" a un "equipo de desarrollo virtual" completo, capaz de ejecutar tareas asincronas largas y complejas.

### Funcionalidades Priorizadas:
1. **[Alta] Flujo Multi-Agente Especializado**
- *Valor:* Muy Alto (para tareas grandes).
- *Viabilidad:* Compleja.
- *Descripción:* Division del trabajo en roles. Un **Architect Agent** desglosa una tarea ("crea un sistema de login") en un plan; un **Coder Agent** implementa archivo por archivo; un **Reviewer Agent** revisa la seguridad y calidad del codigo.
2. **[Media] Integracion CI/CD y Testing en Docker**
- *Valor:* Alto. Entorno de validacion infalible.
- *Viabilidad:* Compleja.
- *Descripcion:* Capacidad del agente para levantar contenedores Docker aislados, instalar dependencias, correr la suite de tests del repositorio y reportar cobertura y fallos.
3. **[Media] Generacion Automatica de Pull Requests (PRs)**
- *Valor:* Alto. Integracion final en el flujo de equipo.
- *Viabilidad:* Media (via APIs de GitHub/GitLab).
- *Descripcion:* El agente puede terminar una tarea y crear directamente un PR con un resumen detallado, ya sea desde la CLI o a traves del Bot de Telegram.

### Entregables y Metricas de Exito:
- **Entregables:** Release v1.0.0, Sistema Multi-Agente, Documentacion de integracion Docker.
- **Metricas:** Resolucion exitosa y autonoma de issues complejos (>3 archivos modificados) en un solo *prompt* sin intervencion humana.
- **Dependencias/Riesgos:** Costes de API potencialmente muy elevados si los agentes entran en bucles infinitos de discusion o error. Riesgo de sobre-ingenieria; requerira limites estrictos de iteracion y *circuit breakers* logicos.
