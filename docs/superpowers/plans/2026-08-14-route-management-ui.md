# Lokalny interfejs webowy do zarządzania trasami — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Zastąpić hardkodowaną listę tras w `main.py` plikiem `routes.json` zarządzanym przez lokalny interfejs webowy (Flask), i rozszerzyć definicję trasy o zakres dat, tak by tracker szukał najlepszej ceny w całym okresie zamiast na pojedynczy dzień.

**Architecture:** Wspólny moduł `routes_store.py` czyta/zapisuje `routes.json` i waliduje dane; `app.py` (Flask) używa go do CRUD-a przez formularze HTML; `main.py` używa go do wczytania tras i iteruje po każdym dniu zakresu, wybierając najtańszą ofertę z całego okresu.

**Tech Stack:** Python 3.11, Flask (nowa zależność), Jinja2 (dostarczany przez Flask), `fast_flights` i `requests` (bez zmian).

## Global Constraints

- Trasy przechowywane wyłącznie w `routes.json` w repo — bez bazy danych (spec: poza zakresem).
- Brak automatycznych testów jednostkowych/frameworku testowego — weryfikacja każdego zadania jest ręczna, komendami z dokładnym oczekiwanym wynikiem (spec: sekcja Testowanie).
- Kody lotnisk: dokładnie 3 wielkie litery (`^[A-Z]{3}$`).
- Daty: format `YYYY-MM-DD`, `date_from <= date_to`.
- `max_price`: liczba dodatnia.
- Interfejs webowy służy wyłącznie do CRUD na trasach — nie wyzwala wyszukiwania cen (spec: poza zakresem).
- `.github/workflows/tracker.yml` pozostaje bez zmian.

---

### Task 1: Wspólny moduł przechowywania tras (`routes_store.py`)

**Files:**
- Create: `routes_store.py`
- Create: `routes.json`

**Interfaces:**
- Produces:
  - `load_routes() -> list[dict]`
  - `save_routes(routes: list[dict]) -> None`
  - `validate_route(data: dict) -> dict[str, str]` (puste, gdy dane poprawne; klucze to nazwy pól: `from`, `to`, `date_from`, `date_to`, `max_price`)
  - `add_route(data: dict) -> dict` (zwraca nowo utworzoną trasę z `id`)
  - `get_route(route_id: str) -> dict | None`
  - `update_route(route_id: str, data: dict) -> bool`
  - `delete_route(route_id: str) -> bool`
  - Każda trasa to `dict` z kluczami: `id` (str), `from` (str, 3 wielkie litery), `to` (str, 3 wielkie litery), `date_from` (str `YYYY-MM-DD`), `date_to` (str `YYYY-MM-DD`), `max_price` (float).

- [ ] **Step 1: Utwórz `routes_store.py`**

