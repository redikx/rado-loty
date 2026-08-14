import os
import sys
import requests
from fast_flights import FlightQuery, Passengers, create_query, get_flights

# ---------------------------------------------------------------------------
# CONFIGURATION - Ustaw swoje trasy i budżet
# ---------------------------------------------------------------------------
TARGET_ROUTES = [
    {
        "from": "LUX",          # Kod lotniska wylotu (np. LUX, HHN, CRL, BRU, WAW)
        "to": "BKK",            # Kod lotniska docelowego
        "date": "2027-01-15",   # Data wylotu (YYYY-MM-DD)
        "max_price": 600,       # Prog, ponizej ktorego chcesz alert
    }
]
CURRENCY = "EUR"
# ---------------------------------------------------------------------------

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def send_telegram_msg(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Brak tokenu Telegram! Wiadomosc wypisana w konsoli:")
        print(message)
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
    }
    response = requests.post(url, json=payload, timeout=30)
    if not response.ok:
        print(f"Telegram odrzucil wiadomosc: {response.status_code} {response.text}")


def check_route(route):
    """Zwraca najtanszy lot dla trasy albo None."""
    query = create_query(
        flights=[
            FlightQuery(
                date=route["date"],
                from_airport=route["from"],
                to_airport=route["to"],
            )
        ],
        trip="one-way",
        seat="economy",
        passengers=Passengers(adults=1),
        currency=CURRENCY,
    )

    # W 3.x wynik jest lista obiektow Flights - nie ma atrybutu .flights
    results = get_flights(query)
    if not results:
        return None

    # Kolejnosc zwracana przez Google to "najlepsze", nie "najtansze"
    return min(results, key=lambda f: f.price)


def check_prices():
    alerts = []
    failures = []

    for route in TARGET_ROUTES:
        label = f"{route['from']}-{route['to']}"
        try:
            print(f"Sprawdzam trase: {route['from']} -> {route['to']} na dzien {route['date']}...")

            cheapest = check_route(route)
            if cheapest is None:
                print("Nie znaleziono lotow dla tej trasy.")
                continue

            # price jest teraz liczba calkowita - zadnego parsowania stringow
            price = cheapest.price
            airlines = ", ".join(cheapest.airlines) if cheapest.airlines else "?"
            print(f"Najnizsza znaleziona cena: {price} {CURRENCY} ({airlines})")

            if price <= route["max_price"]:
                msg = (
                    f"\u2708\ufe0f *OKAZJA LOTNICZA!*\n\n"
                    f"*Trasa:* {route['from']} -> {route['to']}\n"
                    f"*Data:* {route['date']}\n"
                    f"*Przewoznik:* {airlines}\n"
                    f"*Cena:* {price} {CURRENCY} (prog: {route['max_price']} {CURRENCY})\n"
                    f"[Otworz Google Flights](https://www.google.com/travel/flights)"
                )
                alerts.append(msg)

        except Exception as e:
            print(f"Blad podczas sprawdzania trasy {label}: {type(e).__name__}: {e}")
            failures.append(label)

    for alert in alerts:
        send_telegram_msg(alert)

    if not alerts:
        print("Brak lotow spelniajacych kryteria cenowe.")

    # Cichy blad w cronie jest gorszy niz brak alertu - niech workflow sie wywali
    if failures:
        print(f"\nNiepowodzenia na trasach: {', '.join(failures)}")
        sys.exit(1)


if __name__ == "__main__":
    check_prices()
