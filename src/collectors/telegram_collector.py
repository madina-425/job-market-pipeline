"""
src/collectors/telegram_collector.py
Collects job postings from public Telegram channels using Telethon.
"""
from __future__ import annotations

import asyncio
import os
import re
from datetime import datetime, timezone
from src.utils.logger import get_logger

log = get_logger(__name__)

# ── Target channels ───────────────────────────────────────────────────────────
DEFAULT_CHANNELS = [
    "itcom_kz",      # IT community Kazakhstan — general IT jobs
    "fbrokerch",     # Freedom channel
    "ml_jobs_kz",    # Data Science / ML jobs KZ (bonus — very relevant)
    "it_jobs_kz",    # IT jobs KZ (bonus — broad IT, has data roles)
]

# Keywords to filter relevant messages
DEFAULT_KEYWORDS = [
    "data analyst", "data engineer", "machine learning", "ml engineer",
    "аналитик данных", "инженер данных", "data science", "аналитик",
    "bi analyst", "etl", "analytics",
]

# How many recent messages to fetch per channel
DEFAULT_MSG_LIMIT = 100

SKILL_KEYWORDS = [
    "python", "sql", "spark", "kafka", "airflow", "dbt", "docker",
    "kubernetes", "aws", "gcp", "azure", "tableau", "power bi", "looker",
    "scikit-learn", "tensorflow", "pytorch", "pandas", "numpy",
    "postgres", "postgresql", "mysql", "mongodb", "clickhouse",
    "hadoop", "snowflake", "databricks", "git", "linux", "scala", "java",
    "powerbi", "superset",
]


class TelegramCollector:
    """Scrapes public Telegram channels for job postings using Telethon."""

    def __init__(
        self,
        api_id: int | None = None,
        api_hash: str | None = None,
        channels: list[str] | None = None,
        keywords: list[str] | None = None,
        msg_limit: int = DEFAULT_MSG_LIMIT,
    ):
        api_id = api_id or os.environ.get("TELEGRAM_API_ID")
        if not api_id:
            raise ValueError("TELEGRAM_API_ID not found in environment variables")
        self.api_id = int(api_id)
        self.api_hash = api_hash or os.environ.get("TELEGRAM_API_HASH")
        if not self.api_hash:
            raise ValueError("TELEGRAM_API_HASH not found in environment variables")
        self.channels = list(channels or DEFAULT_CHANNELS)
        keywords = list(keywords or DEFAULT_KEYWORDS)
        self.keywords = tuple(kw.lower() for kw in keywords)
        self.msg_limit = msg_limit

    def collect(self) -> list[dict]:
        """Sync entry point — runs the async collector."""
        return asyncio.run(self._collect_all())

    # ── Async core ────────────────────────────────────────────────────────────

    async def _collect_all(self) -> list[dict]:
        try:
            from telethon import TelegramClient
        except ImportError:
            log.error("Telethon not installed. Run: pip install telethon")
            return []

        results: list[dict] = []
        async with TelegramClient("tg_session", self.api_id, self.api_hash) as client:
            for channel in self.channels:
                log.info("Telegram: scraping @%s", channel)
                try:
                    posts = await self._scrape_channel(client, channel)
                    log.info("Telegram: got %d relevant posts from @%s", len(posts), channel)
                    results.extend(posts)
                except Exception as exc:
                    log.error("Telegram: failed to scrape @%s: %s", channel, exc)

        log.info("Telegram: collected %d total posts", len(results))
        return results

    async def _scrape_channel(self, client, channel: str) -> list[dict]:
        """Fetch and filter recent messages from one channel."""
        posts = []
        async for message in client.iter_messages(channel, limit=self.msg_limit):
            if not message.text:
                continue
            if not self._is_relevant(message.text):
                continue
            posts.append(self._normalize(message, channel))
        return posts

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _is_relevant(self, text: str) -> bool:
        text_lower = text.lower()
        return any(kw in text_lower for kw in self.keywords)

    def _normalize(self, message, channel: str) -> dict:
        text = message.text or ""
        salary_from, salary_to, currency = _parse_salary(text)

        return {
            "source": f"telegram_{channel}",
            "external_id": f"tg_{channel}_{message.id}",
            "title": _extract_title(text),
            "company": _extract_company(text),
            "location": _extract_location(text),
            "country": "Kazakhstan",
            "salary_from": salary_from,
            "salary_to": salary_to,
            "salary_currency": currency,
            "remote_type": _extract_remote_type(text),
            "seniority": _extract_seniority(text),
            "skills": _extract_skills(text),
            "description": text.strip(),
            "url": f"https://t.me/{channel}/{message.id}",
            "published_at": message.date.astimezone(timezone.utc).isoformat(),
            "collected_at": datetime.now(timezone.utc).isoformat(),
        }


