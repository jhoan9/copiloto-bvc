"""Encuentra y lee el export de órdenes de la app (por ejemplo, "Información financiera.csv").

Está hecho para que el agente encuentre el archivo a la primera, sin buscar en el disco:
- Reconoce el export por sus COLUMNAS, no por el nombre. "Información financiera (3).csv",
  "export.csv" o "informacion_financiera.csv" funcionan igual.
- Lo busca en datos/, en la raíz del proyecto, en la carpeta actual y en Descargas/Downloads
  (también dentro de OneDrive). Si hay varios, usa el que llega a la fecha más reciente.
- Si el más reciente está fuera de datos/, lo copia a datos/informacion_financiera.csv
  (guarda el anterior en datos/respaldo/). Así el siguiente comando lo encuentra directo.
- Aguanta lo que hace Excel al abrir y guardar el archivo: codificación de Windows (cp1252),
  punto y coma como separador, números con punto de miles y coma decimal, y fechas como
  05/11/2026 10:22.
"""
import csv
import datetime as dt
import glob
import io
import os
import re
import shutil
import unicodedata

from . import config as C
from .numeros import num

NOMBRE_DESTINO = "informacion_financiera.csv"
NO_SON_EXPORT = {"operaciones_manuales.csv", "diario.csv"}

# columna lógica -> nombres aceptados (normalizados: sin tildes, minúsculas, solo letras/números)
COLUMNAS = {
    "fecha": ("fechayhora", "fechahora", "fecha"),
    "ticker": ("simbolodelaaccion", "simbolo", "ticker", "nemotecnico", "accion", "especie"),
    "tipo": ("tipodeorden", "tipo", "operacion", "lado"),
    "estado": ("estado",),
    "cantidad": ("accionescompletadas", "cantidad", "acciones"),
    "precio": ("precioporaccion", "precio"),
    "comision": ("valorcomision", "comision"),
}
OBLIGATORIAS = ("fecha", "ticker", "tipo", "cantidad", "precio")

MES = {"ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6, "jul": 7, "ago": 8,
       "sept": 9, "sep": 9, "oct": 10, "nov": 11, "dic": 12}
_FECHA_TEXTO = re.compile(r"(\d+) (\w+)\.? (\d{4}),? (\d+):(\d+)(?::\d+)? ?(a|p)\.? ?m\.?", re.I)
_FORMATOS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M",
             "%d/%m/%Y %I:%M %p", "%d/%m/%Y", "%d-%m-%Y %H:%M", "%d-%m-%Y")


class ExportError(Exception):
    pass


def _norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


def parse_fecha(s):
    s = " ".join(str(s).strip().replace(" ", " ").replace(" ", " ").split())
    m = _FECHA_TEXTO.match(s)
    if m:
        d, mo, y, h, mi, ap = m.groups()
        h = int(h) % 12 + (12 if ap.lower() == "p" else 0)
        return dt.datetime(int(y), MES[mo.lower()[:4] if mo.lower().startswith("sept") else mo.lower()[:3]],
                           int(d), h, int(mi))
    t = re.sub(r"\s*a\.?\s*m\.?$", " AM", s, flags=re.I)
    t = re.sub(r"\s*p\.?\s*m\.?$", " PM", t, flags=re.I)
    for fmt in _FORMATOS:
        try:
            return dt.datetime.strptime(t, fmt)
        except ValueError:
            pass
    raise ValueError("Fecha no reconocida: %r" % s)


def _leer_texto(path):
    with open(path, "rb") as f:
        crudo = f.read()
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return crudo.decode(enc), enc
        except UnicodeDecodeError:
            pass
    raise ExportError("No pude leer %s (codificación desconocida)" % path)


def leer_tabla(path):
    """(filas como listas, encabezado, info) con codificación y separador detectados."""
    texto, enc = _leer_texto(path)
    primera = texto.split("\n", 1)[0]
    sep = max((",", ";", "\t"), key=primera.count)
    filas = [r for r in csv.reader(io.StringIO(texto), delimiter=sep) if any(c.strip() for c in r)]
    if not filas:
        raise ExportError("%s está vacío" % os.path.basename(path))
    return filas[0], filas[1:], {"codificacion": enc, "separador": sep}


def _mapa(encabezado):
    norm = [_norm(h) for h in encabezado]
    mapa = {}
    for clave, nombres in COLUMNAS.items():
        for n in nombres:
            if n in norm:
                mapa[clave] = norm.index(n)
                break
    return mapa


def _num_excel_es(s):
    """Excel en español: la coma SIEMPRE es decimal ("809,000" = 809). Sin coma, num() decide."""
    t = str(s).strip().replace("$", "").replace(" ", "").replace("\u00a0", "")
    if "," in t:
        return float(t.replace(".", "").replace(",", "."))
    return num(t)


