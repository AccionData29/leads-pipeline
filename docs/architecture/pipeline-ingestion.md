# Pipeline de ingesta y procesamiento

![Pipeline completo](./diagrams/02-pipeline-ingesta.svg)

## Etapas

1. Ingesta desde fuentes heterogéneas.
2. Validación de esquema, tipos y campos obligatorios.
3. Normalización a un modelo canónico.
4. Deduplicación y resolución de registros.
5. Matching contra catálogo de motocicletas.
6. Enriquecimiento de conversaciones con IA.
7. Scoring con histórico + señales actuales.
8. Asignación considerando reglas y capacidad.
9. Persistencia y reporting.

![Detalle de ingesta](./diagrams/03-detalle-ingesta.svg)

![Calidad y deduplicación](./diagrams/04-calidad-normalizacion-dedupe.svg)

![IA y scoring](./diagrams/05-ia-y-scoring.svg)

![Asignación](./diagrams/06-asignacion-asesores.svg)