# ── Text parsers ──────────────────────────────────────────────────────────────

def _extract_title(text: str) -> str | None:
    """First non-empty line is usually the job title."""
    for line in text.splitlines():
        line = line.strip().lstrip("🔥💼📌👉#").strip()
        if len(line) > 5:
            return line[:120]
    return None


def _extract_company(text: str) -> str | None:
    """Look for common company name patterns."""
    patterns = [
        r"компания[:\s]+([^\n]+)",
        r"company[:\s]+([^\n]+)",
        r"работодатель[:\s]+([^\n]+)",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()[:100]
    return None


def _extract_location(text: str) -> str | None:
    """Look for city mentions."""
    cities = ["Алматы", "Астана", "Almaty", "Astana", "Шымкент", "Remote", "Удалённо", "Удаленно"]
    text_lower = text.lower()
    for city in cities:
        if city.lower() in text_lower:
            return city
    return None


def _extract_remote_type(text: str) -> str:
    text_lower = text.lower()
    if any(w in text_lower for w in ["remote", "удалённо", "удаленно", "дистанционно"]):
        return "remote"
    if any(w in text_lower for w in ["гибрид", "hybrid"]):
        return "hybrid"
    if any(w in text_lower for w in ["офис", "office", "на месте"]):
        return "on-site"
    return "unknown"


def _extract_seniority(text: str) -> str:
    text_lower = text.lower()
    if any(w in text_lower for w in ["senior", "lead", "principal"]):
        return "senior"
    if any(w in text_lower for w in ["junior", "стажёр", "intern", "trainee"]):
        return "junior"
    if any(w in text_lower for w in ["middle", "mid"]):
        return "mid"
    return "unknown"


def _parse_salary(text: str) -> tuple[int | None, int | None, str | None]:
    """
    Extract salary range from text.
    Handles patterns like:
      - 800 000 - 1 200 000 KZT
      - $2000 - $4000
      - от 500 000 тг
    """
    # Detect currency
    currency = None
    if re.search(r"\$|usd", text, re.IGNORECASE):
        currency = "USD"
    elif re.search(r"€|eur", text, re.IGNORECASE):
        currency = "EUR"
    elif re.search(r"kzt|тг|тенге|₸", text, re.IGNORECASE):
        currency = "KZT"

    # Extract numbers (handle spaces inside numbers like "1 200 000")
    numbers = re.findall(r"\d[\d\s]{2,}\d", text)
    cleaned = []
    for n in numbers:
        val = int(n.replace(" ", ""))
        if val >= 100:   # filter out noise like years
            cleaned.append(val)

    if len(cleaned) >= 2:
        return cleaned[0], cleaned[1], currency
    if len(cleaned) == 1:
        return cleaned[0], None, currency
    return None, None, currency


def _extract_skills(text: str) -> list[str]:
    text_lower = text.lower()
    return [kw for kw in SKILL_KEYWORDS if re.search(r"\b" + re.escape(kw) + r"\b", text_lower)]
