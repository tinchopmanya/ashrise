# Ashrise Prompts

Prompts estructurados para agentes de investigación y triage operativo. En Sprint 5 ya se sincronizan a **Langfuse** desde este repo; estos archivos siguen siendo el fallback repo-local y la referencia editable.

## Mapeo a Langfuse

Cada prompt crítico se registra con su `prompt_ref` canónico:

| Archivo | Langfuse ref | Categoría de candidata |
|---|---|---|
| `kill-vertical-small-quickwin.md` | `kill-vertical-small-qw@v1` | `small-quickwin` |
| `kill-vertical-saas-v2.md` | `kill-vertical-medium-long@v1` | `medium-long` |
| `kill-vertical-unicorn.md` | `kill-vertical-unicorn@v1` | `unicorn` |
| `evaluate-learning-vertical.md` | `kill-vertical-learning@v1` | `learning` |
| `evaluate-profound-ai-experiment.md` | `kill-vertical-profound-ai@v1` | `profound-ai` |
| `kill-vertical-core-sub.md` | `kill-vertical-core-sub@v1` | `core-sub-vertical` |
| `continue-search-delta.md` | `continue-search-delta@v1` | cualquiera con status investigating/promising |
| `daily-triage.md` | `daily-triage@v1` | N/A (operativo, no evalúa candidatas) |

## Lógica de aplicación

Cuando el agente de investigación del Sprint 4 corre sobre una candidata, el flujo es:

1. Leer `vertical_candidates.category` y `vertical_candidates.status`.
2. Si `status IN ('proposed', 'investigating')` y **no hay reporte previo**: usar el prompt de la categoría correspondiente (initial research).
3. Si `status IN ('investigating', 'promising')` y hay reporte previo con < 30 días: usar `continue-search-delta@v1`.
4. Si `status IN ('investigating', 'promising')` y hay reporte previo pero > 90 días: usar el prompt de la categoría (re-investigación profunda, no delta).

El prompt `daily-triage@v1` corre aparte en el cron de la mañana, no depende de la categoría de ninguna candidata individual — opera sobre la `research_queue` entera.

## Diferencias entre prompts

No son variantes del mismo esqueleto. Cada uno tiene lógica propia porque las categorías resuelven preguntas distintas:

- **Small Quick Wins** busca demanda freelance viva en Workana/Fiverr. Criterio: ¿puedo vender esto en 15 días?
- **Unicorn** busca patrones emergentes + moat contra LLM frontier. Default KILL brutal.
- **Learning** evalúa skill transfer a proyectos del portfolio. No mide mercado.
- **Profound AI** propone experimentos concretos ejecutables esta semana con PC aparte.
- **Continue Search Delta** busca solo qué cambió desde el último reporte. Queries quirúrgicas.
- **Daily Triage** ordena la queue del día. Operativo, no investigativo.

## Versionado

Cuando un prompt se actualiza con cambios materiales (no tipos ni ajustes menores):

1. Incrementar versión en Langfuse (`@v1` → `@v2`).
2. Marcar la versión anterior como `is_active=false` en `kill_criteria_templates` si aplica.
3. Crear una decision en Ashrise documentando el cambio y por qué.
4. Idealmente re-correr 1-2 candidatas ya evaluadas con el prompt nuevo para calibrar diferencias.

## Observaciones sobre el uso en Sprint 4

Cuando el agente unificado corra, va a:

1. Determinar qué prompt usar según categoría + status de la candidata (o tipo para triage).
2. Cargar el contenido del prompt desde Langfuse (en Sprint 4 temporalmente desde git).
3. Ejecutar contra Claude/GPT con el input específico de la candidata.
4. Parsear el output estructurado según la sección `<output_required>` del prompt.
5. Guardar resultado en `candidate_research_reports` (o `audit_reports` si es proyecto activo).

Los prompts están diseñados para producir outputs parseables — secciones numeradas, tablas con formato consistente, veredictos de un enum cerrado. Eso simplifica el parser.

## Qué NO está en estos prompts

- El método v3 completo para Medium-Long. Está separado porque es el prompt original maduro, el más largo y el que más conviene proteger.
- Prompts para categoría `core-sub-vertical`. Ya hay seed en `kill_criteria_templates` con `langfuse:kill-vertical-core-sub@v1`, pero el prompt real todavía no existe — se escribirá cuando surja la primera sub-vertical nueva del núcleo ProcurementUY (la más probable: Agro). No hace falta anticipar.
- Prompts de observabilidad o evals de los propios prompts. Eso llega después con Promptfoo.
