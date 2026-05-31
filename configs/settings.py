"""
configs/settings.py
All configuration is read from environment variables (set in .env).
"""
import os
from dataclasses import dataclass

from sqlalchemy.engine import URL


class MissingEnvironmentVariableError(Exception):
    """Raised when a required environment variable is missing."""
    pass


def get_required_env(var_name: str) -> str:
    """Get required environment variable with clear error message."""
    value = os.environ.get(var_name)
    if value is None or not value.strip():
        raise MissingEnvironmentVariableError(
            f"Required environment variable '{var_name}' is not set or empty. "
            f"Please check your .env file or GitHub Secrets."
        )
    return value.strip()


@dataclass(frozen=True)
class AWSConfig:
    access_key_id: str
    secret_access_key: str
    region: str
    s3_bucket: str


@dataclass(frozen=True)
class DBConfig:
    host: str
    port: int
    name: str
    user: str
    password: str
    sslmode: str | None = None

    @property
    def url(self) -> str:
        return URL.create(
            drivername="postgresql+psycopg2",
            username=self.user,
            password=self.password,
            host=self.host,
            port=self.port,
            database=self.name,
        ).render_as_string(hide_password=False)


@dataclass(frozen=True)
class PipelineConfig:
    log_level: str
    env: str
    exchange_rate_api_key: str
    hh_api_base: str
    hh_user_agent: str


def load_aws() -> AWSConfig:
    return AWSConfig(
        access_key_id=get_required_env("AWS_ACCESS_KEY_ID"),
        secret_access_key=get_required_env("AWS_SECRET_ACCESS_KEY"),
        region=os.environ.get("AWS_REGION"),
        s3_bucket=get_required_env("S3_BUCKET_NAME"),
    )


def load_db() -> DBConfig:
    db_name = os.environ.get("DB_NAME", "jobmarket")
    if not db_name.strip():
        raise MissingEnvironmentVariableError(
            "Required environment variable 'DB_NAME' is not set or empty."
        )
    sslmode = os.environ.get("DB_SSLMODE")
    return DBConfig(
        host=get_required_env("DB_HOST"),
        port=int(os.environ.get("DB_PORT", 5432)),
        name=db_name.strip(),
        user=get_required_env("DB_USER"),
        password=get_required_env("DB_PASSWORD"),
        sslmode=sslmode.strip() if sslmode and sslmode.strip() else None,
    )


def load_pipeline() -> PipelineConfig:
    return PipelineConfig(
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
        env=os.environ.get("PIPELINE_ENV", "development"),
        exchange_rate_api_key=os.environ.get("EXCHANGE_RATE_API_KEY", ""),
        hh_api_base=os.environ.get("HH_API_BASE_URL", "https://api.hh.ru"),
        hh_user_agent=os.environ.get(
            "HH_USER_AGENT", "JobMarketPipeline/1.0"
        ),
    )
