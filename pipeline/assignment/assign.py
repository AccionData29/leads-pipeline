from datetime import datetime
import pandas as pd

def assign_leads(scored, advisors, today=None):
    today=today or datetime.now()
    adv=advisors[(advisors["activo_bool"]) & (advisors["capacidad_diaria_leads"]>0)].copy()
    scored=scored.sort_values(["priority","score"],ascending=[True,False],key=lambda s: s.map({"HIGH":0,"MEDIUM":1,"LOW":2}) if s.name=="priority" else s).copy()
    assignments=[]; counters={a:0 for a in adv["asesor_id"]}
    for _,lead in scored.iterrows():
        candidates=adv[(adv["empresa_id"]==lead["empresa_id"]) & (adv["punto_venta_id"]==lead["punto_venta_id"]) & (adv["capacidad_diaria_leads"]>adv["asesor_id"].map(counters))]
        if candidates.empty: continue
        advisor=candidates.sort_values(["asesor_id"]).iloc[0]
        counters[advisor.asesor_id]+=1
        assignments.append({"lead_id":lead.lead_id,"advisor_id":advisor.asesor_id,"assignment_date":today,"priority_at_assignment":lead.priority,"position":counters[advisor.asesor_id]})
    return pd.DataFrame(assignments)
