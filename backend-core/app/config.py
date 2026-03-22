import os
from urllib.parse import urlparse
from functools import lru_cache
from typing import List


class Settings:
  """Centralized configuration pulled from environment variables."""

  app_name: str = "Agency OS Backend"
  app_version: str = os.getenv("APP_VERSION", "0.0.1")

  supabase_jwt_secret: str
  supabase_jwt_audience: str
  supabase_issuer: str
  supabase_jwks_url: str
  supabase_jwks_cache_ttl_seconds: int

  supabase_url: str | None
  supabase_service_role: str | None

  allowed_origins: List[str]
  usage_logging_enabled: bool
  mcp_pilot_allowed_user_id: str | None
  mcp_pilot_allowed_email: str | None
  mcp_public_base_url: str
  mcp_allowed_hosts: List[str]
  mcp_allowed_origins: List[str]

  def __init__(self) -> None:
    self.supabase_jwt_secret = os.getenv("SUPABASE_JWT_SECRET", "")
    self.supabase_jwt_audience = os.getenv("SUPABASE_JWT_AUDIENCE", "authenticated")
    # default issuer matches current Supabase project; override via env if needed
    default_issuer = os.getenv(
        "SUPABASE_ISSUER",
        "https://iqkmygvncovwdxagewal.supabase.co/auth/v1",
    )
    self.supabase_issuer = default_issuer
    self.supabase_jwks_url = os.getenv(
      "SUPABASE_JWKS_URL",
      f"{self.supabase_issuer.rstrip('/')}/.well-known/jwks.json",
    )
    try:
      self.supabase_jwks_cache_ttl_seconds = int(
        os.getenv("SUPABASE_JWKS_CACHE_TTL_SECONDS", "300")
      )
    except ValueError:
      self.supabase_jwks_cache_ttl_seconds = 300

    self.supabase_url = os.getenv("SUPABASE_URL")
    self.supabase_service_role = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv(
        "SUPABASE_SERVICE_ROLE"
    )

    default_allowed = [
        "https://tools.ecomlabs.ca",
        "http://localhost:3000",
    ]
    allowed = os.getenv("BACKEND_ALLOWED_ORIGINS")
    extra = [origin.strip() for origin in allowed.split(",") if origin.strip()] if allowed else []
    # Always include defaults to avoid CORS regressions even if env is set
    dedup = []
    for origin in default_allowed + extra:
      if origin not in dedup:
        dedup.append(origin)
    self.allowed_origins = dedup

    self.usage_logging_enabled = os.getenv("ENABLE_USAGE_LOGGING", "0") == "1"
    self.mcp_pilot_allowed_user_id = os.getenv("MCP_PILOT_ALLOWED_USER_ID") or None
    self.mcp_pilot_allowed_email = os.getenv("MCP_PILOT_ALLOWED_EMAIL") or None
    self.mcp_public_base_url = os.getenv("MCP_PUBLIC_BASE_URL", "http://localhost:8000/mcp").rstrip("/")

    parsed_mcp_url = urlparse(self.mcp_public_base_url)
    host = parsed_mcp_url.netloc
    origin = f"{parsed_mcp_url.scheme}://{parsed_mcp_url.netloc}" if parsed_mcp_url.scheme and parsed_mcp_url.netloc else ""

    default_mcp_hosts = ["testserver", "localhost", "localhost:*", "127.0.0.1", "127.0.0.1:*"]
    if host:
      default_mcp_hosts.extend([host, f"{parsed_mcp_url.hostname}:*" if parsed_mcp_url.hostname else host])
    explicit_mcp_hosts = os.getenv("MCP_ALLOWED_HOSTS")
    self.mcp_allowed_hosts = _dedupe_csv_values(default_mcp_hosts, explicit_mcp_hosts)

    default_mcp_origins = [
      "https://claude.ai",
      "https://claude.com",
      "http://localhost:3000",
      "http://127.0.0.1:3000",
    ]
    if origin:
      default_mcp_origins.append(origin)
    explicit_mcp_origins = os.getenv("MCP_ALLOWED_ORIGINS")
    self.mcp_allowed_origins = _dedupe_csv_values(default_mcp_origins, explicit_mcp_origins)

    # The parent FastAPI app serves the RFC 9728 protected-resource metadata
    # endpoint, so its CORS policy must also admit the MCP browser origins.
    for origin in self.mcp_allowed_origins:
      if origin not in self.allowed_origins:
        self.allowed_origins.append(origin)


def _dedupe_csv_values(defaults: List[str], raw_csv: str | None) -> List[str]:
  extra = [value.strip() for value in raw_csv.split(",") if value.strip()] if raw_csv else []
  dedup = []
  for value in defaults + extra:
    if value and value not in dedup:
      dedup.append(value)
  return dedup


@lru_cache(maxsize=1)
def get_settings() -> Settings:
  return Settings()


settings = get_settings()
