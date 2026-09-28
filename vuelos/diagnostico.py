"""Diagnóstico: abre Google Flights con un navegador real y muestra qué se ve."""
from fast_flights import FlightQuery, Passengers, create_query
from playwright.sync_api import sync_playwright

q = create_query(
    flights=[FlightQuery(date="2026-12-10", from_airport="AEP", to_airport="SCL")],
    trip="one-way", currency="USD", language="en", max_stops=0,
    passengers=Passengers(adults=2, children=1), carry_on_bags=1,
)
print("URL:", q.url())
with sync_playwright() as p:
    nav = p.chromium.launch()
    pagina = nav.new_page(locale="en-US")
    pagina.goto(q.url(), wait_until="domcontentloaded")
    try:
        pagina.wait_for_selector('[aria-label*="US dollars"]', timeout=30000)
    except Exception as e:
        print("no aparecieron precios:", e)
    pagina.wait_for_timeout(3000)
    print("título:", pagina.title())
    etiquetas = pagina.eval_on_selector_all('[aria-label*="US dollars"]', "els => els.map(e => e.getAttribute('aria-label'))")
    print("etiquetas con precio:", len(etiquetas))
    for t in etiquetas[:12]:
        print("  -", t)
    pagina.screenshot(path="vuelos/diagnostico.png", full_page=True)
    nav.close()
