"""Configuración del agente: valores por defecto + datos/config.json del usuario.

Todo lo que el agente lee y escribe vive en la carpeta `datos/` del proyecto. Se ubica así,
en orden, para que funcione sin importar desde qué carpeta se corra el comando:
  1. la variable de entorno COPILOTO_DIR;
  2. ./datos en la carpeta actual, si existe;
  3. datos/ en la raíz del proyecto (dos carpetas arriba de este skill, donde está instalar.py);
  4. ./datos en la carpeta actual (se crea).
Solo biblioteca estándar.
"""
import copy
import json
import os

DEFAULTS = {
    # --- Cuenta ---
    "capital_cop": 10000000,          # capital total invertible: CÁMBIALO al tuyo
    "plan_comisiones": "pro",          # "pro" o "estandar" (tarifas de abajo)
    # --- Comisiones por orden (incluyen IVA 19%) ---
    # Valores por defecto: tarifas publicadas por la app Trii en 2026 (planes Pro y estándar).
    # Si usas otra comisionista, cambia esta tabla por sus tarifas.
    #   pro: órdenes hasta $5M -> $7.437,50 fijos; más de $5M -> 0,14875% (0,125% + IVA).
    "comisiones": {
        "pro": {"umbral_cop": 5000000, "fija_cop": 7437.5, "pct_sobre_umbral": 0.0014875},
        "estandar": {"umbral_cop": 5000000, "fija_cop": 17701.25, "pct_sobre_umbral": 0.002975},
    },
    "suscripcion_pro_mes_cop": 27900,
    # --- Reglas de riesgo (por qué cada una: referencias/reglas.md) ---
    "reglas": {
        "stop_pct": 3.0,                  # stop de pérdida por defecto (% bajo la entrada)
        "objetivo_r": 2.0,                # objetivo = 2 veces el riesgo (R): con stop -3%, +6%
        "max_dias_perdedora": 10,         # si a los N días va en rojo, salir
        "max_dias_total": 20,             # ninguna operación más de N días hábiles
        "max_posicion_pct": 30.0,         # máx. % del capital en una sola acción
        "max_orden_cop": 20000000,        # tope por orden: limita el daño de una sola mala compra
        "min_orden_cop": 2000000,         # por debajo la comisión pasa del 0,4%
        "max_perdida_operacion_pct": 1.0, # pérdida máx. por operación, % del capital
        "max_perdida_mes_pct": 4.0,       # si el mes va en -4%, no más compras ese mes
        "max_posiciones_abiertas": 4,
        "min_rr_neto": 1.5,               # ganancia/riesgo DESPUÉS de comisiones
        "dias_bloqueo_eventos": 2,        # no comprar N días hábiles antes de resultados
        "permitir_promediar_a_la_baja": False,
    },
    # --- Datos de mercado ---
    # Proveedor de precios: "yahoo" (gratis, no oficial) o "manual" (datos/precios.json).
    "proveedor_precios": "yahoo",
    # Símbolo en Yahoo para cada ticker. Las acciones globales que la app negocia en pesos
    # (terminan en CO) se siguen con la acción original en EE. UU. y se convierten con la TRM.
    "simbolos": {
        "NUCO": {"yahoo": "NU", "moneda": "USD"},
        "NVDACO": {"yahoo": "NVDA", "moneda": "USD"},
        "AAPLCO": {"yahoo": "AAPL", "moneda": "USD"},
        "GDXCO": {"yahoo": "GDX", "moneda": "USD"},
        "MSFTCO": {"yahoo": "MSFT", "moneda": "USD"},
    },
    "sufijo_yahoo_bvc": ".CL",        # p. ej. ECOPETROL -> ECOPETROL.CL (verifícalo con `copiloto.py precio`)
    "simbolo_trm": "COP=X",
    # --- Horario BVC (hora Colombia) ---
    "horario": {
        "regular": {"apertura": "09:30", "cierre": "16:00"},
        "verano_ny": {"apertura": "08:30", "cierre": "15:00"},
        "minutos_subasta_cierre": 10,
    },
    "dias_no_bursatiles_extra": [],   # agrega aquí días que la BVC anuncie por circular
}


RAIZ_PROYECTO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def base_dir():
    env = os.environ.get("COPILOTO_DIR")
    if env:
        return env
    aqui = os.path.join(os.getcwd(), "datos")
    if os.path.isdir(aqui):
        return aqui
    if os.path.exists(os.path.join(RAIZ_PROYECTO, "instalar.py")):
        return os.path.join(RAIZ_PROYECTO, "datos")
    return aqui


def path(*parts):
    return os.path.join(base_dir(), *parts)


def _merge(base, extra):
    out = copy.deepcopy(base)
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load(config_path=None):
    p = config_path or path("config.json")
    user = {}
    if os.path.exists(p):
        with open(p, encoding="utf-8-sig") as f:  # -sig: el Bloc de notas agrega BOM
            user = json.load(f)
    if "plan_trii" in user:  # nombre viejo de la clave (versiones trii-agente)
        user.setdefault("plan_comisiones", user.pop("plan_trii"))
    return _merge(DEFAULTS, user)


def save_default(config_path=None, overwrite=False):
    p = config_path or path("config.json")
    if os.path.exists(p) and not overwrite:
        return p, False
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(DEFAULTS, f, ensure_ascii=False, indent=2)
    return p, True


def read_json(p, default=None):
    if not os.path.exists(p):
        return default
    with open(p, encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(p, data):
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    os.replace(tmp, p)
    return p
