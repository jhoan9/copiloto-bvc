"""Plan de una operación ANTES de comprar: stop, objetivo, cantidad y números netos de
comisiones. Nada aquí envía órdenes."""
import datetime as dt
import math

from . import calendario as cal
from . import comisiones as com
from .numeros import num


def atr(velas, n=14):
    if len(velas) < n + 1:
        return None
    trs = []
    for a, b in zip(velas[-n - 1:-1], velas[-n:]):
        trs.append(max(b["maximo"] - b["minimo"], abs(b["maximo"] - a["cierre"]), abs(b["minimo"] - a["cierre"])))
    return sum(trs) / n


def calcular_stop(entrada, modo, cfg, velas=None):
    """modo: 'pct:3' (3% bajo la entrada), 'precio:10500' o 'atr:2' (2 x ATR14)."""
    modo = modo or "pct:%s" % cfg["reglas"]["stop_pct"]
    tipo, _, val = modo.partition(":")
    v = num(val)
    if tipo == "pct":
        return round(entrada * (1 - v / 100), 2), "stop %.1f%% bajo la entrada" % v
    if tipo == "precio":
        return v, "stop fijado a mano"
    if tipo == "atr":
        a = atr(velas or [])
        if not a:
            raise ValueError("Se necesitan al menos 15 velas diarias para el stop por ATR")
        return round(entrada - v * a, 2), "stop a %.1f x ATR14 (ATR = %.2f)" % (v, a)
    raise ValueError("Modo de stop no reconocido: %r" % modo)


def _pesos(x):
    return "$" + "{:,.0f}".format(x).replace(",", ".")


def calcular_objetivo(entrada, objetivo, riesgo_accion, cfg):
    """objetivo: None (R de la config), 'pct:6', 'r:2', 'precio:4550' o un precio."""
    r = cfg["reglas"]
    if objetivo is None or objetivo == "":
        return round(entrada + r["objetivo_r"] * riesgo_accion, 2), "%.1f R" % r["objetivo_r"]
    tipo, _, val = str(objetivo).partition(":")
    if not val:
        tipo, val = "precio", tipo
    v = num(val)
    if tipo == "pct":
        return round(entrada * (1 + v / 100), 2), "objetivo %.1f%% sobre la entrada" % v
    if tipo == "r":
        return round(entrada + v * riesgo_accion, 2), "%.1f R" % v
    if tipo != "precio":
        raise ValueError("Objetivo no reconocido: %r. Usa un precio (4550), pct:5 o r:2." % objetivo)
    if v <= entrada:
        pista = ""
        if v * 1000 > entrada * 0.5 and v * 1000 < entrada * 3:
            pista = " Parece escrito en miles: ¿querías %s? Escríbelo sin puntos (%d)." % (_pesos(v * 1000), v * 1000)
        raise ValueError("El objetivo (%s) debe quedar por ENCIMA de la entrada (%s).%s También puedes usar "
                         "--objetivo pct:5 (5%% sobre la entrada)." % (_pesos(v) if v >= 100 else v, _pesos(entrada), pista))
    return v, "fijado a mano"


def crear(ticker, entrada, cfg, stop_modo=None, objetivo=None, capital=None, cantidad=None,
          velas=None, posicion_actual=None, hoy=None, motivo="", valor=None):
    """Plan de compra. La cantidad sale de las reglas; con `valor` (pesos a invertir) se
    toma el menor entre ese monto y lo que permiten las reglas. Mejor no fijar `cantidad`."""
    r = cfg["reglas"]
    capital = capital or cfg["capital_cop"]
    stop, stop_desc = calcular_stop(entrada, stop_modo, cfg, velas)
    if stop >= entrada:
        raise ValueError("El stop (%s) debe quedar por debajo de la entrada (%s)." % (_pesos(stop), _pesos(entrada)))
    riesgo_accion = entrada - stop
    obj, obj_desc = calcular_objetivo(entrada, objetivo, riesgo_accion, cfg)
    ya_tengo = (posicion_actual or {}).get("costo", 0.0)
    if cantidad is not None and cantidad * entrada > capital:
        raise ValueError("%d acciones a %s son %s, más que todo tu capital (%s). Para invertir un monto usa "
                         "--valor (por ejemplo --valor 5000000) y deja que el agente calcule la cantidad."
                         % (cantidad, _pesos(entrada), _pesos(cantidad * entrada), _pesos(capital)))
    if cantidad is None:
        max_perdida = capital * r["max_perdida_operacion_pct"] / 100
        opciones = [(math.floor(max_perdida / riesgo_accion), "pérdida máxima por operación"),
                    (math.floor(max(0.0, capital * r["max_posicion_pct"] / 100 - ya_tengo) / entrada), "máximo por acción"),
                    (math.floor(r["max_orden_cop"] / entrada), "orden máxima")]
        if valor:
            opciones.append((math.floor(valor / entrada), "monto que pediste (%s)" % _pesos(valor)))
        cantidad, limitante = min(opciones)
        cantidad = max(0, cantidad)
    else:
        limitante = "cantidad fijada a mano"
    def _perdida(q):
        v = q * entrada
        return v + com.comision(v, cfg) - (q * stop - com.comision(q * stop, cfg))
    if limitante != "cantidad fijada a mano":
        tope = capital * r["max_perdida_operacion_pct"] / 100
        while cantidad > 0 and _perdida(cantidad) > tope:
            cantidad -= max(1, cantidad // 100)
            limitante = "pérdida máxima por operación (con comisiones)"
    valor = cantidad * entrada
    c_compra = com.comision(valor, cfg)
    costo = valor + c_compra
    perdida_stop = costo - (cantidad * stop - com.comision(cantidad * stop, cfg))
    ganancia_obj = cantidad * obj - com.comision(cantidad * obj, cfg) - costo
    hoy = hoy or dt.date.today()
    return {
        "ticker": ticker, "creado": hoy.isoformat(), "motivo": motivo,
        "entrada": entrada, "cantidad": cantidad, "valor_orden": round(valor, 2),
        "comision_compra": c_compra, "costo_total": round(costo, 2),
        "stop": stop, "stop_desc": stop_desc, "objetivo": obj, "objetivo_desc": obj_desc,
        "perdida_neta_en_stop": round(perdida_stop, 2) if cantidad else 0,
        "ganancia_neta_en_objetivo": round(ganancia_obj, 2) if cantidad else 0,
        "rr_neto": round(ganancia_obj / perdida_stop, 2) if cantidad and perdida_stop > 0 else 0,
        "precio_equilibrio": round(com.precio_equilibrio(cantidad, costo, cfg), 2) if cantidad else 0,
        "pct_del_capital": round(100 * (valor + ya_tengo) / capital, 1),
        "cantidad_limitada_por": limitante,
        "salir_si_en_rojo_el": cal.sumar_dias_bursatiles(hoy, r["max_dias_perdedora"], cfg).isoformat(),
        "salir_a_mas_tardar_el": cal.sumar_dias_bursatiles(hoy, r["max_dias_total"], cfg).isoformat(),
    }
