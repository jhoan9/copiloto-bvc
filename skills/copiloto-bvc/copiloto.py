#!/usr/bin/env python3
"""copiloto-bvc: asistente de decisiones para invertir en acciones colombianas.

No ejecuta órdenes: calcula, valida contra tus reglas y te deja la orden escrita.
Solo biblioteca estándar de Python 3.8+.

  python3 copiloto.py init
  python3 copiloto.py archivos          # qué export y qué archivos está usando (diagnóstico)
  python3 copiloto.py reloj [--festivos]
  python3 copiloto.py precio CEMARGOS
  python3 copiloto.py cartera [--csv RUTA] [--precio CEMARGOS=11200 ...]
  python3 copiloto.py plan CEMARGOS --entrada 10800 [--valor 5000000] [--stop pct:3|precio:10450|atr:2] [--objetivo pct:6] [--guardar]
  python3 copiloto.py riesgo CEMARGOS
  python3 copiloto.py simular NVDACO [--stop 3 --objetivo 4.5 --dias 20 --valor 5000000]
  python3 copiloto.py ticket compra CEMARGOS [--registrar]
  python3 copiloto.py ticket venta NUCO --cantidad 102 --precio 42000 --motivo "regla 10 días"
  python3 copiloto.py evento agregar NUCO 2026-11-12 resultados
  python3 copiloto.py operacion agregar venta CEMARGOS --cantidad 557 --precio 10800 --fecha 2026-11-11
  python3 copiloto.py historial [--csv RUTA] [--desde 2026-01-01] [--con-historico [--detalle]]
"""
import argparse
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
for _s in (sys.stdout, sys.stderr):  # Windows: evita errores con tildes y símbolos
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from copiloto_lib import calendario as cal  # noqa: E402
from copiloto_lib import cartera, datos, exportes, plan as planmod, reglas, revision, simulador, ticket  # noqa: E402
from copiloto_lib import comisiones as com  # noqa: E402
from copiloto_lib import config as C  # noqa: E402
from copiloto_lib.numeros import num  # noqa: E402


def m(x):
    s = "{:,.0f}".format(abs(x)).replace(",", ".")
    return ("-$" if x < 0 else "$") + s


def out(args, data, texto):
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
    else:
        print(texto)


def _precios_forzados(args):
    d = {}
    if getattr(args, "mercado", None) and getattr(args, "ticker", None):
        d[args.ticker.upper()] = args.mercado
    lista = getattr(args, "precio", None)
    for kv in (lista if isinstance(lista, list) else []):
        k, _, v = kv.partition("=")
        d[k.strip().upper()] = num(v)
    return d


def _precio(ticker, cfg, forzados):
    if ticker in forzados:
        return forzados[ticker], "dado por ti"
    try:
        p = datos.precio(ticker, cfg)
        return p["precio"], p["fuente"]
    except datos.DatosError as e:
        return None, str(e)


def _ordenes(args):
    p = getattr(args, "csv", None)
    ords = cartera.leer_ordenes(p)
    if not ords:
        sys.exit(cartera.ULTIMO_EXPORT.get("error") or exportes.mensaje_no_encontrado())
    return ords


def _nota_export():
    """Una línea (a stderr) con el export que se usó, para que nadie tenga que buscarlo."""
    i = cartera.ULTIMO_EXPORT
    if not i.get("ruta"):
        return
    txt = "[export] %s · %d órdenes del %s al %s" % (i["ruta"], i["ordenes"], i["desde"].date(), i["hasta"].date())
    if i.get("copiado_desde"):
        txt += " · copiado desde " + i["copiado_desde"]
    if i.get("manuales"):
        txt += " · +%d manuales" % i["manuales"]
    print(txt, file=sys.stderr)


