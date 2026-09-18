# Motos Leads Pipeline

Pipeline Python de punta a punta para el assessment de Analista de IA.

## Flujo

1. Descubrimiento/validación de fuentes.
2. Normalización de teléfonos, nombres, ciudades, canales, fechas y modelos.
3. Matching contra catálogo.
4. Deduplicación de clientes.
5. Enriquecimiento de conversaciones con IA (OpenAI opcional; mock determinista para desarrollo/demo).
6. Entrenamiento de Logistic Regression con `historico_cierres.csv`.
7. Scoring de leads actuales.
8. Asignación por empresa/punto de venta/capacidad.
9. Reportes y artefactos auditables.
10. Persistencia PostgreSQL opcional, alineada al contrato EF Core del backend.

## Instalación

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -e .
cp .env.example .env
```

Coloque los archivos fuente en `data/raw/` o indique `--source-dir`.

## Ejecutar sin PostgreSQL

```bash
leads-pipeline --no-db
```

Esto genera CSV/JSON/modelo en `data/output/`.

## Ejecutar con PostgreSQL

El esquema compartido es propiedad del backend .NET y se administra exclusivamente con EF Core migrations.

Primero, desde `leads-backend`:

```bash
dotnet ef database update
```

Después, desde este proyecto:

```bash
leads-pipeline
```

También puedes ejecutar `leads-pipeline --init-db`; por compatibilidad con versiones anteriores, esta opción **solo valida** el contrato existente y no crea tablas.

El `pipeline/persistence/schema.sql` es un espejo documental del contrato EF Core para entornos aislados; no debe ejecutarse sobre la base compartida.

La capa `pipeline/persistence/mappings.py` traduce los nombres internos `snake_case` a las columnas PascalCase creadas por EF Core y transforma los identificadores de fuente (`LD-00001`, `EMP-03`, `PV-014`, `AS-001`) a los `bigint` definidos por el backend.

## IA real

Configure:

```env
AI_PROVIDER=openai
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4.1-mini
```

El pipeline usa salida JSON estructurada y conserva proveedor, modelo, confianza y versión del prompt.

## Diseño de automatización

El mismo entrypoint es ejecutable desde cron, GitHub Actions, un scheduler o un worker. No requiere ejecutar notebooks ni etapas manuales.

## Idempotencia / producción

La siguiente iteración deberá agregar un repositorio de upsert por clave natural, checksum de archivos y control de `pipeline_runs` para impedir duplicados entre ejecuciones. Para el assessment se dejan artefactos por `run_id` y el pipeline es reproducible.


## Seguridad / datos sensibles

- `.env` nunca se commitea (ver `.gitignore`). Copie `.env.example` y complete sus propios valores locales.
- `data/`, y los CSV/JSON de origen (`leads.csv`, `asesores.csv`, `conversaciones.json`, `historico_cierres.csv`) contienen PII real de clientes (nombres, teléfonos, correos) y están excluidos del repositorio. Colóquelos localmente; nunca los commitee.
- Si una credencial llegó a subirse a git (aunque sea en un commit anterior), rótela en el motor de base de datos: quitarla del working tree no la invalida, sigue en el historial hasta que se reescriba explícitamente y se cambie la contraseña.
- `POST /api/v1/pipeline/runs` no tiene autenticación en este código base; si se expone fuera de una red de confianza, añada autenticación (API key, mTLS, red privada) antes de desplegarlo.

## PostgreSQL / .NET contract alignment

The shared PostgreSQL schema is owned by the .NET backend and EF Core migrations. The Python pipeline does not create or alter the shared schema. Run the backend migrations first, then execute the pipeline.

Python keeps `snake_case` internally and translates to the quoted PascalCase EF Core columns only at the persistence boundary. Source identifiers such as `LD-00001`, `EMP-03`, `PV-014` and `AS-001` are mapped deterministically to the current backend `bigint` contract. Customer UUIDs are generated during deduplication and reused directly by persistence.

Typical execution:

```powershell
# from leads-backend
dotnet ef database update

# from leads-pipeline
python -m pytest -q
python -m pipeline.main
```

Do not run `pipeline/persistence/schema.sql` against the shared backend database. It is a contract mirror for isolated development/reference only.
