"""Cartera desde el export de órdenes de la app (ver exportes.py).

Lee las órdenes aprobadas, las ordena y arma pares compra -> ventas (cada compra con las
ventas que la cerraron), como se lleva en una hoja de control:
  1) una compra abierta con la misma cantidad; 2) compras que suman exacto la cantidad;
  3) si no, la compra más reciente (LIFO). Cuando una venta cierra varias compras, la
  comisión se reparte por cantidad.
También acepta operaciones manuales en datos/operaciones_manuales.csv (mismas columnas que
el export) para cosas que la app no exporta, como una venta por readquisición u OPA.
"""
import itertools
import os

from . import config as C
from . import exportes

parse_fecha = exportes.parse_fecha
ULTIMO_EXPORT = {}   # qué archivo se usó en este comando (lo muestra la CLI)
_CACHE = {}


def leer_export(path):
    """Órdenes aprobadas de un export, ordenadas por fecha."""
    return exportes.leer_export(path)[0]


def leer_ordenes(export_path=None):
    """Órdenes del export (encontrado solo, ver exportes.py) + datos/operaciones_manuales.csv.

    Si no hay export devuelve [] y deja el motivo en ULTIMO_EXPORT["error"]."""
    if export_path in _CACHE:
        return list(_CACHE[export_path])
    ULTIMO_EXPORT.clear()
    try:
        info = exportes.export_activo(export_path)
        ords = leer_export(info["ruta"])
        ULTIMO_EXPORT.update(info)
    except exportes.ExportError as e:
        ULTIMO_EXPORT["error"] = str(e)
        ords = []
    man = C.path("operaciones_manuales.csv")
    if ords and os.path.exists(man):
        ya = {(o["fecha"], o["ticker"], o["tipo"], o["cantidad"], o["precio"]) for o in ords}
        try:
            extra = exportes.leer_export(man, origen="manual")[0]
        except exportes.ExportError as e:
            extra = []
            ULTIMO_EXPORT["error_manuales"] = str(e)
        extra = [o for o in extra if (o["fecha"], o["ticker"], o["tipo"], o["cantidad"], o["precio"]) not in ya]
        ULTIMO_EXPORT["manuales"] = len(extra)
        ords = sorted(ords + extra, key=lambda o: o["fecha"])
    _CACHE[export_path] = ords
    return list(ords)


def armar_pares(ordenes, desde=None):
    """Lista de lotes: {compra, ventas[], abierta_cant}. Solo órdenes desde `desde`."""
    lotes = []
    for o in ordenes:
        if desde and o["fecha"] < desde:
            continue
        if o["tipo"] == "Compra":
            lotes.append({"compra": o, "abierta_cant": o["cantidad"], "ventas": []})
            continue
        q = o["cantidad"]
        abiertos = [l for l in lotes if l["compra"]["ticker"] == o["ticker"] and l["abierta_cant"] > 0]
        if sum(l["abierta_cant"] for l in abiertos) < q:
            continue  # venta de acciones compradas antes de `desde`
        asign = None
        exactos = [l for l in abiertos if l["abierta_cant"] == q]
        if exactos:
            asign = [(exactos[-1], q)]
        else:
            for k in range(2, min(5, len(abiertos)) + 1):
                for comb in itertools.combinations(list(reversed(abiertos)), k):
                    if sum(l["abierta_cant"] for l in comb) == q:
                        asign = [(l, l["abierta_cant"]) for l in comb]
                        break
                if asign:
                    break
        if not asign:
            asign, resto = [], q
            for l in reversed(abiertos):
                t = min(resto, l["abierta_cant"])
                asign.append((l, t))
                resto -= t
                if resto == 0:
                    break
        for l, t in asign:
            l["abierta_cant"] -= t
            l["ventas"].append({"fecha": o["fecha"], "cantidad": t, "precio": o["precio"],
                                "comision": o["comision"] * t / q, "orden_total": q})
    return lotes


def resumen_lote(l):
    c = l["compra"]
    inv = c["cantidad"] * c["precio"] + c["comision"]
    vendidas = sum(v["cantidad"] for v in l["ventas"])
    recibido = sum(v["cantidad"] * v["precio"] - v["comision"] for v in l["ventas"])
    costo_vendido = inv * vendidas / c["cantidad"] if c["cantidad"] else 0
    return {"ticker": c["ticker"], "fecha_compra": c["fecha"], "cantidad": c["cantidad"],
            "precio_compra": c["precio"], "invertido": inv, "vendidas": vendidas,
            "abiertas": l["abierta_cant"], "recibido": recibido,
            "ganancia_realizada": recibido - costo_vendido,
            "fecha_ultima_venta": max((v["fecha"] for v in l["ventas"]), default=None),
            "costo_abierto": inv * l["abierta_cant"] / c["cantidad"] if c["cantidad"] else 0}


def posiciones_abiertas(lotes):
    """Agrupa los lotes abiertos por acción."""
    pos = {}
    for l in lotes:
        if l["abierta_cant"] <= 0:
            continue
        r = resumen_lote(l)
        p = pos.setdefault(r["ticker"], {"ticker": r["ticker"], "cantidad": 0, "costo": 0.0, "lotes": []})
        p["cantidad"] += r["abiertas"]
        p["costo"] += r["costo_abierto"]
        p["lotes"].append({"fecha_compra": r["fecha_compra"], "cantidad": r["abiertas"],
                           "precio_compra": r["precio_compra"], "costo": r["costo_abierto"]})
    for p in pos.values():
        p["costo_promedio"] = p["costo"] / p["cantidad"]
        p["primera_compra"] = min(x["fecha_compra"] for x in p["lotes"])
    return pos


def operaciones_cerradas(lotes):
    out = []
    for l in lotes:
        if l["abierta_cant"] == 0 and l["ventas"]:
            r = resumen_lote(l)
            r["rentab"] = r["ganancia_realizada"] / r["invertido"] if r["invertido"] else 0
            r["dias"] = (r["fecha_ultima_venta"].date() - r["fecha_compra"].date()).days
            out.append(r)
    return out
