from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://quickdesk:quickdesk@localhost:5432/quickdesk"
    jwt_secret: str = "dev-only-secret"
    jwt_expires_min: int = 480
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    frontend_origin: str = "http://localhost:5173"
    kb_dir: Path = REPO_ROOT / "kb"


settings = Settings()
