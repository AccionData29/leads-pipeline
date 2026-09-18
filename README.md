# Motos Leads Pipeline — Assessment Analista de IA

Solución de punta a punta para priorizar y asignar leads de motocicletas: ingesta y calidad de datos, IA sobre conversaciones, scoring, asignación a asesores, y una API + dashboard para operarlo. Este documento describe el flujo completo (los tres repositorios); cada uno conserva además su propio README con el detalle específico.

| Repo | Rol | README propio |
|---|---|---|
| `leads-pipeline` (este) | Ingesta, calidad, normalización, IA, scoring, asignación | — |
| `leads-backend` | API .NET, dueño del esquema PostgreSQL (EF Core), orquesta la ejecución del pipeline | `leads-backend/README.md` |
| `leads-frontend` | Dashboard Angular para el equipo comercial | `leads-frontend/README.md` |

Diagrama de arquitectura completo: [`docs/architecture/`](docs/architecture/) (9 diagramas SVG + overview). El diagrama de despliegue (`09-despliegue.svg`) refleja la topología real desplegada en Railway.

## 1. Qué hace

1. **Ingesta y validación** de 5 fuentes: `leads.csv`, `historico_cierres.csv`, `catalogo_motos.csv`, `asesores.csv`, `conversaciones.json`.
2. **Normalización**: teléfonos, nombres, ciudades, canal, fechas y texto de modelo a un formato canónico.
3. **Matching contra catálogo** de motos (exacto y difuso con `rapidfuzz`).
4. **Deduplicación** de clientes por teléfono/email/nombre normalizados → `customer_id` (UUID determinístico).
5. **Enriquecimiento con IA** de las conversaciones de WhatsApp: modelo de interés, forma de pago, intención, objeción, si pidió cita/cotización (proveedor `mock` determinista o `openai` con salida JSON estructurada).
6. **Scoring**: Logistic Regression entrenada con el histórico de cierres (`historico_cierres.csv`) + un ajuste acotado y transparente con las señales de IA (no se presentan como "entrenadas" variables que no existen en el histórico).
7. **Asignación** a asesores por empresa/punto de venta/capacidad diaria disponible, priorizando por score.
8. **Persistencia** en PostgreSQL (esquema propiedad de `leads-backend`/EF Core) + artefactos por ejecución (CSV/JSON/modelo) para trazabilidad.
9. **Exposición**: `leads-backend` expone la API REST operacional (`/api/v1/leads`, `/score`, `/assignment`, `/advisors`, `/pipeline/runs`, …) y `leads-frontend` la consume en un dashboard (KPIs, prioridad, canal, cola de trabajo).

## 2. Cómo se ejecuta

### Local, cada pieza por separado

```bash
# leads-pipeline
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
cp .env.example .env
leads-pipeline --no-db          # corre todo y escribe data/output/, sin Postgres

# leads-backend (requiere Postgres)
dotnet ef database update --project src/Leads.Infrastructure --startup-project src/Leads.Api
dotnet run --project src/Leads.Api

# leads-frontend
npm install && npm start        # http://localhost:4200
```

### Local, integrado con Docker Compose

`leads-backend/docker-compose.yml` levanta Postgres + pipeline (uvicorn) + API .NET en la misma red:

```bash
cd leads-backend/Leads
docker compose up --build
```

### Desplegado (Railway)

Los tres servicios + Postgres corren hoy en un proyecto de Railway, con solo el frontend expuesto públicamente (el backend y el pipeline son privados y se hablan por red interna `*.railway.internal`). Ver `docs/architecture/diagrams/09-despliegue.svg`. Redeploy manual con `railway up --service <nombre>` por repo; no hay CI/CD automático todavía (ver sección 5).

## 3. Decisiones técnicas tomadas

- **Tres repos con un contrato explícito** (`INTEGRATION_CONTRACT.md` / `leads-backend/CONTRACT.md`) en vez de un monolito: Python es dueño del procesamiento/IA, .NET es dueño del esquema productivo y las migraciones (EF Core), PostgreSQL es el punto de integración. Ninguno de los dos ejecuta migraciones del otro.
- **`customer_id` UUID determinístico** derivado de la clave canónica del cliente (no un `customer_key` separado), para que Python y EF Core/PostgreSQL compartan el mismo identificador sin acoplar tipos.
- **Traducción explícita `snake_case` → PascalCase** solo en la capa de persistencia (`pipeline/persistence/mappings.py`), para que el resto del pipeline no conozca el contrato de EF Core.
- **Proveedor de IA desacoplado** (`Enricher` como interfaz; `mock` o `openai` intercambiables) para tener un modo determinista y gratuito para desarrollo/demo, y un modo real con salida JSON estructurada cuando se necesite.
- **Modelo histórico + señales de IA como ajuste acotado**, no como reemplazo: el score final pondera 80/20 el modelo entrenado sobre el histórico real y el ajuste de señales de IA, para no aparentar que el modelo "sabe" algo que no vio en el entrenamiento.
- **Sin autenticación/roles todavía**: el frontend segmenta por `empresaId`/`puntoVentaId` como *contexto funcional*, no como control de acceso (ver Supuestos). Documentado explícitamente para que no se confunda con una barrera de seguridad real.
- **Despliegue con solo un servicio público**: en Railway, `frontend` (nginx) es la única puerta de entrada a internet; hace de proxy inverso hacia `backend` por la red privada del proyecto, que a su vez llama a `pipeline` también por red privada. Esto minimiza superficie de ataque sin cambiar ni una línea del contrato HTTP existente.
- **Secretos nunca en código ni en `appsettings.json`**: variables de entorno por servicio, con referencias (`${{Postgres.PGPASSWORD}}` en Railway) en vez de contraseñas literales.

