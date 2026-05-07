from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM provider: "groq" or "anthropic"
    llm_provider: str = "groq"

    # Groq — get from https://console.groq.com
    groq_api_key: str = ""
    groq_model: str = "llama-3.1-8b-instant"   # free tier, very fast

    # Anthropic (Claude) — get from https://console.anthropic.com
    anthropic_api_key: str = ""

    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from_name: str = "BeyondSure"
    database_url: str = "sqlite:///./aria.db"
    human_approval_mode: bool = True   # Phase 2: drafts need human approval
    debug: bool = True

    class Config:
        env_file = ".env"


settings = Settings()
