"""
src/loaders/rds_loader.py
Upserts cleaned job data into AWS RDS PostgreSQL using SQLAlchemy.
Uses fingerprint column for idempotent upserts — safe to re-run daily.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from src.utils.logger import get_logger

log = get_logger(__name__)


class RDSLoader:
    def __init__(self, db_url: str):
        self.engine: Engine = create_engine(
            db_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,       # reconnect on stale connections
            connect_args={"connect_timeout": 10},
        )

    # ── Public interface ──────────────────────────────────────────────────────

    def upsert_jobs(self, df: pd.DataFrame) -> int:
        """Insert new jobs; skip rows whose fingerprint already exists. Returns insert count."""
        if df.empty:
            log.warning("RDS: received empty DataFrame — nothing to load")
            return 0

        cols = [
            "external_id", "fingerprint", "source", "title", "company",
            "location", "country", "salary_from", "salary_to",
            "salary_currency", "salary_usd_from", "salary_usd_to",
            "salary_usd_mid", "remote_type", "seniority",
            "role_category", "skills", "url", "published_at", "collected_at",
        ]
        # Keep only columns that exist in both schema and DataFrame
        safe_cols = [c for c in cols if c in df.columns]
        df_load = df[safe_cols].copy()

        # Serialise skills list to Postgres array syntax
        df_load["skills"] = df_load["skills"].apply(
            lambda s: "{" + ",".join(f'"{x}"' for x in s) + "}" if isinstance(s, list) else "{}"
        )

        inserted = 0
        with self.engine.begin() as conn:
            for _, row in df_load.iterrows():
                try:
                    result = conn.execute(
                        text("""
                            INSERT INTO jobs (
                                external_id, fingerprint, source, title, company,
                                location, country, salary_from, salary_to,
                                salary_currency, salary_usd_from, salary_usd_to,
                                salary_usd_mid, remote_type, seniority,
                                role_category, skills, url, published_at, collected_at
                            ) VALUES (
                                :external_id, :fingerprint, :source, :title, :company,
                                :location, :country, :salary_from, :salary_to,
                                :salary_currency, :salary_usd_from, :salary_usd_to,
                                :salary_usd_mid, :remote_type, :seniority,
                                :role_category, :skills::text[], :url, :published_at, :collected_at
                            )
                            ON CONFLICT (fingerprint) DO NOTHING
                        """),
                        row.to_dict(),
                    )
                    inserted += result.rowcount
                except SQLAlchemyError as exc:
                    log.error("RDS: insert failed for %s: %s", row.get("external_id"), exc)

        log.info("RDS: inserted %d new jobs (skipped duplicates)", inserted)
        return inserted

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
            return True
        except SQLAlchemyError:
            return False

"""Load data to PostgreSQL RDS."""
import pandas as pd
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

class RDSLoader:
    def __init__(self):
        self.db_host = os.getenv("DB_HOST", "localhost")
        self.db_port = os.getenv("DB_PORT", "5432")
        self.db_name = os.getenv("DB_NAME", "jobmarket")
        self.db_user = os.getenv("DB_USER", "pipeline_user")
        self.db_password = os.getenv("DB_PASSWORD", "devpassword")
        
        db_url = f"postgresql+psycopg2://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
        self.engine = create_engine(db_url)
    
    def load_df(self, df: pd.DataFrame, table: str = "jobs", if_exists: str = "append"):
        """Load DataFrame into PostgreSQL table."""
        df.to_sql(table, self.engine, if_exists=if_exists, index=False)
        
        with self.engine.connect() as conn:
            count = conn.execute(text(f"SELECT COUNT(*) FROM {table};")).scalar()
        
        return count
