"""
src/loaders/s3_loader.py
Uploads raw and processed job data to AWS S3.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

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

    def upload_log_file(self, path: str | Path, run_ts: datetime | None = None) -> str | None:
        """Upload pipeline log file to S3 (dated prefix)."""
        log_path = Path(path)
        if not log_path.is_file():
            log.warning("S3: log file not found: %s", log_path)
            return None
        now = run_ts or self._utc_now()
        key = (
            f"logs/{now.year}/{now.month:02d}/{now.day:02d}/"
            f"pipeline_{now.strftime('%H-%M-%S')}.log"
        )
        return self._upload(log_path.read_bytes(), key, "text/plain; charset=utf-8")

    def list_recent(self, prefix: str, max_keys: int = 10) -> list[str]:
        """Return the most recent object keys under a prefix (for verification)."""
        try:
            resp = self.client.list_objects_v2(
                Bucket=self.bucket,
                Prefix=prefix.rstrip("/") + "/",
                MaxKeys=1000,
            )
        except (BotoCoreError, ClientError) as exc:
            log.error("S3 list failed for prefix %s: %s", prefix, exc)
            return []
        contents = resp.get("Contents") or []
        epoch = datetime.min.replace(tzinfo=timezone.utc)
        contents.sort(key=lambda o: o.get("LastModified") or epoch, reverse=True)
        return [obj["Key"] for obj in contents[:max_keys]]

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