def cmd_archivos(args, cfg):
    filas = exportes.revisar_candidatos()
    try:
        activo = exportes.export_activo(getattr(args, "csv", None))
        cartera.ULTIMO_EXPORT.update(activo)
    except exportes.ExportError as e:
        activo = {"error": str(e)}
    man = C.path("operaciones_manuales.csv")
    data = {"carpeta_datos": C.base_dir(), "config": C.path("config.json"),
            "config_existe": os.path.exists(C.path("config.json")), "capital_cop": cfg["capital_cop"],
            "export_en_uso": activo, "operaciones_manuales": man if os.path.exists(man) else None,
            "carpetas_revisadas": exportes.carpetas_de_busqueda(),
            "candidatos": [{"ruta": p, "valido": i is not None, "motivo": e,
                            "ordenes": i and i["ordenes"], "hasta": i and i["hasta"]} for p, i, e in filas]}
    l = ["Carpeta de datos: %s" % data["carpeta_datos"],
         "Config: %s (%s) · capital %s" % (data["config"], "ok" if data["config_existe"] else "NO EXISTE: corre init",
                                           m(cfg["capital_cop"]))]
    if "error" in activo:
        l.append("Export: NO ENCONTRADO\n" + activo["error"])
    else:
        l.append("Export en uso: %s · %d órdenes del %s al %s · %s, separador '%s'%s"
                 % (activo["ruta"], activo["ordenes"], activo["desde"].date(), activo["hasta"].date(),
                    activo["codificacion"], activo["separador"],
                    (" · copiado desde " + activo["copiado_desde"]) if activo.get("copiado_desde") else ""))
    l.append("Operaciones manuales: " + (man if data["operaciones_manuales"] else "no hay (opcional)"))
    if filas:
        l.append("Archivos revisados:")
        for c in data["candidatos"]:
            l.append("  %s %s%s" % ("✓" if c["valido"] else "✗", c["ruta"],
                                    (" (%d órdenes hasta %s)" % (c["ordenes"], c["hasta"].date())) if c["valido"]
                                    else " (" + c["motivo"] + ")"))
    out(args, data, "\n".join(l))


def cmd_init(args):
    p, nuevo = C.save_default()
    if not os.path.exists(C.path("eventos.json")):
        C.write_json(C.path("eventos.json"), [])
    print(("Creé " if nuevo else "Ya existía ") + p)
    print("Siguiente paso: pon tu capital en capital_cop y revisa tus reglas en ese archivo. Luego exporta "
          "\"Información financiera\" (CSV) desde la app y déjalo en Descargas: el agente lo encuentra solo.")


def cmd_reloj(args, cfg):
    ahora = dt.datetime.fromisoformat(args.ahora) if args.ahora else dt.datetime.now(cal.TZ_CO)
    st = cal.estado(ahora, cfg)
    txt = "BVC %s · %s · %s" % (st["ahora"], st["fase"], ("próxima rueda " + st["proxima_rueda"]))
    if st.get("apertura"):
        txt += "\nHorario de hoy: %s a %s (subasta de cierre desde %s)." % (st["apertura"], st["cierre"], st["inicio_subasta_cierre"])
    if st["motivo"]:
        txt += "\nHoy no hay rueda: " + st["motivo"]
    if args.festivos:
        anio = ahora.year
        fs = sorted(cal.festivos(anio).items())
        st["festivos"] = [(d.isoformat(), n) for d, n in fs if d.weekday() < 5]
        txt += "\nFestivos %d en días hábiles:\n" % anio + "\n".join("  %s %s" % x for x in st["festivos"])
    out(args, st, txt)


def cmd_precio(args, cfg):
    try:
        p = datos.precio(args.ticker.upper(), cfg, usar_cache=not args.sin_cache)
    except datos.DatosError as e:
        sys.exit(str(e) + "\nUsa el precio que ves en la app con --precio o ponlo en datos/precios.json.")
    txt = "%s: %s (%s)" % (p["ticker"], m(p["precio"]), p["fuente"])
    if p.get("aviso"):
        txt += "\n" + p["aviso"]
    out(args, p, txt)


