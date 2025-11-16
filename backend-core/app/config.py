import os
from functools import lru_cache
from typing import List


class Settings:
  """Centralized configuration pulled from environment variables."""

  app_name: str = "Agency OS Backend"
  app_version: str = os.getenv("APP_VERSION", "0.0.1")

  supabase_jwt_secret: str
  supabase_jwt_audience: str
  supabase_issuer: str

  supabase_url: str | None
  supabase_service_role: str | None

  allowed_origins: List[str]
  usage_logging_enabled: bool

  def __init__(self) -> None:
    self.supabase_jwt_secret = os.getenv("SUPABASE_JWT_SECRET", "")
    self.supabase_jwt_audience = os.getenv("SUPABASE_JWT_AUDIENCE", "authenticated")
    # default issuer matches current Supabase project; override via env if needed
    default_issuer = os.getenv(
        "SUPABASE_ISSUER",
        "https://iqkmygvncovwdxagewal.supabase.co/auth/v1",
    )
    self.supabase_issuer = default_issuer

    self.supabase_url = os.getenv("SUPABASE_URL")
    self.supabase_service_role = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv(
        "SUPABASE_SERVICE_ROLE"
    )

    default_allowed = [
        "https://tools.ecomlabs.ca",
        "http://localhost:3000",
    ]
    allowed = os.getenv("BACKEND_ALLOWED_ORIGINS")
    if allowed:
      self.allowed_origins = [origin.strip() for origin in allowed.split(",") if origin.strip()]
    else:
      self.allowed_origins = default_allowed

    self.usage_logging_enabled = os.getenv("ENABLE_USAGE_LOGGING", "0") == "1"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
  return Settings()


settings = get_settings()
