from pydantic_settings import BaseSettings, SettingsConfigDict


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
    # The verified sender address (for SendGrid this differs from smtp_user="apikey")
    email_from_address: str = ""
    database_url: str = "sqlite:///./aria.db"
    human_approval_mode: bool = True   # Phase 2: drafts need human approval
    debug: bool = True

    # Chat + alert config
    base_url: str = "http://localhost:8000"           # used to build chat links in emails
    alert_email: str = ""                             # team inbox for hot-lead alerts
    whatsapp_business_number: str = ""                # team's WA number for internal alerts (e.g. "919304712348")
    # WhatsApp Cloud API (Meta)
    # Get from: developers.facebook.com → your app → WhatsApp → API Setup
    whatsapp_api_token: str = ""                      # Bearer token (use permanent System User token for prod)
    whatsapp_phone_number_id: str = ""                # Phone Number ID (NOT the actual phone number)
    whatsapp_business_account_id: str = ""            # WhatsApp Business Account ID (from API Setup page)
    whatsapp_webhook_verify_token: str = "aria_beyondsure_2024"  # match this in Meta dashboard webhook config

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
