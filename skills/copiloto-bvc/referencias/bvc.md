# BVC, comisiones y fuentes de datos

## Horario de acciones (hora Colombia)
- Horario regular: negociación continua de 9:30 a.m. a 4:00 p.m.
- Mientras Nueva York está en horario de verano (en 2026, del 9 de marzo al 1 de noviembre),
  la BVC corre su jornada una hora: de 8:30 a.m. a 3:00 p.m.
- La subasta de cierre son los últimos minutos y termina en un momento aleatorio. Ese
  precio de calce es el cierre oficial. En el precio de calce gana el que cruza más acciones.
  La duración se ajusta en `horario.minutos_subasta_cierre`; por defecto son 10.
- Confirma siempre en las circulares de la BVC. Si anuncia días no hábiles adicionales,
  agrégalos en `dias_no_bursatiles_extra`.

## Festivos
Se calculan con la Ley Emiliani y la Pascua, así que sirven para cualquier año. En 2026 hay
18 festivos en días hábiles: 1 ene, 12 ene, 23 mar, 2 y 3 abr, 1 may, 18 may, 8 jun, 15 jun,
29 jun, 20 jul, 7 ago, 17 ago, 12 oct, 2 nov, 16 nov, 8 dic y 25 dic.

## Comisiones por defecto (con IVA)
Son las tarifas publicadas por la app Trii en 2026. Si usas otra comisionista, cambia la
tabla `comisiones` en `datos/config.json`.
- **Plan Pro:** $7.437,50 por orden de hasta $5M. Por encima de $5M, 0,14875% (0,125% más
  IVA). Son los valores que aparecen en el export.
- **Plan estándar:** el doble.
- Una compra y su venta de $2M pagan cerca de 0,74% en comisiones. Por eso hay un mínimo por
  orden.

## Ejecución
Las apps de inversión no son la comisionista: detrás hay una sociedad comisionista de bolsa
inscrita ante la Superintendencia Financiera, que es la que ejecuta las órdenes. Las acciones de la BVC solo se compran a través
de una comisionista inscrita, y los brokers internacionales no dan acceso al mercado local.
No hay una API pública para que un programa envíe órdenes, por eso la ejecución es manual.

## Datos
- **Yahoo Finance** (gratis, no oficial): sirve para las acciones globales siguiendo la
  acción en EE. UU. (NU, NVDA…) y pasándola a pesos con la TRM (COP=X). Para las acciones de
  la BVC prueba `TICKER.CL` con `copiloto.py precio TICKER`. Si no responde, usa el modo manual.
- **Modo manual:** `datos/precios.json` con `{"CEMARGOS": 11200}` y
  `datos/historico/TICKER.csv` con las columnas fecha, apertura, maximo, minimo, cierre y
  volumen. El histórico lo puedes descargar de investing.com o de la web de la BVC.
