# copiloto-bvc

Asistente de decisiones para invertir en **acciones colombianas** (BVC) y en las acciones
globales que las apps colombianas negocian en pesos. Funciona como *skill* para agentes de IA
(OpenCode, Claude Code) y también como programa de terminal.

**No compra ni vende por ti.** Revisa tu cartera, calcula cuánto comprar y dónde poner el
stop, simula la operación con el histórico, la valida contra tus reglas de riesgo y te deja
la orden escrita. Tú la pones en la app.

> Proyecto independiente y sin fines comerciales. No está afiliado ni respaldado por la Bolsa
> de Valores de Colombia, por Trii ni por ninguna comisionista. Esos nombres se mencionan solo
> para describir compatibilidad (formato del export, tarifas de ejemplo). No es asesoría
> financiera.

---

## Contenido

1. [Qué hace](#qué-hace)
2. [Requisitos](#requisitos)
3. [Instalación (Windows + OpenCode)](#instalación-windows--opencode)
4. [Tus datos](#tus-datos)
5. [Uso diario](#uso-diario)
6. [Comandos](#comandos)
7. [Actualizar](#actualizar)
8. [Problemas comunes](#problemas-comunes)
9. [Estructura del proyecto](#estructura-del-proyecto)
10. [Pruebas](#pruebas)
11. [Letra pequeña](#letra-pequeña)

---

## Qué hace

| Función | Qué te da |
|---|---|
| **Cartera** | Lee el export de tu app, arma cada compra con sus ventas y revisa las posiciones abiertas: MANTENER, VENDER, TOMAR GANANCIA o REVISAR |
| **Plan** | Stop, objetivo, cantidad según tu pérdida máxima, comisiones y punto de equilibrio |
| **Riesgo** | PASA o BLOQUEA. Revisa efectivo disponible, tamaño, concentración, pérdida máxima, ganancia/riesgo, promediar a la baja, pérdida del mes, resultados próximos y que el precio de entrada sea realista |
| **Operaciones recientes** | Si tus datos no están al día, pregunta qué vendiste o compraste desde el último export, y lo registra |
| **Simulador** | Historia real y Montecarlo (10.000 caminos) con velas diarias |
| **Calendario BVC** | Festivos de cualquier año, horario de verano de Nueva York y subasta de cierre |
| **Ticket** | Los pasos para poner la orden a mano (límite, stop y objetivo), más un diario de decisiones |
| **Historial** | Qué habría pasado con tus operaciones si hubieras seguido las reglas |

## Requisitos

- **Python 3.8 o superior.** No hace falta instalar nada con pip. En Windows, al instalar
  Python marca "Add python.exe to PATH". Para comprobarlo: `python --version`.
- **Git**, para clonar y actualizar. Para comprobarlo: `git --version`.
- **Un agente (opcional):** [OpenCode](https://opencode.ai), gratis, o Claude Code. Sin agente,
  todo funciona igual desde la terminal.
- **Internet (opcional),** para traer precios de Yahoo Finance. Sin internet puedes darle los
  precios a mano.

## Instalación (Windows + OpenCode)

Abre PowerShell y corre estos comandos, de a uno:

```powershell
cd D:\agentes
git clone https://github.com/jhoan9/copiloto-bvc.git
cd copiloto-bvc
python instalar.py
```

El instalador:

- crea `datos\config.json`;
- busca tu export de órdenes en Descargas;
- quita copias viejas del skill;
- corre las pruebas y verifica que lleguen los precios.

Termina con `RESUMEN: LISTO` o te dice qué falta.

Después:

1. Abre `datos\config.json` y pon **tu capital** en `capital_cop`. Revisa también las reglas.
2. Abre OpenCode **en esa carpeta**:
   ```powershell
   opencode
   ```
3. Elige un modelo con `/models` y quédate en el modo **Build** (la tecla Tab cambia de modo).
4. Escribe `revisa mi cartera`.

OpenCode carga el skill desde `skills\`, porque así lo dice `opencode.json`, y lee las reglas
del proyecto en `AGENTS.md`. No hay que copiar carpetas.

**¿Venías de la versión anterior (`trii-agente`)?** Trae tus datos con:

```powershell
python instalar.py --traer-datos D:\agentes\trii-agente
```

El instalador copia tu config, tu export, el diario y las operaciones manuales sin pisar nada.
También entiende la clave vieja `plan_trii`.

<details>
<summary>Linux / macOS / Claude Code</summary>

```bash
git clone https://github.com/jhoan9/copiloto-bvc.git
cd copiloto-bvc
python3 instalar.py
```

En Claude Code, como plugin: `/plugin marketplace add RUTA/copiloto-bvc` y luego
`/plugin install copiloto-bvc@copiloto-bvc`. También puedes copiar
`skills/copiloto-bvc` a `~/.claude/skills/`.
</details>

## Tus datos

Todo lo tuyo vive en la carpeta `datos\`. Está en `.gitignore`, así que **nunca se sube** al
repositorio.

| Archivo | Qué es | Quién lo crea |
|---|---|---|
| `config.json` | Capital, plan de comisiones, reglas, símbolos | `init` / tú |
| `informacion_financiera.csv` | Copia de tu export de órdenes | el agente, solo |
| `operaciones_manuales.csv` | Operaciones que aún no están en el export, o que la app no exporta (por ejemplo, una venta en una OPA o readquisición). Cuando llegan en un export nuevo, no se cuentan dos veces | `operacion agregar` / tú |
| `estado.json` | Hasta qué día confirmaste que tus datos están al día | `operacion` |
| `diario.csv` | Tus decisiones: qué compraste o vendiste, por qué, y si fue una excepción | `ticket --registrar` |
| `eventos.json` | Fechas de resultados y dividendos | `evento agregar` |
| `planes.json` | Último plan guardado por acción | `plan --guardar` |
| `precios.json`, `historico\` | Precios a mano, si no usas Yahoo | tú (opcional) |
| `respaldo\` | Versiones anteriores de lo que se reemplazó | el agente |

**El export de órdenes.** En la app, exporta tu historial de órdenes ("Información
financiera", en CSV) y déjalo en **Descargas**. **No hace falta renombrarlo ni moverlo.** El
agente:

- lo reconoce por sus columnas;
- si hay varios, usa el que llega a la fecha más reciente;
- lo copia a `datos\` y guarda el anterior en `datos\respaldo\`;
- lo lee aunque lo hayas abierto y guardado en Excel (punto y coma, coma decimal, tildes).

Para ver qué archivo está usando:

```powershell
python skills\copiloto-bvc\copiloto.py archivos
```

## Uso diario

En OpenCode basta con pedirlo en español. Estos son ejemplos:

| Cuándo | Qué le escribes |
|---|---|
| Antes de operar | "¿Hay rueda hoy y a qué hora cierra?" |
| Revisar posiciones | "Revisa mi cartera" (o "...con NUCO a 39.000 y CEMARGOS a 10.800", si Yahoo no cuadra con la app) |
| Antes de comprar | "Evalúa una compra de ECOPETROL al precio actual y, si pasa, prepárame la orden" |
| Probar una regla | "Simula ECOPETROL con stop de 5% y objetivo de 10%" |
| Eventos | "¿Cuándo presenta resultados Nu? Agrégalo" |
| Revisión mensual | "¿Cómo me habría ido este año siguiendo las reglas?" |
| Después de operar | "Vendí 557 CEMARGOS a 10.800 hoy": el agente lo registra. O exporta de nuevo a Descargas y el siguiente comando lo toma solo |
| Saldo exacto | "Mi saldo disponible en la app es 6.000.000": el agente lo usa en vez del estimado |

**Revisa siempre lo que te muestra el agente:**

- Antes de cada respuesta debe correr un comando, algo como `python ...copiloto.py ...`. Si te
  da precios o cantidades sin haber corrido nada, se los está inventando.
- Un precio de "$3" o "$4", o cientos de miles de acciones por unos pocos millones de pesos,
  es un error. En ese caso cambia de modelo con `/models`.

## Comandos

Todos se corren con `python skills\copiloto-bvc\copiloto.py <comando>`. En Linux o macOS
usa `python3` y `/`.

| Comando | Ejemplo |
|---|---|
| `init` | Crea `datos\config.json` |
| `archivos` | Qué export usa, de dónde lo sacó y qué archivos descartó y por qué |
| `reloj [--festivos]` | `reloj --festivos` |
| `precio TICKER` | `precio ECOPETROL` |
| `cartera [--precio T=V]` | `cartera --precio NUCO=39000` |
| `plan TICKER --entrada X` | `plan CELSIA --entrada 4330 --valor 5000000 --guardar` (opciones: `--valor` pesos a invertir; `--stop pct:3`, `precio:4200` o `atr:2`; `--objetivo 4550` o `pct:6`; `--mercado 4335`) |
| `riesgo TICKER` | `riesgo ECOPETROL` |
| `simular TICKER` | `simular ECOPETROL --stop 5 --objetivo 10` |
| `ticket compra TICKER` | `ticket compra ECOPETROL --estrategia "rebote" --registrar` |
| `ticket venta TICKER` | `ticket venta NUCO --cantidad 102 --precio 42000 --motivo "regla 10 días" --registrar` |
| `evento agregar/listar` | `evento agregar NUCO 2026-11-12 resultados` |
| `operacion agregar` | `operacion agregar venta CEMARGOS --cantidad 557 --precio 10800 --fecha 2026-11-10 --hora 10:30` |
| `operacion confirmar` | Confirma que no hubo más operaciones desde el último export (no vuelve a preguntar hoy) |
| `historial` | `historial --desde 2026-01-01 --con-historico --detalle` |

**Precios:** escríbelos en pesos y sin puntos, por ejemplo `2515`. Si escribes `2.515`, el
agente lo entiende igual, como dos mil quinientos quince. Todos los comandos aceptan `--json`;
los que leen órdenes aceptan además `--csv RUTA`.

## Actualizar

En OpenCode, escribe `/instalar-copiloto --actualizar`. O en PowerShell:

```powershell
python instalar.py --actualizar
```

Eso hace `git pull` y vuelve a correr el instalador. Tu carpeta `datos\` no se toca. Después,
reinicia OpenCode.

## Problemas comunes

| Síntoma | Solución |
|---|---|
| `Configuration is invalid ... skills` al abrir OpenCode | Tu versión de OpenCode usa otro formato. Este repo trae `"skills": {"paths": ["./skills"]}`. Si tu versión pide una lista, cámbialo por `"skills": ["./skills"]` |
| "No encontré el export de órdenes" | Corre el comando `archivos`: te dice dónde buscó y por qué descartó cada archivo. Exporta de nuevo a Descargas o usa `--csv "RUTA"` |
| El agente busca archivos una y otra vez | Recuérdale: "usa el comando archivos, no busques en el disco". Si sigue, cambia de modelo |
| Precios raros ($3, $4) o cantidades enormes | El modelo leyó mal el número. El agente lo frena: "precio de entrada" bloquea la operación, y "NO SE CREÓ EL PLAN" sale si el objetivo queda por debajo de la entrada o la cantidad supera tu capital. Pide montos en palabras ("invierte 5 millones"), que el agente convierte en `--valor` |
| "No hay efectivo para comprar" | Todo tu capital está en posiciones abiertas. Si vendiste algo después del export, díselo al agente (lo registra con `operacion agregar`). Si tu saldo en la app es otro, pásalo con `--efectivo` o ponlo en `efectivo_cop` en `datos\config.json` |
| La cantidad sale menor que el monto que pediste | Lo limita la pérdida máxima por operación (1% del capital por defecto). La línea del plan dice qué lo limitó. Para comprar más, usa un stop más corto o, si de verdad quieres arriesgar más, sube `max_perdida_operacion_pct` en `datos\config.json` |
| Yahoo no trae el precio | Dalo a mano: `--precio NUCO=39000` (cartera) o `--mercado 39000` (plan y riesgo), o ponlo en `datos\precios.json` |
| `python` no se reconoce | Instala Python y marca "Add python.exe to PATH", o usa `py` en vez de `python` |
| Errores con tildes en la consola | Ya está resuelto en el programa. Si persiste, corre `chcp 65001` antes |

## Estructura del proyecto

```
copiloto-bvc/
├── instalar.py                     instalador / actualizador
├── opencode.json                   le dice a OpenCode dónde está el skill
├── AGENTS.md                       reglas del proyecto para el agente
├── .opencode/commands/             comando /instalar-copiloto
├── skills/copiloto-bvc/
│   ├── SKILL.md                    instrucciones para el agente
│   ├── copiloto.py                 la herramienta (CLI)
│   ├── copiloto_lib/               cartera, exportes, plan, reglas, simulador...
│   └── referencias/                por qué de las reglas; horario, festivos y comisiones
├── tests/                          pruebas offline con datos sintéticos
└── datos/                          TUS datos (se crea al instalar, no se sube a git)
```

## Pruebas

```powershell
python -m unittest discover -s tests -v
```

Corren sin internet y con datos sintéticos.

## Letra pequeña

- **No es asesoría financiera.** Es software que hace cuentas con datos públicos y con tu
  historial. Las decisiones son tuyas.
- **Un stop no garantiza el precio.** Si la acción abre con un hueco, la orden se ejecuta más
  abajo.
- **Los datos de Yahoo no son oficiales.** Para las acciones globales, el precio es la acción
  en EE. UU. multiplicada por la TRM. Confirma siempre en tu app.
- **El simulador usa el pasado.** Resultados, noticias o suspensiones pueden hacer cosas que
  el histórico nunca mostró.
- **Las tarifas de comisión por defecto** son las publicadas por una app colombiana en 2026.
  Ajusta las tuyas en `datos\config.json`.
- **El export es información personal.** Queda en `datos\`, que no se sube a git. No lo
  publiques.

Basado en ideas de [day-trader-skill](https://github.com/Jakeschincariol/day-trader-skill)
(MIT), adaptado al mercado colombiano. Licencia MIT.
