"""Diagnóstico: prueba variantes de consulta y muestra qué devuelve Google."""
import traceback

from fast_flights import FlightQuery, Passengers, create_query, fetch_flights_html
from fast_flights.parser import parse
from selectolax.lexbor import LexborHTMLParser

VARIANTES = {
    "completa": dict(currency="USD", language="es", max_stops=0, carry_on_bags=1, passengers=Passengers(adults=2, children=1)),
    "sin_equipaje": dict(currency="USD", language="es", max_stops=0, passengers=Passengers(adults=2, children=1)),
    "1_adulto_en": dict(currency="USD", language="en", passengers=Passengers(adults=1)),
    "minima": dict(),
}

for nombre, kw in VARIANTES.items():
    print(f"\n===== {nombre} =====")
    q = create_query(flights=[FlightQuery(date="2026-12-10", from_airport="AEP", to_airport="SCL")], trip="one-way", **kw)
    print("URL:", q.url())
    try:
        html = fetch_flights_html(q)
        doc = LexborHTMLParser(html)
        titulo = doc.css_first("title")
        print("largo html:", len(html), "| título:", titulo.text() if titulo else None)
        script = doc.css_first(r"script.ds\:1")
        print("script ds:1:", bool(script))
        if script:
            print("inicio script:", script.text()[:600])
        else:
            print("inicio html:", html[:800])
        r = parse(html)
        print("vuelos:", len(r), [(f.airlines, f.price) for f in r[:5]])
    except Exception:
        traceback.print_exc()
