"""Prueba puntual: ¿se pueden leer los precios de Sky Airline?

1. Google Flights: lista todos los vuelos directos (con y sin precio) de las
   fechas recomendadas, para ver si Sky aparece y en qué horarios.
2. skyairline.com: abre el sitio, registra las llamadas a su API y guarda
   capturas, para ver si se puede automatizar la búsqueda.

Deja todo en vuelos/diagnostico/.
"""

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from buscar_vuelos import url_busqueda  # noqa: E402

SALIDA = Path(__file__).parent / "diagnostico"
FECHAS = [
    ("AEP", "SCL", date(2026, 12, 15)),
    ("AEP", "SCL", date(2026, 12, 16)),
    ("AEP", "SCL", date(2026, 12, 17)),
    ("SCL", "AEP", date(2027, 1, 27)),
    ("SCL", "AEP", date(2027, 2, 3)),
]
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)


def google_flights(pagina) -> list[str]:
    lineas = []
    for origen, destino, dia in FECHAS:
        pagina.goto(url_busqueda(origen, destino, dia), wait_until="domcontentloaded")
        try:
            pagina.wait_for_selector('[aria-label*="flight with"]', timeout=25000)
        except Exception as e:  # noqa: BLE001
            lineas.append(f"## {origen}-{destino} {dia}: sin resultados ({e.__class__.__name__})")
            continue
        pagina.wait_for_timeout(2000)
        etiquetas = pagina.eval_on_selector_all(
            '[aria-label*="flight with"]', "els => els.map(e => e.getAttribute('aria-label'))"
        )
        lineas.append(f"## {origen}-{destino} {dia}: {len(etiquetas)} vuelos")
        for et in dict.fromkeys(etiquetas):
            marca = "SKY " if "sky" in et.lower() else "    "
            lineas.append(f"{marca}{et[:260]}")
    return lineas


def sitio_sky(contexto) -> list[str]:
    lineas = []
    llamadas = []

    def registrar(resp):
        tipo = resp.headers.get("content-type", "")
        if "json" in tipo or "/api" in resp.url:
            llamadas.append(f"{resp.status} {resp.request.method} {resp.url[:300]}")

    pagina = contexto.new_page()
    pagina.on("response", registrar)
    for url in ("https://www.skyairline.com/argentina", "https://www.skyairline.com/chile"):
        try:
            r = pagina.goto(url, wait_until="domcontentloaded", timeout=45000)
            pagina.wait_for_timeout(8000)
            nombre = url.rsplit("/", 1)[-1]
            pagina.screenshot(path=str(SALIDA / f"sky_{nombre}.png"), full_page=False)
            lineas.append(f"## {url}: HTTP {r.status if r else '?'} · título: {pagina.title()!r}")
            texto = pagina.inner_text("body")[:1500].replace("\n", " | ")
            lineas.append(f"Texto: {texto}")
            controles = pagina.eval_on_selector_all(
                "input, button, select, [role=combobox]",
                "els => els.slice(0, 60).map(e => [e.tagName, e.type || '', e.name || '', e.id || '',"
                " e.getAttribute('placeholder') || '', e.getAttribute('aria-label') || '',"
                " (e.innerText || '').slice(0, 40)].join(' · '))",
            )
            lineas.append("Controles:")
            lineas += [f"  {c}" for c in controles]
        except Exception as e:  # noqa: BLE001
            lineas.append(f"## {url}: error {e.__class__.__name__}: {str(e)[:300]}")
    lineas.append("## Llamadas JSON/API")
    lineas += llamadas[:150]
    return lineas


