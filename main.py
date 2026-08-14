import os
import sys
from datetime import datetime, timedelta

import requests
from fast_flights import FlightQuery, Passengers, create_query, get_flights

import routes_store

CURRENCY = "EUR"

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

DATE_FORMAT = "%Y-%m-%d"


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


def _date_range(date_from, date_to):
    start = datetime.strptime(date_from, DATE_FORMAT)
    end = datetime.strptime(date_to, DATE_FORMAT)
    days = (end - start).days
    return [(start + timedelta(days=i)).strftime(DATE_FORMAT) for i in range(days + 1)]


def _cheapest_for_date(route, date):
    query = create_query(
        flights=[
            FlightQuery(
                date=date,
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


def check_route(route):
    """Zwraca (data, najtanszy_lot) dla najlepszej ceny w calym zakresie dat, albo None."""
    best_date = None
    best_flight = None
    any_success = False

    for date in _date_range(route["date_from"], route["date_to"]):
        try:
            flight = _cheapest_for_date(route, date)
            any_success = True
        except Exception as e:
            print(f"Blad podczas sprawdzania dnia {date}: {type(e).__name__}: {e}")
            continue

        if flight is None:
            continue
        if best_flight is None or flight.price < best_flight.price:
            best_date = date
            best_flight = flight

    if not any_success:
        raise RuntimeError(
            f"Wszystkie dni w zakresie {route['date_from']}..{route['date_to']} zawiodly."
        )

    if best_flight is None:
        return None
    return best_date, best_flight


def check_prices():
    alerts = []
    failures = []

    for route in routes_store.load_routes():
        try:
            label = f"{route.get('from', '?')}-{route.get('to', '?')}"
            print(
                f"Sprawdzam trase: {route['from']} -> {route['to']} "
                f"w okresie {route['date_from']}..{route['date_to']}..."
            )

            result = check_route(route)
            if result is None:
                print("Nie znaleziono lotow dla tej trasy.")
                continue

            best_date, cheapest = result
            price = cheapest.price
            airlines = ", ".join(cheapest.airlines) if cheapest.airlines else "?"
            print(f"Najnizsza znaleziona cena: {price} {CURRENCY} ({airlines}) w dniu {best_date}")

            if price <= route["max_price"]:
                msg = (
                    f"✈️ *OKAZJA LOTNICZA!*\n\n"
                    f"*Trasa:* {route['from']} -> {route['to']}\n"
                    f"*Data:* {best_date}\n"
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
