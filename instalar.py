"""Instala, actualiza o revisa copiloto-bvc. Lo puede correr el agente (OpenCode) por ti.

    python instalar.py                          # instala o revisa todo
    python instalar.py --actualizar             # baja la última versión del repo (git pull)
    python instalar.py --traer-datos D:\\agentes\\trii-agente   # copia los datos de una instalación vieja
    python instalar.py RUTA\\copiloto-bvc.zip   # actualiza desde un zip (si no usas git)
    python instalar.py RUTA\\export.csv          # usa ese export de la app
    python instalar.py --sin-internet           # no prueba Yahoo

Se puede correr las veces que quieras. Nunca borra tus datos de datos/: lo que reemplaza
lo guarda antes en datos/respaldo/.
"""
import datetime as dt
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

RAIZ = os.path.dirname(os.path.abspath(__file__))
DATOS = os.path.join(RAIZ, "datos")
CLI = os.path.join(RAIZ, "skills", "copiloto-bvc", "copiloto.py")
NO_TOCAR = {"datos", "trii", ".git"}
REEMPLAZAR = {"skills", "tests"}
SKILLS_VIEJOS = (os.path.join(".opencode", "skills", "trii-agente"),
                 os.path.join(".opencode", "skills", "copiloto-bvc"))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

resultados = []


def ok(msg):
    resultados.append(("OK", msg))
    print("[OK]    " + msg)


def aviso(msg):
    resultados.append(("AVISO", msg))
    print("[AVISO] " + msg)


def error(msg):
    resultados.append(("ERROR", msg))
    print("[ERROR] " + msg)


def respaldo(ruta):
    destino = os.path.join(DATOS, "respaldo", dt.datetime.now().strftime("%Y%m%d-%H%M%S"))
    os.makedirs(destino, exist_ok=True)
    final = os.path.join(destino, os.path.basename(ruta.rstrip("\\/")))
    shutil.move(ruta, final)
    return final


def actualizar_desde_zip(zip_path, raiz=RAIZ):
    """Copia el contenido del zip sobre el proyecto, sin tocar datos/ ni .git/."""
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(zip_path) as z:
            for n in z.namelist():  # no aceptar rutas que se salgan de la carpeta
                if n.startswith(("/", "\\")) or ".." in n.replace("\\", "/").split("/"):
                    raise ValueError("El zip trae una ruta no permitida: " + n)
            z.extractall(tmp)
        origen = tmp
        hijos = os.listdir(tmp)
        if len(hijos) == 1 and os.path.isdir(os.path.join(tmp, hijos[0])):
            origen = os.path.join(tmp, hijos[0])
        if not os.path.exists(os.path.join(origen, "skills", "copiloto-bvc", "copiloto.py")):
            raise ValueError("Ese zip no es copiloto-bvc (no trae skills/copiloto-bvc/copiloto.py)")
        n = 0
        for nombre in os.listdir(origen):
            if nombre in NO_TOCAR:
                continue
            src, dst = os.path.join(origen, nombre), os.path.join(raiz, nombre)
            if os.path.isdir(src):
                if nombre in REEMPLAZAR and os.path.isdir(dst):
                    shutil.rmtree(dst)
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)
            n += 1
    return n


def traer_datos(origen, destino=DATOS):
    """Copia los datos de una instalación anterior (carpeta trii/ o datos/) sin pisar nada."""
    for sub in ("datos", "trii", ""):
        cand = os.path.join(origen, sub) if sub else origen
        if os.path.isfile(os.path.join(cand, "config.json")) or os.path.isfile(
                os.path.join(cand, "informacion_financiera.csv")):
            break
    else:
        raise ValueError("No encontré datos (config.json o informacion_financiera.csv) en " + origen)
    os.makedirs(destino, exist_ok=True)
    copiados = []
    for nombre in os.listdir(cand):
        src, dst = os.path.join(cand, nombre), os.path.join(destino, nombre)
        if nombre in ("cache", "respaldo") or os.path.exists(dst):
            continue
        (shutil.copytree if os.path.isdir(src) else shutil.copy2)(src, dst)
        copiados.append(nombre)
    return cand, copiados


def correr(args, timeout=120):
    r = subprocess.run(args if args[0] == "git" else [sys.executable] + args, cwd=RAIZ, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=timeout)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def _valor(argv, flag):
    if flag in argv:
        i = argv.index(flag)
        if i + 1 < len(argv):
            return argv[i + 1]
    return None


