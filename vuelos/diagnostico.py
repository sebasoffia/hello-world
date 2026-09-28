"""Diagnóstico: consulta una fecha y muestra qué se logra leer de Google."""
import sys
import traceback
from pathlib import Path

from fast_flights import FlightQuery, Passengers, create_query, fetch_flights_html

sys.path.insert(0, str(Path(__file__).parent))
from buscar_vuelos import extraer_vuelos  # noqa: E402

VARIANTES = {
    "con_carry_on": dict(carry_on_bags=1),
    "sin_equipaje": dict(),
}

for nombre, kw in VARIANTES.items():
    print(f"\n===== {nombre} =====")
    q = create_query(
        flights=[FlightQuery(date="2026-12-10", from_airport="AEP", to_airport="SCL")],
        trip="one-way", currency="USD", language="es", max_stops=0,
        passengers=Passengers(adults=2, children=1), **kw,
    )
    print("URL:", q.url())
    try:
        vuelos, sin_precio = extraer_vuelos(fetch_flights_html(q))
        print(f"vuelos con precio: {len(vuelos)} | omitidos sin precio: {sin_precio}")
        for v in vuelos:
            print("  ", v)
    except Exception:
        traceback.print_exc()
