# Por qué existe cada regla

Las reglas por defecto atacan los errores más comunes de quien opera solo y sin plan.

| Problema típico | Regla | Valor por defecto |
|---|---|---|
| Pocas pérdidas grandes se comen muchas ganancias pequeñas | Stop de pérdida en cada compra | `stop_pct: 3` |
| Las perdedoras se dejan correr "a ver si vuelve" | Salir si sigue en rojo a los N días hábiles; ninguna operación dura más de M | `max_dias_perdedora: 10`, `max_dias_total: 20` |
| Una sola compra muy grande arruina el mes | Tope por orden | `max_orden_cop: 20000000` |
| En órdenes pequeñas la comisión fija se come la ganancia | Mínimo por orden | `min_orden_cop: 2000000` |
| Se gana poco cuando se acierta y se pierde mucho cuando no | Objetivo de 2 veces el riesgo y ganancia/riesgo mínima después de comisiones | `objetivo_r: 2`, `min_rr_neto: 1.5` |
| Todo el capital termina en una sola acción | Máximo por acción, como % del capital | `max_posicion_pct: 30` |
| Se compra más de lo que va perdiendo | No promediar a la baja | `permitir_promediar_a_la_baja: false` |
| Un mes malo se vuelve dos | Pérdida máxima del mes: al llegar, no más compras ese mes | `max_perdida_mes_pct: 4` |
| Demasiadas posiciones para seguirlas bien | Máximo de posiciones abiertas | `max_posiciones_abiertas: 4` |
| Una compra justo antes de resultados es una apuesta | Bloqueo N días hábiles antes de resultados | `dias_bloqueo_eventos: 2` |
| La pérdida de cada operación depende del tamaño, no solo del stop | Pérdida máxima por operación como % del capital: de ahí sale la cantidad | `max_perdida_operacion_pct: 1` |

## Cómo ajustarlas con tus datos

1. Exporta tus órdenes y corre `historial --desde AAAA-01-01`. Muestra cuánto habrías
   ahorrado con el stop y cuántas compras habrían bloqueado los límites de tamaño.
2. Con internet, `historial --con-historico` repite cada operación con los precios diarios
   reales.
3. Antes de cambiar el stop o el objetivo de una acción, prueba con `simular TICKER --stop X --objetivo Y`.
4. Cambia los valores en `datos/config.json`. Ese archivo es tuyo y no se sube al repositorio.
