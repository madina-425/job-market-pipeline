import os
api_key = os.environ.get("EXCHANGE_RATE_API_KEY", "")
from src.utils.currency import get_rates, to_usd

rates = get_rates()
print("KZT rate:", rates.get("KZT"))   # должно быть ~450-480
print("RUB rate:", rates.get("RUB"))

# тест конвертации
print(to_usd(500_000, "KZT"))   # ~1100 USD
print(to_usd(2000, "USD"))      # 2000.0
print(to_usd(None, "KZT"))     # None