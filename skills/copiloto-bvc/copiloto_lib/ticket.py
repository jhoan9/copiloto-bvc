"""Ticket para poner la orden A MANO en la app y diario de decisiones.

Ningún broker regulado en Colombia ofrece hoy una API pública para que un programa envíe
órdenes de acciones de la BVC a nombre de una persona, así que el agente nunca ejecuta:
te deja la orden escrita, tú la revisas y la pones en la app.
"""
import csv
import datetime as dt
import os

from . import config as C

CAMPOS = ["fecha", "ticker", "accion", "cantidad", "precio", "stop", "objetivo", "valor", "motivo",
          "estrategia", "veredicto_riesgo", "decision"]


def texto_compra(plan, veredicto):
    m = lambda x: "{:,.0f}".format(x).replace(",", ".")
    lineas = [
        "ORDEN PARA PONER EN LA APP: COMPRA %s" % plan["ticker"],
        "  Validación de riesgo: %s" % veredicto,
        "  1. En la app abre %s y toca Comprar." % plan["ticker"],
        "  2. Tipo de orden: Límite. Precio: $%s. Cantidad: %d acciones (≈ $%s)." % (m(plan["entrada"]), plan["cantidad"], m(plan["valor_orden"])),
        "  3. Cuando se ejecute, crea la orden de stop loss (si tu plan lo permite): venta de %d a $%s." % (plan["cantidad"], m(plan["stop"])),
        "  4. Deja una orden límite de venta en el objetivo: $%s." % m(plan["objetivo"]),
        "  5. Si el %s sigue en rojo, vende. Fecha máxima para salir: %s." % (plan["salir_si_en_rojo_el"], plan["salir_a_mas_tardar_el"]),
        "  Si toca el stop pierdes ≈ $%s; si llega al objetivo ganas ≈ $%s (ya con comisiones)."
        % (m(plan["perdida_neta_en_stop"]), m(plan["ganancia_neta_en_objetivo"])),
    ]
    if veredicto != "PASA":
        lineas.insert(1, "  ⚠ Tus reglas BLOQUEAN esta compra. Si la haces igual, anótalo como excepción.")
    return "\n".join(lineas)


def texto_venta(ticker, cantidad, precio, motivo=""):
    m = lambda x: "{:,.0f}".format(x).replace(",", ".")
    return "\n".join([
        "ORDEN PARA PONER EN LA APP: VENTA %s" % ticker,
        "  1. En la app abre %s y toca Vender." % ticker,
        "  2. Tipo de orden: Límite. Precio: $%s. Cantidad: %d acciones (vende todo en UNA orden: una sola comisión)." % (m(precio), cantidad),
        "  3. Cancela el stop loss y la orden de objetivo que tenías puestas para esta acción.",
        "  Motivo: %s" % (motivo or "-"),
    ])


def registrar(fila):
    p = C.path("diario.csv")
    nuevo = not os.path.exists(p)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        if nuevo:
            w.writeheader()
        fila = dict(fila)
        fila.setdefault("fecha", dt.datetime.now().strftime("%Y-%m-%d %H:%M"))
        w.writerow({k: fila.get(k, "") for k in CAMPOS})
    return p
