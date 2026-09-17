import pandas as pd
import uuid

def build_customer_groups(leads: pd.DataFrame):
    x=leads.copy()
    x["customer_key"] = ""
    keys=[]
    for _,r in x.iterrows():
        phone=r.get("telefono_normalizado","")
        email=r.get("email_normalizado","")
        name=r.get("nombre_normalizado","")
        city=r.get("ciudad_normalizada","")
        if phone: key=f"phone:{phone}"
        elif email: key=f"email:{email}"
        else: key=f"namecity:{name}|{city}"
        keys.append(key)
    x["customer_key"]=keys
    x["customer_id"] = x["customer_key"].map(lambda s: str(uuid.uuid5(uuid.NAMESPACE_URL, f"motos-leads:customer:{s}")))
    counts=x.groupby("customer_id")["lead_id"].transform("count")
    x["is_duplicate"] = counts > 1
    x["duplicate_group_id"] = x["customer_id"].where(x["is_duplicate"])
    x["duplicate_confidence"] = x.apply(lambda r: 1.0 if str(r["customer_key"]).startswith(("phone:","email:")) else 0.75 if r["is_duplicate"] else 0.0, axis=1)
    x["duplicate_reason"] = x.apply(lambda r: "same_phone_or_email" if r["is_duplicate"] and str(r["customer_key"]).split(":",1)[0] in ("phone","email") else "same_name_city" if r["is_duplicate"] else "", axis=1)
    return x
