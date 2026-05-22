"""
configs/settings.py
All configuration is read from environment variables (set in .env or Docker).
Never hardcode secrets — this file only reads, never stores.
"""
import os
from dataclasses import dataclass


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

    @property
    def url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.name}"
        )


@dataclass(frozen=True)
class PipelineConfig:
    log_level: str
    env: str
    exchange_rate_api_key: str
    hh_api_base: str
    hh_user_agent: str


def load_aws() -> AWSConfig:
    return AWSConfig(
        access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        region=os.environ.get("AWS_REGION", "eu-west-1"),
        s3_bucket=os.environ["S3_BUCKET_NAME"],
    )


def load_db() -> DBConfig:
    return DBConfig(
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", 5432)),
        name=os.environ.get("DB_NAME", "jobmarket"),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
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
