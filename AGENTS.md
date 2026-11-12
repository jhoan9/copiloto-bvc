# copiloto-bvc: reglas para el agente

Asistente de decisiones para acciones colombianas. El skill está en
`skills/copiloto-bvc/` (léelo: `SKILL.md`), y OpenCode lo carga desde ahí por
`opencode.json`. No lo copies a `.opencode/skills/`.

## Comandos

`python skills\copiloto-bvc\copiloto.py <comando>`, desde la raíz del proyecto.
- En Windows usa `python`, no `python3`.
- En PowerShell, cada comando va en una sola línea con todos sus argumentos.

## Archivos: no los busques

- El agente encuentra solo el export de órdenes, en `datos/` y en Descargas, y te dice cuál
  usó en la línea `[export] ...`.
- **No uses** `ls`, `dir`, `Get-ChildItem`, `find` ni leas CSV para buscarlo.
- Si falta, corre `copiloto.py archivos` una sola vez y muéstrale al usuario lo que dice.

## Instalar y actualizar

Hazlo tú. No le pidas al usuario que copie archivos.

| Situación | Qué correr |
|---|---|
| Falta `datos/config.json`, o el usuario pide instalar, revisar o reparar | `python instalar.py` |
| El usuario pide actualizar | `python instalar.py --actualizar` (hace git pull) |
| El usuario trae datos de una instalación anterior | `python instalar.py --traer-datos "RUTA"` |
| El usuario trae un zip | `python instalar.py "RUTA\copiloto-bvc.zip"` |

## Datos y seguridad

- `datos/` son los datos personales del usuario. No los edites a mano, no los borres y no los
  subas a git.
- Nunca pidas ni guardes usuarios o contraseñas de la app.
- Nunca envíes órdenes. El usuario las pone a mano.
