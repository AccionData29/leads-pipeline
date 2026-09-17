"""Mapping between the pipeline's Python (snake_case) model and the
PostgreSQL contract owned by the .NET/EF Core backend.

The pipeline intentionally keeps snake_case internally. Only the persistence
boundary translates names and source identifiers to the physical database
contract.
"""
from __future__ import annotations

import re
import unicodedata
import uuid
from typing import Any

# PostgreSQL column names are case-sensitive here because EF Core created the
# PascalCase identifiers as quoted identifiers.
LEAD_COLUMNS = {
    "lead_id": "LeadId",
    "fecha_registro": "FechaRegistro",
    "canal": "Canal",
    "empresa_id": "EmpresaId",
    "punto_venta_id": "PuntoVentaId",
    "nombre_cliente": "NombreCliente",
    "telefono": "Telefono",
    "email": "Email",
    "ciudad": "Ciudad",
    "modelo_interes_texto": "ModeloInteresTexto",
    "estado_gestion": "EstadoGestion",
    "fecha_primer_contacto": "FechaPrimerContacto",
    "campania": "Campania",
    "customer_id": "CustomerId",
    "telefono_normalizado": "TelefonoNormalizado",
    "email_normalizado": "EmailNormalizado",
    "ciudad_normalizada": "CiudadNormalizada",
    "canal_normalizado": "CanalNormalizado",
    "modelo_texto_normalizado": "ModeloTextoNormalizado",
    "motorcycle_sku": "MotorcycleSku",
    "model_match_confidence": "ModelMatchConfidence",
    "model_match_method": "ModelMatchMethod",
}

# Source identifiers are stable business identifiers (LD-00001, EMP-03,
# PV-014, AS-001), while the current backend contract uses bigint for these
# identifiers. For the assessment data, the numeric suffix is the canonical
# deterministic mapping.
def source_id_to_int(value: Any, expected_prefix: str | None = None) -> int:
    raw = str(value or "").strip()
    match = re.fullmatch(r"([A-Za-z]+)-(\d+)", raw)
    if not match:
        raise ValueError(f"Unsupported source identifier: {raw!r}")
    prefix, digits = match.groups()
    if expected_prefix and prefix.upper() != expected_prefix.upper():
        raise ValueError(f"Expected {expected_prefix}-NNNNN identifier, got {raw!r}")
    number = int(digits)
    if number <= 0:
        raise ValueError(f"Identifier must be positive: {raw!r}")
    return number


def customer_uuid(customer_key: str) -> uuid.UUID:
    """Create a stable UUID from the pipeline's deterministic customer key."""
    return uuid.uuid5(uuid.NAMESPACE_URL, f"motos-leads:customer:{customer_key}")


def normalize_status(value: Any) -> str:
    """Map source lead statuses to the backend LeadStatus enum names."""
    raw = " ".join(str(value or "").strip().lower().split())
    raw = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
    mapping = {
        "": "New",
        "sin gestion": "New",
        "nuevo": "New",
        "contactado": "Contacted",
        "no contesta": "Contacted",
        "cotizacion enviada": "Qualified",
        "en proceso": "Qualified",
        "calificado": "Qualified",
        "cita": "Appointment",
        "ganado": "Won",
        "cerrado": "Won",
        "descartado": "Lost",
        "perdido": "Lost",
    }
    return mapping.get(raw, "New")


def quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def probability_to_db(value: Any, field_name: str = "probability") -> float | None:
    """Normalize confidence/probability values to the backend 0..1 contract.

    The EF Core model stores these values as numeric(5,4), so a percentage
    such as 100.0 must be persisted as 1.0. Values already in 0..1 are kept.
    """
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid {field_name}: {value!r}") from exc
    if number < 0:
        raise ValueError(f"{field_name} cannot be negative: {number}")
    if number > 1.0:
        if number <= 100.0:
            number /= 100.0
        else:
            raise ValueError(f"{field_name} exceeds 100%: {number}")
    return round(number, 4)
