"""
src/transformers/job_transformer.py
Cleans and normalises raw job records from all sources into a unified schema.

Transformations applied:
  - Deduplicate by external_id and title+company fingerprint
  - Normalise salaries (monthly → monthly, convert to USD)
  - Parse and normalise skill list
  - Classify remote/hybrid/on-site
  - Infer seniority from title when missing
  - Clean company and title text
  - Parse publication dates to UTC
"""
from __future__ import annotations

import hashlib
import re
import pandas as pd

from src.utils.currency import to_usd
from src.utils.logger import get_logger

log = get_logger(__name__)

# Canonical skill aliases — expand as needed
SKILL_ALIASES: dict[str, str] = {
    "python3": "python",
    "py": "python",
    "postgresql": "postgres",
    "postgressql": "postgres",
    "ms sql": "sql server",
    "mssql": "sql server",
    "aws s3": "s3",
    "amazon s3": "s3",
    "scikit learn": "scikit-learn",
    "sklearn": "scikit-learn",
    "tensorflow 2": "tensorflow",
    "tf": "tensorflow",
    "pytorch": "pytorch",
    "machine learning": "ml",
    "deep learning": "dl",
    "natural language processing": "nlp",
    "computer vision": "cv",
    "apache spark": "spark",
    "apache kafka": "kafka",
    "apache airflow": "airflow",
    "google bigquery": "bigquery",
    "microsoft azure": "azure",
    "google cloud platform": "gcp",
    "amazon web services": "aws",
}


