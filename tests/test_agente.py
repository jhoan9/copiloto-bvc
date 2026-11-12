"""Pruebas offline: python3 -m unittest discover -s tests -v"""
import datetime as dt
import os
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(AQUI), "skills", "copiloto-bvc"))

from copiloto_lib import calendario as cal, cartera, comisiones as com, config as C  # noqa: E402
from copiloto_lib import datos, exportes, plan as planmod, reglas, revision, simulador, ticket  # noqa: E402

FX = os.path.join(AQUI, "fixtures")
CFG = C.load(os.path.join(FX, "no_existe.json"))


class TestCalendario(unittest.TestCase):
    def test_festivos_2026_son_18_en_dias_habiles(self):
        habiles = [d for d in cal.festivos(2026) if d.weekday() < 5]
        self.assertEqual(len(habiles), 18)
        for f in ["2026-01-12", "2026-03-23", "2026-05-18", "2026-06-08", "2026-06-15", "2026-08-17",
                  "2026-11-02", "2026-11-16", "2026-12-08"]:
            self.assertIn(dt.date.fromisoformat(f), cal.festivos(2026), f)

    def test_pascua(self):
        self.assertEqual(cal.pascua(2026), dt.date(2026, 4, 5))
        self.assertEqual(cal.pascua(2027), dt.date(2027, 3, 28))

    def test_horario_verano_y_subasta(self):
        st = cal.estado(dt.datetime(2026, 6, 10, 8, 45), CFG)
        self.assertEqual((st["apertura"], st["cierre"]), ("08:30", "15:00"))
        st = cal.estado(dt.datetime(2026, 11, 10, 15, 52), CFG)
        self.assertEqual(st["fase"], "subasta de cierre")
        st = cal.estado(dt.datetime(2026, 11, 16, 10, 0), CFG)
        self.assertFalse(st["dia_bursatil"])
        self.assertEqual(st["proxima_rueda"], "2026-11-17")

    def test_dias_bursatiles(self):
        self.assertEqual(cal.dias_bursatiles_entre(dt.date(2026, 11, 13), dt.date(2026, 11, 17)), 1)
        self.assertEqual(cal.sumar_dias_bursatiles(dt.date(2026, 11, 13), 1), dt.date(2026, 11, 17))


class TestComisiones(unittest.TestCase):
    def test_tarifas_pro(self):
        self.assertEqual(com.comision(4_000_000, CFG), 7437.5)
        self.assertAlmostEqual(com.comision(5_833_560, CFG), 8677.42, places=1)  # orden real del export

    def test_equilibrio(self):
        costo = 557 * 11200 + com.comision(557 * 11200, CFG)
        pe = com.precio_equilibrio(557, costo, CFG)
        neto = 557 * pe - com.comision(557 * pe, CFG)
        self.assertAlmostEqual(neto, costo, delta=1)


class TestCartera(unittest.TestCase):
    def setUp(self):
        self.ords = cartera.leer_export(os.path.join(FX, "export_demo.csv"))

    def test_lee_solo_aprobadas_y_cantidades_parciales(self):
        self.assertEqual(len(self.ords), 9)
        self.assertEqual([o for o in self.ords if o["ticker"] == "ABC" and o["tipo"] == "Venta"][0]["cantidad"], 300)
        self.assertEqual(self.ords[0]["fecha"], dt.datetime(2026, 10, 1, 10, 0))

    def test_pares_y_posiciones(self):
        lotes = cartera.armar_pares(self.ords)
        pos = cartera.posiciones_abiertas(lotes)
        self.assertEqual(pos["XYZ"]["cantidad"], 500)  # la venta de 50 cerró la compra exacta de 50
        self.assertEqual(pos["QQQ"]["cantidad"], 10)
        cerr = cartera.operaciones_cerradas(lotes)
        demo = [o for o in cerr if o["ticker"] == "DEMO"][0]
        self.assertAlmostEqual(demo["ganancia_realizada"], 100 * 600 - 2 * 7437.5)
        abc = [o for o in cerr if o["ticker"] == "ABC"]
        self.assertEqual(len(abc), 2)  # una venta de 300 cerró dos compras
        self.assertAlmostEqual(sum(o["ganancia_realizada"] for o in abc), 300 * 5200 - 7437.5 - (200 * 5000 + 100 * 5100 + 2 * 7437.5))


