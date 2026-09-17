from pathlib import Path
import json
import pandas as pd
import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from joblib import dump, load

FEATURES_NUM=["precio_lista","horas_al_primer_contacto","numero_contactos"]
FEATURES_CAT=["canal_normalizado","empresa_id","punto_venta_id","modelo_normalizado","forma_pago_declarada","manifesto_cuota_inicial","pidio_cita"]

def _feature_frame(data):
    x=data.copy()
    for c in FEATURES_NUM:
        if c not in x: x[c]=np.nan
        x[c]=pd.to_numeric(x[c],errors="coerce")
    for c in FEATURES_CAT:
        if c not in x: x[c]=""
        x[c]=x[c].fillna("").astype(str)
    return x[FEATURES_NUM+FEATURES_CAT]

def train(history: pd.DataFrame, model_path: Path):
    data=history.copy(); X=_feature_frame(data); y=data["target"].astype(int)
    prep=ColumnTransformer([
      ("num",Pipeline([("imp",SimpleImputer(strategy="median")),("scale",StandardScaler())]),FEATURES_NUM),
      ("cat",Pipeline([("imp",SimpleImputer(strategy="most_frequent")),("ohe",OneHotEncoder(handle_unknown="ignore"))]),FEATURES_CAT)])
    pipe=Pipeline([("prep",prep),("model",LogisticRegression(max_iter=1000,class_weight="balanced"))])
    pipe.fit(X,y); probs=pipe.predict_proba(X)[:,1]
    metrics={"roc_auc_train":float(roc_auc_score(y,probs)),"rows":int(len(data)),"positive_rate":float(y.mean())}
    model_path.parent.mkdir(parents=True,exist_ok=True); dump(pipe,model_path)
    (model_path.parent/"metrics.json").write_text(json.dumps(metrics,indent=2),encoding="utf-8")
    return pipe,metrics

def score_current(leads, history, model_path: Path):
    pipe=load(model_path) if model_path.exists() else train(history,model_path)[0]
    x=leads.copy()
    now=pd.Timestamp.now()
    x["horas_al_primer_contacto"]=((now-x["fecha_registro_normalizada"]).dt.total_seconds()/3600).clip(lower=0)
    x["numero_contactos"]=0
    x["modelo_normalizado"]=x["modelo_texto_normalizado"]
    x["forma_pago_declarada"]=x.get("payment_method",pd.Series(["no_informa"]*len(x),index=x.index)).fillna("no_informa")
    x["manifesto_cuota_inicial"]=x["initial_payment"].notna().map({True:"SI",False:"NO_INFORMA"})
    x["pidio_cita"]=x["requested_appointment"].fillna(False).map({True:"SI",False:"NO"})
    historical_prob=pipe.predict_proba(_feature_frame(x))[:,1]
    # Business signals extracted by AI. They do not replace the historical model;
    # they add a transparent, bounded adjustment for information unavailable in the historical dataset.
    intent=x["intent"].fillna("").astype(str).str.lower()
    signal=np.zeros(len(x))
    signal += intent.map({"alta":0.12,"media":0.05,"baja":-0.08}).fillna(0).to_numpy()
    signal += x["requested_appointment"].fillna(False).astype(int).to_numpy()*0.08
    signal += x["requested_quote"].fillna(False).astype(int).to_numpy()*0.05
    signal += x["initial_payment"].notna().astype(int).to_numpy()*0.05
    signal -= (x["horas_al_primer_contacto"]>24).astype(int).to_numpy()*0.04
    final=np.clip(0.8*historical_prob+0.2*np.clip(historical_prob+signal,0,1),0,1)
    out=pd.DataFrame({"lead_id":x["lead_id"].values,"historical_probability":historical_prob,"score":final})
    out["priority"]=pd.cut(out["score"],[-.01,.33,.66,1.01],labels=["LOW","MEDIUM","HIGH"]).astype(str)
    return out
