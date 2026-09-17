# Arquitectura — Leads Platform

Esta carpeta contiene la documentación visual de la solución de punta a punta.

## Diagramas

1. [Arquitectura general](./diagrams/01-arquitectura-general.svg)
2. [Pipeline de ingesta](./diagrams/02-pipeline-ingesta.svg)
3. [Detalle de ingesta y Quality Gate](./diagrams/03-detalle-ingesta.svg)
4. [Calidad, normalización y deduplicación](./diagrams/04-calidad-normalizacion-dedupe.svg)
5. [IA y scoring](./diagrams/05-ia-y-scoring.svg)
6. [Asignación de asesores](./diagrams/06-asignacion-asesores.svg)
7. [Modelo lógico de datos](./diagrams/07-modelo-datos.svg)
8. [Integración Angular → .NET → Python → PostgreSQL](./diagrams/08-integracion.svg)
9. [Despliegue y operación](./diagrams/09-despliegue.svg)

## Principios de arquitectura

- **Angular**: experiencia de usuario, visualización y monitoreo.
- **.NET**: API operacional, casos de uso, seguridad y persistencia transaccional.
- **Python**: procesamiento de datos, IA, scoring y asignación.
- **PostgreSQL**: persistencia compartida y trazabilidad.
- **Contratos explícitos** entre .NET y Python.
- **Idempotencia** para ejecuciones repetibles.
- **Quality Gate** antes de transformar datos.
- **Trazabilidad** de score, modelo y ejecución.
- **Migraciones productivas** controladas por EF Core en el backend.

## Flujo E2E

```text
Fuentes
  ↓
Ingesta
  ↓
Validación / Quality Gate
  ↓
Normalización
  ↓
Deduplicación
  ↓
Catalog Matching
  ↓
Enriquecimiento IA
  ↓
Scoring
  ↓
Asignación de asesor
  ↓
PostgreSQL
  ↓
.NET API
  ↓
Angular
```

> Los SVG son los artefactos visuales principales para que la documentación se vea correctamente en GitHub y otros visores Markdown, sin depender de un renderer Mermaid.
