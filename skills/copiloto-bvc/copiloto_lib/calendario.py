"""Calendario y reloj de la Bolsa de Valores de Colombia (BVC).

Festivos: se calculan con las reglas colombianas (Ley 51 de 1983, "Ley Emiliani") y la
Pascua, así que funcionan para cualquier año. Horario: la BVC mueve su jornada una hora
antes mientras Nueva York está en horario de verano. Verifica siempre las circulares de la
BVC: puede declarar días no hábiles adicionales (agrégalos en config.json).
"""
import datetime as dt

try:
    from zoneinfo import ZoneInfo
    TZ_CO = ZoneInfo("America/Bogota")
except Exception:  # pragma: no cover - Python sin zoneinfo
    TZ_CO = dt.timezone(dt.timedelta(hours=-5))


def pascua(anio):
    a = anio % 19
    b, c = divmod(anio, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = ((h + l - 7 * m + 114) % 31) + 1
    return dt.date(anio, mes, dia)


def _lunes_siguiente(d):
    return d + dt.timedelta(days=(7 - d.weekday()) % 7)


def festivos(anio):
    """Diccionario fecha -> nombre de los festivos de Colombia en `anio`."""
    p = pascua(anio)
    fijos = {
        dt.date(anio, 1, 1): "Año Nuevo",
        dt.date(anio, 5, 1): "Día del Trabajo",
        dt.date(anio, 7, 20): "Día de la Independencia",
        dt.date(anio, 8, 7): "Batalla de Boyacá",
        dt.date(anio, 12, 8): "Inmaculada Concepción",
        dt.date(anio, 12, 25): "Navidad",
        p - dt.timedelta(days=3): "Jueves Santo",
        p - dt.timedelta(days=2): "Viernes Santo",
    }
    trasladables = {
        dt.date(anio, 1, 6): "Reyes Magos",
        dt.date(anio, 3, 19): "San José",
        dt.date(anio, 6, 29): "San Pedro y San Pablo",
        dt.date(anio, 8, 15): "Asunción de la Virgen",
        dt.date(anio, 10, 12): "Día de la Raza",
        dt.date(anio, 11, 1): "Todos los Santos",
        dt.date(anio, 11, 11): "Independencia de Cartagena",
    }
    out = dict(fijos)
    for d, n in trasladables.items():
        out[_lunes_siguiente(d)] = n
    for dias, n in ((43, "Ascensión"), (64, "Corpus Christi"), (71, "Sagrado Corazón")):
        out[p + dt.timedelta(days=dias)] = n
    return out


def es_dia_bursatil(d, cfg=None):
    if d.weekday() >= 5:
        return False, "fin de semana"
    n = festivos(d.year).get(d)
    if n:
        return False, "festivo: " + n
    extra = set((cfg or {}).get("dias_no_bursatiles_extra", []))
    if d.isoformat() in extra:
        return False, "día no hábil anunciado por la BVC"
    return True, ""


def dias_bursatiles_entre(a, b, cfg=None):
    """Días bursátiles en (a, b]: cuántas ruedas pasaron desde `a` hasta `b`."""
    if b <= a:
        return 0
    n, d = 0, a
    while d < b:
        d += dt.timedelta(days=1)
        if es_dia_bursatil(d, cfg)[0]:
            n += 1
    return n


def sumar_dias_bursatiles(d, n, cfg=None):
    while n > 0:
        d += dt.timedelta(days=1)
        if es_dia_bursatil(d, cfg)[0]:
            n -= 1
    return d


def _verano_ny(d):
    """True si Nueva York está en horario de verano ese día (2º domingo de marzo al
    1er domingo de noviembre, regla vigente en EE. UU.)."""
    mar1 = dt.date(d.year, 3, 1)
    inicio = mar1 + dt.timedelta(days=(6 - mar1.weekday()) % 7 + 7)
    nov1 = dt.date(d.year, 11, 1)
    fin = nov1 + dt.timedelta(days=(6 - nov1.weekday()) % 7)
    return inicio <= d < fin


def horario(d, cfg):
    h = cfg["horario"]["verano_ny" if _verano_ny(d) else "regular"]
    hh = lambda s: dt.time(*map(int, s.split(":")))
    return hh(h["apertura"]), hh(h["cierre"])


def estado(ahora, cfg):
    """Estado de la BVC en `ahora` (datetime con zona o naive en hora Colombia)."""
    if ahora.tzinfo is None:
        ahora = ahora.replace(tzinfo=TZ_CO)
    ahora = ahora.astimezone(TZ_CO)
    d = ahora.date()
    ok, motivo = es_dia_bursatil(d, cfg)
    sig = d
    while True:
        sig += dt.timedelta(days=1)
        if es_dia_bursatil(sig, cfg)[0]:
            break
    out = {"ahora": ahora.strftime("%Y-%m-%d %H:%M"), "dia_bursatil": ok, "motivo": motivo,
           "proxima_rueda": sig.isoformat()}
    if not ok:
        out.update(abierta=False, fase="cerrada")
        return out
    ap, ci = horario(d, cfg)
    sub = (dt.datetime.combine(d, ci) - dt.timedelta(minutes=cfg["horario"]["minutos_subasta_cierre"])).time()
    t = ahora.time()
    if t < ap:
        fase = "antes de la apertura"
    elif t < sub:
        fase = "negociación continua"
    elif t < ci:
        fase = "subasta de cierre"
    else:
        fase = "cerrada (después del cierre)"
    out.update(abierta=ap <= t < ci, fase=fase, apertura=ap.strftime("%H:%M"),
               inicio_subasta_cierre=sub.strftime("%H:%M"), cierre=ci.strftime("%H:%M"))
    return out