```python
import json
import os
import re
import uuid
from datetime import datetime

ROUTES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "routes.json")

AIRPORT_RE = re.compile(r"^[A-Z]{3}$")
DATE_FORMAT = "%Y-%m-%d"


def load_routes():
    if not os.path.exists(ROUTES_FILE):
        return []
    with open(ROUTES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_routes(routes):
    with open(ROUTES_FILE, "w", encoding="utf-8") as f:
        json.dump(routes, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _parse_date(value):
    return datetime.strptime(value, DATE_FORMAT)


def validate_route(data):
    """Zwraca słownik {pole: komunikat błędu} - pusty, gdy dane są poprawne."""
    errors = {}

    from_airport = (data.get("from") or "").strip().upper()
    if not AIRPORT_RE.match(from_airport):
        errors["from"] = "Kod lotniska wylotu musi się składać z 3 wielkich liter (np. WAW)."

    to_airport = (data.get("to") or "").strip().upper()
    if not AIRPORT_RE.match(to_airport):
        errors["to"] = "Kod lotniska docelowego musi się składać z 3 wielkich liter (np. BKK)."

    date_from_raw = (data.get("date_from") or "").strip()
    date_to_raw = (data.get("date_to") or "").strip()
    date_from = date_to = None
    try:
        date_from = _parse_date(date_from_raw)
    except ValueError:
        errors["date_from"] = "Data początkowa musi być w formacie YYYY-MM-DD."
    try:
        date_to = _parse_date(date_to_raw)
    except ValueError:
        errors["date_to"] = "Data końcowa musi być w formacie YYYY-MM-DD."

    if date_from and date_to and date_from > date_to:
        errors["date_to"] = "Data końcowa nie może być wcześniejsza niż data początkowa."

    max_price_raw = data.get("max_price")
    try:
        max_price = float(max_price_raw)
        if max_price <= 0:
            errors["max_price"] = "Próg cenowy musi być liczbą większą od zera."
    except (TypeError, ValueError):
        errors["max_price"] = "Próg cenowy musi być liczbą."

    return errors


def _normalize(data):
    return {
        "from": data["from"].strip().upper(),
        "to": data["to"].strip().upper(),
        "date_from": data["date_from"].strip(),
        "date_to": data["date_to"].strip(),
        "max_price": float(data["max_price"]),
    }


def add_route(data):
    routes = load_routes()
    route = {"id": uuid.uuid4().hex[:8]}
    route.update(_normalize(data))
    routes.append(route)
    save_routes(routes)
    return route


def get_route(route_id):
    for route in load_routes():
        if route["id"] == route_id:
            return route
    return None


def update_route(route_id, data):
    routes = load_routes()
    for i, route in enumerate(routes):
        if route["id"] == route_id:
            updated = {"id": route_id}
            updated.update(_normalize(data))
            routes[i] = updated
            save_routes(routes)
            return True
    return False


def delete_route(route_id):
    routes = load_routes()
    remaining = [r for r in routes if r["id"] != route_id]
    if len(remaining) == len(routes):
        return False
    save_routes(remaining)
    return True
```

- [ ] **Step 2: Zweryfikuj walidację ręcznie**

Run:
```bash
python -c "
import routes_store as rs
errors = rs.validate_route({'from': 'waw123', 'to': 'BKK', 'date_from': '2027-01-20', 'date_to': '2027-01-10', 'max_price': '-5'})
print(sorted(errors.keys()))
"
```
Expected output: `['date_to', 'from', 'max_price']`

- [ ] **Step 3: Zweryfikuj pełny cykl CRUD ręcznie (i wyczyść dane testowe)**

Run:
```bash
python -c "
import routes_store as rs

route = rs.add_route({'from': 'waw', 'to': 'bkk', 'date_from': '2027-01-10', 'date_to': '2027-01-12', 'max_price': '500'})
assert route['from'] == 'WAW' and route['max_price'] == 500.0
assert rs.get_route(route['id']) == route

assert rs.update_route(route['id'], {'from': 'krk', 'to': 'bkk', 'date_from': '2027-01-10', 'date_to': '2027-01-12', 'max_price': '450'})
updated = rs.get_route(route['id'])
assert updated['from'] == 'KRK' and updated['max_price'] == 450.0

assert rs.delete_route(route['id'])
assert rs.get_route(route['id']) is None
assert rs.load_routes() == []
print('OK')
"
```
Expected output: `OK`

- [ ] **Step 4: Utwórz pusty `routes.json`**

```bash
echo "[]" > routes.json
```

(Plik powinien już zawierać `[]` po Step 3, ale ten krok gwarantuje spójny stan nawet jeśli Step 3 zostanie pominięty przy ponownym uruchamianiu planu.)

- [ ] **Step 5: Commit**

```bash
git add routes_store.py routes.json
git commit -m "Add routes_store module for CRUD on routes.json"
```

---

### Task 2: Interfejs webowy (`app.py` + szablony)

**Files:**
- Create: `app.py`
- Create: `templates/base.html`
- Create: `templates/routes_list.html`
- Create: `templates/route_form.html`
- Modify: `requirements.txt`

**Interfaces:**
- Consumes: `routes_store.load_routes()`, `routes_store.validate_route(data)`, `routes_store.add_route(data)`, `routes_store.get_route(route_id)`, `routes_store.update_route(route_id, data)`, `routes_store.delete_route(route_id)` (Task 1).
- Produces: Flask app `app` z endpointami `GET /` (widok `routes_list`), `GET/POST /add` (widok `add_route`), `GET/POST /edit/<route_id>` (widok `edit_route`), `POST /delete/<route_id>` (widok `delete_route`).

- [ ] **Step 1: Dodaj Flask do zależności**

Edit `requirements.txt`, dodaj linię:
```
flask>=3.0,<4
```

