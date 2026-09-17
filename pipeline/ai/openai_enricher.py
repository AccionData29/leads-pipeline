import json
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential
from pipeline.ai.base import Enricher, SYSTEM_PROMPT
from pipeline.domain.models import LeadEnrichment

SCHEMA={"type":"object","properties":{
 "modelo_interes":{"type":["string","null"]},"cuota_inicial":{"type":["number","null"]},
 "forma_pago":{"type":["string","null"]},"intencion":{"type":["string","null"]},
 "objecion_principal":{"type":["string","null"]},"pidio_cita":{"type":"boolean"},
 "pidio_cotizacion":{"type":"boolean"},"confidence":{"type":"number"}},
 "required":["modelo_interes","cuota_inicial","forma_pago","intencion","objecion_principal","pidio_cita","pidio_cotizacion","confidence"],"additionalProperties":False}

class OpenAIEnricher(Enricher):
    def __init__(self, api_key, model):
        self.client=OpenAI(api_key=api_key); self.model=model
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1,max=8))
    def extract(self, lead_id, conversation_text):
        r=self.client.chat.completions.create(model=self.model, temperature=0, messages=[
            {"role":"system","content":SYSTEM_PROMPT}, {"role":"user","content":conversation_text}],
            response_format={"type":"json_schema","json_schema":{"name":"lead_enrichment","strict":True,"schema":SCHEMA}})
        d=json.loads(r.choices[0].message.content)
        return LeadEnrichment(lead_id,d["modelo_interes"],d["cuota_inicial"],d["forma_pago"],d["intencion"],d["objecion_principal"],d["pidio_cita"],d["pidio_cotizacion"],d["confidence"],"openai",self.model,"1.0")
