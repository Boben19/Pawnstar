from decimal import Decimal
import requests

from django.utils import timezone

from .models import Currency, ExchangeRate


def fetch_php_rate(currency_code):
    code = currency_code.upper().strip()

    if code == "PHP":
        return Decimal("1")

    url = f"https://api.frankfurter.dev/v2/rate/{code}/PHP"

    response = requests.get(url, timeout=10)
    response.raise_for_status()

    data = response.json()
    rate = Decimal(str(data["rate"]))

    if rate <= 0:
        raise ValueError("Invalid exchange rate")

    return rate


def update_currency_rate(currency):
    rate = fetch_php_rate(currency.code)

    ExchangeRate.objects.update_or_create(
        currency=currency,
        effective_date=timezone.localdate(),
        defaults={"rate_to_php": rate},
    )

    return rate