- [ ] **Step 2: Zainstaluj zależności**

```bash
pip install -r requirements.txt
```
Expected: instalacja kończy się bez błędów, `flask` widoczny w `pip show flask`.

- [ ] **Step 3: Utwórz `templates/base.html`**

```html
<!doctype html>
<html lang="pl">
<head>
  <meta charset="utf-8">
  <title>Rado Loty — trasy</title>
  <style>
    body { font-family: sans-serif; max-width: 700px; margin: 2rem auto; }
    table { border-collapse: collapse; width: 100%; }
    th, td { border: 1px solid #ccc; padding: 0.5rem; text-align: left; }
    .error { color: #b00020; font-size: 0.9em; }
    label { display: block; margin-top: 0.75rem; }
    input { width: 100%; padding: 0.3rem; box-sizing: border-box; }
    .actions { margin-top: 1rem; }
  </style>
</head>
<body>
  <h1>Rado Loty — śledzone trasy</h1>
  {% block content %}{% endblock %}
</body>
</html>
```

- [ ] **Step 4: Utwórz `templates/routes_list.html`**

```html
{% extends "base.html" %}
{% block content %}
  <p><a href="{{ url_for('add_route') }}">Dodaj trasę</a></p>
  {% if routes %}
  <table>
    <tr>
      <th>Z</th><th>Do</th><th>Od daty</th><th>Do daty</th><th>Próg ceny</th><th></th>
    </tr>
    {% for route in routes %}
    <tr>
      <td>{{ route.from }}</td>
      <td>{{ route.to }}</td>
      <td>{{ route.date_from }}</td>
      <td>{{ route.date_to }}</td>
      <td>{{ route.max_price }}</td>
      <td>
        <a href="{{ url_for('edit_route', route_id=route.id) }}">Edytuj</a>
        <form method="post" action="{{ url_for('delete_route', route_id=route.id) }}" style="display:inline">
          <button type="submit" onclick="return confirm('Usunąć trasę {{ route.from }} -> {{ route.to }}?');">Usuń</button>
        </form>
      </td>
    </tr>
    {% endfor %}
  </table>
  {% else %}
  <p>Brak zdefiniowanych tras.</p>
  {% endif %}
{% endblock %}
```

- [ ] **Step 5: Utwórz `templates/route_form.html`**

```html
{% extends "base.html" %}
{% block content %}
  <h2>{{ action }} trasę</h2>
  <form method="post">
    <label>Lotnisko wylotu (kod IATA)
      <input type="text" name="from" value="{{ route.from }}" maxlength="3">
    </label>
    {% if errors.from %}<div class="error">{{ errors.from }}</div>{% endif %}

    <label>Lotnisko docelowe (kod IATA)
      <input type="text" name="to" value="{{ route.to }}" maxlength="3">
    </label>
    {% if errors.to %}<div class="error">{{ errors.to }}</div>{% endif %}

    <label>Data początkowa (YYYY-MM-DD)
      <input type="text" name="date_from" value="{{ route.date_from }}">
    </label>
    {% if errors.date_from %}<div class="error">{{ errors.date_from }}</div>{% endif %}

    <label>Data końcowa (YYYY-MM-DD)
      <input type="text" name="date_to" value="{{ route.date_to }}">
    </label>
    {% if errors.date_to %}<div class="error">{{ errors.date_to }}</div>{% endif %}

    <label>Próg cenowy
      <input type="text" name="max_price" value="{{ route.max_price }}">
    </label>
    {% if errors.max_price %}<div class="error">{{ errors.max_price }}</div>{% endif %}

    <div class="actions">
      <button type="submit">{{ action }}</button>
      <a href="{{ url_for('routes_list') }}">Anuluj</a>
    </div>
  </form>
{% endblock %}
```

- [ ] **Step 6: Utwórz `app.py`**

