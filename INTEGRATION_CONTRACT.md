# Contrato de integración .NET ↔ Python

## Principio

Se mantienen **3 repositorios**: `leads-frontend`, `leads-backend` y `leads-pipeline`.
Las fases del pipeline siguen siendo módulos dentro de `leads-pipeline`.

PostgreSQL es el punto de integración. **EF Core/.NET es dueño del esquema y de las migraciones productivas**. Python consume el esquema y ejecuta upserts/cargas de resultados del pipeline.

## Propiedad de datos

| Tabla | Owner | Operación Python | Operación .NET |
|---|---|---|---|
| `leads.leads` | .NET dominio + Python pipeline fields | upsert de ingesta/normalización/matching | CRUD de negocio |
| `leads.customers` | .NET dominio | upsert de identidad normalizada | CRUD de negocio |
| `leads.motorcycles` | .NET catálogo | upsert desde catálogo fuente | consulta/administración |
| `leads.advisors` | .NET dominio | upsert desde maestro fuente | administración |
| `leads.conversations` | Pipeline | upsert | consulta |
| `leads.messages` | Pipeline | insert | consulta |
| `leads.lead_enrichments` | Pipeline IA | insert histórico | consulta |
| `leads.lead_scores` | Pipeline ML | insert histórico | consulta / decisión operativa |
| `leads.lead_assignments` | Pipeline inicialmente | insert | consulta / futura reasignación |
| `leads.pipeline_runs` | Pipeline | upsert estado | consulta/monitorización |

## Flujo

```text
Fuentes CSV/JSON
      |
      v
Python pipeline
  ingesta
  normalización
  deduplicación
  matching catálogo
  IA
  scoring
  asignación
      |
      v
PostgreSQL / schema leads
      |
      v
.NET API
      |
      v
Angular
```

## Idempotencia

- `leads.leads.lead_id` es la clave natural del lead.
- `customers.customer_id` es el identificador canónico generado por Python.
- `conversations.conversacion_id` es único.
- `pipeline_runs.run_id` es UUID.
- En cada ejecución, los datos actuales de leads/catálogo/asesores se hacen **upsert**.
- Enriquecimientos, scores y asignaciones son históricos y se insertan con timestamp.

## Contrato de API actual

- `GET /api/v1/leads`
- `GET /api/v1/leads/{leadId}`
- `GET /api/v1/leads/{leadId}/score`
- `GET /api/v1/leads/{leadId}/assignment`
- `GET /api/v1/references/motorcycles`
- `GET /api/v1/references/advisors`
- `GET /api/v1/health`

## Ejecución

Python puede ejecutarse como job programado/container. No se recomienda que el API .NET lance el proceso Python directamente en el mismo proceso web.

Para producción, el scheduler/orquestador dispara `leads-pipeline`; el backend expone estado y resultados. Si posteriormente se requiere ejecución manual desde UI, el API debe crear una solicitud de ejecución y un worker/orquestador ejecutar Python de forma asíncrona.

## Migraciones

No ejecutar `Database.Migrate()` automáticamente al arrancar producción. Las migraciones EF Core se versionan y despliegan explícitamente.
