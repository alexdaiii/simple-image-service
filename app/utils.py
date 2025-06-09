import logging
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError

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


@lru_cache
def s3_client() -> Any:
    """Get the S3 client."""
    if get_settings().aws_profile_name:
        log.debug(f"Creating S3 client with profile: {get_settings().aws_profile_name}")
        session = boto3.Session(profile_name=get_settings().aws_profile_name)
    else:
        log.debug("Creating S3 client with default profile")
        session = boto3.Session()
    return session.client(
        "s3",
    )


def upload_file_bytes(
    file_bytes: bytes, bucket: str, object_name: str, content_type: str = None
) -> bool:
    """
    Upload a file as bytes to an S3 bucket.

    :param file_bytes: bytes to upload
    :param bucket: S3 bucket
    :param object_name: S3 key (path)
    :param content_type: MIME type (optional)
    :return: True if uploaded successfully, False otherwise
    """
    extra_args = {}
    if content_type:
        extra_args["ContentType"] = content_type
    try:
        s3_client().upload_fileobj(
            BytesIO(file_bytes), bucket, object_name, ExtraArgs=extra_args
        )
    except ClientError as e:
        log.error(e)
        return False
    log.debug(f"Uploaded {object_name} to bucket {bucket}")
    return True


def get_file_bytes(bucket: str, object_name: str) -> bytes:
    """
    Download a file from S3 and return its bytes.

    :param bucket: S3 bucket
    :param object_name: S3 key (path)
    :return: file bytes
    :raises: Exception if file does not exist or can't be downloaded
    """
    try:
        file_stream = BytesIO()
        s3_client().download_fileobj(bucket, object_name, file_stream)
        file_stream.seek(0)
        return file_stream.read()
    except ClientError as e:
        log.error(e)
        raise FileNotFoundError(
            f"Could not fetch {object_name} from bucket {bucket}: {e}"
        )
