from pathlib import Path
import json
import pandas as pd

REQUIRED = {
    "leads.csv": ["lead_id","fecha_registro","canal","empresa_id","punto_venta_id","nombre_cliente","telefono","email","ciudad","modelo_interes_texto","estado_gestion","fecha_primer_contacto","campania"],
    "historico_cierres.csv": ["lead_id","fecha_registro","canal","empresa_id","punto_venta_id","modelo_cotizado","precio_lista","horas_al_primer_contacto","numero_contactos","manifesto_cuota_inicial","forma_pago_declarada","pidio_cita","desenlace"],
    "catalogo_motos.csv": ["sku","marca","linea","cilindraje","segmento","precio_lista","puntos_venta_disponibles","unidades_disponibles"],
    "asesores.csv": ["asesor_id","nombre","punto_venta_id","empresa_id","capacidad_diaria_leads","activo","fecha_ingreso"],
}

def _check_columns(name: str, df: pd.DataFrame):
    missing = [c for c in REQUIRED[name] if c not in df.columns]
    if missing:
        raise ValueError(f"{name}: missing columns: {missing}")

def load_sources(raw_dir: Path):
    raw_dir.mkdir(parents=True, exist_ok=True)
    result = {}
    for name in REQUIRED:
        path = raw_dir / name
        if not path.exists():
            raise FileNotFoundError(f"Required source not found: {path}")
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
        _check_columns(name, df)
        result[name.removesuffix('.csv')] = df
    conv_path = raw_dir / "conversaciones.json"
    if not conv_path.exists():
        raise FileNotFoundError(f"Required source not found: {conv_path}")
    with conv_path.open(encoding="utf-8") as f:
        result["conversaciones"] = json.load(f)
    return result
