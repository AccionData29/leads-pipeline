from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd
from sqlalchemy import create_engine, inspect, text

from pipeline.config.settings import settings
from pipeline.persistence.mappings import (
    customer_uuid,
    normalize_status,
    quote_identifier,
    source_id_to_int,
    probability_to_db,
)

logger = logging.getLogger(__name__)


class Database:
    """Persistence adapter for the PostgreSQL schema owned by the .NET backend.

    Python uses snake_case internally. This adapter is the only place where
    Python column names are translated to the EF Core/PostgreSQL contract.
    """

    SCHEMA = "leads"

    def __init__(self, url: str | None = None):
        self.engine = create_engine(url or settings.database_url, pool_pre_ping=True)

    def _table_columns(self, table: str) -> set[str]:
        inspector = inspect(self.engine)
        return {c["name"] for c in inspector.get_columns(table, schema=self.SCHEMA)}

    def validate_schema(self) -> None:
        """Fail early with a useful message instead of a cryptic UndefinedColumn."""
        inspector = inspect(self.engine)
        if self.SCHEMA not in inspector.get_schema_names():
            raise RuntimeError(
                "PostgreSQL schema 'leads' does not exist. "
                "Run the .NET EF Core migrations before running the Python pipeline."
            )

        required = {
            "leads": {"LeadId", "FechaRegistro", "Canal", "EmpresaId", "PuntoVentaId", "NombreCliente", "EstadoGestion"},
            "customers": {"CustomerId", "EmpresaId", "Nombre"},
            "motorcycles": {"Sku", "Marca", "Linea", "Cilindraje", "PrecioLista", "PuntosVentaDisponibles", "UnidadesDisponibles"},
            "advisors": {"AsesorId", "Nombre", "PuntoVentaId", "EmpresaId", "CapacidadDiariaLeads", "Activo", "FechaIngreso"},
            "conversations": {"Id", "ConversacionId", "LeadId", "Canal", "FechaInicio"},
            "messages": {"Id", "ConversationId", "SenderType", "Content", "SentAt"},
            "lead_enrichments": {"Id", "LeadId", "Confianza", "Provider", "PipelineVersion", "CreatedAt"},
            "lead_scores": {"Id", "LeadId", "HistoricalProbability", "FinalScore", "Priority", "ReasonsJson", "ModelVersion", "CreatedAt"},
            "lead_assignments": {"Id", "LeadId", "AsesorId", "AssignedAt", "Reason"},
            "pipeline_runs": {"RunId", "Status", "StartedAt", "FinishedAt", "Error"},
        }
        missing_tables = [t for t in required if not inspect(self.engine).has_table(t, schema=self.SCHEMA)]
        if missing_tables:
            raise RuntimeError(
                "The PostgreSQL schema is not aligned with the backend. "
                f"Missing tables: {', '.join(missing_tables)}. "
                "Apply the .NET EF Core migrations first."
            )

        missing = {
            table: sorted(cols - self._table_columns(table))
            for table, cols in required.items()
            if cols - self._table_columns(table)
        }
        if missing:
            details = "; ".join(f"{t}: {', '.join(cols)}" for t, cols in missing.items())
            raise RuntimeError(
                "The PostgreSQL schema exists but is not the current backend contract. "
                f"Missing columns -> {details}. "
                "Do not run the Python schema.sql over the backend database; create/apply an EF Core migration."
            )

    def init_schema(self, schema_path: Path | None = None) -> None:
        raise RuntimeError(
            "Database schema ownership belongs to .NET/EF Core. "
            "Do not initialize PostgreSQL from pipeline/persistence/schema.sql. "
            "Run 'dotnet ef database update' from the backend instead."
        )

    @staticmethod
    def _executemany(connection, sql: str, rows: list[dict]) -> None:
        if rows:
            connection.execute(text(sql), rows)

    def save_run(self, run: dict) -> None:
        payload = {
            "RunId": run["run_id"],
            "Status": run["status"],
            "StartedAt": run["started_at"],
            "FinishedAt": run.get("finished_at"),
            "PipelineVersion": run.get("pipeline_version", settings.pipeline_version),
            "RecordsFailed": int(run.get("records_failed", 0)),
            "RecordsProcessed": int(run.get("records_processed", 0)),
            "RecordsRead": int(run.get("records_read", 0)),
            "SummaryJson": run.get("summary_json"),
            "Error": run.get("error"),
        }
        sql = '''
        INSERT INTO leads."pipeline_runs"
            ("RunId", "Status", "StartedAt", "FinishedAt", "PipelineVersion",
             "RecordsFailed", "RecordsProcessed", "RecordsRead", "SummaryJson", "Error")
        VALUES (:RunId, :Status, :StartedAt, :FinishedAt, :PipelineVersion,
                :RecordsFailed, :RecordsProcessed, :RecordsRead, :SummaryJson, :Error)
        ON CONFLICT ("RunId") DO UPDATE SET
            "Status" = EXCLUDED."Status",
            "FinishedAt" = EXCLUDED."FinishedAt",
            "PipelineVersion" = EXCLUDED."PipelineVersion",
            "RecordsFailed" = EXCLUDED."RecordsFailed",
            "RecordsProcessed" = EXCLUDED."RecordsProcessed",
            "RecordsRead" = EXCLUDED."RecordsRead",
            "SummaryJson" = EXCLUDED."SummaryJson",
            "Error" = EXCLUDED."Error"
        '''
        with self.engine.begin() as conn:
            conn.execute(text(sql), payload)

    def save_customers(self, df: pd.DataFrame) -> None:
        if df is None or df.empty:
            return
        x = df.drop_duplicates("customer_id").copy()
        rows = []
        for _, r in x.iterrows():
            rows.append({
                "CustomerId": uuid.UUID(str(r["customer_id"])),
                "EmpresaId": source_id_to_int(r.get("empresa_id"), "EMP"),
                "Nombre": str(r.get("nombre_cliente") or "Cliente"),
                "TelefonoNormalizado": str(r.get("telefono_normalizado") or "") or None,
                "EmailNormalizado": str(r.get("email_normalizado") or "") or None,
                "Ciudad": str(r.get("ciudad") or "") or None,
            })
        sql = '''
        INSERT INTO leads."customers"
            ("CustomerId", "EmpresaId", "Nombre", "TelefonoNormalizado", "EmailNormalizado", "Ciudad")
        VALUES (:CustomerId, :EmpresaId, :Nombre, :TelefonoNormalizado, :EmailNormalizado, :Ciudad)
        ON CONFLICT ("CustomerId") DO UPDATE SET
            "EmpresaId" = EXCLUDED."EmpresaId",
            "Nombre" = EXCLUDED."Nombre",
            "TelefonoNormalizado" = EXCLUDED."TelefonoNormalizado",
            "EmailNormalizado" = EXCLUDED."EmailNormalizado",
            "Ciudad" = EXCLUDED."Ciudad"
        '''
        with self.engine.begin() as conn:
            self._executemany(conn, sql, rows)

    def save_leads(self, df: pd.DataFrame) -> None:
        if df is None or df.empty:
            return
        rows = []
        for _, r in df.iterrows():
            rows.append({
                "LeadId": source_id_to_int(r["lead_id"], "LD"),
                "FechaRegistro": r.get("fecha_registro"),
                "Canal": str(r.get("canal") or ""),
                "EmpresaId": source_id_to_int(r.get("empresa_id"), "EMP"),
                "PuntoVentaId": source_id_to_int(r.get("punto_venta_id"), "PV"),
                "NombreCliente": str(r.get("nombre_cliente") or "Cliente"),
                "Telefono": str(r.get("telefono") or "") or None,
                "Email": str(r.get("email") or "") or None,
                "Ciudad": str(r.get("ciudad") or "") or None,
                "ModeloInteresTexto": str(r.get("modelo_interes_texto") or "") or None,
                "EstadoGestion": normalize_status(r.get("estado_gestion")),
                "FechaPrimerContacto": r.get("fecha_primer_contacto"),
                "Campania": str(r.get("campania") or "") or None,
                "CustomerId": uuid.UUID(str(r["customer_id"])),
                "TelefonoNormalizado": str(r.get("telefono_normalizado") or "") or None,
                "EmailNormalizado": str(r.get("email_normalizado") or "") or None,
                "CiudadNormalizada": str(r.get("ciudad_normalizada") or "") or None,
                "CanalNormalizado": str(r.get("canal_normalizado") or "") or None,
                "ModeloTextoNormalizado": str(r.get("modelo_texto_normalizado") or "") or None,
                "MotorcycleSku": str(r.get("motorcycle_sku") or "") or None,
                "ModelMatchConfidence": probability_to_db(r.get("model_match_confidence"), "model_match_confidence") if pd.notna(r.get("model_match_confidence")) else None,
                "ModelMatchMethod": str(r.get("model_match_method") or "") or None,
            })
        columns = list(rows[0].keys())
        col_sql = ", ".join(quote_identifier(c) for c in columns)
        val_sql = ", ".join(f":{c}" for c in columns)
        update = ", ".join(f'{quote_identifier(c)} = EXCLUDED.{quote_identifier(c)}' for c in columns if c != "LeadId")
        sql = f'''
        INSERT INTO leads."leads" ({col_sql})
        VALUES ({val_sql})
        ON CONFLICT ("LeadId") DO UPDATE SET {update}
        '''
        with self.engine.begin() as conn:
            self._executemany(conn, sql, rows)

    def save_catalog(self, df: pd.DataFrame) -> None:
        if df is None or df.empty:
            return
        rows = []
        for _, r in df.iterrows():
            rows.append({
                "Sku": str(r["sku"]),
                "Marca": str(r["marca"]),
                "Linea": str(r["linea"]),
                "Cilindraje": int(float(r["cilindraje"])),
                "Segmento": str(r["segmento"]),
                "PrecioLista": float(r["precio_lista"]),
                "PuntosVentaDisponibles": len([x for x in str(r["puntos_venta_disponibles"]).split("|") if x]),
                "UnidadesDisponibles": int(float(r["unidades_disponibles"])),
            })
        sql = '''
        INSERT INTO leads."motorcycles"
            ("Sku", "Marca", "Linea", "Cilindraje", "Segmento", "PrecioLista", "PuntosVentaDisponibles", "UnidadesDisponibles")
        VALUES (:Sku, :Marca, :Linea, :Cilindraje, :Segmento, :PrecioLista, :PuntosVentaDisponibles, :UnidadesDisponibles)
        ON CONFLICT ("Sku") DO UPDATE SET
            "Marca" = EXCLUDED."Marca", "Linea" = EXCLUDED."Linea", "Cilindraje" = EXCLUDED."Cilindraje",
            "Segmento" = EXCLUDED."Segmento", "PrecioLista" = EXCLUDED."PrecioLista",
            "PuntosVentaDisponibles" = EXCLUDED."PuntosVentaDisponibles", "UnidadesDisponibles" = EXCLUDED."UnidadesDisponibles"
        '''
        with self.engine.begin() as conn:
            self._executemany(conn, sql, rows)

    def save_advisors(self, df: pd.DataFrame) -> None:
        if df is None or df.empty:
            return
        rows = []
        for _, r in df.iterrows():
            rows.append({
                "AsesorId": source_id_to_int(r["asesor_id"], "AS"),
                "Nombre": str(r["nombre"]),
                "PuntoVentaId": source_id_to_int(r["punto_venta_id"], "PV"),
                "EmpresaId": source_id_to_int(r["empresa_id"], "EMP"),
                "CapacidadDiariaLeads": int(r["capacidad_diaria_leads"]),
                "Activo": bool(r["activo_bool"]),
                "FechaIngreso": r["fecha_ingreso"],
            })
        sql = '''
        INSERT INTO leads."advisors"
            ("AsesorId", "Nombre", "PuntoVentaId", "EmpresaId", "CapacidadDiariaLeads", "Activo", "FechaIngreso")
        VALUES (:AsesorId, :Nombre, :PuntoVentaId, :EmpresaId, :CapacidadDiariaLeads, :Activo, :FechaIngreso)
        ON CONFLICT ("AsesorId") DO UPDATE SET
            "Nombre" = EXCLUDED."Nombre", "PuntoVentaId" = EXCLUDED."PuntoVentaId", "EmpresaId" = EXCLUDED."EmpresaId",
            "CapacidadDiariaLeads" = EXCLUDED."CapacidadDiariaLeads", "Activo" = EXCLUDED."Activo", "FechaIngreso" = EXCLUDED."FechaIngreso"
        '''
        with self.engine.begin() as conn:
            self._executemany(conn, sql, rows)

    @staticmethod
    def _utc_datetime(value) -> datetime:
        ts = pd.to_datetime(value, errors="coerce")
        if pd.isna(ts):
            return datetime.now(timezone.utc)
        if ts.tzinfo is None:
            return ts.to_pydatetime().replace(tzinfo=timezone.utc)
        return ts.to_pydatetime().astimezone(timezone.utc)

    def save_conversations(self, conversations: list[dict]) -> None:
        if not conversations:
            return
        with self.engine.begin() as conn:
            conv_sql = '''
            INSERT INTO leads."conversations"
                ("ConversacionId", "LeadId", "Canal", "FechaInicio")
            VALUES (:ConversacionId, :LeadId, :Canal, :FechaInicio)
            ON CONFLICT ("ConversacionId") DO UPDATE SET
                "LeadId" = EXCLUDED."LeadId", "Canal" = EXCLUDED."Canal", "FechaInicio" = EXCLUDED."FechaInicio"
            RETURNING "Id"
            '''
            msg_sql = '''
            INSERT INTO leads."messages"
                ("ConversationId", "SenderType", "Content", "SentAt")
            VALUES (:ConversationId, :SenderType, :Content, :SentAt)
            '''
            for c in conversations:
                lead_id = source_id_to_int(c["lead_id"], "LD")
                row = {
                    "ConversacionId": str(c["conversacion_id"]),
                    "LeadId": lead_id,
                    "Canal": str(c.get("canal") or ""),
                    "FechaInicio": self._utc_datetime(c.get("fecha_inicio")),
                }
                conversation_id = conn.execute(text(conv_sql), row).scalar_one()
                # Idempotency: replace messages for the conversation before reloading them.
                conn.execute(text('DELETE FROM leads."messages" WHERE "ConversationId" = :id'), {"id": conversation_id})
                start = self._utc_datetime(c.get("fecha_inicio"))
                rows = []
                for m in c.get("mensajes", []):
                    hour = str(m.get("hora") or "00:00")
                    try:
                        hh, mm = [int(x) for x in hour.split(":")[:2]]
                        sent = start.replace(hour=hh, minute=mm, second=0, microsecond=0)
                    except (ValueError, TypeError):
                        sent = start
                    rows.append({
                        "ConversationId": conversation_id,
                        "SenderType": str(m.get("emisor") or "unknown"),
                        "Content": str(m.get("texto") or ""),
                        "SentAt": sent,
                    })
                self._executemany(conn, msg_sql, rows)

    def save_enrichments(self, enrichments: Iterable) -> None:
        rows = []
        now = datetime.now(timezone.utc)
        for e in enrichments:
            rows.append({
                "LeadId": source_id_to_int(e.lead_id, "LD"),
                "ModeloInteres": e.model_interest,
                "CuotaInicial": e.initial_payment,
                "FormaPago": e.payment_method,
                "Intencion": e.intent,
                "Objecion": e.main_objection,
                "SolicitoCita": bool(e.requested_appointment),
                "SolicitoCotizacion": bool(e.requested_quote),
                "Confianza": probability_to_db(e.confidence, "enrichment_confidence"),
                "Provider": str(e.provider or "mock"),
                "PipelineVersion": settings.pipeline_version,
                "CreatedAt": now,
            })
        sql = '''
        INSERT INTO leads."lead_enrichments"
            ("LeadId", "ModeloInteres", "CuotaInicial", "FormaPago", "Intencion", "Objecion",
             "SolicitoCita", "SolicitoCotizacion", "Confianza", "Provider", "PipelineVersion", "CreatedAt")
        VALUES (:LeadId, :ModeloInteres, :CuotaInicial, :FormaPago, :Intencion, :Objecion,
                :SolicitoCita, :SolicitoCotizacion, :Confianza, :Provider, :PipelineVersion, :CreatedAt)
        '''
        with self.engine.begin() as conn:
            self._executemany(conn, sql, rows)

    def save_scores(self, scores: pd.DataFrame) -> None:
        if scores is None or scores.empty:
            return
        now = datetime.now(timezone.utc)
        rows = []
        for _, r in scores.iterrows():
            rows.append({
                "LeadId": source_id_to_int(r["lead_id"], "LD"),
                "HistoricalProbability": probability_to_db(r["historical_probability"], "historical_probability"),
                "FinalScore": probability_to_db(r["score"], "final_score"),
                "Priority": str(r["priority"]),
                "ReasonsJson": json.dumps(r.get("reasons", []), ensure_ascii=False),
                "ModelVersion": str(r.get("model_version") or settings.pipeline_version),
                "CreatedAt": now,
            })
        sql = '''
        INSERT INTO leads."lead_scores"
            ("LeadId", "HistoricalProbability", "FinalScore", "Priority", "ReasonsJson", "ModelVersion", "CreatedAt")
        VALUES (:LeadId, :HistoricalProbability, :FinalScore, :Priority, :ReasonsJson, :ModelVersion, :CreatedAt)
        '''
        with self.engine.begin() as conn:
            self._executemany(conn, sql, rows)

    def save_assignments(self, assignments: pd.DataFrame) -> None:
        if assignments is None or assignments.empty:
            return
        rows = []
        for _, r in assignments.iterrows():
            rows.append({
                "LeadId": source_id_to_int(r["lead_id"], "LD"),
                "AsesorId": source_id_to_int(r["advisor_id"], "AS"),
                "AssignedAt": self._utc_datetime(r.get("assignment_date")),
                "Reason": "Asignación por empresa, punto de venta y capacidad disponible",
            })
        sql = '''
        INSERT INTO leads."lead_assignments"
            ("LeadId", "AsesorId", "AssignedAt", "Reason")
        VALUES (:LeadId, :AsesorId, :AssignedAt, :Reason)
        '''
        with self.engine.begin() as conn:
            self._executemany(conn, sql, rows)