class TestPlanYRiesgo(unittest.TestCase):
    def test_plan_respeta_perdida_maxima_y_concentracion(self):
        pl = planmod.crear("ECOPETROL", 2600, CFG, hoy=dt.date(2026, 11, 11))
        self.assertLessEqual(pl["perdida_neta_en_stop"], CFG["capital_cop"] * 0.01 + 1)
        self.assertLessEqual(pl["pct_del_capital"], 30.0)
        ver = reglas.revisar_plan(pl, CFG, {}, 0, [], dt.date(2026, 11, 11))
        self.assertEqual(ver["veredicto"], "PASA")

    def test_bloquea_promediar_a_la_baja_y_resultados(self):
        pos = {"NUCO": {"ticker": "NUCO", "cantidad": 102, "costo": 5005437.5, "costo_promedio": 49073}}
        pl = planmod.crear("NUCO", 39000, CFG, cantidad=20, hoy=dt.date(2026, 11, 11))
        ev = [{"ticker": "NUCO", "fecha": "2026-11-12", "tipo": "resultados"}]
        ver = reglas.revisar_plan(pl, CFG, pos, 0, ev, dt.date(2026, 11, 11))
        reglas_bloq = {c["regla"] for c in ver["checks"] if c["estado"] == "BLOQUEA"}
        self.assertIn("promediar a la baja", reglas_bloq)
        self.assertIn("evento", reglas_bloq)
        self.assertIn("orden mínima", reglas_bloq)

    def test_bloquea_orden_grande_y_mes_en_rojo(self):
        cfg = C.load(os.path.join(FX, "no_existe.json"))
        cfg["capital_cop"] = 100_000_000
        pl = planmod.crear("ISA", 27000, cfg, cantidad=1000, hoy=dt.date(2026, 11, 11))
        ver = reglas.revisar_plan(pl, cfg, {}, -5_000_000, [], dt.date(2026, 11, 11))
        bloq = {c["regla"] for c in ver["checks"] if c["estado"] == "BLOQUEA"}
        self.assertTrue({"orden máxima", "pérdida del mes"} <= bloq)

    def test_revisar_posicion_regla_de_dias(self):
        pos = {"ticker": "NUCO", "cantidad": 102, "costo": 5005437.5, "costo_promedio": 49073,
               "primera_compra": dt.datetime(2026, 10, 14)}
        r = reglas.revisar_posicion(pos, 39000, CFG, hoy=dt.date(2026, 11, 11))
        self.assertEqual(r["accion"], "VENDER")
        self.assertTrue(any("stop" in x for x in r["razones"]))


class TestSimulador(unittest.TestCase):
    def setUp(self):
        self.velas = datos.leer_csv_velas(os.path.join(FX, "DEMO_velas.csv"))

    def test_salida_con_hueco_y_mismo_dia(self):
        v = [{"apertura": 95, "maximo": 96, "minimo": 90, "cierre": 92}]
        self.assertEqual(simulador._salida(100, 97, 106, v, 5)[:2], ("stop", 95))
        v = [{"apertura": 100, "maximo": 107, "minimo": 96, "cierre": 101}]
        self.assertEqual(simulador._salida(100, 97, 106, v, 5)[0], "stop")  # los dos el mismo día: conservador
        v = [{"apertura": 100, "maximo": 101, "minimo": 99, "cierre": 100.5}] * 3
        self.assertEqual(simulador._salida(100, 97, 106, v, 3)[:2], ("tiempo", 100.5))

    def test_montecarlo_reproducible(self):
        a = simulador.montecarlo(self.velas, 0.03, 0.06, 20, 3_500_000, CFG, n=500, semilla=19)
        b = simulador.montecarlo(self.velas, 0.03, 0.06, 20, 3_500_000, CFG, n=500, semilla=19)
        self.assertEqual(a, b)
        self.assertAlmostEqual(a["pct_objetivo"] + a["pct_stop"] + a["pct_tiempo"], 1.0)

    def test_historia(self):
        h = simulador.historia(self.velas, 0.03, 0.06, 20, 3_500_000, CFG)
        self.assertGreater(h["n"], 200)


