from pydantic_settings import BaseSettings, SettingsConfigDict


class OAuthSettings(BaseSettings):
    server_domain: str          # e.g. "https://ragmcp.coyoteworld.net"
    google_client_id: str
    allowed_email_domain: str = "pragmaframe.ca"
    jwks_cache_ttl: int = 300

    model_config = SettingsConfigDict(
        env_prefix="OAUTH_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )
