"""
scripts/verify_data.py
Check that RDS and S3 contain pipeline data (run after ETL or from laptop).

  python -m scripts.verify_data
"""
from __future__ import annotations

import sys

from configs import settings
from src.loaders.rds_loader import RDSLoader
from src.loaders.s3_loader import S3Loader
from src.utils.logger import get_logger

log = get_logger("verify_data")


def main() -> int:
    print("=" * 60)
    print("Pipeline storage verification")
    print("=" * 60)

    rds = RDSLoader()
    if not rds.health_check():
        print("RDS: FAIL — cannot connect (check DB_HOST, security group, credentials)")
        return 1
    print("RDS: OK — connected")

    stats = rds.load_for_analytics(
        """
        SELECT
            COUNT(*) AS total_jobs,
            COUNT(*) FILTER (WHERE collected_at >= NOW() - INTERVAL '7 days') AS jobs_last_7d,
            MAX(collected_at) AS last_collected_at
        FROM jobs
        """
    )
    if stats.empty:
        print("RDS: no stats (empty result)")
    else:
        row = stats.iloc[0]
        print(f"RDS jobs.total_jobs       = {row['total_jobs']}")
        print(f"RDS jobs.last_7_days      = {row['jobs_last_7d']}")
        print(f"RDS jobs.last_collected_at = {row['last_collected_at']}")

    sample = rds.load_for_analytics(
        """
        SELECT source, title, company, role_category, collected_at
        FROM jobs
        ORDER BY collected_at DESC NULLS LAST
        LIMIT 5
        """
    )
    if sample.empty:
        print("RDS: no rows in jobs table yet — run the ETL pipeline first")
    else:
        print("\nRDS sample (latest 5):")
        print(sample.to_string(index=False))

    try:
        aws = settings.load_aws()
    except Exception as exc:
        print(f"\nS3: skipped — {exc}")
        return 0 if not stats.empty and stats.iloc[0]["total_jobs"] else 1

    s3 = S3Loader(bucket=aws.s3_bucket, region=aws.region or "eu-west-1")
    print(f"\nS3 bucket: {aws.s3_bucket}")
    for prefix in ("raw", "processed", "reports", "logs"):
        keys = s3.list_recent(prefix, max_keys=5)
        if keys:
            print(f"  {prefix}/ (latest):")
            for k in keys:
                print(f"    - s3://{aws.s3_bucket}/{k}")
        else:
            print(f"  {prefix}/ — no objects yet")

    total = int(stats.iloc[0]["total_jobs"]) if not stats.empty else 0
    if total == 0:
        print("\nResult: RDS is empty — run: python -m pipelines.etl_pipeline")
        return 1
    print("\nResult: data present — ready for dashboards (connect to RDS table `jobs`)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