class TestRevisionYTicket(unittest.TestCase):
    def test_revision_aproximada_corta_perdidas(self):
        cerr = [{"ganancia_realizada": -100000, "rentab": -0.10, "invertido": 1_000_000},
                {"ganancia_realizada": 20000, "rentab": 0.02, "invertido": 25_000_000}]
        r = revision.aproximada(cerr, CFG)
        self.assertEqual(r["resultado_con_stop"], -30000 + 20000)
        self.assertEqual(r["compras_mayores_al_maximo"], 1)
        self.assertEqual(r["compras_menores_al_minimo"], 1)

    def test_revision_historica_excluye_precios_que_no_cuadran(self):
        velas = [{"fecha": "2026-03-02", "apertura": 100, "maximo": 102, "minimo": 98, "cierre": 101},
                 {"fecha": "2026-03-03", "apertura": 101, "maximo": 108, "minimo": 100, "cierre": 107}]
        base = {"ticker": "X", "cantidad": 100, "ganancia_realizada": 500, "fecha_compra": dt.datetime(2026, 3, 2, 10)}
        ok = dict(base, precio_compra=100)
        malo = dict(base, precio_compra=150)  # la fuente dice 98-102: no es el mismo precio
        r = revision.con_historico([ok, malo], {"X": velas}, CFG)
        self.assertEqual((r["operaciones_simuladas"], r["excluidas"]), (1, 1))
        self.assertEqual(r["detalle"][0]["salida"], "objetivo")
        self.assertIn("no coincide", r["detalle_excluidas"][0]["motivo"])
        self.assertEqual(r["por_ticker"]["X"]["excluidas"], 1)

    def test_trm_por_fecha(self):
        tasas = [("2026-01-02", 3900.0), ("2026-01-05", 3950.0)]
        self.assertEqual(datos._tasa_en(tasas, "2026-01-04"), 3900.0)
        self.assertEqual(datos._tasa_en(tasas, "2026-01-05"), 3950.0)
        self.assertEqual(simulador.veredicto(0.002), "Sin ventaja clara")
        self.assertEqual(simulador.veredicto(0.006), "A favor")

    def test_ticket_y_diario(self):
        pl = planmod.crear("ECOPETROL", 2600, CFG, hoy=dt.date(2026, 11, 11))
        txt = ticket.texto_compra(pl, "PASA")
        self.assertIn("Límite", txt)
        self.assertIn("stop loss", txt)
        with tempfile.TemporaryDirectory() as d:
            os.environ["COPILOTO_DIR"] = d
            try:
                p = ticket.registrar({"ticker": "ECOPETROL", "accion": "compra"})
                self.assertTrue(os.path.exists(p))
            finally:
                del os.environ["COPILOTO_DIR"]



class TestInstalador(unittest.TestCase):
    def test_zip_actualiza_codigo_sin_tocar_datos(self):
        sys.path.insert(0, os.path.dirname(AQUI))
        import instalar
        with tempfile.TemporaryDirectory() as tmp:
            proj = os.path.join(tmp, "copiloto-bvc")
            os.makedirs(os.path.join(proj, "datos"))
            os.makedirs(os.path.join(proj, "skills", "copiloto-bvc"))
            with open(os.path.join(proj, "datos", "config.json"), "w") as f:
                f.write("MIO")
            with open(os.path.join(proj, "skills", "copiloto-bvc", "viejo.py"), "w") as f:
                f.write("x")
            z = os.path.join(tmp, "nuevo.zip")
            import zipfile
            with zipfile.ZipFile(z, "w") as zf:
                zf.writestr("copiloto-bvc/skills/copiloto-bvc/copiloto.py", "print(1)")
                zf.writestr("copiloto-bvc/datos/config.json", "PISADO")
                zf.writestr("copiloto-bvc/README.md", "nuevo")
            instalar.actualizar_desde_zip(z, raiz=proj)
            with open(os.path.join(proj, "datos", "config.json")) as f:
                self.assertEqual(f.read(), "MIO")
            self.assertTrue(os.path.exists(os.path.join(proj, "skills", "copiloto-bvc", "copiloto.py")))
            self.assertFalse(os.path.exists(os.path.join(proj, "skills", "copiloto-bvc", "viejo.py")))
            malo = os.path.join(tmp, "malo.zip")
            with zipfile.ZipFile(malo, "w") as zf:
                zf.writestr("../fuera.txt", "x")
            with self.assertRaises(ValueError):
                instalar.actualizar_desde_zip(malo, raiz=proj)


if __name__ == "__main__":
    unittest.main()


class TestNumerosYPrecio(unittest.TestCase):
    def test_numeros_en_formato_colombiano(self):
        from copiloto_lib.numeros import num
        casos = {"2.515": 2515, "614.980": 614980, "$1.234.567": 1234567, "4.850,5": 4850.5,
                 "2515": 2515, "3,5": 3.5, "4.85": 4.85, "2,515.50": 2515.5, "571.000": 571000}
        for txt, esperado in casos.items():
            self.assertAlmostEqual(num(txt), esperado, msg=txt)

    def test_bloquea_entrada_lejos_del_mercado(self):
        pl = planmod.crear("ECOPETROL", 2.515, CFG, hoy=dt.date(2026, 11, 11))
        ver = reglas.revisar_plan(pl, CFG, {}, 0, [], dt.date(2026, 11, 11), precio_mercado=2515, fuente_precio="test")
        self.assertEqual(ver["veredicto"], "BLOQUEA")
        self.assertTrue(any(c["regla"] == "precio de entrada" for c in ver["checks"]))
        pl = planmod.crear("ECOPETROL", 2515, CFG, hoy=dt.date(2026, 11, 11))
        ver = reglas.revisar_plan(pl, CFG, {}, 0, [], dt.date(2026, 11, 11), precio_mercado=2520)
        self.assertFalse(any(c["regla"] == "precio de entrada" for c in ver["checks"]))


class TestExportes(unittest.TestCase):
    """El export se reconoce por columnas, en el formato original o guardado por Excel."""

    def _excel(self, destino):
        import csv
        with open(os.path.join(FX, "export_demo.csv"), encoding="utf-8-sig") as f:
            filas = list(csv.reader(f))
        with open(destino, "w", encoding="cp1252", newline="") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(filas[0])
            for r in filas[1:]:
                r = list(r)
                r[0] = exportes.parse_fecha(r[0]).strftime("%d/%m/%Y %H:%M")
                for k in range(6, len(r)):
                    try:
                        r[k] = "{:,.2f}".format(float(r[k])).replace(",", "X").replace(".", ",").replace("X", ".")
                    except ValueError:
                        pass
                w.writerow(r)

    def test_excel_en_espanol_da_lo_mismo(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "cualquier nombre.csv")
            self._excel(p)
            a, info = exportes.leer_export(p)
            b, _ = exportes.leer_export(os.path.join(FX, "export_demo.csv"))
            self.assertEqual((info["separador"], info["codificacion"]), (";", "cp1252"))
            self.assertEqual(len(a), len(b))
            for x, y in zip(a, b):
                self.assertEqual((x["fecha"], x["ticker"], x["tipo"], x["cantidad"]),
                                 (y["fecha"], y["ticker"], y["tipo"], y["cantidad"]))
                self.assertAlmostEqual(x["precio"], y["precio"], places=1)

    def test_numero_excel_coma_siempre_decimal(self):
        self.assertEqual(exportes._num_excel_es("809,000"), 809.0)
        self.assertEqual(exportes._num_excel_es("10.920,5"), 10920.5)
        self.assertEqual(exportes._num_excel_es("10.920"), 10920.0)

    def test_encuentra_el_mas_reciente_y_lo_copia_a_datos(self):
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            home, datos_dir = os.path.join(tmp, "home"), os.path.join(tmp, "datos")
            os.makedirs(os.path.join(home, "Downloads"))
            os.makedirs(datos_dir)
            shutil.copy(os.path.join(FX, "export_demo.csv"),
                        os.path.join(home, "Downloads", "Información financiera (3).csv"))
            with open(os.path.join(home, "Downloads", "otra cosa.csv"), "w") as f:
                f.write("a,b\n1,2\n")
            viejo_home, viejo_dir = os.environ.get("HOME"), os.environ.get("COPILOTO_DIR")
            os.environ["HOME"], os.environ["COPILOTO_DIR"] = home, datos_dir
            os.environ["USERPROFILE"] = home
            try:
                info = exportes.export_activo()
                self.assertTrue(info["copiado_desde"].endswith("(3).csv"))
                self.assertTrue(os.path.exists(os.path.join(datos_dir, "informacion_financiera.csv")))
                info2 = exportes.export_activo()  # la segunda vez ya está en datos/
                self.assertNotIn("copiado_desde", info2)
            finally:
                for k, v in (("HOME", viejo_home), ("COPILOTO_DIR", viejo_dir)):
                    if v is None:
                        os.environ.pop(k, None)
                    else:
                        os.environ[k] = v

    def test_mensaje_claro_si_no_hay_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            viejo = os.environ.get("COPILOTO_DIR")
            os.environ["COPILOTO_DIR"] = tmp
            try:
                with self.assertRaises(exportes.ExportError) as e:
                    exportes.leer_export(os.path.join(FX, "DEMO_velas.csv"))
                self.assertIn("faltan las columnas", str(e.exception))
            finally:
                if viejo is None:
                    os.environ.pop("COPILOTO_DIR", None)
                else:
                    os.environ["COPILOTO_DIR"] = viejo


