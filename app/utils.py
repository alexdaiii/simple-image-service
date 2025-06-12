import logging
from functools import lru_cache

from pydantic import computed_field, FilePath, NewPath
from pydantic_settings import BaseSettings

from app.logging import LogLevels

log = logging.getLogger(__name__)


class Settings(BaseSettings):
    # cors
    allowed_origins: str | None = None
    """A comma-separated list of allowed origins for CORS. No spaces allowed."""
    allowed_origins_regex: str | None = None

    @computed_field
    @property
    def allowed_origins_list(self) -> list[str]:
        """Parse the allowed origins into a list."""
        if not self.allowed_origins:
            return []

        return [origin.strip() for origin in self.allowed_origins.split(",")]

    # AWS S3 settings
    aws_s3_bucket: str
    aws_profile_name: str | None = None

    # clouflare settings
    auth_exclude_paths: set[str] = {"/favicon.ico", "/health"}
    policy_aud: str
    team_domain: str
    pyjwk_cache_lifespan: int = 14400  # default in Cloudflare
    allowlist_file: FilePath = "/config/post_allowlist.json"
    """A json file with a list of allowed emails for Cloudflare Zero Trust Access."""

    host: str = "http://localhost:8000"

    max_file_size: int = 5 * 1024 * 1024  # Default to 5 MB
    allowed_formats: set[str] = {"avif", "jpeg", "png", "webp", "jpg", "gif"}

    log_level: LogLevels = LogLevels.error

    db_file: FilePath | NewPath = "/data/images.sqlite"

    @computed_field
    @property
    def sqlite_db(self) -> str:
        """Construct the SQLite database URL."""
        return f"sqlite+aiosqlite:///{self.db_file}"

    @computed_field
    @property
    def certs_utl(self) -> str:
        """Construct the URL for the certificates."""
        return f"https://{self.team_domain}/cdn-cgi/access/certs"


@lru_cache
def get_settings() -> Settings:
    """Get application settings from environment variables."""
    return Settings()


