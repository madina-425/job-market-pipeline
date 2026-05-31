"""
pipelines/test_collect_and_upload_telegram.py
Simple test pipeline: collect from Telegram → upload raw data to S3
Usage: python -m pipelines.test_collect_and_upload_telegram
"""
from __future__ import annotations

from configs import settings
from src.collectors.telegram_collector import TelegramCollector
from src.loaders.s3_loader import S3Loader
from src.utils.logger import get_logger

log = get_logger("collect_and_upload_telegram")


def main():
    log.info("=" * 60)
    log.info("Starting: Collect & Upload Telegram to S3")

    # ── Setup ──────────────────────────────────────────────────────────────────
    aws_cfg = settings.load_aws()
    s3 = S3Loader(bucket=aws_cfg.s3_bucket, region=aws_cfg.region)

    # ── Collect from Telegram ──────────────────────────────────────────────────
    log.info("Collecting from Telegram...")
    try:
        tg = TelegramCollector()
        tg_jobs = tg.collect()
        log.info(f"✓ Telegram: collected {len(tg_jobs)} jobs")

        # Upload to S3
        key = s3.save_raw(tg_jobs, source="telegram")
        if key:
            log.info(f"✓ S3: uploaded to {key}")
        else:
            log.error("✗ Failed to upload Telegram data to S3")
    except Exception as exc:
        log.error(f"✗ Telegram collection failed: {exc}")

    log.info("=" * 60)
    log.info("Done!")


if __name__ == "__main__":
    main()
