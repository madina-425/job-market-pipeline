"""
pipelines/test_collect_and_upload.py
Simple test pipeline: collect from sources → upload raw data to S3
Usage: python -m pipelines.test_collect_and_upload
"""
from __future__ import annotations

from configs import settings
from src.collectors.hh_collector import HHCollector
from src.loaders.s3_loader import S3Loader
from src.utils.logger import get_logger

log = get_logger("collect_and_upload")


def main():
    log.info("=" * 60)
    log.info("Starting: Collect & Upload to S3")

    # ── Setup ──────────────────────────────────────────────────────────────────
    aws_cfg = settings.load_aws()
    s3 = S3Loader(bucket=aws_cfg.s3_bucket, region=aws_cfg.region)

    # ── Collect from HH ────────────────────────────────────────────────────────
    log.info("Collecting from HeadHunter...")
    try:
        hh = HHCollector()
        hh_jobs = hh.collect()
        log.info(f"✓ HH: collected {len(hh_jobs)} jobs")

        # Upload to S3
        key = s3.save_raw(hh_jobs, source="headhunter")
        if key:
            log.info(f"✓ S3: uploaded to {key}")
        else:
            log.error("✗ Failed to upload HH data to S3")
    except Exception as exc:
        log.error(f"✗ HH collection failed: {exc}")

    log.info("=" * 60)
    log.info("Done!")


if __name__ == "__main__":
    main()
