# Pipeline first-run guide

This repository now has a runnable ETL entrypoint at:

- `/home/runner/work/pipeline/pipeline/src/pipelines/etl_pipeline.py`

It follows this exact order:

1. collect raw jobs
2. save raw to S3 immediately
3. transform raw jobs
4. save processed clean backup
5. upsert clean rows into DB (new rows only)

## First run (copy/paste)

```bash
cd /home/runner/work/pipeline/pipeline
python -m src.pipelines.etl_pipeline
```

## What happens on first run

- Collector: `HHCollector` pulls jobs from HeadHunter.
- Raw backup: saved immediately under `local_s3/raw/...` (JSON).
- Transform: basic normalize + deduplicate by `external_id`.
- Processed backup: saved under `local_s3/processed/.../jobs_clean.json`.
- DB upsert: in-memory adapter inserts only unseen `external_id` values.

## What to change for production (S3 + PostgreSQL)

Edit `/home/runner/work/pipeline/pipeline/src/pipelines/etl_pipeline.py` in `main()` and replace:

- `JsonFileS3Adapter()` with your real S3 client (`save_raw`, `save_processed` to parquet)
- `InMemoryRDSAdapter()` with your PostgreSQL client (`upsert_jobs`)
- `SimpleTransformer()` with your full transformer if needed

You do **not** need to change `run_pipeline(...)` order.
