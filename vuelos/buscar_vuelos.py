"""Búsqueda diaria de vuelos Aeroparque (AEP) <-> Santiago (SCL).

Consulta Google Flights (vía la librería fast-flights) para cada fecha del
rango configurado, guarda el histórico en CSV y genera un reporte en Markdown
con las combinaciones ida + vuelta más baratas para el grupo completo.

Uso:
    pip install -r vuelos/requirements.txt
    python vuelos/buscar_vuelos.py
"""

import csv
import json
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

CARPETA = Path(__file__).parent
CONFIG = json.loads((CARPETA / "config.json").read_text(encoding="utf-8"))
HISTORIAL = CARPETA / "datos" / "historial_precios.csv"
REPORTE = CARPETA / "datos" / "reporte.md"

COLUMNAS = ["fecha_consulta", "tramo", "fecha_vuelo", "aerolinea", "salida", "llegada", "precio_total"]


@dataclass
class Vuelo:
    tramo: str  # "ida" o "vuelta"
    fecha_vuelo: str
    aerolinea: str
    salida: str
    llegada: str
    precio_total: int  # para todo el grupo, en la moneda configurada


def rango_fechas(desde: str, hasta: str) -> list[date]:
    inicio, fin = date.fromisoformat(desde), date.fromisoformat(hasta)
    return [inicio + timedelta(days=i) for i in range((fin - inicio).days + 1)]


def consultar(origen: str, destino: str, dia: date, tramo: str) -> list[Vuelo]:
    """Devuelve los vuelos directos de un día, con el precio para todo el grupo."""
    from fast_flights import FlightQuery, FlightsNotFound, Passengers, create_query, get_flights

    pasajeros = CONFIG["pasajeros"]
    query = create_query(
        flights=[FlightQuery(date=dia.isoformat(), from_airport=origen, to_airport=destino)],
        trip="one-way",
        passengers=Passengers(adults=pasajeros["adultos"], children=pasajeros["ninos"]),
        currency=CONFIG["moneda"],
        language="es",
        max_stops=0 if CONFIG["solo_directos"] else None,
        carry_on_bags=CONFIG["equipaje"]["carry_on"],
        checked_bags=CONFIG["equipaje"]["despachado"],
    )
    try:
        resultados = get_flights(query)
    except FlightsNotFound:
        return []

    vuelos = []
    for r in resultados:
        primer, ultimo = r.flights[0], r.flights[-1]
        vuelos.append(
            Vuelo(
                tramo=tramo,
                fecha_vuelo=dia.isoformat(),
                aerolinea=" + ".join(r.airlines),
                salida="%02d:%02d" % primer.departure.time,
                llegada="%02d:%02d" % ultimo.arrival.time,
                precio_total=int(r.price),
            )
        )
    return vuelos


def buscar_todo() -> tuple[list[Vuelo], list[str]]:
    vuelos, errores = [], []
    tramos = [
        ("ida", CONFIG["origen"], CONFIG["destino"], CONFIG["ida"]),
        ("vuelta", CONFIG["destino"], CONFIG["origen"], CONFIG["vuelta"]),
    ]
    for tramo, origen, destino, rango in tramos:
        for dia in rango_fechas(rango["desde"], rango["hasta"]):
            try:
                vuelos.extend(consultar(origen, destino, dia, tramo))
            except Exception as e:  # una fecha fallida no debe cortar la búsqueda
                errores.append(f"{tramo} {dia}: {type(e).__name__}: {e}")
            time.sleep(CONFIG["pausa_segundos"])
    return vuelos, errores


def leer_historial() -> list[dict]:
    if not HISTORIAL.exists():
        return []
    with HISTORIAL.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def guardar_historial(hoy: str, historial: list[dict], vuelos: list[Vuelo]) -> None:
    """Reescribe el histórico reemplazando las filas de hoy (si se corre dos veces el mismo día)."""
    HISTORIAL.parent.mkdir(parents=True, exist_ok=True)
    with HISTORIAL.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(COLUMNAS)
        for h in historial:
            if h["fecha_consulta"] != hoy:
                w.writerow([h[c] for c in COLUMNAS])
        for v in vuelos:
            w.writerow([hoy, v.tramo, v.fecha_vuelo, v.aerolinea, v.salida, v.llegada, v.precio_total])


def mas_barato_por_dia(vuelos: list[Vuelo], tramo: str) -> dict[str, Vuelo]:
    mejores: dict[str, Vuelo] = {}
    for v in vuelos:
        if v.tramo == tramo and (v.fecha_vuelo not in mejores or v.precio_total < mejores[v.fecha_vuelo].precio_total):
            mejores[v.fecha_vuelo] = v
    return mejores


