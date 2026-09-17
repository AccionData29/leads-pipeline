from abc import ABC, abstractmethod
from pipeline.domain.models import LeadEnrichment

SYSTEM_PROMPT = """Extrae exclusivamente información explícita de una conversación comercial de motocicletas. No inventes datos. Si un campo no aparece, usa null/false según corresponda. Devuelve JSON con: modelo_interes, cuota_inicial, forma_pago, intencion, objecion_principal, pidio_cita, pidio_cotizacion, confidence."""

class Enricher(ABC):
    @abstractmethod
    def extract(self, lead_id: str, conversation_text: str) -> LeadEnrichment: ...
