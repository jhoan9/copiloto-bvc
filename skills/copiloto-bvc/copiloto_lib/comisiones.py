"""Comisiones por orden según la tabla de config (ya incluyen IVA)."""


def comision(valor_orden, cfg):
    """Comisión en COP de UNA orden de compra o venta por `valor_orden` pesos."""
    t = cfg["comisiones"][cfg.get("plan_comisiones", "pro")]
    if valor_orden <= 0:
        return 0.0
    if valor_orden <= t["umbral_cop"]:
        return float(t["fija_cop"])
    return round(valor_orden * t["pct_sobre_umbral"], 2)


def ida_y_vuelta(cantidad, precio_compra, precio_venta, cfg):
    """Comisiones de comprar y vender `cantidad` acciones."""
    return comision(cantidad * precio_compra, cfg) + comision(cantidad * precio_venta, cfg)


def precio_equilibrio(cantidad, costo_total, cfg):
    """Precio de venta al que recuperas `costo_total` (compra + su comisión), pagando la
    comisión de venta. Resuelve el caso fijo y el porcentual."""
    if cantidad <= 0:
        return 0.0
    t = cfg["comisiones"][cfg.get("plan_comisiones", "pro")]
    p_fijo = (costo_total + t["fija_cop"]) / cantidad
    if p_fijo * cantidad <= t["umbral_cop"]:
        return p_fijo
    return costo_total / (cantidad * (1 - t["pct_sobre_umbral"]))
