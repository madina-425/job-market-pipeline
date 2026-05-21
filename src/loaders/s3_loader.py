"""
src/loaders/s3_loader.py
Saves raw (pre-transform) job data as JSON to AWS S3.

S3 folder structure:
  s3://{bucket}/
    raw/
      {source}/
        {YYYY}/{MM}/{DD}/
          jobs_{HH-MM-SS}.json
    processed/
      {YYYY}/{MM}/{DD}/
        jobs_clean.parquet
    reports/
      {YYYY-MM-DD}/
        summary.json
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from io import BytesIO

import boto3
import pandas as pd
from botocore.exceptions import BotoCoreError, ClientError

from dotenv import load_dotenv
load_dotenv()

from src.utils.logger import get_logger

log = get_logger(__name__)


class S3Loader:
    def __init__(self, bucket: str, region: str = "eu-west-1"):
        self.bucket = bucket
        self.client = boto3.client("s3", region_name=region)

    # ── Public interface ──────────────────────────────────────────────────────

    def save_raw(self, jobs: list[dict], source: str) -> str | None:
        """Upload raw job list as JSON. Returns S3 key or None on failure."""
        now = datetime.now(timezone.utc)
        key = (
            f"raw/{source}/"
            f"{now.year}/{now.month:02d}/{now.day:02d}/"
            f"jobs_{now.strftime('%H-%M-%S')}.json"
        )
        payload = json.dumps(jobs, ensure_ascii=False, default=str).encode("utf-8")
        return self._upload(payload, key, "application/json")

    def save_processed(self, df: pd.DataFrame) -> str | None:
        """Upload cleaned DataFrame as Parquet."""
        now = datetime.now(timezone.utc)
        key = (
            f"processed/"
            f"{now.year}/{now.month:02d}/{now.day:02d}/"
            f"jobs_clean.parquet"
        )
        buf = BytesIO()
        df.to_parquet(buf, index=False, engine="pyarrow")
        return self._upload(buf.getvalue(), key, "application/octet-stream")

    def save_report(self, report: dict) -> str | None:
        """Upload a daily analytics report as JSON."""
        now = datetime.now(timezone.utc)
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
                ServerSideEncryption="AES256",   # encrypt at rest
            )
            log.info("S3: uploaded s3://%s/%s (%d bytes)", self.bucket, key, len(data))
            return key
        except (BotoCoreError, ClientError) as exc:
            log.error("S3 upload failed for key %s: %s", key, exc)
            return None

    """Upload data to S3 bucket."""
    def upload_df(self, df: pd.DataFrame, prefix: str = "raw-jobs") -> str:
        """Upload DataFrame as CSV to S3. Returns S3 path."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        s3_key = f"{prefix}/{timestamp}_jobs.csv"
        
        csv_buffer = df.to_csv(index=False)
        self.s3_client.put_object(
            Bucket=self.bucket,
            Key=s3_key,
            Body=csv_buffer,
            ContentType="text/csv",
        )
        
        return f"s3://{self.bucket}/{s3_key}"
    
    def download_df(self, s3_path: str) -> pd.DataFrame:
        """Download CSV from S3 into DataFrame."""
        parts = s3_path.replace("s3://", "").split("/", 1)
        bucket, key = parts[0], parts[1]
        
        obj = self.s3_client.get_object(Bucket=bucket, Key=key)
        return pd.read_csv(obj["Body"])