## 4. Supuestos asumidos

- Los datos de origen son **sintéticos** (lo indica `LEEME.txt` del paquete de assessment) y contienen inconsistencias deliberadas — parte del ejercicio es detectarlas. Aun así se les dio el mismo tratamiento de higiene de datos/secretos que a datos reales (nunca committeados, fuera de la imagen Docker), porque esa disciplina no debería depender de si el dato es real o no.
- Un mismo `lead_id` duplicado en la fuente se resuelve conservando **un registro canónico** (el último por orden de aparición); no se asumió que la duplicación fuera un error a rechazar.
- `empresa_id`/`punto_venta_id` enviados desde el navegador son un **contexto de UI**, no un límite de seguridad; en producción real el backend debería forzarlos server-side (ver frontend README, sección "Importante sobre seguridad").
- El esquema de PostgreSQL productivo **siempre lo crea/migra `leads-backend`** vía EF Core; el pipeline valida contra ese esquema (`validate_schema()`) y nunca lo crea (`pipeline/persistence/schema.sql` es solo un espejo de referencia para entornos aislados).
- `AI_PROVIDER=mock` es aceptable como entrega/demo reproducible; `openai` es opcional y no se asumió que hubiera credencial disponible en el entorno de evaluación.
- El volumen de datos (~1.500 leads, ~2.200 históricos, 677 conversaciones) es tratable en memoria con pandas en una sola ejecución; no se asumió necesidad de procesamiento distribuido.

## 5. Qué haría con más tiempo

- **Ingesta dinámica** en vez de CSV/JSON estáticos: un endpoint o job que traiga los datos de origen (CRM, formulario, API de WhatsApp) en vez de subir archivos a mano a un volumen — es la evolución natural de lo que hoy es un volumen persistente en Railway.
- **Idempotencia real de producción**: checksum por archivo fuente + UPSERT transaccional por clave natural, en vez de reprocesar todo en cada corrida (hoy documentado como pendiente en `docs.md`).
- **Autenticación y autorización real**: login, roles, y `empresaId`/`puntoVentaId` forzados server-side (Row-Level Security en PostgreSQL o filtrado obligatorio en el backend), no solo como contexto de UI.
- **Endpoint de agregación para el dashboard** (`GET /api/v1/dashboard`) que calcule KPIs con SQL en vez de que el frontend traiga todas las páginas de `/leads` para calcularlos en el navegador.
- **Partir la clase `Database` del pipeline** (hoy hace de conexión + validación de esquema + persistencia de 8 entidades) en repositorios por entidad — quedó identificado pero no se ejecutó un refactor grande sin poder correrlo contra una base real en el momento del hallazgo.
- **CI/CD real**: cada repo conectado a GitHub Actions/Railway para build + test + deploy automático en cada push, en vez del `railway up` manual usado para levantar el entorno actual.
- **Rotar la credencial de PostgreSQL que quedó expuesta en el historial de git** (ya removida del código actual en los 3 repos, pero sigue visible en commits antiguos) y, si se requiere, purgar ese historial.
- **Monitoreo/alertas** sobre `pipeline_runs` (hoy solo se puede consultar el estado, no hay alerta activa si una corrida falla).

## Seguridad / datos sensibles

- `.env` nunca se commitea (ver `.gitignore`). Copie `.env.example` y complete sus propios valores locales.
- `data/` y los CSV/JSON de origen están excluidos del repositorio (son datos sintéticos de assessment, pero se tratan con la misma disciplina que datos reales: nunca committeados, nunca horneados en la imagen Docker).
- Si una credencial llegó a subirse a git (aunque sea en un commit anterior), rótela en el motor de base de datos: quitarla del working tree no la invalida, sigue en el historial hasta que se reescriba explícitamente y se cambie la contraseña.
- `POST /api/v1/pipeline/runs` no tiene autenticación en este código base; si se expone fuera de una red de confianza, añada autenticación (API key, mTLS, red privada) antes de desplegarlo. En el despliegue actual esto se mitiga dejando el pipeline sin dominio público.

## PostgreSQL / .NET contract alignment

The shared PostgreSQL schema is owned by the .NET backend and EF Core migrations. The Python pipeline does not create or alter the shared schema. Run the backend migrations first, then execute the pipeline.

Python keeps `snake_case` internally and translates to the quoted PascalCase EF Core columns only at the persistence boundary. Source identifiers such as `LD-00001`, `EMP-03`, `PV-014` and `AS-001` are mapped deterministically to the current backend `bigint` contract. Customer UUIDs are generated during deduplication and reused directly by persistence.

Do not run `pipeline/persistence/schema.sql` against the shared backend database. It is a contract mirror for isolated development/reference only.