class TestPlanEntradasMalas(unittest.TestCase):
    def test_valor_limita_la_cantidad(self):
        pl = planmod.crear("CELSIA", 4330, CFG, valor=1_000_000, stop_modo="pct:3", hoy=dt.date(2026, 11, 11))
        self.assertEqual(pl["cantidad"], 1_000_000 // 4330)
        self.assertIn("monto que pediste", pl["cantidad_limitada_por"])

    def test_objetivo_por_debajo_de_la_entrada_da_pista(self):
        with self.assertRaises(ValueError) as e:
            planmod.crear("CELSIA", 4330, CFG, objetivo="4.55", hoy=dt.date(2026, 11, 11))
        self.assertIn("4550", str(e.exception))
        pl = planmod.crear("CELSIA", 4330, CFG, objetivo="pct:6", hoy=dt.date(2026, 11, 11))
        self.assertAlmostEqual(pl["objetivo"], 4330 * 1.06, places=1)

    def test_cantidad_mayor_al_capital_no_se_acepta(self):
        with self.assertRaises(ValueError) as e:
            planmod.crear("CELSIA", 4330, CFG, cantidad=1_154_734, hoy=dt.date(2026, 11, 11))
        self.assertIn("--valor", str(e.exception))


class TestEfectivoYOperaciones(unittest.TestCase):
    def test_sin_efectivo_la_cantidad_es_cero_y_bloquea(self):
        pl = planmod.crear("CELSIA", 4330, CFG, valor=5_000_000, efectivo=500_000, hoy=dt.date(2026, 11, 11))
        self.assertLessEqual(pl["costo_total"], 500_000)
        self.assertIn("efectivo disponible", pl["cantidad_limitada_por"])
        pl = planmod.crear("CELSIA", 4330, CFG, hoy=dt.date(2026, 11, 11))
        ver = reglas.revisar_plan(pl, CFG, {}, 0, [], dt.date(2026, 11, 11), precio_mercado=4330, efectivo=100_000)
        self.assertTrue(any(c["regla"] == "efectivo" and c["estado"] == "BLOQUEA" for c in ver["checks"]))

    def test_estado_capital(self):
        pos = {"A": {"costo": 6_000_000}, "B": {"costo": 3_000_000}}
        cfg = dict(CFG, capital_cop=10_000_000, efectivo_cop=None)
        self.assertEqual(cartera.estado_capital(pos, cfg)["disponible"], 1_000_000)
        self.assertEqual(cartera.estado_capital(pos, cfg, efectivo=2_500_000)["disponible"], 2_500_000)

    def test_venta_registrada_cierra_la_posicion_y_no_se_duplica(self):
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            viejo = os.environ.get("COPILOTO_DIR")
            os.environ["COPILOTO_DIR"] = tmp
            try:
                exp = os.path.join(tmp, "informacion_financiera.csv")
                with open(exp, "w", encoding="utf-8") as f:
                    f.write("Fecha y hora,Símbolo de la acción,Tipo de orden,Estado,Acciones completadas,"
                            "Acciones pendientes,Precio por acción,Total invertido,Valor comisión,Total estimado\n"
                            "\"2 nov 2026, 9:40 a. m.\",DEMO,Compra,Aprobado,100,0,10000,1000000,7437.5,0\n")
                cartera._CACHE.clear()
                pos = cartera.posiciones_abiertas(cartera.armar_pares(cartera.leer_ordenes()))
                self.assertEqual(pos["DEMO"]["cantidad"], 100)
                cartera.registrar_operacion("Venta", "DEMO", 100, 10500, dt.datetime(2026, 11, 10, 11, 0), 7437.5)
                pos = cartera.posiciones_abiertas(cartera.armar_pares(cartera.leer_ordenes()))
                self.assertNotIn("DEMO", pos)
                # llega un export nuevo con esa misma venta (otra hora, precio redondeado): no se duplica
                with open(exp, "a", encoding="utf-8") as f:
                    f.write("\"10 nov 2026, 11:03 a. m.\",DEMO,Venta,Aprobado,100,0,10500.4,1050040,7437.5,0\n")
                cartera._CACHE.clear()
                ords = cartera.leer_ordenes()
                self.assertEqual(sum(1 for o in ords if o["tipo"] == "Venta"), 1)
            finally:
                cartera._CACHE.clear()
                if viejo is None:
                    os.environ.pop("COPILOTO_DIR", None)
                else:
                    os.environ["COPILOTO_DIR"] = viejo
