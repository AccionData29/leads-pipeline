import pandas as pd
from pipeline.deduplication.dedupe import build_customer_groups

def test_same_phone_groups():
    df=pd.DataFrame([{"lead_id":"1","telefono_normalizado":"573001112233","email_normalizado":"a@x.com","nombre_normalizado":"juan","ciudad_normalizada":"bogota"},{"lead_id":"2","telefono_normalizado":"573001112233","email_normalizado":"b@x.com","nombre_normalizado":"juan","ciudad_normalizada":"bogota"}])
    out=build_customer_groups(df); assert out.customer_id.nunique()==1; assert out.is_duplicate.all()