def cmd_cartera(args, cfg):
    hoy = dt.date.today()
    lotes = cartera.armar_pares(_ordenes(args))
    pos = cartera.posiciones_abiertas(lotes)
    forz = _precios_forzados(args)
    planes = C.read_json(C.path("planes.json"), {}) or {}
    eventos = C.read_json(C.path("eventos.json"), []) or []
    filas, txt = [], []
    for t, p in sorted(pos.items()):
        px, fuente = _precio(t, cfg, forz)
        if px is None:
            txt.append("%s: %d acciones, costo %s. Sin precio (%s). Pásalo con --precio %s=VALOR."
                       % (t, p["cantidad"], m(p["costo"]), fuente, t))
            continue
        r = reglas.revisar_posicion(p, px, cfg, planes.get(t), eventos, hoy)
        r["fuente_precio"] = fuente
        filas.append(r)
        txt.append("%s · %d acciones · costo prom. %s · precio %s · %s (%+.1f%%) · %d ruedas\n  → %s: %s"
                   % (t, r["cantidad"], m(r["costo_promedio"]), m(px), m(r["resultado"]), r["resultado_pct"],
                      r["ruedas_abierta"], r["accion"], " ".join(r["razones"])))
    cerr = cartera.operaciones_cerradas(lotes)
    mes = sum(o["ganancia_realizada"] for o in cerr if o["fecha_ultima_venta"].strftime("%Y-%m") == hoy.strftime("%Y-%m"))
    txt.append("Resultado realizado del mes: %s (límite: -%s)." % (m(mes), m(cfg["capital_cop"] * cfg["reglas"]["max_perdida_mes_pct"] / 100)))
    cap = _capital(args, cfg, pos)
    txt.append("Capital %s · invertido al costo %s · efectivo disponible %s (%s)."
               % (m(cap["capital"]), m(cap["invertido"]), m(cap["disponible"]), cap["fuente_disponible"]))
    desde = cartera.fecha_de_los_datos()
    pregunta = None
    if desde and desde < hoy and getattr(args, "efectivo", None) is None:
        pregunta = _pregunta_cierres(pos, desde)
        txt.insert(0, pregunta + "\nCon los datos que hay:")
    out(args, {"posiciones": filas, "resultado_mes": mes, "capital": cap, "datos_hasta": desde, "pregunta": pregunta},
        "\n".join(txt))


def cmd_plan(args, cfg):
    t = args.ticker.upper()
    hoy = dt.date.today()
    velas = None
    if args.stop and args.stop.startswith("atr"):
        velas = datos.historico(t, cfg)
    pos = _posiciones(args)
    aviso = ""
    efectivo = None
    if cartera.ULTIMO_EXPORT.get("ruta"):
        cap = _capital(args, cfg, pos)
        efectivo = cap["disponible"]
        desde = cartera.fecha_de_los_datos()
        al_dia = args.efectivo is not None or (desde and desde >= hoy)
        if efectivo < cfg["reglas"]["min_orden_cop"]:
            msg = ("NO SE CREÓ EL PLAN: no hay efectivo para comprar. Capital %s, invertido (al costo) %s, disponible %s "
                   "(%s); la orden mínima es %s." % (m(cap["capital"]), m(cap["invertido"]), m(efectivo),
                                                    cap["fuente_disponible"], m(cfg["reglas"]["min_orden_cop"])))
            if not al_dia:
                msg += "\n" + _pregunta_cierres(pos, desde)
            msg += ("\nSi la app muestra otro saldo disponible, vuelve a correr el plan con --efectivo VALOR.")
            print(msg)
            sys.exit(3)
        if not al_dia:
            aviso = _pregunta_cierres(pos, desde) + "\nMientras tanto, este es el plan con los datos que hay:\n"
    else:
        aviso = ("AVISO: no encontré tu export, así que el plan NO sabe cuánto efectivo tienes ni qué posiciones "
                 "abiertas hay. Pásalo con --efectivo VALOR o exporta tus órdenes.\n")
    try:
        pl = planmod.crear(t, args.entrada, cfg, args.stop, args.objetivo, cantidad=args.cantidad, velas=velas,
                           posicion_actual=pos.get(t), hoy=hoy, motivo=args.motivo or "", valor=args.valor,
                           efectivo=efectivo)
    except ValueError as e:
        sys.exit("NO SE CREÓ EL PLAN: %s" % e)
    ver = _riesgo(pl, cfg, pos, args, hoy, efectivo=efectivo)
    if args.guardar:
        planes = C.read_json(C.path("planes.json"), {}) or {}
        planes[t] = pl
        C.write_json(C.path("planes.json"), planes)
    txt = ("PLAN %s · entrada %s · %d acciones (%s = %.2f millones, limitada por %s)\n"
           "  Stop %s (%s) · objetivo %s (%s) · equilibrio %s\n"
           "  Si toca el stop: %s · si llega al objetivo: %s · ganancia/riesgo neto %.2f\n"
           "  Si sigue en rojo el %s, salir. Fecha máxima: %s.\n"
           % (t, m(pl["entrada"]), pl["cantidad"], m(pl["valor_orden"]), pl["valor_orden"] / 1e6,
              pl["cantidad_limitada_por"], m(pl["stop"]),
              pl["stop_desc"], m(pl["objetivo"]), pl["objetivo_desc"], m(pl["precio_equilibrio"]),
              m(-pl["perdida_neta_en_stop"]), m(pl["ganancia_neta_en_objetivo"]), pl["rr_neto"],
              pl["salir_si_en_rojo_el"], pl["salir_a_mas_tardar_el"]))
    txt = aviso + txt + _texto_riesgo(ver)
    out(args, {"plan": pl, "riesgo": ver, "efectivo_disponible": efectivo, "pregunta": aviso or None}, txt)


