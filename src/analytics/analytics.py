"""
src/analytics/analytics.py
Computes analytics reports from the PostgreSQL database.
Generates aggregated tables used by the Streamlit dashboard.
"""
from __future__ import annotations

import pandas as pd

from src.loaders.rds_loader import RDSLoader
from src.utils.logger import get_logger

log = get_logger(__name__)


class JobAnalytics:
    def __init__(self, loader: RDSLoader):
        self.db = loader

    def refresh_views(self):
        """Refresh all materialised views after a pipeline run."""
        views = [
            "mv_skill_demand",
            "mv_salary_summary",
            "mv_remote_trends",
            "mv_city_hiring",
        ]
        from sqlalchemy import text
        with self.db.engine.begin() as conn:
            for view in views:
                conn.execute(text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view}"))
                log.info("Refreshed %s", view)

    # ── Report generators ─────────────────────────────────────────────────────

    def top_skills(self, role: str | None = None, n: int = 30) -> pd.DataFrame:
        """Top N most demanded skills, optionally filtered by role."""
        where = f"WHERE role_category = '{role}'" if role else ""
        return self.db.load_for_analytics(f"""
            SELECT skill, SUM(frequency) AS frequency
            FROM mv_skill_demand
            {where}
            GROUP BY skill
            ORDER BY frequency DESC
            LIMIT {n}
        """)

    def salary_by_role_seniority(self) -> pd.DataFrame:
        return self.db.load_for_analytics("""
            SELECT role_category, seniority, job_count,
                   avg_salary_usd, median_salary_usd,
                   min_salary_usd, max_salary_usd
            FROM mv_salary_summary
            ORDER BY role_category, seniority
        """)

    def remote_trend(self) -> pd.DataFrame:
        return self.db.load_for_analytics("""
            SELECT week, remote_type, job_count
            FROM mv_remote_trends
            ORDER BY week
        """)

    def city_hiring(self, role: str | None = None) -> pd.DataFrame:
        where = f"WHERE role_category = '{role}'" if role else ""
        return self.db.load_for_analytics(f"""
            SELECT location, role_category, job_count
            FROM mv_city_hiring
            {where}
            ORDER BY job_count DESC
            LIMIT 20
        """)

    def top_companies(self, n: int = 15) -> pd.DataFrame:
        return self.db.load_for_analytics(f"""
            SELECT company, COUNT(*) AS open_positions,
                   ROUND(AVG(salary_usd_mid)) AS avg_salary_usd
            FROM jobs
            WHERE published_at >= now() - INTERVAL '30 days'
              AND company IS NOT NULL
            GROUP BY company
            ORDER BY open_positions DESC
            LIMIT {n}
        """)

    def daily_volume(self) -> pd.DataFrame:
        return self.db.load_for_analytics("""
            SELECT
                DATE_TRUNC('day', published_at)::date AS day,
                role_category,
                COUNT(*)::INT AS job_count
            FROM jobs
            WHERE published_at >= now() - INTERVAL '30 days'
            GROUP BY day, role_category
            ORDER BY day
        """)

    def build_summary_report(self) -> dict:
        """Generate a JSON-serialisable summary for S3 daily report."""
        total = self.db.load_for_analytics("SELECT COUNT(*) AS n FROM jobs").iloc[0]["n"]
        by_role = self.db.load_for_analytics("""
            SELECT role_category, COUNT(*) AS n
            FROM jobs WHERE published_at >= now() - INTERVAL '7 days'
            GROUP BY role_category
        """).to_dict("records")

        top_skills = self.top_skills(n=10).to_dict("records")

        return {
            "total_jobs": int(total),
            "last_7_days_by_role": by_role,
            "top_10_skills": top_skills,
        }
