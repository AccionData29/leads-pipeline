import re
import unicodedata
import pandas as pd
from rapidfuzz import process, fuzz

def text_norm(value):
    if value is None: return ""
    s = str(value).strip().lower()
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"\s+", " ", s)
    return s

def phone_norm(value):
    digits = re.sub(r"\D", "", str(value or ""))
    if digits.startswith("57") and len(digits) == 12: return digits
    if len(digits) == 10 and digits.startswith("3"): return "57" + digits
    return digits

def parse_datetime(value):
    if value is None or str(value).strip() == "": return pd.NaT
    return pd.to_datetime(value, errors="coerce", dayfirst=True, format="mixed")

def normalize_leads(df):
    x = df.copy()
    x["nombre_normalizado"] = x["nombre_cliente"].map(text_norm)
    x["telefono_normalizado"] = x["telefono"].map(phone_norm)
    x["email_normalizado"] = x["email"].map(lambda v: str(v).strip().lower())
    x["ciudad_normalizada"] = x["ciudad"].map(text_norm).replace({"bogota d.c.":"bogota", "sta marta":"santa marta", "medellin":"medellin"})
    x["canal_normalizado"] = x["canal"].map(text_norm).replace({"formulario web":"formulario web", "meta ads":"meta ads", "whatsapp":"whatsapp"})
    x["estado_normalizado"] = x["estado_gestion"].map(text_norm)
    x["fecha_registro_normalizada"] = x["fecha_registro"].map(parse_datetime)
    x["fecha_primer_contacto_normalizada"] = x["fecha_primer_contacto"].map(parse_datetime)
    x["modelo_texto_normalizado"] = x["modelo_interes_texto"].map(text_norm)
    return x

def normalize_catalog(df):
    x=df.copy()
    x["linea_normalizada"] = x["linea"].map(text_norm)
    x["marca_normalizada"] = x["marca"].map(text_norm)
    x["precio_lista"] = pd.to_numeric(x["precio_lista"], errors="coerce")
    x["unidades_disponibles"] = pd.to_numeric(x["unidades_disponibles"], errors="coerce")
    return x

def normalize_advisors(df):
    x=df.copy()
    x["activo_bool"] = x["activo"].map(text_norm).eq("si")
    x["capacidad_diaria_leads"] = pd.to_numeric(x["capacidad_diaria_leads"], errors="coerce").fillna(0).astype(int)
    return x

def normalize_history(df):
    x=df.copy()
    x["fecha_registro_normalizada"] = x["fecha_registro"].map(parse_datetime)
    x["canal_normalizado"] = x["canal"].map(text_norm)
    x["modelo_normalizado"] = x["modelo_cotizado"].map(text_norm)
    for c in ["precio_lista","horas_al_primer_contacto","numero_contactos"]:
        x[c]=pd.to_numeric(x[c], errors="coerce")
    x["cuota_bool"] = x["manifesto_cuota_inicial"].map(text_norm).eq("si")
    x["credito_bool"] = x["forma_pago_declarada"].map(text_norm).eq("credito")
    x["cita_bool"] = x["pidio_cita"].map(text_norm).eq("si")
    x["target"] = x["desenlace"].map(text_norm).eq("cerrado").astype(int)
    return x

def match_catalog(model_text, catalog_df, threshold=88):
    if not model_text: return None, 0, "none"
    choices = catalog_df["linea_normalizada"].tolist()
    exact = next((i for i,v in enumerate(choices) if v == model_text), None)
    if exact is not None:
        return catalog_df.iloc[exact]["sku"], 100, "exact"
    match = process.extractOne(model_text, choices, scorer=fuzz.token_set_ratio)
    if not match: return None, 0, "none"
    value, score, idx = match
    if score >= threshold:
        return catalog_df.iloc[idx]["sku"], score, "fuzzy"
    return None, score, "unmatched"

def apply_catalog_match(leads, catalog, threshold=88):
    x=leads.copy()
    matches=[match_catalog(v,catalog,threshold) for v in x["modelo_texto_normalizado"]]
    x["motorcycle_sku"]=[m[0] for m in matches]
    x["model_match_confidence"]=[m[1] for m in matches]
    x["model_match_method"]=[m[2] for m in matches]
    return x