def _posiciones(args):
    try:
        return cartera.posiciones_abiertas(cartera.armar_pares(cartera.leer_ordenes(getattr(args, "csv", None))))
    except Exception:
        return {}


def _lista_posiciones(pos):
    return ", ".join("%s %d acc. (%s)" % (t, p["cantidad"], m(p["costo"])) for t, p in sorted(pos.items())) or "ninguna"


def _pregunta_cierres(pos, desde):
    return ("PREGUNTA AL USUARIO ANTES DE SEGUIR: tus datos llegan hasta el %s. Posiciones abiertas según esos datos: %s. "
            "¿Vendiste (o compraste) algo después de esa fecha? Por cada operación necesito: acción, compra o venta, "
            "cantidad, precio y fecha. Se registra con:\n  copiloto.py operacion agregar venta TICKER --cantidad N "
            "--precio P --fecha AAAA-MM-DD\n(o exporta de nuevo desde la app y déjalo en Descargas). Si no hubo nada: "
            "copiloto.py operacion confirmar"
            % (desde, _lista_posiciones(pos)))


def _capital(args, cfg, pos):
    return cartera.estado_capital(pos, cfg, getattr(args, "efectivo", None))


def _riesgo(pl, cfg, pos, args, hoy, efectivo=None):
    mes = 0.0
    try:
        cerr = cartera.operaciones_cerradas(cartera.armar_pares(cartera.leer_ordenes(args.csv)))
        mes = sum(o["ganancia_realizada"] for o in cerr if o["fecha_ultima_venta"].strftime("%Y-%m") == hoy.strftime("%Y-%m"))
    except Exception:
        pass
    mercado, fuente = _precio(pl["ticker"], cfg, _precios_forzados(args))
    if efectivo is None and cartera.ULTIMO_EXPORT.get("ruta"):
        efectivo = _capital(args, cfg, pos)["disponible"]
    return reglas.revisar_plan(pl, cfg, pos, mes, C.read_json(C.path("eventos.json"), []), hoy,
                               precio_mercado=mercado, fuente_precio=fuente, efectivo=efectivo)


def _texto_riesgo(ver):
    return "RIESGO: %s\n" % ver["veredicto"] + "\n".join("  [%s] %s: %s" % (c["estado"], c["regla"], c["detalle"]) for c in ver["checks"])