def busqueda_sky(contexto) -> list[str]:
    """Llena el formulario de Sky (solo ida AEP→SCL) y registra qué API responde."""
    lineas = []
    cuerpos = []

    def registrar(resp):
        url = resp.url
        if "skyairline.com" in url and "butter-cache" not in url and "feature" not in url:
            linea = f"{resp.status} {resp.request.method} {url[:300]}"
            lineas.append("  API " + linea)
            if not url.endswith(".js") and (resp.request.method == "POST" or any(k in url.lower() for k in ("avail", "flight", "search", "fare", "offer"))):
                try:
                    cuerpos.append(f"### {linea}\nPETICION: {(resp.request.post_data or '')[:2000]}\nRESPUESTA: {resp.text()[:60000]}")
                except Exception:  # noqa: BLE001
                    pass

    contexto.on("response", registrar)
    pagina = contexto.new_page()

    def paso(nombre, accion):
        try:
            accion()
            pagina.wait_for_timeout(1500)
            lineas.append(f"OK {nombre}")
        except Exception as e:  # noqa: BLE001
            lineas.append(f"FALLO {nombre}: {e.__class__.__name__}: {str(e)[:200]}")
        pagina.screenshot(path=str(SALIDA / f"paso_{nombre}.png"))

    pagina.goto("https://www.skyairline.com/argentina", wait_until="domcontentloaded", timeout=45000)
    pagina.wait_for_timeout(6000)
    paso("cerrar_aviso", lambda: pagina.get_by_text("Continuar en SKY Argentina").click(timeout=8000))
    paso("solo_ida", lambda: pagina.get_by_text("Solo ida", exact=True).click(timeout=8000))
    textos = pagina.locator("input[type=text]")

    def destino():
        textos.nth(1).click()
        textos.nth(1).fill("Santiago")
        pagina.wait_for_timeout(2500)
        pagina.get_by_text("Aeropuerto Santiago (SCL)").first.click(timeout=8000)

    paso("destino", destino)

    def fecha():
        dia = pagina.locator(".vc-day.id-2026-12-16 .vc-day-content").first
        for _ in range(6):
            if dia.is_visible():
                break
            pagina.locator("button.vc-next").first.click()
            pagina.wait_for_timeout(700)
        dia.click(timeout=5000)

    paso("fecha", fecha)
    botones = pagina.locator("button:visible").all_inner_texts()
    lineas.append("Botones visibles: " + " | ".join(t.strip()[:30] for t in botones if t.strip())[:800])
    for texto in ("Confirmar", "Aplicar", "Listo", "Continuar"):
        boton = pagina.get_by_role("button", name=texto)
        if boton.count() and boton.first.is_visible():
            paso("confirmar_fecha", lambda: boton.first.click(timeout=5000))
            break

    def pasajeros():
        textos.nth(3).click(timeout=5000)
        pagina.wait_for_timeout(1500)
        (SALIDA / "pasajeros.html").write_text(pagina.inner_html("body")[:400000], encoding="utf-8")

    paso("pasajeros", pasajeros)
    pagina.keyboard.press("Escape")
    paso("buscar", lambda: pagina.get_by_role("button", name="Buscar vuelo").click(timeout=8000, force=True))
    pagina.wait_for_timeout(15000)
    for i, pg in enumerate(contexto.pages):
        lineas.append(f"Pestaña {i}: {pg.url}")
        try:
            pg.screenshot(path=str(SALIDA / f"resultado_{i}.png"), full_page=True)
            (SALIDA / f"resultado_{i}.txt").write_text(pg.inner_text("body"), encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            lineas.append(f"  sin captura: {e.__class__.__name__}")
    lineas.append(f"URL final: {pagina.url}")
    pagina.screenshot(path=str(SALIDA / "paso_99_resultado.png"), full_page=False)
    (SALIDA / "sky_api.txt").write_text("\n\n".join(cuerpos) or "(sin respuestas)", encoding="utf-8")
    return lineas


def main() -> int:
    from playwright.sync_api import sync_playwright

    SALIDA.mkdir(exist_ok=True)
    with sync_playwright() as p:
        navegador = p.chromium.launch()
        contexto = navegador.new_context(locale="es-AR", user_agent=UA, viewport={"width": 1366, "height": 900})
        sky = busqueda_sky(contexto)
        navegador.close()
    texto = "\n".join(["# Búsqueda en skyairline.com", *sky])
    (SALIDA / "resultado.txt").write_text(texto, encoding="utf-8")
    print(texto)
    return 0


if __name__ == "__main__":
    sys.exit(main())
