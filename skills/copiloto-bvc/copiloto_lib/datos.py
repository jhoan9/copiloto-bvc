"""Precios de mercado.

Proveedores:
- "yahoo": endpoint público de gráficos de Yahoo Finance (gratis, NO oficial: puede fallar,
  cambiar o tener retraso). Las acciones de la BVC se piden como TICKER + sufijo (".CL" por
  defecto; verifica que tu acción exista con `python3 copiloto.py precio TICKER`).
  Las acciones globales que se negocian en pesos (NUCO, NVDACO...) se siguen con la acción en EE. UU. y se
  pasan a pesos con la TRM (COP=X). Es una aproximación: en la app cotizan en pesos con su
  propio libro de órdenes, así que confirma siempre en la app antes de operar.
- "manual": lee datos/precios.json -> {"CEMARGOS": 10800, ...} y, para el historial,
  datos/historico/TICKER.csv con columnas fecha,apertura,maximo,minimo,cierre,volumen.

Siempre puedes forzar un precio con --precio en los comandos: el precio en vivo de la app
es el que manda.
"""
import csv
import datetime as dt
import json
import os
import time
import urllib.parse
import urllib.request

from . import config as C

UA = "Mozilla/5.0 (copiloto-bvc; uso personal)"


class DatosError(Exception):
    pass


def _get_json(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def simbolo_yahoo(ticker, cfg):
    s = cfg["simbolos"].get(ticker)
    if s:
        return s["yahoo"], s.get("moneda", "COP")
    return ticker + cfg.get("sufijo_yahoo_bvc", ".CL"), "COP"


def _yahoo_chart(sym, rango="6mo", intervalo="1d"):
    url = ("https://query2.finance.yahoo.com/v8/finance/chart/%s?range=%s&interval=%s"
           % (urllib.parse.quote(sym), rango, intervalo))
    try:
        data = _get_json(url)
    except Exception as e:  # red, 404, rate limit
        raise DatosError("Yahoo no respondió para %s: %s" % (sym, e))
    res = (data.get("chart") or {}).get("result")
    if not res:
        err = (data.get("chart") or {}).get("error")
        raise DatosError("Yahoo no tiene datos de %s (%s)" % (sym, err))
    return res[0]


def velas_desde_yahoo(chart):
    ts = chart.get("timestamp") or []
    q = (chart.get("indicators") or {}).get("quote", [{}])[0]
    out = []
    for i, t in enumerate(ts):
        c = q.get("close", [None])[i]
        if c is None:
            continue
        out.append({"fecha": dt.datetime.utcfromtimestamp(t).date().isoformat(),
                    "apertura": q["open"][i], "maximo": q["high"][i], "minimo": q["low"][i],
                    "cierre": c, "volumen": (q.get("volume") or [0])[i] or 0})
    return out


def trm(cfg, cache=True):
    ch = _cached("TRM", lambda: _yahoo_chart(cfg["simbolo_trm"], "5d"), cache)
    return float(ch["meta"]["regularMarketPrice"])


def trm_historica(cfg, rango="1y", usar_cache=True):
    """Lista ordenada de (fecha, TRM de cierre) desde Yahoo (COP=X)."""
    sym = cfg["simbolo_trm"]
    ch = _cached(sym + "_" + rango, lambda: _yahoo_chart(sym, rango), usar_cache, ttl=3600)
    return [(v["fecha"], float(v["cierre"])) for v in velas_desde_yahoo(ch)]


def _tasa_en(tasas, fecha):
    """TRM del día o, si ese día no hubo dato, la del último día anterior."""
    import bisect
    if not tasas:
        return None
    i = bisect.bisect_right([f for f, _ in tasas], fecha) - 1
    return tasas[i][1] if i >= 0 else tasas[0][1]


def _cached(clave, fn, usar_cache, ttl=600):
    p = C.path("cache", clave.replace("/", "_") + ".json")
    if usar_cache and os.path.exists(p) and time.time() - os.path.getmtime(p) < ttl:
        return C.read_json(p)
    data = fn()
    C.write_json(p, data)
    return data


def precio(ticker, cfg, usar_cache=True):
    """Último precio en COP. Devuelve dict con precio, fuente y aviso."""
    manual = C.read_json(C.path("precios.json"), {}) or {}
    if cfg.get("proveedor_precios") == "manual" or ticker in manual:
        if ticker not in manual:
            raise DatosError("No hay precio manual para %s en datos/precios.json" % ticker)
        return {"ticker": ticker, "precio": float(manual[ticker]), "fuente": "manual (datos/precios.json)"}
    sym, moneda = simbolo_yahoo(ticker, cfg)
    ch = _cached(sym + "_q", lambda: _yahoo_chart(sym, "5d"), usar_cache)
    p = float(ch["meta"]["regularMarketPrice"])
    out = {"ticker": ticker, "simbolo": sym, "fuente": "Yahoo Finance (no oficial)"}
    if moneda == "USD":
        t = trm(cfg, usar_cache)
        out.update(precio=round(p * t, 2), precio_usd=p, trm=t,
                   aviso="Aproximado: %s en EE. UU. x TRM. En la app puede variar." % sym)
    else:
        out["precio"] = p
    return out


def historico(ticker, cfg, rango="1y", usar_cache=True):
    """Velas diarias en COP: lista de dicts fecha/apertura/maximo/minimo/cierre/volumen."""
    p = C.path("historico", ticker + ".csv")
    if os.path.exists(p):
        return leer_csv_velas(p)
    if cfg.get("proveedor_precios") == "manual":
        raise DatosError("Sin histórico manual para %s (datos/historico/%s.csv)" % (ticker, ticker))
    sym, moneda = simbolo_yahoo(ticker, cfg)
    ch = _cached(sym + "_" + rango, lambda: _yahoo_chart(sym, rango), usar_cache, ttl=3600)
    velas = velas_desde_yahoo(ch)
    if moneda == "USD":
        # Cada vela con la TRM de SU fecha (no la de hoy): con la TRM actual, los precios de
        # hace meses quedan corridos y la revisión del historial ve huecos que nunca existieron.
        tasas = trm_historica(cfg, rango, usar_cache)
        hoy = trm(cfg, usar_cache)
        for v in velas:
            t = _tasa_en(tasas, v["fecha"]) or hoy
            v["trm"] = t
            for k in ("apertura", "maximo", "minimo", "cierre"):
                v[k] = round(v[k] * t, 2)
    if not velas:
        raise DatosError("Histórico vacío para %s" % sym)
    return velas


def leer_csv_velas(p):
    out = []
    with open(p, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out.append({"fecha": r["fecha"], "apertura": float(r["apertura"]), "maximo": float(r["maximo"]),
                        "minimo": float(r["minimo"]), "cierre": float(r["cierre"]),
                        "volumen": float(r.get("volumen") or 0)})
    out.sort(key=lambda v: v["fecha"])
    return out
