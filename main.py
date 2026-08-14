import os
import requests
from fast_flights import FlightData, Passengers, str_to_date, get_flights

# ---------------------------------------------------------------------------
# CONFIGURATION - Ustaw swoje trasy i budżet
# ---------------------------------------------------------------------------
# Słownik z trasami, które chcesz śledzić:
# Klucz: "Skąd-Dokąd", Wartość: max cena (w EUR/PLN)
TARGET_ROUTES = [
    {
        "from": "LUX",         # Kod lotniska wylotu (np. LUX, WAW, CRL)
        "to": "BKK",           # Kod lotniska docelowego (np. BKK)
        "date": "2027-01-15",   # Data wylotu (YYYY-MM-DD)
        "max_price": 600       # Maksymalna cena, poniżej której chcesz alert
    }
]
CURRENCY = "EUR" # Waluta (np. EUR, PLN)
# ---------------------------------------------------------------------------

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram_msg(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Brak tokenu Telegram! Wiadomość wypisana w konsoli:")
        print(message)
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    requests.post(url, json=payload)

def check_prices():
    alerts = []
    
    for route in TARGET_ROUTES:
        try:
            print(f"Sprawdzam trasę: {route['from']} -> {route['to']} na dzień {route['date']}...")
            
            result = get_flights(
                flight_data=[
                    FlightData(
                        date=route['date'],
                        from_airport=route['from'],
                        to_airport=route['to']
                    )
                ],
                trip="one-way",
                seat="economy",
                passengers=Passengers(adults=1),
                currency=CURRENCY
            )
            
            if not result.flights:
                print("Nie znaleziono lotów dla tej trasy.")
                continue

            # Pobieramy najtańszy lot
            cheapest = result.flights[0]
            price = float(cheapest.price.replace(" ", "").replace("€", "").replace("zł", "").replace(",", "."))
            
            print(f"Najniższa znaleziona cena: {price} {CURRENCY}")
            
            if price <= route['max_price']:
                msg = (
                    f"✈️ *OKAZJA LOTNICZA!*\n\n"
                    f"📍 **Trasa:** {route['from']} ➔ {route['to']}\n"
                    f"📅 **Data:** {route['date']}\n"
                    f"💰 **Cena:** *{price} {CURRENCY}* (Próg: {route['max_price']} {CURRENCY})\n"
                    f"🔗 [Otwórz Google Flights](https://www.google.com/travel/flights)"
                )
                alerts.append(msg)
                
        except Exception as e:
            print(f"Błąd podczas sprawdzania trasy {route['from']}-{route['to']}: {e}")

    if alerts:
        for alert in alerts:
            send_telegram_msg(alert)
    else:
        print("Brak lotów spełniających kryteria cenowe.")

if __name__ == "__main__":
    check_prices()
