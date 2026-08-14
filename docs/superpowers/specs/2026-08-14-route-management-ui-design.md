# Lokalny interfejs webowy do zarządzania trasami

Data: 2026-08-14

## Cel

Obecnie trasy do śledzenia (lotnisko wylotu, lotnisko docelowe, data, próg cenowy) są
zdefiniowane jako hardkodowana stała `TARGET_ROUTES` w `main.py`. Celem jest dodanie
lokalnego interfejsu webowego, w którym można dodawać/edytować/usuwać trasy, oraz
rozszerzenie definicji trasy o **zakres dat** zamiast pojedynczej daty — tak, by tracker
wyszukiwał najlepszą (najtańszą) okazję cenową w danym okresie na dane połączenie.

## Zakres

- Lokalny interfejs webowy (Flask) do zarządzania listą tras — tylko CRUD, bez
  wyzwalania wyszukiwania cen z poziomu UI.
- Trasy przechowywane w pliku `routes.json` w repo (bez bazy danych).
- `main.py` zmieniony tak, by czytał trasy z `routes.json` i dla trasy z zakresem dat
  sprawdzał **każdy dzień z osobna**, alarmując o najlepszej cenie znalezionej w całym
  zakresie.
- GitHub Actions workflow (`tracker.yml`) bez zmian — dalej odpala `main.py` wg
  harmonogramu, teraz czytającego `routes.json`.

## Poza zakresem

- Hosting w chmurze / stały URL dostępny zdalnie.
- Baza danych.
- Wyzwalanie wyszukiwania na żądanie z poziomu UI.
- Automatyczne testy jednostkowe (projekt obecnie ich nie ma).

## Struktura plików

```
rado-loty/
├── app.py                 # nowy — serwer Flask, CRUD na trasach
├── routes.json             # nowy — lista tras (zastępuje TARGET_ROUTES)
├── templates/
│   ├── base.html           # nowy — wspólny layout
│   ├── routes_list.html    # nowy — lista tras + linki edytuj/usuń
│   └── route_form.html     # nowy — formularz dodaj/edytuj (wspólny)
├── main.py                 # zmieniony — czyta routes.json, obsługuje zakres dat
├── requirements.txt        # zmieniony — dodany flask
└── .github/workflows/tracker.yml   # bez zmian
```

## Model danych (`routes.json`)

```json
[
  {
    "id": "a1b2c3",
    "from": "LUX",
    "to": "BKK",
    "date_from": "2027-01-10",
    "date_to": "2027-01-20",
    "max_price": 600
  }
]
```

- `id` — krótki losowy identyfikator (np. `uuid4().hex[:8]`), generowany przy dodaniu
  trasy, używany do edycji/usuwania konkretnego wpisu.
- `date_from` / `date_to` zastępują dawne pojedyncze pole `date`. Walidacja:
  `date_from <= date_to`, oba w formacie `YYYY-MM-DD`.
- `from` / `to` — kody lotnisk, 3 wielkie litery.
- `max_price` — liczba dodatnia.
- Jeśli `routes.json` nie istnieje przy pierwszym uruchomieniu `app.py`, tworzona jest
  pusta lista `[]`.
- Plik jest czytany i zapisywany bezpośrednio (bez blokad/współbieżności) — wystarczające
  dla pojedynczego użytkownika edytującego kilka/kilkanaście tras lokalnie.

## Interfejs webowy (`app.py`)

Trasy CRUD, brak logiki wyszukiwania cen w serwerze webowym:

- `GET /` — lista tras z `routes.json` w tabeli (from, to, zakres dat, max_price) +
  przyciski "Edytuj" / "Usuń" przy każdej, i link "Dodaj trasę" u góry.
- `GET/POST /add` — formularz dodania trasy; POST waliduje dane i dopisuje nowy wpis do
  `routes.json`, potem przekierowuje na `/`.
- `GET/POST /edit/<id>` — formularz wypełniony danymi istniejącej trasy; POST nadpisuje
  wpis o danym `id` w `routes.json`.
- `POST /delete/<id>` — usuwa wpis o danym `id` z `routes.json`, przekierowuje na `/`.

Walidacja po stronie serwera (kody lotnisk, format dat, `date_from <= date_to`,
`max_price > 0`); błędy wyświetlane nad formularzem bez zapisu do pliku.

## Zmiany w `main.py`

- Nowa funkcja `load_routes()` czyta `routes.json` zamiast korzystać ze stałej
  `TARGET_ROUTES`. Brak pliku lub pusta lista → log informacyjny i czyste zakończenie
  (nie traktowane jako błąd).
- `check_route(route)` iteruje po każdym dniu od `date_from` do `date_to` włącznie,
  wywołując zapytanie do `fast_flights` osobno dla każdej daty, i zbiera najtańszą
  ofertę wraz z datą, dla której została znaleziona (`min` po cenie po wszystkich dniach
  i wszystkich wynikach z każdego dnia).
- Wiadomość alertu wysyłana na Telegram zyskuje pole `*Data:*` ustawione na konkretny
  dzień, w którym znaleziono najlepszą cenę (nie na cały zakres).
- Reszta logiki bez zmian: próg ceny (`max_price`), wysyłka przez Telegram, zbieranie
  `failures`, `sys.exit(1)` gdy którakolwiek trasa się w całości nie powiodła.

## Obsługa błędów

- Pojedynczy nieudany dzień w zakresie dat (np. przejściowy błąd sieci/scrapingu) nie
  przerywa sprawdzania całej trasy — błąd per-dzień jest łapany i logowany, a pozostałe
  dni w zakresie są sprawdzane dalej.
- Trasa trafia do listy `failures` (i finalnie do `sys.exit(1)`) tylko wtedy, gdy
  **wszystkie** dni w jej zakresie się nie powiodły.
- Dłuższe zakresy dat oznaczają więcej zapytań do Google Flights, dłuższy czas działania
  workflow i większe ryzyko throttlingu ze strony Google — świadomie zaakceptowane
  ograniczenie, warte wzmianki w README.

## Testowanie

Brak automatycznych testów jednostkowych w projekcie obecnie — nie wprowadzamy nowego
frameworku testowego w ramach tej zmiany. Weryfikacja ręczna:

- `python app.py` lokalnie: dodanie, edycja i usunięcie trasy przez przeglądarkę,
  sprawdzenie zawartości `routes.json` po każdej operacji.
- `python main.py` lokalnie z przykładowym `routes.json` zawierającym krótki zakres dat
  (np. 2 dni), żeby zweryfikować poprawność pętli po datach i wyboru najlepszej oferty
  oraz treści alertu.