```python
from flask import Flask, redirect, render_template, request, url_for

import routes_store

app = Flask(__name__)


@app.route("/")
def routes_list():
    routes = routes_store.load_routes()
    return render_template("routes_list.html", routes=routes)


@app.route("/add", methods=["GET", "POST"])
def add_route():
    if request.method == "POST":
        errors = routes_store.validate_route(request.form)
        if errors:
            return render_template("route_form.html", route=request.form, errors=errors, action="Dodaj")
        routes_store.add_route(request.form)
        return redirect(url_for("routes_list"))
    return render_template("route_form.html", route={}, errors={}, action="Dodaj")


@app.route("/edit/<route_id>", methods=["GET", "POST"])
def edit_route(route_id):
    route = routes_store.get_route(route_id)
    if route is None:
        return redirect(url_for("routes_list"))
    if request.method == "POST":
        errors = routes_store.validate_route(request.form)
        if errors:
            return render_template("route_form.html", route=request.form, errors=errors, action="Zapisz")
        routes_store.update_route(route_id, request.form)
        return redirect(url_for("routes_list"))
    return render_template("route_form.html", route=route, errors={}, action="Zapisz")


@app.route("/delete/<route_id>", methods=["POST"])
def delete_route(route_id):
    routes_store.delete_route(route_id)
    return redirect(url_for("routes_list"))


if __name__ == "__main__":
    app.run(debug=True)
```

- [ ] **Step 7: Zweryfikuj CRUD end-to-end przez curl (bez potrzeby przeglądarki)**

Uruchom serwer w tle:
```bash
python app.py &
sleep 1
curl -s http://127.0.0.1:5000/ | grep "Brak zdefiniowanych tras"
```
Expected: linia zawierająca `Brak zdefiniowanych tras` (routes.json jest puste z Task 1).

Dodaj trasę:
```bash
curl -s -X POST http://127.0.0.1:5000/add \
  -d "from=waw&to=bkk&date_from=2027-01-10&date_to=2027-01-12&max_price=500" -L \
  | grep -E "WAW|BKK"
cat routes.json
```
Expected: strona listy zawiera `WAW` i `BKK`; `routes.json` zawiera jeden wpis z `"from": "WAW"`, `"to": "BKK"`, `"max_price": 500.0` i wygenerowanym `id`.

Edytuj i usuń (podmień `<ID>` na wartość `id` z `routes.json`):
```bash
ROUTE_ID=$(python -c "import routes_store as rs; print(rs.load_routes()[0]['id'])")
curl -s -X POST "http://127.0.0.1:5000/edit/$ROUTE_ID" \
  -d "from=krk&to=bkk&date_from=2027-01-10&date_to=2027-01-12&max_price=450" -L \
  | grep "KRK"
curl -s -X POST "http://127.0.0.1:5000/delete/$ROUTE_ID" -L | grep "Brak zdefiniowanych tras"
cat routes.json
```
Expected: po edycji strona zawiera `KRK`; po usunięciu strona ponownie zawiera `Brak zdefiniowanych tras`; `routes.json` zawiera `[]`.

Zatrzymaj serwer:
```bash
kill %1
```

- [ ] **Step 8: Commit**

```bash
git add app.py templates/ requirements.txt
git commit -m "Add local Flask UI for CRUD on tracked routes"
```

---

### Task 3: `main.py` — wczytywanie z `routes.json` i wyszukiwanie w zakresie dat

**Files:**
- Modify: `main.py`

**Interfaces:**
- Consumes: `routes_store.load_routes() -> list[dict]` (Task 1).
- Produces: `_date_range(date_from: str, date_to: str) -> list[str]`, `_cheapest_for_date(route: dict, date: str) -> Flight | None`, `check_route(route: dict) -> tuple[str, Flight] | None` (rzuca `RuntimeError` gdy wszystkie dni w zakresie zawiodły), `check_prices() -> None`.

- [ ] **Step 1: Zastąp zawartość `main.py`**

```python
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
        label = f"{route['from']}-{route['to']}"
        try:
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
```

- [ ] **Step 2: Zweryfikuj `_date_range` ręcznie**

```bash
python -c "
import main
assert main._date_range('2027-01-10', '2027-01-12') == ['2027-01-10', '2027-01-11', '2027-01-12']
assert main._date_range('2027-01-10', '2027-01-10') == ['2027-01-10']
print('OK')
"
```
Expected output: `OK`

- [ ] **Step 3: Zweryfikuj wybór najlepszej oferty z zakresu (bez sieci, przez podmianę `_cheapest_for_date`)**

