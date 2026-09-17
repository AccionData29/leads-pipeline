import pandas as pd
from pipeline.assignment.assign import assign_leads

def test_capacity():
    scored=pd.DataFrame([{"lead_id":f"L{i}","score":.9,"priority":"HIGH","empresa_id":"E1","punto_venta_id":"P1"} for i in range(5)])
    adv=pd.DataFrame([{"asesor_id":"A1","empresa_id":"E1","punto_venta_id":"P1","capacidad_diaria_leads":2,"activo_bool":True}])
    out=assign_leads(scored,adv); assert len(out)==2
