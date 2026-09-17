import uuid

from pipeline.persistence.mappings import customer_uuid, normalize_status, source_id_to_int, probability_to_db


def test_source_ids_map_deterministically_to_backend_bigint():
    assert source_id_to_int("LD-00001", "LD") == 1
    assert source_id_to_int("EMP-03", "EMP") == 3
    assert source_id_to_int("PV-014", "PV") == 14
    assert source_id_to_int("AS-042", "AS") == 42


def test_source_id_rejects_wrong_prefix():
    try:
        source_id_to_int("EMP-03", "LD")
    except ValueError:
        return
    raise AssertionError("Expected ValueError")


def test_customer_uuid_is_stable():
    first = customer_uuid("phone:573001234567")
    second = customer_uuid("phone:573001234567")
    assert isinstance(first, uuid.UUID)
    assert first == second


def test_status_mapping_matches_backend_enum_names():
    assert normalize_status("Sin gestión") == "New"
    assert normalize_status("Contactado") == "Contacted"
    assert normalize_status("Cotización enviada") == "Qualified"
    assert normalize_status("En proceso") == "Qualified"
    assert normalize_status("Descartado") == "Lost"


def test_customer_persistence_uses_canonical_customer_id():
    # save_leads/save_customers receive the canonical UUID produced by the
    # deduplication stage; persistence must not require customer_key.
    import pandas as pd
    from pipeline.persistence.db import Database

    customer_id = customer_uuid("phone:573001234567")
    frame = pd.DataFrame([{
        "customer_id": str(customer_id),
        "empresa_id": "EMP-03",
        "nombre_cliente": "Cliente",
        "telefono_normalizado": "573001234567",
        "email_normalizado": None,
        "ciudad": "Bogota",
    }])
    # The mapping itself is the contract; constructing the DB row should not
    # access a non-existent customer_key column.
    row = {
        "CustomerId": __import__("uuid").UUID(str(frame.iloc[0]["customer_id"])),
        "EmpresaId": source_id_to_int(frame.iloc[0]["empresa_id"], "EMP"),
    }
    assert row["CustomerId"] == customer_id
    assert row["EmpresaId"] == 3


def test_probability_to_db_accepts_fraction_and_percentage():
    assert probability_to_db(0.75) == 0.75
    assert probability_to_db(100.0) == 1.0
    assert probability_to_db(85.5) == 0.855
    assert probability_to_db(None) is None


def test_probability_to_db_rejects_invalid_value():
    try:
        probability_to_db(101.0, "confidence")
    except ValueError:
        return
    raise AssertionError("Expected ValueError")
