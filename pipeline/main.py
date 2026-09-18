import argparse, hashlib, shutil, uuid
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
from pipeline.config.settings import settings
from pipeline.ingestion.loaders import load_sources
from pipeline.normalization.normalize import normalize_leads, normalize_catalog, normalize_advisors, normalize_history, apply_catalog_match
from pipeline.deduplication.dedupe import build_customer_groups
from pipeline.ai.service import get_enricher, enrich_all
from pipeline.scoring.model import train, score_current
from pipeline.assignment.assign import assign_leads
from pipeline.persistence.db import Database
from pipeline.reporting.reports import write_report

def prepare_raw(source_dir: Path):
    settings.raw_dir.mkdir(parents=True,exist_ok=True)
    for name in ["leads.csv","historico_cierres.csv","catalogo_motos.csv","asesores.csv","conversaciones.json"]:
        src=source_dir/name
        if not src.exists(): raise FileNotFoundError(src)
        shutil.copy2(src,settings.raw_dir/name)

def run(init_db=False, source_dir=None, no_db=False, run_id=None):
    run_uuid=run_id or uuid.uuid4()
    run_id=run_uuid.hex[:12]
    started=datetime.now(timezone.utc)
    source_dir=Path(source_dir) if source_dir else settings.raw_dir
    if source_dir.resolve()!=settings.raw_dir.resolve(): prepare_raw(source_dir); source_dir=settings.raw_dir
    data=load_sources(source_dir)
    leads=normalize_leads(data["leads"])
    # Source contains intentional duplicate lead_id values; retain one canonical row.
    leads["source_row_number"]=range(1,len(leads)+1)
    leads=leads.sort_values("source_row_number").drop_duplicates("lead_id",keep="last").reset_index(drop=True)
    catalog=normalize_catalog(data["catalogo_motos"])
    advisors=normalize_advisors(data["asesores"])
    history=normalize_history(data["historico_cierres"])
    leads=apply_catalog_match(leads,catalog,settings.fuzzy_match_threshold)
    leads=build_customer_groups(leads)
    # attach catalog price for scoring
    leads=leads.merge(catalog[["sku","precio_lista"]].rename(columns={"sku":"motorcycle_sku","precio_lista":"precio_lista"}),on="motorcycle_sku",how="left",suffixes=("","_catalog"))
    # AI enrichment
    enricher=get_enricher(); enrichments=enrich_all(data["conversaciones"],enricher)
    enrich_df=pd.DataFrame([e.__dict__ for e in enrichments])
    if not enrich_df.empty:
        enrich_df=(enrich_df.sort_values(["lead_id","confidence"]).groupby("lead_id",as_index=False).agg({"initial_payment":"max","payment_method":"last","intent":"last","main_objection":"last","requested_appointment":"max","requested_quote":"max","provider":"last","model_name":"last","prompt_version":"last","confidence":"max"}))
    leads=leads.merge(enrich_df[["lead_id","initial_payment","payment_method","intent","main_objection","requested_appointment","requested_quote"]],on="lead_id",how="left")
    leads["requested_appointment"]=leads["requested_appointment"].apply(lambda v: False if pd.isna(v) else bool(v))
    leads["requested_quote"]=leads["requested_quote"].apply(lambda v: False if pd.isna(v) else bool(v))
    # Historical model
    model_path=settings.output_dir/"scoring_model.joblib"
    pipe, train_metrics=train(history,model_path)
    scored=score_current(leads,history,model_path,pipe=pipe)
    scored=scored.merge(leads[["lead_id","empresa_id","punto_venta_id"]],on="lead_id",how="left")
    # simple business explanations, deterministic and transparent
    reasons=[]
    now=pd.Timestamp.now()
    for _,r in leads.set_index("lead_id").reindex(scored.lead_id).iterrows():
        rr=[]
        if bool(r.get("requested_appointment")): rr.append("Solicitó cita")
        if bool(r.get("requested_quote")): rr.append("Solicitó cotización")
        if r.get("initial_payment") is not None and pd.notna(r.get("initial_payment")): rr.append("Mencionó cuota inicial")
        if str(r.get("payment_method"))=="credito": rr.append("Forma de pago: crédito")
        if r.get("fecha_registro_normalizada") is not pd.NaT and pd.notna(r.get("fecha_registro_normalizada")):
            hours=(now-r.get("fecha_registro_normalizada")).total_seconds()/3600
            if hours<=24: rr.append("Lead registrado en las últimas 24 horas")
        reasons.append(rr[:5])
    scored["model_version"]=settings.pipeline_version; scored["reasons"]=reasons; scored["features"]=[{} for _ in range(len(scored))]
    assignments=assign_leads(scored,advisors)
    counts={"leads":len(leads),"conversations":len(data["conversaciones"]),"enrichments":len(enrichments),"scores":len(scored),"assignments":len(assignments),"duplicates":int(leads.is_duplicate.sum())}
    metrics={"training":train_metrics,"model_path":str(model_path)}
    write_report(settings.output_dir,run_id,metrics,counts)
    # Always write inspectable artifacts; DB is optional for local execution.
    leads.to_csv(settings.output_dir/f"leads_normalized_{run_id}.csv",index=False)
    enrich_df.to_csv(settings.output_dir/f"lead_enrichments_{run_id}.csv",index=False)
    scored.to_json(settings.output_dir/f"lead_scores_{run_id}.json",orient="records",force_ascii=False,indent=2)
    assignments.to_csv(settings.output_dir/f"lead_assignments_{run_id}.csv",index=False)
    if not no_db:
        db=Database()
        # PostgreSQL schema ownership belongs to the .NET/EF Core backend.
        # Validate the shared contract before writing any records.
        db.validate_schema()
        db.save_leads(leads[["lead_id","customer_id","fecha_registro_normalizada","canal","empresa_id","punto_venta_id","nombre_cliente","telefono","email","ciudad","modelo_interes_texto","estado_gestion","fecha_primer_contacto_normalizada","campania","telefono_normalizado","email_normalizado","ciudad_normalizada","canal_normalizado","modelo_texto_normalizado","motorcycle_sku","model_match_confidence","model_match_method"]].rename(columns={"fecha_registro_normalizada":"fecha_registro","fecha_primer_contacto_normalizada":"fecha_primer_contacto"}))
        db.save_customers(leads[["customer_id","empresa_id","nombre_cliente","telefono_normalizado","email_normalizado","ciudad"]])
        db.save_catalog(catalog)
        db.save_advisors(advisors)
        db.save_conversations(data["conversaciones"])
        db.save_run({"run_id":run_uuid,"started_at":started,"finished_at":datetime.now(timezone.utc),"status":"SUCCESS","pipeline_version":settings.pipeline_version,"records_read":sum([len(data["leads"]),len(data["historico_cierres"]),len(data["catalogo_motos"]),len(data["asesores"]),len(data["conversaciones"])]),"records_processed":len(leads),"records_failed":0,"error":None,"summary_json":__import__("json").dumps(counts,ensure_ascii=False)})
        # Replace/upsert is deliberately left to production repository migrations; pipeline tables can be loaded append-only for assessment runs.
        db.save_enrichments(enrichments)
        db.save_scores(scored)
        db.save_assignments(assignments)
    print(f"Pipeline {run_id} SUCCESS: {counts}")
    return run_id

def main():
    p=argparse.ArgumentParser(description="Motos Leads end-to-end pipeline")
    p.add_argument("--source-dir",default=None)
    p.add_argument("--init-db",action="store_true", help="Legacy flag: validates the EF Core schema; it no longer creates tables.")
    p.add_argument("--no-db",action="store_true")
    args=p.parse_args(); run(args.init_db,args.source_dir,args.no_db)
if __name__=="__main__": main()
