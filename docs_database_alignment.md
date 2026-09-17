# Database contract alignment

## Source of truth

The shared PostgreSQL schema is owned by the .NET backend and EF Core migrations. Python must not create or alter the shared schema.

## Naming

Python keeps `snake_case` internally. At the persistence boundary, `mappings.py` writes the EF Core/PostgreSQL identifiers such as `"LeadId"`, `"FechaRegistro"`, `"EmpresaId"`, `"PuntoVentaId"`, `"CustomerId"`, etc.

## Identifier mapping

The assessment source uses identifiers such as `LD-00001`, `EMP-03`, `PV-014`, and `AS-001`, while the current backend contract uses `bigint`. For this dataset the numeric suffix is used deterministically (`LD-00001 -> 1`, `EMP-03 -> 3`, `PV-014 -> 14`, `AS-001 -> 1`).

Customer IDs are deterministic UUIDv5 values generated from the canonical customer key.

## Development database reset

Only when the database is disposable/development data:

```sql
DROP SCHEMA IF EXISTS leads CASCADE;
```

Then recreate the schema from the backend project with EF Core migrations:

```bash
dotnet ef database update
```

Finally execute the pipeline:

```bash
leads-pipeline
```

Do not run the Python `schema.sql` against the shared backend database. If the database contains the old Python lowercase schema, reset the development schema as above or create/apply the appropriate EF Core migration before running the pipeline.
