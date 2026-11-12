---
description: Instala, actualiza o revisa copiloto-bvc (código, export de órdenes, pruebas)
---
Instala, actualiza o revisa copiloto-bvc en este proyecto.

1. Desde la raíz del proyecto ejecuta, en una sola línea: `python instalar.py $ARGUMENTS`
   - Sin argumentos: instala o revisa todo.
   - `--actualizar`: baja la última versión con git pull.
   - `--traer-datos "RUTA"`: copia los datos de una instalación anterior.
   - Una ruta `.zip`: actualiza desde ese zip.
2. Lee la salida y explícale al usuario en pocas líneas qué quedó listo y qué falta.
   - Si hay `[ERROR]`, explica la causa y propón el arreglo antes de cambiar archivos.
   - Si hay `[AVISO]` sobre el export, dile que lo exporte desde la app a Descargas, sin
     renombrarlo. No busques el archivo tú mismo.
3. No toques `datos/`. No pidas contraseñas. El agente nunca envía órdenes.
4. Si todo quedó LISTO, recuérdale que reinicie OpenCode y que pruebe con "revisa mi cartera".