def cmd_riesgo(args, cfg):
    t = args.ticker.upper()
    pl = (C.read_json(C.path("planes.json"), {}) or {}).get(t)
    if not pl:
        sys.exit("No hay plan guardado para %s. Crea uno con: copiloto.py plan %s --entrada PRECIO --guardar" % (t, t))
    pos = _posiciones(args)
    ver = _riesgo(pl, cfg, pos, args, dt.date.today())
    out(args, ver, _texto_riesgo(ver))


def cmd_simular(args, cfg):
    t = args.ticker.upper()
    r = cfg["reglas"]
    velas = datos.leer_csv_velas(args.velas) if args.velas else datos.historico(t, cfg, rango=args.rango)
    stop = (args.stop if args.stop is not None else r["stop_pct"]) / 100
    obj = (args.objetivo if args.objetivo is not None else r["stop_pct"] * r["objetivo_r"]) / 100
    dias = args.dias or r["max_dias_total"]
    valor = args.valor or min(r["max_orden_cop"], cfg["capital_cop"] * r["max_posicion_pct"] / 100)
    h = simulador.historia(velas, stop, obj, dias, valor, cfg)
    mc = simulador.montecarlo(velas, stop, obj, dias, valor, cfg, n=args.caminos)
    f = lambda x: "%.1f%%" % (100 * x)
    txt = ("SIMULACIÓN %s · stop -%s · objetivo +%s · máx. %d ruedas · orden ≈ %s · %d velas (%s a %s)\n"
           "  Historia real (%d entradas): objetivo %s · stop %s · por tiempo %s · ganan neto %s · resultado medio %s → %s\n"
           "  Montecarlo (%d caminos, semilla %d): objetivo %s · stop %s · por tiempo %s · ganan neto %s · resultado medio %s → %s\n"
           "  Es una simulación con el pasado de la acción, no una predicción."
           % (t, f(stop), f(obj), dias, m(valor), len(velas), velas[0]["fecha"], velas[-1]["fecha"],
              h["n"], f(h["pct_objetivo"]), f(h["pct_stop"]), f(h["pct_tiempo"]), f(h["pct_gana_neto"]),
              f(h["resultado_medio_neto_pct"]), h["veredicto"],
              mc["caminos"], mc["semilla"], f(mc["pct_objetivo"]), f(mc["pct_stop"]), f(mc["pct_tiempo"]),
              f(mc["pct_gana_neto"]), f(mc["resultado_medio_neto_pct"]), mc["veredicto"]))
    out(args, {"historia": h, "montecarlo": mc}, txt)


def cmd_ticket(args, cfg):
    t = args.ticker.upper()
    if args.lado == "compra":
        pl = (C.read_json(C.path("planes.json"), {}) or {}).get(t)
        if not pl:
            sys.exit("Primero crea y guarda el plan: copiloto.py plan %s --entrada PRECIO --guardar" % t)
        pos = _posiciones(args)
        ver = _riesgo(pl, cfg, pos, args, dt.date.today())
        txt = ticket.texto_compra(pl, ver["veredicto"])
        fila = {"ticker": t, "accion": "compra", "cantidad": pl["cantidad"], "precio": pl["entrada"], "stop": pl["stop"],
                "objetivo": pl["objetivo"], "valor": pl["valor_orden"], "motivo": pl.get("motivo", ""),
                "estrategia": args.estrategia or "", "veredicto_riesgo": ver["veredicto"], "decision": args.decision or ""}
    else:
        if not (args.cantidad and args.precio):
            sys.exit("Para vender indica --cantidad y --precio.")
        txt = ticket.texto_venta(t, args.cantidad, args.precio, args.motivo)
        fila = {"ticker": t, "accion": "venta", "cantidad": args.cantidad, "precio": args.precio,
                "valor": args.cantidad * args.precio, "motivo": args.motivo or "", "decision": args.decision or ""}
    if args.registrar:
        txt += "\nRegistrado en " + ticket.registrar(fila)
    out(args, fila, txt)