class JobTransformer:
    """Transforms a list of raw dicts into a clean pandas DataFrame."""

    def transform(self, raw_jobs: list[dict]) -> pd.DataFrame:
        if not raw_jobs:
            log.warning("Transformer received empty job list")
            return pd.DataFrame()

        df = pd.DataFrame(raw_jobs)
        log.info("Transformer: starting with %d records", len(df))

        df = self._clean_text_fields(df)
        df = self._parse_dates(df)
        df = self._normalise_salaries(df)
        df = self._normalise_skills(df)
        df = self._classify_remote(df)
        df = self._infer_seniority(df)
        df = self._add_role_category(df)
        df = self._deduplicate(df)
        df = self._add_fingerprint(df)

        log.info("Transformer: finished with %d clean records", len(df))
        return df

    # ── Steps ─────────────────────────────────────────────────────────────────

    def _clean_text_fields(self, df: pd.DataFrame) -> pd.DataFrame:
        for col in ("title", "company", "location"):
            if col in df.columns:
                df[col] = (
                    df[col]
                    .astype(str)
                    .str.strip()
                    .str.replace(r"\s+", " ", regex=True)
                    .replace("nan", None)
                    .replace("None", None)
                )
        # Strip HTML from description
        if "description" in df.columns:
            df["description"] = df["description"].apply(_strip_html)
        return df

    def _parse_dates(self, df: pd.DataFrame) -> pd.DataFrame:
        if "published_at" in df.columns:
            df["published_at"] = pd.to_datetime(
                df["published_at"], utc=True, errors="coerce"
            )
        return df

    def _normalise_salaries(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add salary_usd_from / salary_usd_to columns."""
        df["salary_usd_from"] = df.apply(
            lambda r: to_usd(r.get("salary_from"), r.get("salary_currency")),
            axis=1,
        )
        df["salary_usd_to"] = df.apply(
            lambda r: to_usd(r.get("salary_to"), r.get("salary_currency")),
            axis=1,
        )
        # Midpoint for easy analysis
        df["salary_usd_mid"] = df.apply(
            lambda r: _midpoint(r["salary_usd_from"], r["salary_usd_to"]), axis=1
        )
        return df

    def _normalise_skills(self, df: pd.DataFrame) -> pd.DataFrame:
        """Lower-case, de-alias, and deduplicate skills list."""
        if "skills" not in df.columns:
            df["skills"] = [[] for _ in range(len(df))]
            return df

        def clean_skills(skills) -> list[str]:
            if not isinstance(skills, list):
                return []
            cleaned = []
            for s in skills:
                s = str(s).lower().strip()
                s = SKILL_ALIASES.get(s, s)
                if s and len(s) > 1:
                    cleaned.append(s)
            return list(dict.fromkeys(cleaned))   # deduplicate preserving order

        df["skills"] = df["skills"].apply(clean_skills)
        # Also extract skills from title/description
        df["skills"] = df.apply(
            lambda r: list(
                dict.fromkeys(
                    r["skills"]
                    + _extract_skills_from_text(r.get("title", "") or "")
                    + _extract_skills_from_text(r.get("description", "") or "")
                )
            ),
            axis=1,
        )
        return df

    def _classify_remote(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize remote_type to: remote | hybrid | on-site | unknown."""
        def classify(val):
            if not isinstance(val, str):
                return "unknown"
            val = val.lower().strip()
            if val in ("on site", "onsite"):
                return "on-site"
            if val in ("remote", "hybrid"):
                return val
            return "unknown"

        df["remote_type"] = df["remote_type"].apply(classify)
        return df

    def _infer_seniority(self, df: pd.DataFrame) -> pd.DataFrame:
        """Fill missing seniority from job title."""
        def infer(row):
            if row.get("seniority") not in (None, "unknown", ""):
                return row["seniority"]
            title = str(row.get("title", "")).lower()
            if any(w in title for w in ["senior", "sr.", "lead", "principal", "staff"]):
                return "senior"
            if any(w in title for w in ["junior", "jr.", "intern", "trainee", "entry"]):
                return "junior"
            if any(w in title for w in ["middle", "mid"]):
                return "mid"
            return "unknown"

        df["seniority"] = df.apply(infer, axis=1)
        return df

    def _add_role_category(self, df: pd.DataFrame) -> pd.DataFrame:
        """Classify into ML Engineer, Data Engineer, Data Analyst, or Other."""
        def categorise(title: str) -> str:
            t = str(title).lower()

            # ML Engineer patterns (English + Russian)
            ml_keywords = [
                "machine learning", "ml engineer", "deep learning", "ai engineer",
                "инженер ml", "инженер ai", "инженер машинного обучения",
                "machine learning engineer",
            ]
            if any(w in t for w in ml_keywords):
                return "ML/AI Engineer"

            # Data Engineer patterns (English + Russian)
            de_keywords = [
                "data engineer", "data pipeline", "etl", "data platform",
                "инженер данных", "data infrastructure", "analytics engineer",
                "инженер аналитики", "инженер аналитики данных",
            ]
            if any(w in t for w in de_keywords):
                return "Data Engineer"

            # Data Analyst patterns (English + Russian) with exclusions
            da_keywords = [
                "data analyst", "analytics", "bi analyst", "business analyst",
                "аналитик данных", "data scientist",
            ]
            exclude_keywords = [
                "финансовый", "системный", "бизнес-аналитик",
                "бизнес аналитик", "менеджер", "продаж", "маркетолог",
                "сметчик", "проектировщик", "директор", "координатор",
                "инженер пто", "девопс", "devops", "сервисный",
            ]
            if any(w in t for w in da_keywords):
                if not any(ex in t for ex in exclude_keywords):
                    return "Data Analyst"

            return "Other"

        df["role_category"] = df["title"].apply(categorise)
        return df

    def _deduplicate(self, df: pd.DataFrame) -> pd.DataFrame:
        before = len(df)
        # Primary dedup: exact external_id match
        df = df.drop_duplicates(subset=["external_id"], keep="first")
        # Secondary: same title + company (catches cross-source dupes)
        df["_dup_key"] = (
            df["title"].fillna("").str.lower()
            + "|"
            + df["company"].fillna("").str.lower()
        )
        df = df.drop_duplicates(subset=["_dup_key"], keep="first")
        df = df.drop(columns=["_dup_key"])
        log.info("Dedup: removed %d duplicates", before - len(df))
        return df.reset_index(drop=True)

    def _add_fingerprint(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add a stable row hash for idempotent upserts."""
        def fingerprint(row):
            raw = f"{row.get('external_id')}|{row.get('title')}|{row.get('company')}"
            return hashlib.sha256(raw.encode()).hexdigest()[:16]

        df["fingerprint"] = df.apply(fingerprint, axis=1)
        return df


# ── Free helpers ──────────────────────────────────────────────────────────────

SKILL_KEYWORDS = [
    "python", "sql", "spark", "kafka", "airflow", "dbt", "docker",
    "kubernetes", "aws", "gcp", "azure", "tableau", "power bi", "looker",
    "scikit-learn", "tensorflow", "pytorch", "pandas", "numpy",
    "postgres", "mysql", "mongodb", "redis", "elasticsearch",
    "hadoop", "hive", "presto", "trino", "snowflake", "databricks",
    "git", "linux", "bash", "r", "scala", "java",
]


def _extract_skills_from_text(text: str) -> list[str]:
    text = text.lower()
    return [kw for kw in SKILL_KEYWORDS if re.search(r"\b" + re.escape(kw) + r"\b", text)]


def _strip_html(html: str) -> str:
    if not html:
        return ""
    clean = re.sub(r"<[^>]+>", " ", str(html))
    return re.sub(r"\s+", " ", clean).strip()


def _midpoint(a: float | None, b: float | None) -> float | None:
    if a is not None and b is not None:
        return round((a + b) / 2, 2)
    if a is not None:
        return a
    if b is not None:
        return b
    return None