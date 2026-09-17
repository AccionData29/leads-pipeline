from pipeline.ai.mock import MockEnricher
from pipeline.config.settings import settings

def get_enricher():
    if settings.ai_provider.lower()=="openai":
        if not settings.openai_api_key:
            raise ValueError("AI_PROVIDER=openai requires OPENAI_API_KEY")
        from pipeline.ai.openai_enricher import OpenAIEnricher
        return OpenAIEnricher(settings.openai_api_key, settings.openai_model)
    return MockEnricher()

def conversations_to_text(conversation):
    return "\n".join(f"{m.get('emisor','')}: {m.get('texto','')}" for m in conversation.get("mensajes",[]))

def enrich_all(conversations, enricher):
    return [enricher.extract(c["lead_id"], conversations_to_text(c)) for c in conversations]
