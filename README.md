# Careyess — color de pantalla para Redshift

Ventana GTK sencilla para **elegir el tono y el brillo de la pantalla** sin editar
`redshift.conf` a mano. Pensada para Xfce/Linux Mint, funciona en cualquier
escritorio con X11 y GTK3.

![Ajuste rápido](screenshots/ajuste-rapido.png)

## Qué hace

- **Ajuste rápido:** temperatura de 1000 a 6500 K con atajos (2700, 3400, 4000,
  5500, 6500), brillo del filtro de 30 a 100 % y botón para guardar un color fijo.
- **Automático:** temperatura de día y de noche, transición gradual y guardado de
  la programación para que Redshift cambie solo según la hora.
- Escribe `~/.config/redshift.conf` (guardando una copia `.bak`) y reinicia
  Redshift para aplicar el cambio.
- **Arranca solo al iniciar sesión:** el instalador deja Redshift aplicando tu
  configuración sin que tengas que abrir nada.
- **Instala la última versión de Redshift:** al terminar compara la versión
  instalada con la última publicada (1.12) y te avisa si hay algo más nuevo.
- **Sin vistas previas en vivo a propósito:** si la ventana aplicara el color por
  su cuenta, el servicio de Redshift lo reaplicaría a los pocos segundos y la
  pantalla parpadearía entre tonos. Aquí solo se toca la pantalla al pulsar
  *Guardar*.

<p align="center">
  <img src="screenshots/automatico.png" alt="Pestaña Automático" width="520">
</p>

## Requisitos

- Linux con **X11** (Redshift usa `randr`; en Wayland puro puede no aplicarse).
- `redshift` y Python 3 con PyGObject/GTK3.
- `redshift-gtk` es opcional: si está, se usa su bandeja; si no, careyess arranca
  `redshift` directamente con la configuración guardada.

**No hace falta instalarlos a mano:** `install.sh` detecta lo que falta y lo
instala con el gestor de paquetes de la distribución (apt, dnf, pacman o zypper).

## Instalación

```sh
git clone https://github.com/NeriVice/redshift-color.git
cd redshift-color
./install.sh
```

El instalador:

1. Instala lo que falte del sistema (Python 3, PyGObject con GTK3, Redshift y,
   cuando existe, `redshift-gtk`). Pide la contraseña de sudo si hace falta.
   De Redshift se instala la versión más reciente disponible y se comprueba
   contra la última publicada en upstream.
2. Copia el programa en `~/.local/bin/careyess` y el lanzador de una sola
   instancia en `~/.local/bin/careyess-redshift`.
3. Instala el icono y deja la entrada **Careyess** en el menú.
4. Deja Redshift arrancando solo al iniciar sesión (si no usás `redshift-gtk`,
   que ya trae el suyo).
5. Borra los restos de la versión anterior, que se llamaba «Color de pantalla».

Opciones:

```sh
./install.sh --no-deps   # solo copia careyess, no toca paquetes del sistema
./install.sh --start     # además arranca Redshift al terminar
```

## Uso

1. Abrí **Careyess** desde el menú (buscá *careyess* o *color*), o ejecutá
   `careyess` en una terminal.
2. Elegí el tono: a la derecha (5500–6500 K) se ve más neutro/claro; a la
   izquierda (2700–3400 K) más cálido y anaranjado.
3. Ajustá el brillo si querés atenuar el filtro.
4. Pulsá **Guardar como color fijo** (o **Guardar programación** en la pestaña
   Automático). Redshift se reinicia y mantiene el ajuste.

Desde la terminal:

```sh
careyess                     # abre en Ajuste rápido
careyess --tab auto          # abre en Automático
careyess --version
```

> Guardar tarda un segundo y la pantalla pasa brevemente por un tono neutro
> mientras Redshift se reinicia: es normal.

## Cómo funciona

La ventana lee y escribe las claves de la sección `[redshift]` de
`~/.config/redshift.conf` conservando el resto del archivo:

| Clave | Uso |
|---|---|
| `temp-day`, `temp-night` | temperatura de día y de noche |
| `brightness-day`, `brightness-night` | brillo del filtro (0.1–1.0) |
| `transition` | `1` transición gradual, `0` cambio inmediato |

Al guardar se reinicia Redshift (`pkill` + lanzador de instancia única). Antes de
arrancarlo se neutraliza la rampa con `redshift -x`; si no, al reiniciar sobre una
pantalla ya cálida el filtro se multiplica y la pantalla queda cada vez más oscura.

El script `careyess-redshift` evita que se lancen dos instancias de Redshift a la
vez (dos instancias aplican rampas distintas y producen parpadeos). Si existe
`redshift-gtk` lo usa; si no, arranca `redshift -c ~/.config/redshift.conf`, que
aplica el filtro igual, sin icono de bandeja.

## Desinstalar

```sh
./uninstall.sh
```

No borra tu `~/.config/redshift.conf`.

## Problemas conocidos

- **Wayland:** Redshift necesita `randr`; en Wayland puro el ajuste puede no
  aplicarse. Usá una sesión X11 (Xfce, Mate, Cinnamon con Xorg).
- **La pantalla se ve oscura:** el brillo del panel no lo controla Redshift; usá
  las teclas de brillo. El ajuste de esta ventana solo afecta al filtro de color.
- Si algo queda raro, reiniciá Redshift a mano:
  `pkill -x redshift && careyess-redshift &`

## Licencia

MIT — ver [LICENSE](LICENSE).
