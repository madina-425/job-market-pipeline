"""
tests/test_transformer.py
Unit tests for the JobTransformer.
Run: pytest tests/ -v
"""
import pytest
from src.transformers.job_transformer import JobTransformer, _strip_html, _midpoint


SAMPLE_JOBS = [
    {
        "source": "headhunter",
        "external_id": "hh_001",
        "title": "Senior Data Engineer",
        "company": "  EPAM Systems  ",
        "location": "Almaty",
        "country": "Kazakhstan",
        "salary_from": 800_000,
        "salary_to": 1_200_000,
        "salary_currency": "KZT",
        "remote_type": "remote",
        "seniority": None,
        "skills": ["Python", "Spark", "python"],   # intentional duplicate
        "description": "<p>We need a <b>Python</b> expert.</p>",
        "url": "https://hh.ru/vacancy/001",
        "published_at": "2024-03-01T10:00:00+00:00",
        "collected_at": "2024-03-02T00:00:00+00:00",
    },
    {
        "source": "djinni",
        "external_id": "djinni_002",
        "title": "junior ML engineer",
        "company": "Choco",
        "location": "Astana",
        "country": "Kazakhstan",
        "salary_from": 1500,
        "salary_to": 2500,
        "salary_currency": "USD",
        "remote_type": "hybrid",
        "seniority": "junior",
        "skills": ["TensorFlow 2", "scikit learn", "Python"],
        "description": "Looking for a junior ML engineer with PyTorch skills.",
        "url": "https://djinni.co/jobs/002",
        "published_at": "2024-03-01T12:00:00+00:00",
        "collected_at": "2024-03-02T00:00:00+00:00",
    },
    # Duplicate of first job (same title+company) — should be removed
    {
        "source": "remoteok",
        "external_id": "remoteok_003",
        "title": "Senior Data Engineer",
        "company": "EPAM Systems",
        "location": "Remote",
        "country": None,
        "salary_from": 4000,
        "salary_to": None,
        "salary_currency": "USD",
        "remote_type": "remote",
        "seniority": None,
        "skills": ["spark"],
        "description": "",
        "url": "https://remoteok.com/003",
        "published_at": "2024-03-01T08:00:00+00:00",
        "collected_at": "2024-03-02T00:00:00+00:00",
    },
]


@pytest.fixture
def transformer():
    return JobTransformer()


@pytest.fixture
def clean_df(transformer):
    return transformer.transform(SAMPLE_JOBS)


class TestTransformer:
    def test_output_not_empty(self, clean_df):
        assert len(clean_df) > 0

    def test_deduplication(self, clean_df):
        """Cross-source duplicate (same title+company) should be removed."""
        assert len(clean_df) == 2, f"Expected 2 after dedup, got {len(clean_df)}"

    def test_company_name_stripped(self, clean_df):
        epam_row = clean_df[clean_df["external_id"] == "hh_001"].iloc[0]
        assert epam_row["company"] == "EPAM Systems"

    def test_salary_usd_conversion(self, clean_df):
        """KZT salary should be converted to USD."""
        row = clean_df[clean_df["external_id"] == "hh_001"].iloc[0]
        assert row["salary_usd_from"] is not None
        assert row["salary_usd_from"] > 0
        assert row["salary_usd_from"] < 5000   # 800k KZT ≈ $1,700

    def test_skill_deduplication(self, clean_df):
        row = clean_df[clean_df["external_id"] == "hh_001"].iloc[0]
        skills = row["skills"]
        assert skills.count("python") == 1, "Python should not be duplicated"

    def test_skill_alias_normalisation(self, clean_df):
        row = clean_df[clean_df["external_id"] == "djinni_002"].iloc[0]
        skills = row["skills"]
        assert "scikit-learn" in skills, "scikit learn should be normalised to scikit-learn"
        assert "tensorflow" in skills, "TensorFlow 2 should be normalised to tensorflow"

    def test_seniority_inferred_from_title(self, clean_df):
        row = clean_df[clean_df["external_id"] == "hh_001"].iloc[0]
        assert row["seniority"] == "senior"

    def test_html_stripped_from_description(self, clean_df):
        row = clean_df[clean_df["external_id"] == "hh_001"].iloc[0]
        assert "<p>" not in row["description"]
        assert "Python" in row["description"]

    def test_role_category_assigned(self, clean_df):
        de_row = clean_df[clean_df["external_id"] == "hh_001"].iloc[0]
        assert de_row["role_category"] == "Data Engineer"
        ml_row = clean_df[clean_df["external_id"] == "djinni_002"].iloc[0]
        assert ml_row["role_category"] == "ML Engineer"

    def test_fingerprint_added(self, clean_df):
        assert "fingerprint" in clean_df.columns
        assert clean_df["fingerprint"].notna().all()

    def test_remote_type_valid(self, clean_df):
        valid = {"remote", "hybrid", "on-site", "unknown"}
        assert set(clean_df["remote_type"].unique()).issubset(valid)

    def test_published_at_parsed(self, clean_df):
        import pandas as pd
        assert pd.api.types.is_datetime64_any_dtype(clean_df["published_at"])

    def test_empty_input(self, transformer):
        df = transformer.transform([])
        assert df.empty

    def test_salary_midpoint(self):
        assert _midpoint(1000, 2000) == 1500.0
        assert _midpoint(1000, None) == 1000
        assert _midpoint(None, None) is None

    def test_strip_html(self):
        assert _strip_html("<p>Hello <b>world</b></p>") == "Hello world"
        assert _strip_html("") == ""
        assert _strip_html(None) == ""
