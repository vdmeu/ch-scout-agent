from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # App
    app_env: str = Field(default="development")
    log_level: str = Field(default="info")

    # Discord
    scout_webhook_url: str = Field(default="")

    # Supabase
    supabase_url: str = Field(default="")
    supabase_key: str = Field(default="")

    # External API — for draft reply links
    api_base_url: str = Field(default="https://ch-api-production-b552.up.railway.app")

    # Optional API keys
    stackoverflow_api_key: str = Field(default="")
    github_token: str = Field(default="")
    reddit_user_agent: str = Field(default="ch-scout-agent/1.0")

    # Scoring
    min_relevance_score: float = Field(default=0.5)

    # Poll intervals (minutes)
    poll_interval_stackoverflow: int = Field(default=15)
    poll_interval_hackernews: int = Field(default=30)
    poll_interval_reddit: int = Field(default=30)
    poll_interval_github: int = Field(default=15)

    # Lookback window (seconds)
    lookback_seconds: int = Field(default=86400)

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


settings = Settings()
