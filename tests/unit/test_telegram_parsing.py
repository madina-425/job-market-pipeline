"""
tests/unit/test_telegram_parsing.py
Unit tests for Telegram text parsing helpers.
Run: pytest tests/unit/test_telegram_parsing.py -v
"""
from src.collectors.telegram_collector import (
    TelegramCollector,
    _extract_company,
    _extract_location,
    _extract_remote_type,
    _extract_seniority,
    _extract_skills,
    _extract_title,
    _parse_salary,
)


def test_is_relevant_checks_keywords():
    collector = TelegramCollector(api_id=1, api_hash="hash", keywords=["data analyst"])
    assert collector._is_relevant("Hiring Data Analyst in Almaty")
    assert not collector._is_relevant("Hiring backend engineer")


def test_extract_title_strips_emojis():
    text = "🔥 Senior Data Engineer\nКомпания: ACME"
    assert _extract_title(text) == "Senior Data Engineer"


def test_extract_company_matches_patterns():
    text = "Компания: EPAM Systems\nЛокация: Алматы"
    assert _extract_company(text) == "EPAM Systems"


def test_extract_location_matches_known_city():
    text = "Работа в Алматы или Remote"
    assert _extract_location(text) in {"Алматы", "Remote"}


def test_extract_remote_type_variants():
    assert _extract_remote_type("Удаленно, full-time") == "remote"
    assert _extract_remote_type("Hybrid role") == "hybrid"
    assert _extract_remote_type("Office in Astana") == "on-site"


def test_extract_seniority_rules():
    assert _extract_seniority("Senior Data Engineer") == "senior"
    assert _extract_seniority("Junior analyst") == "junior"
    assert _extract_seniority("Middle data engineer") == "mid"


def test_parse_salary_kzt_range():
    text = "ЗП 800 000 - 1 200 000 KZT"
    assert _parse_salary(text) == (800000, 1200000, "KZT")


def test_parse_salary_usd_range():
    text = "Salary $2000 - $4000"
    assert _parse_salary(text) == (2000, 4000, "USD")


def test_parse_salary_single_value():
    text = "от 500 000 тг"
    assert _parse_salary(text) == (500000, None, "KZT")


def test_extract_skills_detects_keywords():
    text = "Stack: Python, SQL, Power BI, AWS"
    skills = set(_extract_skills(text))
    assert {"python", "sql", "power bi", "aws"}.issubset(skills)
