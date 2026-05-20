"""
src/collectors/hh_collector.py
Collects job postings from the HeadHunter API using OAuth 2.0 authentication.

Docs: https://api.hh.ru/openapi/redoc
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Generator
import os

import requests
from dotenv import load_dotenv
load_dotenv()

from src.utils.logger import get_logger

log = get_logger(__name__)

# HeadHunter area ID for Kazakhstan
KZ_AREA_ID = 40

# Role keywords to search for
TARGET_ROLES = [
    "Data Analyst",
    "Data Engineer",
    "Machine Learning Engineer",
    "ML Engineer",
    "аналитик данных",
    "инженер данных",
]

HH_BASE = "https://api.hh.ru"
HH_AUTH_URL = "https://hh.ru/oauth/token"


class HHCollector:
    """Wraps the HeadHunter vacancy search API with OAuth 2.0 authentication."""

    def __init__(self, client_id: str | None = None, client_secret: str | None = None):
        self.client_id = client_id or os.getenv("HH_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("HH_CLIENT_SECRET")
        
        if not self.client_id or not self.client_secret:
            raise ValueError("HH_CLIENT_ID and HH_CLIENT_SECRET must be provided")
        
        self.session = requests.Session()
        self.access_token = None
        self._authenticate()

    def _authenticate(self) -> None:
        """Obtain OAuth 2.0 access token."""
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        try:
            resp = requests.post(HH_AUTH_URL, data=payload, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            self.access_token = data["access_token"]
            log.info("HH: successfully authenticated")
        except requests.RequestException as exc:
            log.error("HH: authentication failed: %s", exc)
            raise

        # Update session headers with Bearer token
        self.session.headers.update({
            "Authorization": f"Bearer {self.access_token}",
            "User-Agent": "JobMarketPipeline/1.0",
        })

    # ── Public interface ──────────────────────────────────────────────────────

    def collect(self) -> list[dict]:
        """Return a flat list of raw vacancy dicts (one per posting)."""
        all_vacancies: list[dict] = []
        for role in TARGET_ROLES:
            log.info("HH: collecting role '%s'", role)
            for vacancy in self._paginate(role):
                all_vacancies.append(self._enrich(vacancy))
            time.sleep(0.5)   # be polite to the API
        log.info("HH: collected %d raw vacancies", len(all_vacancies))
        return all_vacancies

    # ── Private helpers ───────────────────────────────────────────────────────

    def _paginate(self, text: str) -> Generator[dict, None, None]:
        """Yield all vacancies for *text* across all pages."""
        page, per_page = 0, 50
        while True:
            params = {
                "text": text,
                "area": KZ_AREA_ID,
                "per_page": per_page,
                "page": page,
                "only_with_salary": False,
            }
            try:
                resp = self.session.get(
                    f"{HH_BASE}/vacancies", params=params, timeout=10
                )
                resp.raise_for_status()
            except requests.RequestException as exc:
                log.error("HH API error on page %d: %s", page, exc)
                break

            data = resp.json()
            items = data.get("items", [])
            if not items:
                break

            yield from items

            if page >= data.get("pages", 1) - 1:
                break
            page += 1
            time.sleep(0.3)

    def _enrich(self, vacancy: dict) -> dict:
        """
        Fetch the full vacancy detail (description, skills) for a summary item.
        Falls back to summary data if detail fetch fails.
        """
        vacancy_id = vacancy.get("id")
        detail: dict = {}
        try:
            resp = self.session.get(
                f"{HH_BASE}/vacancies/{vacancy_id}", timeout=10
            )
            resp.raise_for_status()
            detail = resp.json()
        except requests.RequestException as exc:
            log.warning("Could not fetch detail for vacancy %s: %s", vacancy_id, exc)

        salary = vacancy.get("salary") or {}
        area = vacancy.get("area") or {}
        employer = vacancy.get("employer") or {}
        experience = vacancy.get("experience") or {}
        schedule = vacancy.get("schedule") or {}

        key_skills = [s["name"] for s in detail.get("key_skills", [])]

        return {
            "source": "headhunter",
            "external_id": f"hh_{vacancy_id}",
            "title": vacancy.get("name"),
            "company": employer.get("name"),
            "location": area.get("name"),
            "country": "Kazakhstan",
            "salary_from": salary.get("from"),
            "salary_to": salary.get("to"),
            "salary_currency": salary.get("currency"),
            "remote_type": _map_schedule(schedule.get("id")),
            "seniority": _map_experience(experience.get("id")),
            "skills": key_skills,
            "description": detail.get("description", ""),
            "url": vacancy.get("alternate_url"),
            "published_at": vacancy.get("published_at"),
            "collected_at": datetime.now(timezone.utc).isoformat(),
        }


# ── Mapping helpers ───────────────────────────────────────────────────────────

def _map_schedule(schedule_id: str | None) -> str:
    mapping = {
        "remote": "remote",
        "fullDay": "on-site",
        "shift": "on-site",
        "flexible": "hybrid",
        "flyInFlyOut": "on-site",
    }
    return mapping.get(schedule_id or "", "unknown")


def _map_experience(exp_id: str | None) -> str:
    mapping = {
        "noExperience": "junior",
        "between1And3": "mid",
        "between3And6": "senior",
        "moreThan6": "senior",
    }
    return mapping.get(exp_id or "", "unknown")

if __name__ == "__main__":
    collector = HHCollector()
    vacancies = collector.collect()
    print(f"Collected {len(vacancies)} vacancies")
    if vacancies:
        print(vacancies[0])