"""
pipelines/etl_pipeline.py
Orchestrates the full Extract → Transform → Load pipeline.
Run directly:  python -m pipelines.etl_pipeline
Or via GitHub Actions (see .github/workflows/pipeline.yml).
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone

from configs import settings
from src.collectors.hh_collector import HHCollector
from src.collectors.telegram_collector import TelegramCollector
from src.loaders.rds_loader import RDSLoader
from src.loaders.s3_loader import S3Loader
from src.transformers.job_transformer import JobTransformer
from src.utils.logger import get_logger

log = get_logger("etl_pipeline")


def run():
    start = time.time()
    run_ts = datetime.now(timezone.utc).isoformat()
    log.info("=" * 60)
    log.info("Pipeline run started at %s", run_ts)

    # ── Load config ───────────────────────────────────────────────────────────
    aws_cfg = settings.load_aws()

    # ── Initialise services ───────────────────────────────────────────────────
    s3 = S3Loader(bucket=aws_cfg.s3_bucket, region=aws_cfg.region)
    rds = RDSLoader()
    transformer = JobTransformer()

    if not rds.health_check():
        log.error("RDS health check failed — aborting pipeline")
        sys.exit(1)

    # ── EXTRACT ───────────────────────────────────────────────────────────────
    log.info("Stage: EXTRACT")
    all_raw: list[dict] = []

    collectors = [
        ("headhunter", HHCollector()),
        ("telegram", TelegramCollector()),
    ]

    for source_name, collector in collectors:
        try:
            raw = collector.collect()
            log.info("  [%s] collected %d raw records", source_name, len(raw))
            s3.save_raw(raw, source=source_name)   # persist raw immediately
            all_raw.extend(raw)
        except Exception as exc:
            log.error("  [%s] collection failed: %s", source_name, exc)

    log.info("Extract complete: %d total raw records", len(all_raw))

    if not all_raw:
        log.warning("No records collected — pipeline stopping early")
        sys.exit(0)

    # ── TRANSFORM ─────────────────────────────────────────────────────────────
    log.info("Stage: TRANSFORM")
    clean_df = transformer.transform(all_raw)
    log.info("Transform complete: %d clean records", len(clean_df))

    # Save processed parquet to S3
    s3.save_processed(clean_df)

    # ── LOAD ──────────────────────────────────────────────────────────────────
    log.info("Stage: LOAD")
    inserted = rds.upsert_jobs(clean_df)
    log.info("Load complete: %d new jobs inserted", inserted)

    elapsed = round(time.time() - start, 1)
    log.info("Pipeline finished in %ss", elapsed)
    log.info("=" * 60)


if __name__ == "__main__":
    run()