def mejores_combinaciones(vuelos: list[Vuelo], n: int) -> list[tuple[Vuelo, Vuelo, int]]:
    idas = mas_barato_por_dia(vuelos, "ida")
    vueltas = mas_barato_por_dia(vuelos, "vuelta")
    estadia = CONFIG["estadia_dias"]
    combos = []
    for i in idas.values():
        for v in vueltas.values():
            dias = (date.fromisoformat(v.fecha_vuelo) - date.fromisoformat(i.fecha_vuelo)).days
            if estadia["min"] <= dias <= estadia["max"]:
                combos.append((i, v, i.precio_total + v.precio_total))
    return sorted(combos, key=lambda c: c[2])[:n]


def minimo_anterior(historial: list[dict], hoy: str) -> dict[tuple[str, str], int]:
    """Precio mínimo por (tramo, fecha_vuelo) en la consulta anterior a hoy."""
    fechas = sorted({h["fecha_consulta"] for h in historial if h["fecha_consulta"] < hoy})
    if not fechas:
        return {}
    ultima = fechas[-1]
    minimos: dict[tuple[str, str], int] = {}
    for h in historial:
        if h["fecha_consulta"] == ultima:
            clave = (h["tramo"], h["fecha_vuelo"])
            minimos[clave] = min(minimos.get(clave, 10**9), int(h["precio_total"]))
    return minimos


def generar_reporte(hoy: str, vuelos: list[Vuelo], errores: list[str], anterior: dict) -> str:
    moneda = CONFIG["moneda"]
    p = CONFIG["pasajeros"]
    eq = CONFIG["equipaje"]
    lineas = [
        f"# Vuelos {CONFIG['origen']} ⇄ {CONFIG['destino']} — consulta del {hoy}",
        "",
        f"Grupo: {p['adultos']} adultos + {p['ninos']} niño(s). "
        f"Precios en {moneda} para **todo el grupo**, vuelos {'directos' if CONFIG['solo_directos'] else 'con o sin escala'}, "
        f"con carry-on incluido (carry_on={eq['carry_on']}, despachado={eq['despachado']}).",
        "",
    ]
    if not vuelos:
        lineas += ["**No se obtuvieron resultados.** Revise los errores más abajo.", ""]
    else:
        lineas += ["## Mejores combinaciones ida + vuelta", "", f"| # | Ida | Vuelta | Días | Total {moneda} | Por persona |", "|---|---|---|---|---|---|"]
        total_pax = p["adultos"] + p["ninos"]
        for n, (i, v, total) in enumerate(mejores_combinaciones(vuelos, CONFIG["top_combinaciones"]), 1):
            dias = (date.fromisoformat(v.fecha_vuelo) - date.fromisoformat(i.fecha_vuelo)).days
            lineas.append(
                f"| {n} | {i.fecha_vuelo} {i.salida} ({i.aerolinea}) | {v.fecha_vuelo} {v.salida} ({v.aerolinea}) "
                f"| {dias} | {total:,} | {total // total_pax:,} |"
            )
        lineas.append("")

        alertas = []
        for tramo in ("ida", "vuelta"):
            lineas += [f"## Precio más bajo por día — {tramo}", "", f"| Fecha | Aerolínea | Hora | Total {moneda} | vs. ayer |", "|---|---|---|---|---|"]
            for fecha, v in sorted(mas_barato_por_dia(vuelos, tramo).items()):
                previo = anterior.get((tramo, fecha))
                if previo:
                    cambio = (v.precio_total - previo) / previo * 100
                    delta = f"{cambio:+.0f}%"
                    if cambio <= -CONFIG["alerta_baja_porcentaje"]:
                        alertas.append(f"{tramo} {fecha}: bajó {abs(cambio):.0f}% ({previo:,} → {v.precio_total:,} {moneda})")
                else:
                    delta = "—"
                lineas.append(f"| {fecha} | {v.aerolinea} | {v.salida} | {v.precio_total:,} | {delta} |")
            lineas.append("")

        lineas += ["## Alertas de baja de precio", ""]
        lineas += [f"- 🔻 {a}" for a in alertas] or ["Sin bajas relevantes respecto de la consulta anterior."]
        lineas.append("")

    lineas += [
        "## Notas",
        "",
        "- Cada tramo se busca como solo ida, así se pueden combinar aerolíneas distintas.",
        "- El precio de equipaje es una estimación de Google Flights; confirme el total en el sitio de la aerolínea antes de comprar.",
        "- La maleta despachada compartida (1 para el grupo) no siempre se refleja bien: súmela aparte si el reporte usa despachado=0.",
    ]
    if errores:
        lineas += ["", f"## Errores ({len(errores)})", ""] + [f"- {e}" for e in errores[:20]]
    return "\n".join(lineas) + "\n"


def main() -> int:
    hoy = datetime.now(timezone.utc).date().isoformat()
    historial = leer_historial()
    anterior = minimo_anterior(historial, hoy)

    vuelos, errores = buscar_todo()
    guardar_historial(hoy, historial, vuelos)
    reporte = generar_reporte(hoy, vuelos, errores, anterior)
    REPORTE.write_text(reporte, encoding="utf-8")
    print(reporte)
    return 0 if vuelos else 1


if __name__ == "__main__":
    sys.exit(main())
