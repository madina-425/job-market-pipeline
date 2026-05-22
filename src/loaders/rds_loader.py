"""
src/loaders/rds_loader.py
Loads cleaned job data into local PostgreSQL using SQLAlchemy.
Uses fingerprint column for idempotent upserts — safe to re-run daily.
"""
from __future__ import annotations

import os
from dotenv import load_dotenv

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from src.utils.logger import get_logger

load_dotenv()
log = get_logger(__name__)


class RDSLoader:
    def __init__(self):
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = os.getenv("DB_PORT", "5432")
        db_name = os.getenv("DB_NAME", "jobmarket")
        db_user = os.getenv("DB_USER", "pipeline_user")
        db_password = os.getenv("DB_PASSWORD", "devpassword")

        db_url = f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        self.engine: Engine = create_engine(
            db_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            connect_args={"connect_timeout": 10},
        )

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
        safe_cols = [c for c in cols if c in df.columns]
        df_load = df[safe_cols].copy()

        inserted = 0
        raw_conn = self.engine.raw_connection()
        try:
            cur = raw_conn.cursor()
            for _, row in df_load.iterrows():
                try:
                    skills = row.get("skills")
                    skills_array = "{" + ",".join(f'"{x}"' for x in skills) + "}" if isinstance(skills, list) else "{}"

                    cur.execute("""
                        INSERT INTO jobs (
                            external_id, fingerprint, source, title, company,
                            location, country, salary_from, salary_to,
                            salary_currency, salary_usd_from, salary_usd_to,
                            salary_usd_mid, remote_type, seniority,
                            role_category, skills, url, published_at, collected_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::text[], %s, %s, %s)
                        ON CONFLICT (fingerprint) DO NOTHING
                    """, (
                        row.get("external_id"), row.get("fingerprint"), row.get("source"),
                        row.get("title"), row.get("company"), row.get("location"),
                        row.get("country"), row.get("salary_from"), row.get("salary_to"),
                        row.get("salary_currency"), row.get("salary_usd_from"), row.get("salary_usd_to"),
                        row.get("salary_usd_mid"), row.get("remote_type"), row.get("seniority"),
                        row.get("role_category"), skills_array, row.get("url"),
                        row.get("published_at"), row.get("collected_at"),
                    ))
                    inserted += cur.rowcount
                except Exception as exc:
                    log.error("RDS: insert failed for %s: %s", row.get("external_id"), exc)
            raw_conn.commit()
            cur.close()
        finally:
            raw_conn.close()

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
