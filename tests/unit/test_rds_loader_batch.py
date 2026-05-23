"""
tests/unit/test_rds_loader_batch.py
Unit tests for RDSLoader batch insert improvements.
Tests batch insert, error handling, and skill array conversion.
Run: pytest tests/unit/test_rds_loader_batch.py -v
"""
import pytest
import pandas as pd
from psycopg2 import Error as PsycopgError
from unittest.mock import MagicMock, patch
from src.loaders.rds_loader import RDSLoader


@pytest.fixture
def mock_rds_loader():
    """Create RDSLoader with mocked engine."""
    with patch('src.loaders.rds_loader.create_engine'):
        loader = RDSLoader()
        return loader


def test_upsert_jobs_empty_dataframe(mock_rds_loader):
    """Empty DataFrame returns 0 with warning log."""
    df = pd.DataFrame()
    result = mock_rds_loader.upsert_jobs(df)
    assert result == 0


def test_upsert_jobs_batch_insert(mock_rds_loader):
    """Verify executemany is called with all rows at once."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.rowcount = 3
    mock_conn.cursor.return_value = mock_cursor
    mock_rds_loader.engine.raw_connection.return_value = mock_conn

    df = pd.DataFrame([
        {
            "external_id": "id1",
            "fingerprint": "fp1",
            "source": "hh",
            "title": "Engineer",
            "company": "ACME",
            "location": "Almaty",
            "country": "Kazakhstan",
            "salary_from": 1000,
            "salary_to": 2000,
            "salary_currency": "KZT",
            "salary_usd_from": 2.5,
            "salary_usd_to": 5.0,
            "salary_usd_mid": 3.75,
            "remote_type": "remote",
            "seniority": "mid",
            "role_category": "Data Engineer",
            "skills": ["python", "sql"],
            "url": "https://example.com/1",
            "published_at": "2024-01-01",
            "collected_at": "2024-01-02",
        },
        {
            "external_id": "id2",
            "fingerprint": "fp2",
            "source": "djinni",
            "title": "Analyst",
            "company": "XYZ",
            "location": "Astana",
            "country": "Kazakhstan",
            "salary_from": 1500,
            "salary_to": 2500,
            "salary_currency": "USD",
            "salary_usd_from": 1500,
            "salary_usd_to": 2500,
            "salary_usd_mid": 2000,
            "remote_type": "hybrid",
            "seniority": "senior",
            "role_category": "Data Analyst",
            "skills": [],
            "url": "https://example.com/2",
            "published_at": "2024-01-01",
            "collected_at": "2024-01-02",
        }
    ])

    result = mock_rds_loader.upsert_jobs(df)

    # Verify executemany was called (not execute multiple times)
    mock_cursor.executemany.assert_called_once()
    args, kwargs = mock_cursor.executemany.call_args

    # Verify it was called with SQL and a list of tuples
    assert "INSERT INTO jobs" in args[0]
    assert "ON CONFLICT (fingerprint) DO NOTHING" in args[0]
    assert len(args[1]) == 2  # Two rows
    assert result == 3  # Rowcount returned


def test_upsert_jobs_skills_array_conversion(mock_rds_loader):
    """Verify skills list is properly converted for PostgreSQL array."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.rowcount = 1
    mock_conn.cursor.return_value = mock_cursor
    mock_rds_loader.engine.raw_connection.return_value = mock_conn

    df = pd.DataFrame([
        {
            "external_id": "id1",
            "fingerprint": "fp1",
            "source": "hh",
            "title": "Engineer",
            "company": "ACME",
            "location": "Almaty",
            "country": "Kazakhstan",
            "salary_from": 1000,
            "salary_to": 2000,
            "salary_currency": "KZT",
            "salary_usd_from": 2.5,
            "salary_usd_to": 5.0,
            "salary_usd_mid": 3.75,
            "remote_type": "remote",
            "seniority": "mid",
            "role_category": "Data Engineer",
            "skills": ["python", "sql", "spark"],
            "url": "https://example.com/1",
            "published_at": "2024-01-01",
            "collected_at": "2024-01-02",
        }
    ])

    mock_rds_loader.upsert_jobs(df)

    # Extract the data passed to executemany
    args, kwargs = mock_cursor.executemany.call_args
    rows = args[1]

    # Skills should be a list at index 16
    assert rows[0][16] == ["python", "sql", "spark"]


def test_upsert_jobs_empty_skills_converts_to_empty_list(mock_rds_loader):
    """Verify missing/None skills converts to empty list."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.rowcount = 1
    mock_conn.cursor.return_value = mock_cursor
    mock_rds_loader.engine.raw_connection.return_value = mock_conn

    df = pd.DataFrame([
        {
            "external_id": "id1",
            "fingerprint": "fp1",
            "source": "hh",
            "title": "Engineer",
            "company": "ACME",
            "location": "Almaty",
            "country": "Kazakhstan",
            "salary_from": 1000,
            "salary_to": 2000,
            "salary_currency": "KZT",
            "salary_usd_from": 2.5,
            "salary_usd_to": 5.0,
            "salary_usd_mid": 3.75,
            "remote_type": "remote",
            "seniority": "mid",
            "role_category": "Data Engineer",
            "skills": None,
            "url": "https://example.com/1",
            "published_at": "2024-01-01",
            "collected_at": "2024-01-02",
        }
    ])

    mock_rds_loader.upsert_jobs(df)

    args, kwargs = mock_cursor.executemany.call_args
    rows = args[1]
    assert rows[0][16] == []


def test_upsert_jobs_error_handling_rollback(mock_rds_loader):
    """Verify rollback on exception and proper error logging."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.executemany.side_effect = PsycopgError("DB error")
    mock_conn.cursor.return_value = mock_cursor
    mock_rds_loader.engine.raw_connection.return_value = mock_conn

    df = pd.DataFrame([
        {
            "external_id": "id1",
            "fingerprint": "fp1",
            "source": "hh",
            "title": "Engineer",
            "company": "ACME",
            "location": "Almaty",
            "country": "Kazakhstan",
            "salary_from": 1000,
            "salary_to": 2000,
            "salary_currency": "KZT",
            "salary_usd_from": 2.5,
            "salary_usd_to": 5.0,
            "salary_usd_mid": 3.75,
            "remote_type": "remote",
            "seniority": "mid",
            "role_category": "Data Engineer",
            "skills": ["python"],
            "url": "https://example.com/1",
            "published_at": "2024-01-01",
            "collected_at": "2024-01-02",
        }
    ])

    result = mock_rds_loader.upsert_jobs(df)

    # Verify rollback was called
    mock_conn.rollback.assert_called_once()
    # Verify cursor was closed
    mock_cursor.close.assert_called_once()
    # Verify return value is 0 on error
    assert result == 0


def test_upsert_jobs_missing_columns_skipped(mock_rds_loader):
    """Verify missing optional columns are handled gracefully."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.rowcount = 1
    mock_conn.cursor.return_value = mock_cursor
    mock_rds_loader.engine.raw_connection.return_value = mock_conn

    # DataFrame with only required columns
    df = pd.DataFrame([
        {
            "external_id": "id1",
            "fingerprint": "fp1",
            "source": "hh",
            "title": "Engineer",
            "company": "ACME",
        }
    ])

    result = mock_rds_loader.upsert_jobs(df)

    # Should still call executemany with partial row
    mock_cursor.executemany.assert_called_once()
    assert result == 1
