from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    data_dir: Path = Path("./data")
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/leads"
    ai_provider: str = "mock"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    pipeline_version: str = "0.1.0"
    ai_max_retries: int = 3
    ai_batch_size: int = 20
    fuzzy_match_threshold: int = 88
    model_config = SettingsConfigDict(env_prefix="", env_file=".env", extra="ignore")

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def output_dir(self) -> Path:
        return self.data_dir / "output"

settings = Settings()
