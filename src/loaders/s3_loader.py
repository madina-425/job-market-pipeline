"""
src/loaders/s3_loader.py
Uploads raw and processed job data to AWS S3.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from io import BytesIO

import boto3
import pandas as pd
from botocore.exceptions import BotoCoreError, ClientError

from src.utils.logger import get_logger

log = get_logger(__name__)


class S3Loader:
    def __init__(self, bucket: str, region: str = "eu-west-1"):
        self.bucket = bucket
        self.client = boto3.client("s3", region_name=region)

    # ── Write ─────────────────────────────────────────────────────────────────

    def save_raw(self, jobs: list[dict], source: str) -> str | None:
        """Upload raw job list as JSON. Returns S3 key or None on failure."""
        now = self._utc_now()
        key = self._build_dated_key(
            f"raw/{source}",
            f"jobs_{now.strftime('%H-%M-%S')}.json",
            now,
        )
        payload = json.dumps(jobs, ensure_ascii=False, default=str).encode("utf-8")
        return self._upload(payload, key, "application/json")

    def save_processed(self, df: pd.DataFrame) -> str | None:
        """Upload cleaned DataFrame as Parquet."""
        now = self._utc_now()
        key = self._build_dated_key("processed", "jobs_clean.parquet", now)
        buf = BytesIO()
        df.to_parquet(buf, index=False, engine="pyarrow")
        return self._upload(buf.getvalue(), key, "application/octet-stream")

    def save_report(self, report: dict) -> str | None:
        """Upload a daily analytics report as JSON."""
        now = self._utc_now()
        key = f"reports/{now.strftime('%Y-%m-%d')}/summary.json"
        payload = json.dumps(report, ensure_ascii=False, default=str).encode("utf-8")
        return self._upload(payload, key, "application/json")

    # ── Private ───────────────────────────────────────────────────────────────

    def _upload(self, data: bytes, key: str, content_type: str) -> str | None:
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
                ServerSideEncryption="AES256",
            )
            log.info("S3: uploaded s3://%s/%s (%d bytes)", self.bucket, key, len(data))
            return key
        except (BotoCoreError, ClientError) as exc:
            log.error("S3 upload failed for key %s: %s", key, exc)
            return None

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _build_dated_key(prefix: str, filename: str, now: datetime) -> str:
        return (
            f"{prefix}/"
            f"{now.year}/{now.month:02d}/{now.day:02d}/"
            f"{filename}"
        )