def main(argv):
    sin_internet = "--sin-internet" in argv
    origen_datos = _valor(argv, "--traer-datos")
    rutas = [a for a in argv if not a.startswith("--") and a != origen_datos]
    zip_nuevo = next((r for r in rutas if r.lower().endswith(".zip")), None)
    csv_dado = next((r for r in rutas if r.lower().endswith(".csv")), None)

    if sys.version_info < (3, 8):
        error("Necesitas Python 3.8 o superior (tienes %d.%d)." % sys.version_info[:2])
        return 1
    ok("Python %d.%d" % sys.version_info[:2])

    # Actualizar el código (git o zip) y seguir con el instalador NUEVO
    if "--actualizar" in argv:
        if not os.path.isdir(os.path.join(RAIZ, ".git")):
            error("Esta carpeta no es un clon de git. Clona el repo (ver README) o usa un zip.")
            return 1
        code, salida = correr(["git", "pull", "--ff-only"])
        if code:
            error("git pull falló:\n" + salida.strip())
            return 1
        ok("Código actualizado: " + (salida.strip().splitlines() or ["al día"])[-1])
        resto = [a for a in argv if a != "--actualizar"]
        return subprocess.call([sys.executable, os.path.join(RAIZ, "instalar.py")] + resto)
    if zip_nuevo:
        try:
            n = actualizar_desde_zip(zip_nuevo)
        except (ValueError, zipfile.BadZipFile, OSError) as e:
            error(str(e))
            return 1
        ok("Código actualizado desde %s (%d elementos). datos/ no se tocó." % (zip_nuevo, n))
        return subprocess.call([sys.executable, os.path.join(RAIZ, "instalar.py")]
                               + [a for a in argv if a != zip_nuevo])

    if not os.path.isfile(CLI):
        error("No encuentro skills/copiloto-bvc/copiloto.py. Corre esto desde la carpeta del proyecto.")
        return 1

    # Datos: carpeta vieja trii/ dentro del proyecto -> datos/
    vieja = os.path.join(RAIZ, "trii")
    if os.path.isdir(vieja) and not os.path.isdir(DATOS):
        os.rename(vieja, DATOS)
        ok("Tu carpeta trii/ ahora se llama datos/ (mismos archivos)")
    if origen_datos:
        try:
            de, copiados = traer_datos(origen_datos)
            ok("Datos traídos de %s: %s" % (de, ", ".join(copiados) or "nada nuevo (ya estaban)"))
        except (ValueError, OSError) as e:
            error(str(e))

    code, salida = correr([CLI, "init"])
    if code:
        error("init falló:\n" + salida)
        return 1
    ok("Configuración en datos/config.json")

    # Export: el agente lo encuentra solo (datos/, proyecto, Descargas); aquí solo se muestra
    args = [CLI, "archivos"] + (["--csv", csv_dado] if csv_dado else [])
    code, salida = correr(args)
    lineas = salida.strip().splitlines()
    en_uso = next((l for l in lineas if l.startswith("Export en uso")), None)
    if en_uso:
        ok(en_uso)
    else:
        aviso("No encontré el export de órdenes. En la app exporta \"Información financiera\" (CSV) y "
              "déjalo en Descargas; no hace falta renombrarlo. Luego vuelve a correr el instalador.")

    # Skill: OpenCode lo lee desde skills/ (opencode.json); quita copias viejas para no duplicar
    for rel in SKILLS_VIEJOS:
        p = os.path.join(RAIZ, rel)
        if os.path.isdir(p):
            ok("Copia vieja del skill movida a " + os.path.relpath(respaldo(p), RAIZ))
    if os.path.isfile(os.path.join(RAIZ, "opencode.json")):
        ok("OpenCode: skill en skills/ y comando /instalar-copiloto listos")
    else:
        aviso("Falta opencode.json: OpenCode no va a encontrar el skill.")

    code, salida = correr(["-m", "unittest", "discover", "-s", "tests"])
    linea = [l for l in salida.splitlines() if l.startswith("Ran ")]
    if code == 0:
        ok("Pruebas: " + (linea[0] if linea else "OK"))
    else:
        error("Fallaron pruebas:\n" + salida[-2000:])
    if sin_internet:
        aviso("No probé Yahoo (--sin-internet).")
    else:
        code, salida = correr([CLI, "precio", "ECOPETROL", "--sin-cache"], timeout=40)
        if code == 0:
            ok("Precios en línea: " + salida.strip().splitlines()[0])
        else:
            aviso("No pude traer precios de Yahoo. Puedes pasar el precio de la app con --precio "
                  "o ponerlo en datos/precios.json.\n" + salida.strip()[-400:])

    errores = sum(1 for e, _ in resultados if e == "ERROR")
    avisos = sum(1 for e, _ in resultados if e == "AVISO")
    print("\nRESUMEN: %s · %d aviso(s) · %d error(es)" % ("LISTO" if not errores else "CON ERRORES", avisos, errores))
    if not errores:
        print("Abre (o reinicia) OpenCode en esta carpeta y pídele: \"revisa mi cartera\".")
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
