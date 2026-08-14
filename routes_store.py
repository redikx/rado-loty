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