def cmd_operacion(args, cfg):
    """Registra una compra o venta YA EJECUTADA que todavía no está en el export."""
    if args.accion == "confirmar":
        cartera.confirmar_al_dia(dt.date.today())
        return out(args, {"confirmado_hasta": dt.date.today()},
                   "Anotado: no hay más operaciones fuera de tus datos hasta hoy (%s). No vuelvo a preguntar hoy."
                   % dt.date.today())
    if args.accion == "listar":
        p = C.path("operaciones_manuales.csv")
        if not os.path.exists(p):
            return out(args, [], "No hay operaciones manuales.")
        ords = cartera.leer_ordenes(getattr(args, "csv", None))
        man = [o for o in ords if o["origen"] == "manual"]
        return out(args, man, "\n".join("%s %s %s %d a %s" % (o["fecha"], o["tipo"], o["ticker"], o["cantidad"],
                                                             m(o["precio"])) for o in man) or "No hay operaciones manuales.")
    if not (args.tipo and args.ticker and args.cantidad and args.precio and args.fecha):
        sys.exit("Faltan datos. Uso: operacion agregar venta TICKER --cantidad N --precio P --fecha AAAA-MM-DD [--hora HH:MM]")
    t, tipo = args.ticker.upper(), args.tipo.capitalize()
    try:
        fecha = dt.datetime.strptime(args.fecha + " " + (args.hora or "15:00"), "%Y-%m-%d %H:%M")
    except ValueError:
        sys.exit("Fecha u hora no válidas. Usa --fecha AAAA-MM-DD y --hora HH:MM.")
    if fecha.date() > dt.date.today():
        sys.exit("La fecha %s es futura: aquí solo van operaciones YA ejecutadas." % fecha.date())
    pos = _posiciones(args)
    if tipo == "Venta":
        tengo = pos.get(t, {}).get("cantidad", 0)
        if args.cantidad > tengo:
            sys.exit("Según tus datos tienes %d acciones de %s; no puedes registrar una venta de %d. Revisa la acción "
                     "o registra antes la compra que falta." % (tengo, t, args.cantidad))
    comision = args.comision if args.comision is not None else com.comision(args.cantidad * args.precio, cfg)
    p = cartera.registrar_operacion(tipo, t, args.cantidad, args.precio, fecha, comision)
    if not args.hay_mas:
        cartera.confirmar_al_dia(dt.date.today())
    pos2 = cartera.posiciones_abiertas(cartera.armar_pares(cartera.leer_ordenes(getattr(args, "csv", None))))
    cap = _capital(args, cfg, pos2)
    out(args, {"registrada": {"tipo": tipo, "ticker": t, "cantidad": args.cantidad, "precio": args.precio,
                              "fecha": fecha, "comision": comision}, "archivo": p, "capital": cap},
        "Registrada: %s %s %d a %s el %s (comisión %s) en %s.\nAhora: posiciones %s · efectivo disponible %s.\n"
        "Cuando exportes de nuevo desde la app, esta operación no se cuenta dos veces. Si hay más operaciones, "
        "regístralas igual (con --hay-mas en todas menos la última)."
        % (tipo, t, args.cantidad, m(args.precio), fecha.strftime("%Y-%m-%d %H:%M"), m(comision), p,
           _lista_posiciones(pos2), m(cap["disponible"])))


def cmd_evento(args, cfg):
    p = C.path("eventos.json")
    ev = C.read_json(p, []) or []
    if args.accion == "agregar":
        dt.date.fromisoformat(args.fecha)
        ev = [e for e in ev if not (e["ticker"] == args.ticker.upper() and e["fecha"] == args.fecha and e["tipo"] == args.tipo)]
        ev.append({"ticker": args.ticker.upper(), "fecha": args.fecha, "tipo": args.tipo, "nota": args.nota or ""})
        ev.sort(key=lambda e: e["fecha"])
        C.write_json(p, ev)
    hoy = dt.date.today().isoformat()
    fut = [e for e in ev if e["fecha"] >= hoy]
    out(args, fut, "\n".join("%s %s %s %s" % (e["fecha"], e["ticker"], e["tipo"], e.get("nota", "")) for e in fut) or "Sin eventos próximos.")


