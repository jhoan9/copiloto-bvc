"""Lee números como los escribe un colombiano (o un modelo que copió la salida del agente).

En Colombia el punto separa miles y la coma los decimales: "2.515" son dos mil quinientos
quince, no 2,5. Python lee float("2.515") como 2,515 y eso dañaba los planes.

    num("2.515")      -> 2515       num("614.980")  -> 614980
    num("$1.234.567") -> 1234567    num("4.850,5")  -> 4850.5
    num("2515")       -> 2515       num("3,5")      -> 3.5
    num("4.85")       -> 4.85       (no son grupos de 3: decimal)
"""
import re

_MILES_PUNTO = re.compile(r"^\d{1,3}(\.\d{3})+$")
_MILES_COMA = re.compile(r"^\d{1,3}(,\d{3})+\.\d+$")


def num(s):
    if isinstance(s, (int, float)):
        return float(s)
    t = str(s).strip().replace("$", "").replace(" ", "").replace("\u00a0", "").replace("COP", "")
    neg = t.startswith("-")
    t = t.lstrip("+-")
    if not t:
        raise ValueError("número vacío")
    if "," in t and "." in t:
        if _MILES_COMA.match(t):          # 2,515.50 (formato EE. UU.)
            t = t.replace(",", "")
        else:                             # 2.515,50 (formato Colombia)
            t = t.replace(".", "").replace(",", ".")
    elif "," in t:
        partes = t.split(",")
        if len(partes) > 2 or (len(partes[1]) == 3 and len(partes[0]) <= 3 and partes[0] != "0"):
            t = t.replace(",", "")        # 2,515 o 1,234,567: miles
        else:
            t = t.replace(",", ".")       # 3,5: decimal
    elif _MILES_PUNTO.match(t):
        t = t.replace(".", "")            # 2.515 o 1.234.567: miles
    v = float(t)
    return -v if neg else v
