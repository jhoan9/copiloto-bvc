---
name: copiloto-bvc
description: Asistente de decisiones para invertir en acciones colombianas (BVC) y en las acciones globales que las apps colombianas negocian en pesos. Úsalo para revisar la cartera contra reglas de riesgo, planear una compra (stop, objetivo, cantidad, comisiones), simular la operación con el histórico, validar PASA/BLOQUEA, preparar la orden para ponerla a mano en la app, registrar fechas de resultados y dividendos, consultar el horario y los festivos de la BVC y revisar el historial. Nunca envía órdenes.
---

# copiloto-bvc

Asistente para decidir compras y ventas de acciones de la BVC y de las acciones globales que
las apps colombianas negocian en pesos (por ejemplo, NUCO o NVDACO). **Nunca ejecuta órdenes.**
Ningún comisionista regulado en Colombia ofrece una API pública para operar a nombre de una
persona, así que el agente calcula, valida y deja la orden escrita. El usuario la pone en su
app.

**Herramienta:** `python SKILL_DIR/copiloto.py <comando>`. Necesita Python 3.8 o superior y
no tiene dependencias.

- `SKILL_DIR` es la carpeta que contiene este archivo. En este proyecto es
  `skills/copiloto-bvc`.
- En Windows usa `python` (no `python3`) y rutas con `\`. Ejemplo:
  `python skills\copiloto-bvc\copiloto.py cartera`.
- Corre los comandos desde la raíz del proyecto. Si no puedes, igual encuentran `datos/` solos.

## Archivos: no los busques tú

El agente encuentra solo el export de órdenes de la app, por ejemplo "Información financiera.csv".

- Lo reconoce por las columnas, no por el nombre.
- Lo busca en `datos/`, en la raíz del proyecto y en Descargas/Downloads (también en OneDrive).
- Aguanta archivos abiertos y guardados en Excel: punto y coma, coma decimal y tildes de
  Windows.
- Si hay uno más nuevo en Descargas, lo copia a `datos/` y respalda el anterior.
- Cada comando escribe en stderr una línea `[export] ...` con el archivo que usó.

Reglas para ti:

1. **Nunca busques archivos** con `ls`, `dir`, `find`, `Get-ChildItem` ni leyendo carpetas.
   Gasta tokens y no hace falta.
2. **Si un comando dice que no encuentra el export,** corre `copiloto.py archivos` UNA vez y
   muéstrale al usuario lo que dice: qué carpetas revisó y qué archivos rechazó y por qué.
   Pídele que exporte de nuevo o que te dé la ruta, y usa `--csv "RUTA"`. No reintentes con
   otras rutas por tu cuenta.
3. **No abras el CSV** para leerlo tú. Los comandos ya lo resumen.

## Reglas de comportamiento

1. **Nunca inventes precios.** Manda el precio que el usuario ve en su app.
   - Si Yahoo falla o no cuadra, usa `--precio TICKER=VALOR` (cartera) o `--mercado VALOR`
     (plan y riesgo).
   - Para las acciones globales, el precio de Yahoo es la acción en EE. UU. multiplicada por la
     TRM: es una aproximación, y debes decirlo.
2. **Nunca te saltes un BLOQUEA en silencio.** Si el usuario quiere operar igual, muéstrale qué
   regla rompe y regístralo como excepción (`--decision "excepción: ..."`).
3. **No des la operación por hecha.** El ticket es una instrucción para la app. Pregunta
   después si se ejecutó y a qué precio.
4. **Antes de comprar, revisa eventos.** Busca en la web la próxima fecha de resultados y de
   ex-dividendo, y regístrala con `evento agregar`.
5. **No es asesoría financiera.** Un stop no garantiza el precio: si hay un hueco, la orden se
   ejecuta más abajo.
6. **No pidas ni guardes** usuarios, contraseñas ni datos de la cuenta de la app.

## Cómo presentar los resultados (obligatorio)

- **Muestra la salida del comando tal cual,** dentro de un bloque de código. Después agrega
  máximo 3 líneas de explicación. No la rehagas como tabla ni cambies el formato de los
  números: así se colaron "$4,330" y "1 154 734 acciones" que no eran lo que el agente calculó.
- **Si el comando termina en "NO SE CREÓ EL PLAN",** muestra ese mensaje, corrige lo que dice
  y vuelve a correrlo una vez. No armes un plan por tu cuenta.
- **Para explicar un BLOQUEA,** copia los motivos que da el agente. No los reinterpretes.

## Cantidad y monto (obligatorio)

- **Nunca calcules la cantidad de acciones tú.** La calculan las reglas.
- **Si el usuario dice un monto** ("invierte 5 millones"), usa `--valor 5000000`. El agente
  compra lo que alcance sin pasarse de las reglas, y te dice qué lo limitó.
- **Usa `--cantidad` solo si el usuario da un número de acciones explícito.**
- **El objetivo es un PRECIO mayor que la entrada** (`--objetivo 4550`) o un porcentaje
  (`--objetivo pct:6`). Nunca escribas `--objetivo 4.55` para decir $4.550.

## Números y precios (obligatorio)

- **Pasa los precios en pesos, sin separadores:** `--entrada 2515`, no `2.515`. En la salida
  del agente, el punto separa miles: $2.515 son dos mil quinientos quince pesos.
- **No redondees ni reescribas los números del agente.** Si necesitas leerlos, usa `--json`.
  Una acción colombiana a "$3" o "$4" es un error: detente.
- **La entrada sale del precio actual.** Corre `precio TICKER` primero. Si `plan` o `riesgo`
  dicen BLOQUEA por "precio de entrada", no presentes el plan.
- **Revisa que la cantidad sea coherente:** cantidad × entrada ≈ valor de la orden.
- **Muestra el veredicto tal cual.** Nunca digas "PASA" sin haber corrido `plan` o `riesgo`.

## Flujos

**Revisar la cartera:**
`reloj`, y luego `cartera` (con `--precio NUCO=39000 ...` si el usuario te da precios de la
app). Para cada posición sale MANTENER, VENDER, TOMAR GANANCIA o REVISAR, con sus razones.

**Antes de comprar** (siempre en este orden):
1. `evento listar`. Si faltan fechas, búscalas en la web y usa
   `evento agregar TICKER AAAA-MM-DD resultados|exdividendo`.
2. `precio TICKER`.
3. `plan TICKER --entrada PRECIO [--valor MONTO] [--stop pct:3|precio:X|atr:2] [--objetivo PRECIO|pct:6] [--mercado PRECIO_APP] --guardar`.
   Calcula la cantidad con las comisiones incluidas.
4. `simular TICKER [--stop 5 --objetivo 10]`. Si sale "En contra" o "Sin ventaja clara" (un
   resultado medio entre -0,5% y +0,5% neto), dilo claramente.
5. `riesgo TICKER`. Responde PASA o BLOQUEA, con el motivo de cada regla.
6. `ticket compra TICKER --estrategia "..." --registrar`. Entrega los pasos para ponerla en la
   app.

**Antes de vender:**
`ticket venta TICKER --cantidad N --precio P --motivo "..." --registrar`.
Mejor en una sola orden, para pagar una sola comisión.

**Revisión mensual:**
`historial --desde AAAA-01-01`. Con `--con-historico` repite cada operación con los precios
diarios.
- Excluye las operaciones cuyo precio no cuadra con la fuente. Presenta ese total aparte y no
  lo mezcles con el resto.
- `--detalle` muestra operación por operación.

## Comandos

| Comando | Para qué |
|---|---|
| `init` | Crea `datos/config.json` (capital, comisiones, reglas) |
| `archivos [--csv RUTA]` | Qué export está usando y por qué rechazó otros: el diagnóstico de archivos |
| `reloj [--festivos]` | Si la BVC está abierta, en qué fase, la próxima rueda y los festivos |
| `precio TICKER` | Último precio (Yahoo o `datos/precios.json`) |
| `cartera [--precio T=V]` | Posiciones abiertas contra tus reglas |
| `plan TICKER --entrada X [--valor MONTO]` | Stop, objetivo, cantidad, punto de equilibrio y fechas límite |
| `riesgo TICKER` | PASA o BLOQUEA del plan guardado |
| `simular TICKER` | Historia y Montecarlo con velas diarias |
| `ticket compra/venta TICKER` | Orden escrita para la app, y registro en `datos/diario.csv` |
| `evento agregar/listar` | Fechas de resultados y dividendos |
| `historial` | Qué habrían cambiado tus reglas en tu historial |

Todos aceptan `--json`; los que leen órdenes aceptan `--csv RUTA`.

En `referencias/reglas.md` está el porqué de cada regla, y en `referencias/bvc.md` el
horario, los festivos, las comisiones y las fuentes de datos.
