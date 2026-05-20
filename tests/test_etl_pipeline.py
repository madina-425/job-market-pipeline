from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.pipelines.etl_pipeline import (
    InMemoryRDSAdapter,
    JsonFileS3Adapter,
    run_pipeline,
)


class _Collector:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def collect(self):
        self.events.append("collect")
        return [{"external_id": "1"}, {"external_id": "1"}, {"external_id": "2"}]


class _Transformer:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def transform(self, raw_jobs):
        self.events.append("transform")
        return [{"external_id": "1"}, {"external_id": "2"}]


class _S3:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def save_raw(self, raw_jobs, source):
        self.events.append("save_raw")

    def save_processed(self, clean_jobs):
        self.events.append("save_processed")


class _RDS:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def upsert_jobs(self, clean_jobs):
        self.events.append("upsert")


class TestPipelineOrder(unittest.TestCase):
    def test_pipeline_runs_in_required_order(self):
        events: list[str] = []
        clean = run_pipeline(
            collector=_Collector(events),
            transformer=_Transformer(events),
            s3=_S3(events),
            rds=_RDS(events),
            source="headhunter",
        )
        self.assertEqual(["collect", "save_raw", "transform", "save_processed", "upsert"], events)
        self.assertEqual([{"external_id": "1"}, {"external_id": "2"}], clean)


class TestAdapters(unittest.TestCase):
    def test_in_memory_rds_skips_duplicates(self):
        rds = InMemoryRDSAdapter()
        rds.upsert_jobs([{"external_id": "1"}, {"external_id": "1"}, {"external_id": "2"}])
        self.assertEqual(2, len(rds.rows))

    def test_local_s3_adapter_creates_raw_and_processed_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter = JsonFileS3Adapter(base_dir=Path(tmp))
            adapter.save_raw([{"external_id": "1"}], source="headhunter")
            adapter.save_processed([{"external_id": "1"}])

            raw_files = list(Path(tmp).glob("raw/headhunter/*/*/*/jobs_*.json"))
            processed_files = list(Path(tmp).glob("processed/*/*/*/jobs_clean.parquet"))

            self.assertEqual(1, len(raw_files))
            self.assertEqual(1, len(processed_files))


if __name__ == "__main__":
    unittest.main()
