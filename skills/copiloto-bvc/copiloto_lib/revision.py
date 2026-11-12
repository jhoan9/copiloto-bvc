"""Revisión de tu historial: qué habría pasado con tus operaciones si hubieras seguido las
reglas. Dos niveles:
- Con histórico diario de cada acción (online o datos/historico/): repite cada operación
  desde la fecha de compra con stop, objetivo y máximo de días. Es lo más realista.
- Sin histórico: aproximación por resultado final. Topa cada pérdida en el stop (como si
  se hubiera ejecutado justo ahí) y deja igual las ganancias. Es optimista: no sabe si una
  operación ganadora tocó el stop antes de subir.
Además cuenta las compras que las reglas de tamaño habrían bloqueado.
"""
import datetime as dt

from . import comisiones as com
from . import simulador as sim


def aproximada(cerradas, cfg):
    r = cfg["reglas"]
    stop = r["stop_pct"] / 100
    real = sum(o["ganancia_realizada"] for o in cerradas)
    con, cortadas, ahorro = 0.0, 0, 0.0
    for o in cerradas:
        g = o["ganancia_realizada"]
        if o["rentab"] < -stop:
            nuevo = -stop * o["invertido"]
            cortadas += 1
            ahorro += nuevo - g
            g = nuevo
        con += g
    bloq_grande = [o for o in cerradas if o["invertido"] > r["max_orden_cop"]]
    bloq_peq = [o for o in cerradas if o["invertido"] < r["min_orden_cop"]]
    return {"metodo": "aproximada (sin histórico de precios)", "operaciones": len(cerradas),
            "resultado_real": round(real), "resultado_con_stop": round(con),
            "perdidas_cortadas": cortadas, "ahorro_por_stop": round(ahorro),
            "compras_mayores_al_maximo": len(bloq_grande),
            "resultado_de_esas_compras": round(sum(o["ganancia_realizada"] for o in bloq_grande)),
            "compras_menores_al_minimo": len(bloq_peq),
            "resultado_de_esas_compras_pequenas": round(sum(o["ganancia_realizada"] for o in bloq_peq)),
            "aviso": "Optimista: supone que el stop se ejecuta exacto y que ninguna ganadora lo tocó antes."}


TOLERANCIA_PRECIO = 0.03  # el precio de compra puede salirse hasta 3% del rango del día


def _vela_compra(velas, fecha):
    """Vela del día de compra (o la última anterior si ese día no hay dato)."""
    previas = [v for v in velas if v["fecha"] <= fecha]
    return previas[-1] if previas else None


def con_historico(cerradas, velas_por_ticker, cfg):
    """Repite cada operación cerrada con stop, objetivo y máximo de días.

    Antes de simular comprueba que el precio al que compraste esté dentro del rango de
    la vela de ese día (±3%). Si no coincide, la fuente de precios no corresponde a lo que
    ves en la app (otra serie, otra TRM, un split) y la operación se excluye: simularla
    daría un "hueco" falso al día siguiente y una pérdida que nunca habría pasado.
    """
    r = cfg["reglas"]
    stop, obj = r["stop_pct"] / 100, r["stop_pct"] * r["objetivo_r"] / 100
    filas, excluidas = [], []
    for o in cerradas:
        velas = velas_por_ticker.get(o["ticker"]) or []
        f = o["fecha_compra"].date().isoformat()
        e = o["precio_compra"]
        base = {"ticker": o["ticker"], "fecha": f, "precio_compra": e, "real": o["ganancia_realizada"]}
        dia = _vela_compra(velas, f)
        siguientes = [v for v in velas if v["fecha"] > f]
        if not dia or not siguientes:
            excluidas.append(dict(base, motivo="sin datos de precios para esa fecha"))
            continue
        lo, hi = dia["minimo"] * (1 - TOLERANCIA_PRECIO), dia["maximo"] * (1 + TOLERANCIA_PRECIO)
        if not lo <= e <= hi:
            excluidas.append(dict(base, motivo="precio no coincide: la fuente dice %.0f–%.0f el %s"
                                  % (dia["minimo"], dia["maximo"], dia["fecha"]),
                                  rango_fuente=(dia["minimo"], dia["maximo"])))
            continue
        tipo, px, dias = sim._salida(e, e * (1 - stop), e * (1 + obj), siguientes, r["max_dias_total"])
        q = o["cantidad"]
        costo = q * e + com.comision(q * e, cfg)
        neto = q * px - com.comision(q * px, cfg) - costo
        filas.append(dict(base, cantidad=q, con_reglas=neto, salida=tipo, precio_salida=px, dias=dias,
                          dias_reales=o.get("dias")))
    por_ticker = {}
    for x in filas:
        d = por_ticker.setdefault(x["ticker"], {"operaciones": 0, "real": 0.0, "con_reglas": 0.0,
                                                "objetivo": 0, "stop": 0, "tiempo": 0, "abierta": 0, "excluidas": 0})
        d["operaciones"] += 1
        d["real"] += x["real"]
        d["con_reglas"] += x["con_reglas"]
        d[x["salida"]] += 1
    for x in excluidas:
        d = por_ticker.setdefault(x["ticker"], {"operaciones": 0, "real": 0.0, "con_reglas": 0.0,
                                                "objetivo": 0, "stop": 0, "tiempo": 0, "abierta": 0, "excluidas": 0})
        d["excluidas"] += 1
    for d in por_ticker.values():
        d["real"], d["con_reglas"] = round(d["real"]), round(d["con_reglas"])
    return {"metodo": "con histórico diario", "operaciones_simuladas": len(filas),
            "excluidas": len(excluidas), "operaciones_totales": len(cerradas),
            "resultado_real": round(sum(x["real"] for x in filas)),
            "resultado_con_reglas": round(sum(x["con_reglas"] for x in filas)),
            "resultado_real_excluidas": round(sum(x["real"] for x in excluidas)),
            "por_ticker": por_ticker, "detalle": filas, "detalle_excluidas": excluidas,
            "aviso": "Compara solo las operaciones simuladas. Las excluidas no se cuentan en ninguno de los dos totales."}
