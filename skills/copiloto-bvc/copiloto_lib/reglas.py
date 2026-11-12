"""Validación de riesgo: PASA, AVISO o BLOQUEA para cada plan de compra, y revisión de las
posiciones abiertas contra tus reglas. Cada resultado trae la razón en palabras."""
import datetime as dt

from . import calendario as cal

PASA, AVISO, BLOQUEA = "PASA", "AVISO", "BLOQUEA"


def _eventos_proximos(ticker, eventos, desde, dias, cfg):
    hasta = cal.sumar_dias_bursatiles(desde, dias, cfg)
    out = []
    for e in eventos or []:
        if e.get("ticker") != ticker:
            continue
        f = dt.date.fromisoformat(e["fecha"])
        if desde <= f <= hasta:
            out.append(e)
    return out


DESVIO_AVISO = 0.03   # entrada a más de 3% del precio actual: avisa
DESVIO_BLOQUEA = 0.15  # a más de 15%: casi seguro un número mal leído


def revisar_plan(plan, cfg, posiciones=None, resultado_mes=0.0, eventos=None, hoy=None,
                 precio_mercado=None, fuente_precio="", efectivo=None):
    r = cfg["reglas"]
    hoy = hoy or dt.date.fromisoformat(plan["creado"])
    capital = cfg["capital_cop"]
    pos = (posiciones or {}).get(plan["ticker"])
    out = []

    def add(estado, regla, detalle):
        out.append({"estado": estado, "regla": regla, "detalle": detalle})

    e = plan["entrada"]
    if precio_mercado:
        dif = e / precio_mercado - 1
        if abs(dif) > DESVIO_BLOQUEA:
            add(BLOQUEA, "precio de entrada", "La entrada $%s está %+.0f%% lejos del precio actual $%s (%s). "
                "¿Se leyó mal el número? En pesos se escribe sin puntos: 2515, no 2.515."
                % (_m(e), 100 * dif, _m(precio_mercado), fuente_precio))
        elif abs(dif) > DESVIO_AVISO:
            add(AVISO, "precio de entrada", "La entrada $%s está %+.1f%% del precio actual $%s: una orden límite "
                "así puede no ejecutarse (o ejecutarse ya, si está por encima)." % (_m(e), 100 * dif, _m(precio_mercado)))
    else:
        add(AVISO, "precio de entrada", "No pude verificar la entrada contra el precio actual (%s). "
            "Confírmalo en la app o pásalo con --mercado." % (fuente_precio or "sin datos"))
        if e < 100:
            add(BLOQUEA, "precio de entrada", "Una entrada de $%s es sospechosa: ¿era en miles? Escribe el precio "
                "en pesos sin puntos (2515, no 2.515)." % _m(e))
    if efectivo is not None and plan["costo_total"] > efectivo + 1:
        add(BLOQUEA, "efectivo", "La compra cuesta $%s con comisión y tienes $%s disponibles. Si vendiste algo "
            "que no está en tus datos, regístralo con `operacion agregar venta`." % (_m(plan["costo_total"]), _m(efectivo)))
    if plan["cantidad"] <= 0:
        add(BLOQUEA, "cantidad", "Con tus límites la cantidad sale en 0 (%s)." % plan["cantidad_limitada_por"])
    v = plan["valor_orden"]
    if v > r["max_orden_cop"]:
        add(BLOQUEA, "orden máxima", "La orden de $%s supera el máximo de $%s." % (_m(v), _m(r["max_orden_cop"])))
    if 0 < v < r["min_orden_cop"]:
        add(BLOQUEA, "orden mínima", "La orden de $%s es menor a $%s: la comisión se come %.1f%%."
            % (_m(v), _m(r["min_orden_cop"]), 100 * 2 * plan["comision_compra"] / v))
    if plan["pct_del_capital"] > r["max_posicion_pct"] + 1e-9:
        add(BLOQUEA, "concentración", "Quedarías con %.1f%% del capital en %s (máximo %.0f%%)."
            % (plan["pct_del_capital"], plan["ticker"], r["max_posicion_pct"]))
    max_perd = capital * r["max_perdida_operacion_pct"] / 100
    if plan["perdida_neta_en_stop"] > max_perd * 1.01:
        add(BLOQUEA, "pérdida máxima", "Si toca el stop pierdes $%s; tu máximo es $%s."
            % (_m(plan["perdida_neta_en_stop"]), _m(max_perd)))
    if plan["cantidad"] > 0 and plan["rr_neto"] < r["min_rr_neto"]:
        add(BLOQUEA, "ganancia/riesgo", "Después de comisiones ganas %.2f por cada 1 que arriesgas (mínimo %.1f)."
            % (plan["rr_neto"], r["min_rr_neto"]))
    if pos is None and len(posiciones or {}) >= r["max_posiciones_abiertas"]:
        add(BLOQUEA, "posiciones abiertas", "Ya tienes %d posiciones abiertas (máximo %d)."
            % (len(posiciones), r["max_posiciones_abiertas"]))
    if pos and not r["permitir_promediar_a_la_baja"] and plan["entrada"] < pos["costo_promedio"]:
        add(BLOQUEA, "promediar a la baja", "Ya tienes %s con costo promedio $%s y la entrada es más baja: "
            "eso es aumentar una posición que va perdiendo." % (plan["ticker"], _m(pos["costo_promedio"])))
    lim_mes = capital * r["max_perdida_mes_pct"] / 100
    if resultado_mes <= -lim_mes:
        add(BLOQUEA, "pérdida del mes", "El mes va en $%s (límite -$%s): no más compras este mes."
            % (_m(resultado_mes), _m(lim_mes)))
    for e in _eventos_proximos(plan["ticker"], eventos, hoy, r["dias_bloqueo_eventos"], cfg):
        if e.get("tipo") == "resultados":
            add(BLOQUEA, "evento", "%s publica resultados el %s: no se compra justo antes." % (plan["ticker"], e["fecha"]))
        else:
            add(AVISO, "evento", "%s tiene %s el %s." % (plan["ticker"], e.get("tipo", "evento"), e["fecha"]))
    ok, motivo = cal.es_dia_bursatil(hoy, cfg)
    if not ok:
        add(AVISO, "calendario", "Hoy no hay rueda en la BVC (%s)." % motivo)
    if not any(x["estado"] == BLOQUEA for x in out):
        add(PASA, "límites", "Pérdida en stop $%s, ganancia en objetivo $%s, %.1f%% del capital."
            % (_m(plan["perdida_neta_en_stop"]), _m(plan["ganancia_neta_en_objetivo"]), plan["pct_del_capital"]))
    veredicto = BLOQUEA if any(x["estado"] == BLOQUEA for x in out) else PASA
    return {"veredicto": veredicto, "checks": out}


