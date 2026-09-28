"""Diagnóstico: muestra la estructura cruda que devuelve Google Flights."""
import json
import re

from fast_flights import FlightQuery, Passengers, create_query, fetch_flights_html
from selectolax.lexbor import LexborHTMLParser

q = create_query(
    flights=[FlightQuery(date="2026-12-10", from_airport="AEP", to_airport="SCL")],
    trip="one-way", currency="USD", language="es", max_stops=0,
    passengers=Passengers(adults=2, children=1),
)
html = fetch_flights_html(q)
doc = LexborHTMLParser(html)
print("scripts ds:", [s.attributes.get("class") for s in doc.css("script") if (s.attributes.get("class") or "").startswith("ds:")])
datos = doc.css_first(r"script.ds\:1").text().split("data:", 1)[1].rsplit(",", 1)[0]
payload = json.loads(datos)
print("largo payload:", len(payload))
for i, sec in enumerate(payload):
    print(f"--- payload[{i}] ({type(sec).__name__}):", json.dumps(sec, ensure_ascii=False)[:400])
for seccion in (2, 3):
    bloque = payload[seccion]
    for n, k in enumerate((bloque[0] if bloque and bloque[0] else [])[:3]):
        print(f"\n### seccion {seccion} vuelo {n}: len(k)={len(k)}")
        print("k[0][:2]:", json.dumps(k[0][:2], ensure_ascii=False))
        for j, parte in enumerate(k[1:], 1):
            print(f"k[{j}]:", json.dumps(parte, ensure_ascii=False)[:300])
print("\nmontos con US$ en html:", re.findall(r"US\$\s?[\d.,]+", html)[:20])
print("aria-label con precio:", re.findall(r'aria-label="[^"]{0,120}(?:dólares|USD)[^"]{0,80}"', html)[:5])
