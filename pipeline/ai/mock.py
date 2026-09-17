import re
from pipeline.ai.base import Enricher
from pipeline.domain.models import LeadEnrichment

MODELS=["cb 125f twister","xr 150l","cb 190r","navi","dio 110","xre 300","boxer ct 100","pulsar ns 125","pulsar ns 160","pulsar rs 200","xpulse 200","hunk 160r","dash 110","nkd 125","discover 125","best 125"]
class MockEnricher(Enricher):
    def extract(self, lead_id, conversation_text):
        t=conversation_text.lower()
        model=next((m for m in MODELS if m in t), None)
        payment="credito" if any(k in t for k in ["credito","financiad","cuotas","cuota"]) else "contado" if any(k in t for k in ["contado","efectivo"]) else None
        cita=any(k in t for k in ["cita","visitar","voy a la tienda","agendar"])
        quote=any(k in t for k in ["cotizacion","cotización","precio","cuanto vale","cuánto vale"])
        intent="alta" if any(k in t for k in ["la quiero","quiero comprar","comprar","separar","reservar","agendar cita"]) else "media" if any(k in t for k in ["me interesa","estoy mirando","estoy buscando"]) else "baja" if any(k in t for k in ["solo estaba mirando","solo miro","por ahora no"]) else None
        objection=next((k for k in ["precio","cuota","financiación","financiacion","disponibilidad","soat","matrícula","matricula"] if k in t), None)
        amounts=re.findall(r"(?:\$|\b)(\d{1,3}(?:[\.,]\d{3})+|\d{6,8})\b", t)
        initial=None
        if amounts:
            vals=[]
            for a in amounts:
                try: vals.append(float(a.replace('.','').replace(',','')))
                except: pass
            if vals: initial=max(vals)
        confidence=.75 if model or payment or intent else .55
        return LeadEnrichment(lead_id, model, initial if "inicial" in t or "inicial" in t else None, payment, intent, objection, cita, quote, confidence, "mock", None, "1.0")
