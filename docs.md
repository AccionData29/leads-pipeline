# Pipeline — decisiones y operación

## Contrato de ejecución

`python -m pipeline.main [--source-dir DIR] [--init-db] [--no-db]`

- `--source-dir`: carpeta que contiene los 5 archivos fuente.
- `--no-db`: ejecuta todo el procesamiento y genera artefactos sin PostgreSQL.
- `--init-db`: crea tablas del esquema de aislamiento para desarrollo. En producción, el esquema debe venir de EF Core Migrations del backend .NET.

## Orden de etapas

1. Validación de fuentes.
2. Normalización.
3. Homologación de modelos.
4. Deduplicación.
5. Enriquecimiento IA.
6. Entrenamiento/recarga del modelo histórico.
7. Scoring actual.
8. Explicaciones.
9. Asignación por empresa/PV/capacidad.
10. Persistencia/reportes.

## IA

`AI_PROVIDER=mock` es el modo reproducible para desarrollo y demo. `AI_PROVIDER=openai` activa extracción estructurada con un proveedor LLM. La selección del proveedor queda desacoplada mediante `Enricher`.

## Scoring

El modelo histórico es Logistic Regression con variables disponibles en `historico_cierres.csv`. Las señales nuevas extraídas por IA se incorporan como un ajuste acotado y explícito. Esto evita presentar como entrenadas variables que no existen en el histórico.

## Idempotencia

La fuente ya contiene `lead_id` duplicados deliberados; se canoniza un registro por `lead_id`. Para producción, la siguiente versión debe persistir un checksum por archivo y usar UPSERT transaccional por claves naturales.

## Seguridad multiempresa

El pipeline conserva `empresa_id` y `punto_venta_id`. La autorización definitiva y Row-Level Security deben implementarse en la API/PostgreSQL de producción.

## Artefactos

Cada corrida genera:

- `leads_normalized_<run>.csv`
- `lead_enrichments_<run>.csv`
- `lead_scores_<run>.json`
- `lead_assignments_<run>.csv`
- `run_<run>.json`
- `scoring_model.joblib`
- `metrics.json`
