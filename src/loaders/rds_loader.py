"""
src/loaders/rds_loader.py
Loads cleaned job data into PostgreSQL using SQLAlchemy.
Uses fingerprint column for idempotent upserts — safe to re-run daily.
"""
from __future__ import annotations

import pandas as pd
from psycopg2 import Error as PsycopgError
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from configs import settings
from src.utils.logger import get_logger

log = get_logger(__name__)

JOB_COLUMNS = [
    "external_id", "fingerprint", "source", "title", "company",
    "location", "country", "salary_from", "salary_to",
    "salary_currency", "salary_usd_from", "salary_usd_to",
    "salary_usd_mid", "remote_type", "seniority",
    "role_category", "skills", "url", "published_at", "collected_at",
]

INSERT_SQL = """
    INSERT INTO jobs (
        external_id, fingerprint, source, title, company,
        location, country, salary_from, salary_to,
        salary_currency, salary_usd_from, salary_usd_to,
        salary_usd_mid, remote_type, seniority,
        role_category, skills, url, published_at, collected_at
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (fingerprint) DO NOTHING
"""


class RDSLoader:
    def __init__(self):
        db_cfg = settings.load_db()
        self._db_cfg = db_cfg
        connect_args: dict[str, object] = {"connect_timeout": 10}
        if db_cfg.sslmode:
            connect_args["sslmode"] = db_cfg.sslmode

        log.info(
            "RDS: connecting to %s:%s/%s as %s",
            db_cfg.host,
            db_cfg.port,
            db_cfg.name,
            db_cfg.user,
        )
        self.engine: Engine = create_engine(
            db_cfg.url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            connect_args=connect_args,
        )

    def upsert_jobs(self, df: pd.DataFrame) -> int:
        """Batch insert new jobs; skip duplicates via fingerprint. Returns insert count."""
        if df.empty:
            log.warning("RDS: received empty DataFrame — nothing to load")
            return 0

        rows = self._prepare_rows(df)
        if not rows:
            return 0

        raw_conn = self.engine.raw_connection()
        cur = None
        try:
            cur = raw_conn.cursor()
            cur.executemany(INSERT_SQL, rows)
            raw_conn.commit()
            inserted = cur.rowcount
        except PsycopgError as exc:
            raw_conn.rollback()
            log.error("RDS: batch insert failed: %s", exc)
            inserted = 0
        finally:
            if cur:
                cur.close()
            raw_conn.close()

        log.info("RDS: inserted %d new jobs (skipped duplicates)", inserted)
        return inserted

    @staticmethod
    def _prepare_rows(df: pd.DataFrame) -> list[tuple]:
        df_load = df.reindex(columns=JOB_COLUMNS, fill_value=None)
        skills_idx = JOB_COLUMNS.index("skills")
        rows: list[tuple] = []
        for row in df_load.itertuples(index=False, name=None):
            row_list = list(row)
            skills = row_list[skills_idx]
            row_list[skills_idx] = list(skills) if isinstance(skills, list) else []
            rows.append(tuple(row_list))
        return rows

    def load_for_analytics(self, query: str) -> pd.DataFrame:
        """Run an arbitrary SELECT and return a DataFrame. Used by analytics module."""
        try:
            with self.engine.connect() as conn:
                return pd.read_sql(text(query), conn)
        except SQLAlchemyError as exc:
            log.error("RDS: analytics query failed: %s", exc)
            return pd.DataFrame()

    def health_check(self) -> bool:
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            log.info("RDS: connection OK")
            return True
        except SQLAlchemyError as exc:
            log.error(
                "RDS: connection failed (%s:%s/%s): %s",
                self._db_cfg.host,
                self._db_cfg.port,
                self._db_cfg.name,
                exc,
            )
            return False
