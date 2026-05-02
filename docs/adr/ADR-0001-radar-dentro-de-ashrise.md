# ADR-0001: Radar como dominio separado dentro de Ashrise

- Estado: Accepted
- Fecha: 2026-05-02

## Contexto

Ashrise ya existe como sistema operativo local para implementación y operación de candidatas elegidas. Hoy concentra proyectos, state vivo, runs de agentes, handoffs, decisions, ideas, candidates de research, tasks, dashboard, Langfuse, Telegram y el endpoint `/agent/run`.

Radar responde a una necesidad distinta y anterior: discovery, captura de señales, investigación de oportunidades, prompts de descubrimiento y kill, evidencia, scorecards, gates, selección y muerte de candidatas antes de que entren al circuito de implementación.

Una parte importante del flujo de Radar va a ejecutarse en ChatGPT Web, Claude Web u otras interfaces web, sin depender de APIs pagas ni de automatización frágil del navegador. El requisito central no es tener una app desktop por estética, sino reducir al mínimo la fricción para:

- copiar prompts listos para usar;
- ejecutar esos prompts en herramientas web externas;
- descargar JSON válidos con wrapper Radar;
- importar esos archivos localmente con la menor intervención manual posible.

La auditoría del repo real de Ashrise mostró que ya existe una base fuerte reutilizable:

- backend FastAPI;
- Postgres como fuente de verdad;
- dashboard React + Vite;
- candidates de research (`vertical_candidates`);
- `research_queue`;
- ideas;
- tasks;
- decisions;
- `/agent/run`;
- referencias a Langfuse;
- notificaciones/Telegram;
- aggregates de dashboard.

También mostró que esa base no alcanza por sí sola para modelar Radar sin mezclar semánticas:

- `vertical_candidates` ya representa candidatas de research pre-proyecto, no todo el universo de oportunidades estratégicas;
- `ideas` es un buffer mínimo de captura, no un sistema de discovery;
- no existen entidades first-class para signals, evidence, scorecards, gates, prompt library, apply logs o file imports;
- no existe todavía file ingestion local para JSON descargados desde herramientas web.

## Decisión

Radar vivirá dentro del repo Ashrise, pero como dominio propio y separado.

Esto implica:

- Radar tendrá rutas propias bajo `/radar/*`.
- Radar tendrá tablas propias `radar_*`.
- Radar no usará una SQLite separada.
- Radar no será app desktop en esta fase.
- Radar no usará `vertical_candidates` como núcleo del dominio.
- Radar tendrá `radar_candidates` propios.
- La promoción hacia Ashrise se hará mediante vínculo explícito hacia `vertical_candidates` y/o `projects` cuando una candidata avance.

La implementación inicial recomendada es:

- módulo nuevo dentro del backend de Ashrise;
- UI propia de Radar dentro del frontend existente;
- persistencia en la misma base Postgres;
- futuro watcher local de archivos como servicio auxiliar;
- soporte principal para `apply JSON` desde archivo local, drag & drop o inbox propia.

## Alternativas rechazadas

### 1. App separada con SQLite

Se rechaza porque duplicaría backend, modelos, UI, auth, promoción de candidatas e integraciones ya existentes en Ashrise. También abriría una frontera artificial entre discovery e implementación, obligando a sincronizaciones más frágiles.

### 2. Desktop app inmediata con Tauri/Electron

Se rechaza en esta fase porque el problema principal hoy no es el empaquetado nativo sino la ingesta local de archivos descargados desde ChatGPT Web y Claude Web. Ese problema puede resolverse primero con backend local + watcher + UI web.

### 3. Extender `vertical_candidates` para todo Radar

Se rechaza porque sobrecarga una entidad ya sesgada al circuito de research pre-proyecto de Ashrise. Discovery estratégico, señales, scorecards, gates y portfolio review requieren un ciclo de vida más amplio y semánticamente distinto.

### 4. Usar Langfuse como único gestor práctico de prompts

Se rechaza porque Langfuse sirve muy bien para referencias, trazas y prompts profundos, pero no cubre por sí solo el flujo práctico de copiar prompt, ejecutarlo en ChatGPT Web, descargar JSON y aplicarlo con baja fricción.

### 5. Depender solo de copy/paste manual sin file ingestion

Se rechaza porque mantiene demasiada fricción operativa. El objetivo explícito es minimizar la fricción entre herramientas web y Radar, y eso exige soportar import de archivos locales de forma más directa.

## Consecuencias

- Se evita duplicar backend, dashboard y base de datos.
- Se mantiene clara la frontera entre discovery y ejecución/implementación.
- Se habilita un futuro watcher local para archivos `radar_*.json`.
- Se reduce el riesgo de sobrecargar Ashrise con semántica ambigua dentro de `vertical_candidates`.
- Se posterga desktop hasta validar primero el flujo local web + watcher.
- Se preserva una promoción explícita desde Radar hacia Ashrise en vez de mezclar ambos dominios prematuramente.

## Fases futuras

### Fase 1: backend mínimo `radar_*`

Definir el dominio base de Radar dentro de Ashrise con entidades y endpoints mínimos.

### Fase 2: apply JSON manual

Soportar import de JSON por endpoint y UI manual, sin watcher avanzado todavía.

### Fase 3: UI mínima Radar

Agregar superficies iniciales para overview, candidate detail y apply/import.

### Fase 4: prompt library + copy prompt

Incorporar biblioteca práctica de prompts versionados para ejecutar en ChatGPT Web o Claude Web.

### Fase 5: file ingestion / watcher

Agregar watcher local, inbox propia y procesamiento de `radar_*.json`.

### Fase 6: portfolio review

Agregar revisión consolidada de oportunidades, filtros, comparaciones y agrupaciones estratégicas.

### Fase 7: launcher o desktop si realmente aporta

Evaluar empaquetado, launcher o app desktop solo después de validar que el flujo local web + watcher resuelve la fricción principal.