def leer_export(path, origen="export"):
    """Órdenes aprobadas, ordenadas por fecha. Lanza ExportError si no es un export."""
    encabezado, filas, info = leer_tabla(path)
    mapa = _mapa(encabezado)
    faltan = [c for c in OBLIGATORIAS if c not in mapa]
    if faltan:
        raise ExportError("%s no parece un export de órdenes: faltan las columnas %s"
                          % (os.path.basename(path), ", ".join(faltan)))
    # Con ";" el archivo pasó por Excel en español: punto de miles y coma decimal.
    a_numero = _num_excel_es if info["separador"] == ";" else (lambda x: float(str(x).replace(",", "")))
    out, malas = [], 0
    for r in filas:
        def col(k, defecto=""):
            i = mapa.get(k)
            return r[i].strip() if i is not None and i < len(r) else defecto
        if "estado" in mapa and "aprobad" not in _norm(col("estado")):
            continue
        tipo = _norm(col("tipo"))
        tipo = "Compra" if "compra" in tipo or tipo == "buy" else "Venta" if "venta" in tipo or tipo == "sell" else None
        try:
            q = int(a_numero(col("cantidad").split("/")[0]))
            o = {"fecha": parse_fecha(col("fecha")), "ticker": col("ticker").upper(), "tipo": tipo,
                 "cantidad": q, "precio": a_numero(col("precio")),
                 "comision": round(a_numero(col("comision", "0") or "0"), 2), "origen": origen}
        except (ValueError, KeyError):
            malas += 1
            continue
        if tipo and q > 0 and o["ticker"]:
            out.append(o)
        else:
            malas += 1
    out.sort(key=lambda o: o["fecha"])
    info.update(filas_ignoradas=malas)
    return out, info


def carpetas_de_busqueda():
    home = os.path.expanduser("~")
    dirs = [C.base_dir(), C.RAIZ_PROYECTO, os.getcwd()]
    for base in (home, os.path.join(home, "OneDrive")):
        dirs += [os.path.join(base, "Downloads"), os.path.join(base, "Descargas")]
    vistas, out = set(), []
    for d in dirs:
        k = os.path.normcase(os.path.abspath(d))
        if k not in vistas and os.path.isdir(d):
            vistas.add(k)
            out.append(d)
    return out


def _candidatos():
    datos = os.path.normcase(os.path.abspath(C.base_dir()))
    vistos, out = set(), []
    for d in carpetas_de_busqueda():
        en_datos = os.path.normcase(os.path.abspath(d)) == datos
        for p in glob.glob(os.path.join(d, "*.csv")):
            nombre = os.path.basename(p).lower()
            if nombre in NO_SON_EXPORT:
                continue
            # En Descargas solo miramos archivos con pinta de export, para no abrir todo.
            if not en_datos and not re.search(r"financ|export|orden|trii|operacion", _norm(nombre)):
                continue
            k = os.path.normcase(os.path.abspath(p))
            if k not in vistos:
                vistos.add(k)
                out.append(p)
    return out


def revisar_candidatos():
    """Lista de (ruta, info|None, error|None) con todo lo encontrado."""
    res = []
    for p in _candidatos():
        try:
            ords, info = leer_export(p)
            if not ords:
                raise ExportError("no tiene órdenes aprobadas")
            info.update(ordenes=len(ords), desde=ords[0]["fecha"], hasta=ords[-1]["fecha"],
                        modificado=os.path.getmtime(p))
            res.append((p, info, None))
        except (ExportError, OSError) as e:
            res.append((p, None, str(e)))
    return res


def export_activo(ruta=None, sincronizar=True):
    """Ruta e info del export a usar. Si viene `ruta`, se usa esa (y se valida)."""
    if ruta:
        if not os.path.isfile(ruta):
            raise ExportError("No existe el archivo %s" % ruta)
        ords, info = leer_export(ruta)
        info.update(ruta=ruta, ordenes=len(ords))
        return info
    validos = [(p, i) for p, i, e in revisar_candidatos() if i]
    if not validos:
        raise ExportError(mensaje_no_encontrado())
    p, info = max(validos, key=lambda x: (x[1]["hasta"], x[1]["ordenes"], x[1]["modificado"]))
    destino = C.path(NOMBRE_DESTINO)
    info["ruta"] = p
    if sincronizar and os.path.normcase(os.path.abspath(p)) != os.path.normcase(os.path.abspath(destino)):
        os.makedirs(C.base_dir(), exist_ok=True)
        if os.path.exists(destino):
            resp = C.path("respaldo", dt.datetime.now().strftime("%Y%m%d-%H%M%S"))
            os.makedirs(resp, exist_ok=True)
            shutil.move(destino, os.path.join(resp, NOMBRE_DESTINO))
        shutil.copy2(p, destino)
        info.update(copiado_desde=p, ruta=destino)
    return info


def mensaje_no_encontrado():
    return ("No encontré el export de órdenes. Busqué archivos .csv con las columnas del export en:\n  "
            + "\n  ".join(carpetas_de_busqueda())
            + "\nQué hacer: en la app, exporta \"Información financiera\" (CSV) y déjalo en Descargas o en "
            + C.base_dir() + ". También sirve --csv RUTA. No hace falta renombrarlo.")
