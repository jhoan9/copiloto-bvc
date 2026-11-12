"""Simulador con velas DIARIAS (adaptado del "Time Machine" de day-trader-skill, MIT).

Antes de arriesgar plata responde: con este stop, este objetivo y este máximo de días,
¿qué tan seguido se gana y cuánto queda después de comisiones?

1) Historia real: entra al cierre de cada día del histórico y sigue las velas siguientes.
2) Montecarlo: 10.000 caminos armados remuestreando los días reales de la acción.

Reglas de salida, día a día: si la vela abre por debajo del stop sale a la apertura (hueco);
si toca el stop sale en el stop; si toca el objetivo sale en el objetivo; si toca los dos el
mismo día se asume el stop (conservador); al cumplirse el máximo de días sale al cierre.
Es una simulación, no una predicción: resultados, noticias o una suspensión pueden hacer lo
que el histórico nunca hizo.
"""
import random

from . import comisiones as com


def _salida(entrada, stop, objetivo, velas, max_dias):
    for i, v in enumerate(velas[:max_dias], 1):
        if v["apertura"] <= stop:
            return "stop", v["apertura"], i
        if v["apertura"] >= objetivo:
            return "objetivo", v["apertura"], i
        if v["minimo"] <= stop:
            return "stop", stop, i
        if v["maximo"] >= objetivo:
            return "objetivo", objetivo, i
        if i == max_dias:
            return "tiempo", v["cierre"], i
    if velas[:max_dias]:
        return "abierta", velas[min(max_dias, len(velas)) - 1]["cierre"], min(max_dias, len(velas))
    return "abierta", entrada, 0


def _neto(cantidad, entrada, salida, cfg):
    costo = cantidad * entrada + com.comision(cantidad * entrada, cfg)
    return cantidad * salida - com.comision(cantidad * salida, cfg) - costo, costo


def historia(velas, stop_pct, objetivo_pct, max_dias, cantidad_valor, cfg):
    res = []
    for k in range(len(velas) - 1):
        e = velas[k]["cierre"]
        q = max(1, int(cantidad_valor // e))
        tipo, px, dias = _salida(e, e * (1 - stop_pct), e * (1 + objetivo_pct), velas[k + 1:], max_dias)
        if tipo == "abierta":
            continue
        neto, costo = _neto(q, e, px, cfg)
        res.append({"fecha": velas[k]["fecha"], "salida": tipo, "dias": dias, "neto_pct": neto / costo})
    return _resumen(res)


def montecarlo(velas, stop_pct, objetivo_pct, max_dias, cantidad_valor, cfg, n=10000, semilla=19):
    if len(velas) < 30:
        raise ValueError("Se necesitan al menos 30 velas diarias para el Montecarlo")
    rel = []
    for a, b in zip(velas[:-1], velas[1:]):
        c = a["cierre"]
        rel.append((b["apertura"] / c, b["maximo"] / c, b["minimo"] / c, b["cierre"] / c))
    rnd = random.Random(semilla)
    e = velas[-1]["cierre"]
    q = max(1, int(cantidad_valor // e))
    res = []
    for _ in range(n):
        camino, prev = [], e
        for _ in range(max_dias):
            o, h, l, c = rnd.choice(rel)
            camino.append({"apertura": prev * o, "maximo": prev * h, "minimo": prev * l, "cierre": prev * c})
            prev = prev * c
        tipo, px, dias = _salida(e, e * (1 - stop_pct), e * (1 + objetivo_pct), camino, max_dias)
        neto, costo = _neto(q, e, px, cfg)
        res.append({"salida": tipo, "dias": dias, "neto_pct": neto / costo})
    out = _resumen(res)
    out.update(precio_entrada=e, semilla=semilla, caminos=n)
    return out


def _resumen(res):
    n = len(res)
    if not n:
        return {"n": 0}
    cuenta = {k: sum(1 for r in res if r["salida"] == k) for k in ("objetivo", "stop", "tiempo")}
    media = sum(r["neto_pct"] for r in res) / n
    gan = sum(1 for r in res if r["neto_pct"] > 0)
    return {"n": n, "pct_objetivo": cuenta["objetivo"] / n, "pct_stop": cuenta["stop"] / n,
            "pct_tiempo": cuenta["tiempo"] / n, "pct_gana_neto": gan / n,
            "resultado_medio_neto_pct": media,
            "dias_medios": sum(r["dias"] for r in res) / n,
            "veredicto": veredicto(media)}


UMBRAL_VENTAJA = 0.005  # 0,5% neto por operación: por debajo es ruido, no ventaja


def veredicto(media):
    if media >= UMBRAL_VENTAJA:
        return "A favor"
    if media <= -UMBRAL_VENTAJA:
        return "En contra"
    return "Sin ventaja clara"