def cmd_historial(args, cfg):
    desde = dt.datetime.fromisoformat(args.desde) if args.desde else None
    cerr = cartera.operaciones_cerradas(cartera.armar_pares(_ordenes(args), desde))
    if args.con_historico:
        velas = {}
        for t in sorted({o["ticker"] for o in cerr}):
            try:
                velas[t] = datos.historico(t, cfg, rango="2y")
            except datos.DatosError as e:
                print("Sin histórico de %s: %s" % (t, e), file=sys.stderr)
        res = revision.con_historico(cerr, velas, cfg)
        lineas = ["Con histórico diario: %d de %d operaciones simuladas · %d excluidas (dejaron %s en la realidad)."
                  % (res["operaciones_simuladas"], res["operaciones_totales"], res["excluidas"],
                     m(res["resultado_real_excluidas"])),
                  "  Sobre las simuladas → real: %s · con tus reglas: %s" % (m(res["resultado_real"]),
                                                                          m(res["resultado_con_reglas"])),
                  "", "  %-10s %4s %4s %14s %14s   obj/stop/tiempo" % ("Acción", "ops", "excl", "real", "con reglas")]
        for t, d in sorted(res["por_ticker"].items(), key=lambda kv: kv[1]["con_reglas"] - kv[1]["real"]):
            lineas.append("  %-10s %4d %4d %14s %14s   %d/%d/%d" % (t, d["operaciones"], d["excluidas"], m(d["real"]),
                          m(d["con_reglas"]), d["objetivo"], d["stop"], d["tiempo"] + d["abierta"]))
        if res["excluidas"]:
            lineas.append("\n  Excluidas porque el precio de la fuente no cuadra con tu compra (revisa el símbolo,"
                          " o pon el histórico de la acción en datos/historico/TICKER.csv):")
            for x in res["detalle_excluidas"][: (None if args.detalle else 10)]:
                lineas.append("   - %s %s compra a %s: %s" % (x["fecha"], x["ticker"], m(x["precio_compra"]), x["motivo"]))
            if not args.detalle and res["excluidas"] > 10:
                lineas.append("   ... y %d más (usa --detalle)" % (res["excluidas"] - 10))
        if args.detalle:
            lineas.append("\n  Operación por operación (simuladas):")
            for x in res["detalle"]:
                lineas.append("   - %s %-9s compra %s → %-8s día %2d a %s · real %s · con reglas %s"
                              % (x["fecha"], x["ticker"], m(x["precio_compra"]), x["salida"], x["dias"],
                                 m(x["precio_salida"]), m(x["real"]), m(x["con_reglas"])))
        lineas.append("  " + res["aviso"])
        txt = "\n".join(lineas)
    else:
        res = revision.aproximada(cerr, cfg)
        txt = ("%d operaciones cerradas. Resultado real: %s. Con stop de -%.0f%%: %s (%d pérdidas cortadas, %s menos de pérdida).\n"
               "  Compras mayores a %s: %d, que dejaron %s. Compras menores a %s: %d, que dejaron %s.\n  %s"
               % (res["operaciones"], m(res["resultado_real"]), cfg["reglas"]["stop_pct"], m(res["resultado_con_stop"]),
                  res["perdidas_cortadas"], m(res["ahorro_por_stop"]), m(cfg["reglas"]["max_orden_cop"]),
                  res["compras_mayores_al_maximo"], m(res["resultado_de_esas_compras"]), m(cfg["reglas"]["min_orden_cop"]),
                  res["compras_menores_al_minimo"], m(res["resultado_de_esas_compras_pequenas"]), res["aviso"]))
    out(args, res, txt)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Asistente de decisiones para acciones colombianas (no ejecuta órdenes).")
    ap.add_argument("--json", action="store_true", help="salida en JSON")
    ap.add_argument("--config", help="ruta de config.json (por defecto datos/config.json)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    p = sub.add_parser("archivos"); p.add_argument("--csv")
    p = sub.add_parser("reloj"); p.add_argument("--ahora"); p.add_argument("--festivos", action="store_true")
    p = sub.add_parser("precio"); p.add_argument("ticker"); p.add_argument("--sin-cache", action="store_true")
    p = sub.add_parser("cartera"); p.add_argument("--csv"); p.add_argument("--precio", action="append")
    p.add_argument("--efectivo", type=num, help="saldo disponible que muestra la app")
    p = sub.add_parser("plan"); p.add_argument("ticker"); p.add_argument("--entrada", type=num, required=True)
    p.add_argument("--stop", help="pct:3 | precio:4200 | atr:2")
    p.add_argument("--objetivo", help="precio (4550) | pct:6 | r:2")
    p.add_argument("--valor", type=num, help="pesos a invertir (ej. 5000000): el agente calcula la cantidad")
    p.add_argument("--cantidad", type=int, help="mejor no usarlo: la cantidad la calculan las reglas")
    p.add_argument("--motivo"); p.add_argument("--guardar", action="store_true"); p.add_argument("--csv")
    p.add_argument("--mercado", type=num, help="precio actual que ves en la app, si Yahoo no cuadra")
    p.add_argument("--efectivo", type=num, help="saldo disponible que muestra la app")
    p = sub.add_parser("riesgo"); p.add_argument("ticker"); p.add_argument("--csv"); p.add_argument("--mercado", type=num)
    p.add_argument("--efectivo", type=num)
    p = sub.add_parser("simular"); p.add_argument("ticker"); p.add_argument("--stop", type=num)
    p.add_argument("--objetivo", type=num); p.add_argument("--dias", type=int); p.add_argument("--valor", type=num)
    p.add_argument("--rango", default="1y"); p.add_argument("--velas"); p.add_argument("--caminos", type=int, default=10000)
    p = sub.add_parser("ticket"); p.add_argument("lado", choices=["compra", "venta"]); p.add_argument("ticker")
    p.add_argument("--cantidad", type=int); p.add_argument("--precio", type=num); p.add_argument("--motivo")
    p.add_argument("--estrategia"); p.add_argument("--decision"); p.add_argument("--registrar", action="store_true")
    p.add_argument("--csv")
    p = sub.add_parser("operacion"); p.add_argument("accion", choices=["agregar", "listar", "confirmar"])
    p.add_argument("tipo", nargs="?", choices=["compra", "venta"]); p.add_argument("ticker", nargs="?")
    p.add_argument("--cantidad", type=int); p.add_argument("--precio", type=num); p.add_argument("--fecha")
    p.add_argument("--hora"); p.add_argument("--comision", type=num); p.add_argument("--csv")
    p.add_argument("--hay-mas", action="store_true", help="no marcar los datos como al día (faltan más por registrar)")
    p = sub.add_parser("evento"); p.add_argument("accion", choices=["agregar", "listar"])
    p.add_argument("ticker", nargs="?"); p.add_argument("fecha", nargs="?")
    p.add_argument("tipo", nargs="?", default="resultados"); p.add_argument("--nota")
    p = sub.add_parser("historial"); p.add_argument("--csv"); p.add_argument("--desde")
    p.add_argument("--con-historico", action="store_true"); p.add_argument("--detalle", action="store_true")
    args = ap.parse_args(argv)
    if args.cmd == "init":
        return cmd_init(args)
    cfg = C.load(args.config)
    {"archivos": cmd_archivos, "reloj": cmd_reloj, "precio": cmd_precio, "cartera": cmd_cartera, "plan": cmd_plan, "riesgo": cmd_riesgo,
     "simular": cmd_simular, "ticket": cmd_ticket, "evento": cmd_evento, "operacion": cmd_operacion, "historial": cmd_historial}[args.cmd](args, cfg)
    if args.cmd != "archivos":
        _nota_export()


if __name__ == "__main__":
    main()