def revisar_posicion(pos, precio_actual, cfg, plan=None, eventos=None, hoy=None):
    """Qué dicen tus reglas sobre una posición abierta. Devuelve acción sugerida y razones."""
    r = cfg["reglas"]
    hoy = hoy or dt.date.today()
    costo_prom = pos["costo_promedio"]
    stop = (plan or {}).get("stop") or round(costo_prom * (1 - r["stop_pct"] / 100), 2)
    objetivo = (plan or {}).get("objetivo")
    dias = cal.dias_bursatiles_entre(pos["primera_compra"].date() if hasattr(pos["primera_compra"], "date")
                                     else pos["primera_compra"], hoy, cfg)
    valor = pos["cantidad"] * precio_actual
    resultado = valor - pos["costo"]
    pct = resultado / pos["costo"] if pos["costo"] else 0
    razones, accion = [], "MANTENER"
    if precio_actual <= stop:
        accion = "VENDER"
        razones.append("Precio $%s en o bajo el stop $%s." % (_m(precio_actual), _m(stop)))
    if resultado < 0 and dias > r["max_dias_perdedora"]:
        accion = "VENDER"
        razones.append("Lleva %d ruedas en rojo (regla: salir a las %d)." % (dias, r["max_dias_perdedora"]))
    if dias > r["max_dias_total"]:
        accion = "VENDER" if accion == "VENDER" else "REVISAR"
        razones.append("Lleva %d ruedas abierta (máximo %d)." % (dias, r["max_dias_total"]))
    if objetivo and precio_actual >= objetivo:
        accion = "TOMAR GANANCIA"
        razones.append("Llegó al objetivo $%s." % _m(objetivo))
    for e in _eventos_proximos(pos["ticker"], eventos, hoy, 5, cfg):
        razones.append("Evento próximo: %s el %s." % (e.get("tipo", "evento"), e["fecha"]))
    if not razones:
        razones.append("Dentro de tus reglas.")
    return {"ticker": pos["ticker"], "cantidad": pos["cantidad"], "costo_promedio": round(costo_prom, 2),
            "precio": precio_actual, "resultado": round(resultado), "resultado_pct": round(100 * pct, 2),
            "ruedas_abierta": dias, "stop": stop, "objetivo": objetivo, "accion": accion, "razones": razones}


def _m(x):
    s = "{:,.0f}".format(abs(x)).replace(",", ".")
    return ("-" if x < 0 else "") + s
