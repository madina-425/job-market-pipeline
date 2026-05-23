"""
src/utils/currency.py
Converts salary values to USD using live or cached exchange rates.
Falls back to hardcoded approximate rates if the API is unreachable.
"""
import os
from functools import lru_cache

import requests

from src.utils.logger import get_logger

log = get_logger(__name__)

# Fallback rates relative to USD (needs to periodically update in code)
FALLBACK_RATES: dict[str, float] = {
    "KZT": 450.0,   # KZ tenge
    "RUB": 90.0,    # RS ruble
    "USD": 1.0,
    "EUR": 0.92,
    "UAH": 38.0,
}


@lru_cache(maxsize=1)
def get_rates() -> dict[str, float]:
    """Fetch rates once per process from exchangerate-api.com."""
    api_key = os.environ.get("EXCHANGE_RATE_API_KEY", "")
    if not api_key:
        log.warning("No EXCHANGE_RATE_API_KEY — using fallback rates")
        return FALLBACK_RATES
    try:
        url = f"https://v6.exchangerate-api.com/v6/{api_key}/latest/USD"
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        log.info("Exchange rates fetched from API")
        return data["conversion_rates"]
    except Exception as exc:
        log.error("Exchange rate fetch failed: %s — using fallback", exc)
        return FALLBACK_RATES


def to_usd(amount: float | None, currency: str | None) -> float | None:
    """Convert *amount* in *currency* to USD. Returns None if conversion impossible."""
    if amount is None or currency is None:
        return None
    currency = currency.upper().strip()
    rates = get_rates()
    if currency not in rates:
        log.debug("Unknown currency %s", currency)
        return None
    return round(amount / rates[currency], 2)

def to_kzt(amount_usd: float | None) -> float | None:
    """Конвертирует USD → KZT."""
    if amount_usd is None:
        return None
    rates = get_rates()
    kzt_rate = rates.get("KZT", FALLBACK_RATES["KZT"])
    return round(amount_usd * kzt_rate, 0)