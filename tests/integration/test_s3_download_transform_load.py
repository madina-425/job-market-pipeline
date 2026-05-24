"""
pipelines/test_s3_download_transform_load.py
Test pipeline: download raw data from S3 → transform → load to S3/processed and RDS
Usage: python -m pipelines.test_s3_download_transform_load
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone

from configs import settings
from src.loaders.rds_loader import RDSLoader
from src.loaders.s3_loader import S3Loader
from src.transformers.job_transformer import JobTransformer
from src.utils.logger import get_logger

log = get_logger("test_s3_download_transform_load")


def main():
    start = time.time()
    log.info("=" * 60)
    log.info("Test Pipeline: S3 Download → Transform → Load")

    # ── Setup ──────────────────────────────────────────────────────────────────
    aws_cfg = settings.load_aws()
    s3 = S3Loader(bucket=aws_cfg.s3_bucket, region=aws_cfg.region)
    rds = RDSLoader()
    transformer = JobTransformer()

    # ── Health checks ──────────────────────────────────────────────────────────
    if not rds.health_check():
        log.error("✗ RDS health check failed — aborting")
        sys.exit(1)
    log.info("✓ RDS health check passed")

    # ── Download raw data from S3 ──────────────────────────────────────────────
    log.info("Stage: DOWNLOAD")
    all_raw: list[dict] = []

    sources = ["headhunter", "telegram"]  # Add more as collectors are implemented
    for source in sources:
        try:
            raw = s3.download_raw(source)
            if raw:
                log.info("  [%s] downloaded %d records", source, len(raw))
                all_raw.extend(raw)
            else:
                log.warning("  [%s] no data found in S3", source)
        except Exception as exc:
            log.error("  [%s] download failed: %s", source, exc)

    log.info("Download complete: %d total raw records", len(all_raw))

    if not all_raw:
        log.warning("✗ No raw data downloaded — pipeline stopping")
        sys.exit(0)

    # ── Transform ──────────────────────────────────────────────────────────────
    log.info("Stage: TRANSFORM")
    try:
        clean_df = transformer.transform(all_raw)
        log.info("✓ Transform complete: %d clean records", len(clean_df))
    except Exception as exc:
        log.error("✗ Transform failed: %s", exc)
        sys.exit(1)

    if clean_df.empty:
        log.warning("✗ Transform produced no records — pipeline stopping")
        sys.exit(0)

    # ── Save processed to S3 ──────────────────────────────────────────────────
    log.info("Stage: SAVE PROCESSED")
    try:
        s3_key = s3.save_processed(clean_df)
        if s3_key:
            log.info("✓ S3: saved processed data to %s", s3_key)
        else:
            log.error("✗ S3: failed to save processed data")
            sys.exit(1)
    except Exception as exc:
        log.error("✗ S3 save failed: %s", exc)
        sys.exit(1)

    # ── Load to RDS ────────────────────────────────────────────────────────────
    log.info("Stage: LOAD TO RDS")
    try:
        inserted = rds.upsert_jobs(clean_df)
        log.info("✓ RDS: inserted %d new jobs", inserted)
    except Exception as exc:
        log.error("✗ RDS load failed: %s", exc)
        sys.exit(1)

    elapsed = round(time.time() - start, 1)
    log.info("=" * 60)
    log.info("✓ Pipeline completed successfully in %ss", elapsed)
    log.info("=" * 60)


if __name__ == "__main__":
    main()
