"""Prueba puntual: precios de Sky Airline para 2 adultos + 1 niño.

Abre la página de resultados de skyairline.com para cada fecha, lee la
respuesta de su cotizador (farequoting) y anota cada vuelo con el total del
grupo por tarifa. Deja el resultado en vuelos/diagnostico/.
"""

import json
import sys
from datetime import date, timedelta
from pathlib import Path

SALIDA = Path(__file__).parent / "diagnostico"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
TARIFAS = {"ZO": "Basic", "LT": "Light", "ED": "Standard", "PL": "Max", "MF": "Full"}
MERCADO = "argentina"
URL = (
    "https://initial-sale.skyairline.com/es/{m}?origin={o}&destination={d}"
    "&departureDate={f}&arrivalDate={f}&flightType=OW&ADT=2&CHD=1"
)


def fechas(desde: date, hasta: date) -> list[date]:
    return [desde + timedelta(days=i) for i in range((hasta - desde).days + 1)]


def cotizar(pagina, origen: str, destino: str, dia: date) -> list[dict]:
    with pagina.expect_response(lambda r: "farequoting/v1/search/flight" in r.url, timeout=45000) as info:
        pagina.goto(URL.format(m=MERCADO, o=origen, d=destino, f=dia.isoformat()), wait_until="domcontentloaded")
    datos = info.value.json()
    vuelos = []
    for itinerario in (datos.get("itineraryParts") or [[]])[0]:
        tramo = itinerario["segments"][0]
        vuelos.append({
            "fecha": dia.isoformat(),
            "desde": tramo["origin"],
            "hasta": tramo["destination"],
            "salida": tramo["departure"][11:16],
            "llegada": tramo["arrival"][11:16],
            "vuelo": f"H2 {tramo['flight']['flightNumber']}",
            "tarifas": {TARIFAS.get(f["brandId"], f["brandId"]): round(f["total"]["amount"]) for f in itinerario["fares"]},
            "moneda": itinerario["fares"][0]["total"]["currency"] if itinerario["fares"] else "",
        })
    return vuelos


def main() -> int:
    from playwright.sync_api import sync_playwright

    SALIDA.mkdir(exist_ok=True)
    global MERCADO
    consultas = [("BUE", "SCL", date(2026, 12, 16)), ("SCL", "BUE", date(2027, 1, 27))]
    vuelos, lineas = [], []
    with sync_playwright() as p:
        navegador = p.chromium.launch()
        contexto = navegador.new_context(locale="es-AR", user_agent=UA, viewport={"width": 1366, "height": 900})
        pagina = contexto.new_page()
        for mercado, origen, destino, dia in [(m, *c) for m in ("estados-unidos", "chile", "us", "en/united-states") for c in consultas]:
            MERCADO = mercado
            lineas.append(f"Mercado {mercado}")
            try:
                encontrados = cotizar(pagina, origen, destino, dia)
                vuelos += encontrados
                lineas.append(f"OK {origen}-{destino} {dia}: {len(encontrados)} vuelos")
            except Exception as e:  # noqa: BLE001
                lineas.append(f"FALLO {origen}-{destino} {dia}: {e.__class__.__name__}: {str(e)[:200]}")
                pagina.screenshot(path=str(SALIDA / f"fallo_{mercado.replace('/', '_')}_{origen}.png"))
            pagina.wait_for_timeout(1500)
        try:
            cambio = pagina.request.get(
                "https://api.skyairline.com/exchange-rate/v1/currencies/conversion?currencyFrom=USD&currencyTo=ARS"
            ).text()
        except Exception as e:  # noqa: BLE001
            cambio = f"error {e.__class__.__name__}"
        navegador.close()

    (SALIDA / "sky_vuelos.json").write_text(json.dumps(vuelos, ensure_ascii=False, indent=1), encoding="utf-8")
    lineas.append(f"Tipo de cambio Sky USD→ARS: {cambio[:500]}")
    lineas.append("")
    for v in vuelos:
        precios = " · ".join(f"{k} {n:,}" for k, n in v["tarifas"].items())
        lineas.append(f"{v['fecha']} {v['desde']}→{v['hasta']} {v['salida']}-{v['llegada']} {v['vuelo']} [{v['moneda']}] {precios}")
    texto = "\n".join(lineas)
    (SALIDA / "resultado.txt").write_text(texto, encoding="utf-8")
    print(texto)
    return 0


if __name__ == "__main__":
    sys.exit(main())
