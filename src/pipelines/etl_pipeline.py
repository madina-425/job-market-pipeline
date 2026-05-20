"""
src/pipelines/etl_pipeline.py

Pipeline order:
1) collect raw jobs
2) save raw to S3 (or S3-like adapter) immediately
3) transform raw data
4) save processed clean data
5) upsert clean rows into PostgreSQL (or RDS-like adapter)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from src.utils.logger import get_logger

log = get_logger(__name__)


class Collector(Protocol):
    def collect(self) -> list[dict[str, Any]]:
        """Return raw jobs."""


class Transformer(Protocol):
    def transform(self, raw_jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Return clean jobs."""


class S3Storage(Protocol):
    def save_raw(self, raw_jobs: list[dict[str, Any]], source: str) -> None:
        """Persist raw jobs immediately after collection."""

    def save_processed(self, clean_jobs: list[dict[str, Any]]) -> None:
        """Persist clean jobs backup."""


class RDSStorage(Protocol):
    def upsert_jobs(self, clean_jobs: list[dict[str, Any]]) -> None:
        """Insert only new jobs and skip duplicates."""


def run_pipeline(
    collector: Collector,
    transformer: Transformer,
    s3: S3Storage,
    rds: RDSStorage,
    source: str,
) -> list[dict[str, Any]]:
    """Run ETL in the required order."""
    # 1. COLLECT
    raw_jobs = collector.collect()

    # 2. RAW -> S3 (immediately)
    s3.save_raw(raw_jobs, source=source)

    # 3. TRANSFORM
    clean_jobs = transformer.transform(raw_jobs)

    # 4. CLEAN -> S3
    s3.save_processed(clean_jobs)

    # 5. CLEAN -> PostgreSQL
    rds.upsert_jobs(clean_jobs)

    return clean_jobs


class SimpleTransformer:
    """Minimal transformer: normalize key fields and deduplicate by external_id."""

    def transform(self, raw_jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        clean: list[dict[str, Any]] = []
        for row in raw_jobs:
            external_id = str(row.get("external_id") or "").strip()
            if not external_id or external_id in seen:
                continue
            seen.add(external_id)
            clean.append(
                {
                    "external_id": external_id,
                    "source": row.get("source"),
                    "title": row.get("title"),
                    "company": row.get("company"),
                    "location": row.get("location"),
                    "salary_from": row.get("salary_from"),
                    "salary_to": row.get("salary_to"),
                    "salary_currency": row.get("salary_currency"),
                    "remote_type": row.get("remote_type"),
                    "seniority": row.get("seniority"),
                    "skills": row.get("skills") or [],
                    "description": row.get("description") or "",
                    "url": row.get("url"),
                    "published_at": row.get("published_at"),
                    "collected_at": row.get("collected_at"),
                }
            )
        return clean


@dataclass
class JsonFileS3Adapter:
    """
    Local S3-like adapter for first run.
    Stores JSON files in separate raw/ and processed/ folder hierarchies by date.
    """

    base_dir: Path = Path("local_s3")

    def save_raw(self, raw_jobs: list[dict[str, Any]], source: str) -> None:
        now = datetime.now(timezone.utc)
        raw_dir = self.base_dir / "raw" / source / now.strftime("%Y/%m/%d")
        raw_dir.mkdir(parents=True, exist_ok=True)
        raw_file = raw_dir / f"jobs_{now.strftime('%H-%M-%S-%f')}.json"
        raw_file.write_text(json.dumps(raw_jobs, ensure_ascii=False, indent=2), encoding="utf-8")
        log.info("Saved raw data to %s", raw_file)

    def save_processed(self, clean_jobs: list[dict[str, Any]]) -> None:
        now = datetime.now(timezone.utc)
        processed_dir = self.base_dir / "processed" / now.strftime("%Y/%m/%d")
        processed_dir.mkdir(parents=True, exist_ok=True)
        processed_file = processed_dir / "jobs_clean.json"
        processed_file.write_text(
            json.dumps(clean_jobs, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        log.info("Saved processed data to %s", processed_file)


@dataclass
class InMemoryRDSAdapter:
    """Local RDS-like adapter for first run. Keeps only new jobs."""

    seen_ids: set[str] = field(default_factory=set)
    rows: list[dict[str, Any]] = field(default_factory=list)

    def upsert_jobs(self, clean_jobs: list[dict[str, Any]]) -> None:
        inserted = 0
        for row in clean_jobs:
            external_id = str(row.get("external_id") or "").strip()
            if not external_id or external_id in self.seen_ids:
                continue
            self.seen_ids.add(external_id)
            self.rows.append(row)
            inserted += 1
        log.info("Upsert complete: inserted=%d skipped=%d", inserted, len(clean_jobs) - inserted)


def main() -> None:
    """
    First-run local command:
    python -m src.pipelines.etl_pipeline

    This uses:
      - HeadHunter collector
      - local S3-like JSON backup (local_s3/)
      - in-memory RDS-like upsert
    Replace adapters with real S3/PostgreSQL clients for production.
    """
    from src.collectors.hh_collector import HHCollector

    collector = HHCollector()
    transformer = SimpleTransformer()
    s3 = JsonFileS3Adapter()
    rds = InMemoryRDSAdapter()

    clean_jobs = run_pipeline(
        collector=collector,
        transformer=transformer,
        s3=s3,
        rds=rds,
        source="headhunter",
    )
    log.info("Pipeline finished with %d clean jobs", len(clean_jobs))


if __name__ == "__main__":
    main()