```bash
python -c "
import main

class FakeFlight:
    def __init__(self, price, airlines):
        self.price = price
        self.airlines = airlines

fake_prices = {
    '2027-01-10': FakeFlight(700, ['LOT']),
    '2027-01-11': FakeFlight(550, ['Ryanair']),
    '2027-01-12': FakeFlight(600, ['LOT']),
}

def fake_cheapest(route, date):
    return fake_prices[date]

main._cheapest_for_date = fake_cheapest

route = {'from': 'WAW', 'to': 'BKK', 'date_from': '2027-01-10', 'date_to': '2027-01-12', 'max_price': 600}
best_date, flight = main.check_route(route)
assert best_date == '2027-01-11', best_date
assert flight.price == 550, flight.price
print('OK')
"
```
Expected output: `OK`

- [ ] **Step 4: Zweryfikuj odporność na błąd pojedynczego dnia**

```bash
python -c "
import main

class FakeFlight:
    def __init__(self, price, airlines):
        self.price = price
        self.airlines = airlines

def fake_partial(route, date):
    if date == '2027-01-10':
        raise RuntimeError('network blip')
    return FakeFlight(500, ['LOT'])

main._cheapest_for_date = fake_partial
route = {'from': 'WAW', 'to': 'BKK', 'date_from': '2027-01-10', 'date_to': '2027-01-11', 'max_price': 600}
best_date, flight = main.check_route(route)
assert best_date == '2027-01-11', best_date
assert flight.price == 500
print('OK')
"
```
Expected output: `OK`

- [ ] **Step 5: Zweryfikuj, że trasa zawodzi tylko gdy WSZYSTKIE dni zawiodły**

```bash
python -c "
import main

def fake_fail(route, date):
    raise RuntimeError('boom')

main._cheapest_for_date = fake_fail
route = {'from': 'WAW', 'to': 'BKK', 'date_from': '2027-01-10', 'date_to': '2027-01-11', 'max_price': 600}
try:
    main.check_route(route)
    raise SystemExit('expected RuntimeError not raised')
except RuntimeError as e:
    print('OK:', e)
"
```
Expected output zaczyna się od `OK:`

- [ ] **Step 6: Commit**

```bash
git add main.py
git commit -m "Search best price across a date range instead of a single date"
```

---

### Task 4: Dokumentacja (`README`)

**Files:**
- Modify: `README`

**Interfaces:**
- Consumes: nic (dokumentacja).
- Produces: nic (dokumentacja).

- [ ] **Step 1: Zastąp zawartość `README`**

```markdown
# Rado Loty — Flight Price Tracker

Codzienny tracker cen lotów: sprawdza zdefiniowane trasy na Google Flights
i wysyła alert na Telegram, gdy najlepsza cena znaleziona w danym okresie
spadnie poniżej ustawionego progu.

## Konfiguracja tras

Trasy są przechowywane w `routes.json` i zarządzane przez lokalny interfejs
webowy:

```bash
pip install -r requirements.txt
python app.py
```

Otwórz `http://127.0.0.1:5000` w przeglądarce, dodaj/edytuj/usuń trasy
(lotnisko wylotu, lotnisko docelowe, zakres dat, próg cenowy). Zmiany trafiają
od razu do `routes.json` — po zakończeniu edycji zacommituj i wypushuj plik,
żeby zaczął go używać workflow uruchamiany na GitHub Actions:

```bash
git add routes.json
git commit -m "Update tracked routes"
git push
```

Uwaga: im dłuższy zakres dat dla trasy, tym więcej zapytań do Google Flights
(jedno na każdy dzień) — dłuższy czas działania i większe ryzyko throttlingu.

## Uruchamianie trackera

Tracker (`main.py`) jest uruchamiany automatycznie codziennie o 08:00 UTC
przez GitHub Actions (`.github/workflows/tracker.yml`), a także ręcznie z
zakładki Actions na GitHubie. Wymaga sekretów repozytorium:
`TELEGRAM_TOKEN` i `TELEGRAM_CHAT_ID`.

Można go też uruchomić lokalnie:

```bash
python main.py
```

Bez ustawionych zmiennych `TELEGRAM_TOKEN`/`TELEGRAM_CHAT_ID` alerty są
wypisywane w konsoli zamiast wysyłane na Telegram.
```

- [ ] **Step 2: Commit**

```bash
git add README
git commit -m "Document route management UI and tracker usage"
```
