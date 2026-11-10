#!/bin/sh
# careyess — instalador completo.
#
# Instala lo que falta del sistema (Python 3, PyGObject/GTK3, Redshift y,
# cuando existe, redshift-gtk), copia la aplicación, el icono, la entrada del
# menú y deja Redshift arrancando solo al iniciar sesión.
set -eu

SRC=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PREFIX=${PREFIX:-$HOME/.local}
BIN="$PREFIX/bin"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
APPS="$DATA_HOME/applications"
ICONS="$DATA_HOME/icons/hicolor/scalable/apps"
AUTOSTART="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"

WITH_DEPS=1
START_NOW=0

usage() {
    cat <<'EOF'
Uso: ./install.sh [opciones]

  --no-deps   no instala paquetes del sistema (solo copia careyess)
  --start     arranca Redshift al terminar, para aplicar ya la configuración
  -h, --help  muestra esta ayuda
EOF
}

for arg in "$@"; do
    case "$arg" in
        --no-deps) WITH_DEPS=0 ;;
        --start) START_NOW=1 ;;
        -h | --help)
            usage
            exit 0
            ;;
        *)
            echo "Opción desconocida: $arg" >&2
            usage >&2
            exit 2
            ;;
    esac
done

say() { printf '%s\n' "$*"; }
die() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

have() { command -v "$1" >/dev/null 2>&1; }

have_gtk3() {
    python3 - <<'PY' >/dev/null 2>&1
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: F401
PY
}

# --- dependencias ---------------------------------------------------------

pm=""
for candidate in apt-get dnf pacman zypper; do
    if have "$candidate"; then
        pm=$candidate
        break
    fi
done

case "$pm" in
    apt-get)
        PM_PY=python3 PM_GI=python3-gi PM_GTK=gir1.2-gtk-3.0
        PM_RS=redshift PM_RSGTK=redshift-gtk
        ;;
    dnf)
        PM_PY=python3 PM_GI=python3-gobject PM_GTK=gtk3
        PM_RS=redshift PM_RSGTK=redshift-gtk
        ;;
    pacman)
        PM_PY=python PM_GI=python-gobject PM_GTK=gtk3
        PM_RS=redshift PM_RSGTK=""
        ;;
    zypper)
        PM_PY=python3 PM_GI=python3-gobject PM_GTK=gtk3
        PM_RS=redshift PM_RSGTK=""
        ;;
    *)
        PM_PY="" PM_GI="" PM_GTK="" PM_RS="" PM_RSGTK=""
        ;;
esac

as_root() {
    if [ "$(id -u)" -eq 0 ]; then
        "$@"
    elif have sudo; then
        sudo "$@"
    else
        die "hacen falta permisos de root para: $*"
    fi
}

pkg_install() {
    case "$pm" in
        apt-get) as_root apt-get install -y "$@" ;;
        dnf) as_root dnf install -y "$@" ;;
        pacman) as_root pacman -S --needed --noconfirm "$@" ;;
        zypper) as_root zypper --non-interactive install "$@" ;;
        *) return 1 ;;
    esac
}

# apt a veces necesita refrescar la lista antes de encontrar un paquete.
install_packages() {
    pkg_install "$@" && return 0
    if [ "$pm" = apt-get ]; then
        say "Actualizando la lista de paquetes…"
        as_root apt-get update && pkg_install "$@"
        return $?
    fi
    return 1
}

# Versión instalada, por ejemplo «1.12».
redshift_version() {
    redshift -V 2>/dev/null | awk 'NR == 1 {print $2}'
}

# Aviso informativo: última versión publicada de Redshift en upstream.
check_redshift_latest() {
    command -v curl >/dev/null 2>&1 || return 0
    latest=$(curl -fsSL --max-time 6 \
        https://api.github.com/repos/jonls/redshift/releases/latest 2>/dev/null |
        sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p' | head -n 1) || return 0
    latest=${latest#v}
    [ -n "$latest" ] || return 0
    current=$(redshift_version)
    [ -n "$current" ] || return 0
    if [ "$latest" = "$current" ]; then
        say "Redshift $current es la última versión publicada."
    else
        say "Aviso: la última versión publicada de Redshift es $latest y la instalada es $current."
        say "       Si necesitás esa versión, compilala desde https://github.com/jonls/redshift"
    fi
}

if [ "$WITH_DEPS" -eq 1 ]; then
    need=""
    have python3 || need="$need $PM_PY"
    have_gtk3 || need="$need $PM_GI $PM_GTK"
    have redshift || need="$need $PM_RS"

    if [ -n "$need" ]; then
        [ -n "$pm" ] ||
            die "no reconozco el gestor de paquetes; instalá a mano: python3, PyGObject con GTK3 y redshift"
        say "Instalando dependencias:$need"
        # shellcheck disable=SC2086
        install_packages $need ||
            die "no se pudieron instalar las dependencias:$need"
    fi

    check_redshift_latest

    if ! have redshift-gtk; then
        if [ -n "$PM_RSGTK" ] && install_packages "$PM_RSGTK" >/dev/null 2>&1; then
            say "redshift-gtk instalado: bandeja del sistema disponible."
        else
            say "Aviso: redshift-gtk no está disponible; careyess arrancará Redshift directamente."
        fi
    fi
fi

have python3 || die "falta python3"
have_gtk3 || die "falta PyGObject con GTK3 (python3-gi y gir1.2-gtk-3.0 en Debian/Ubuntu)"
have redshift || die "falta redshift (sudo apt install redshift)"

# --- archivos -------------------------------------------------------------

install -d "$BIN" "$APPS" "$ICONS" "$AUTOSTART"
install -m 755 "$SRC/careyess.py" "$BIN/careyess"
install -m 755 "$SRC/careyess-redshift" "$BIN/careyess-redshift"
install -m 644 "$SRC/careyess.desktop" "$APPS/careyess.desktop"
install -m 644 "$SRC/careyess.svg" "$ICONS/careyess.svg"

python3 - "$BIN/careyess" <<'PY' || die "careyess.py no compila"
import sys

source = open(sys.argv[1], encoding="utf-8").read()
compile(source, sys.argv[1], "exec")
PY

# El lanzador del menú apunta a la ruta real de instalación.
sed -i "s|^Exec=.*|Exec=$BIN/careyess|; s|^TryExec=.*|TryExec=$BIN/careyess|" \
    "$APPS/careyess.desktop"

# Restos de versiones anteriores (careye y «Color de pantalla»).
rm -f "$BIN/careye" "$BIN/careye-redshift" \
      "$APPS/careye.desktop" "$ICONS/careye.svg" \
      "$AUTOSTART/careye-redshift.desktop" \
      "$BIN/redshift-color" "$BIN/redshift-gtk-single" \
      "$APPS/redshift-color.desktop"

# Con redshift-gtk, el paquete ya trae su propio arranque automático.
if have redshift-gtk; then
    rm -f "$AUTOSTART/careyess-redshift.desktop"
else
    cat >"$AUTOSTART/careyess-redshift.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Careyess — filtro de Redshift
Comment=Mantiene el color de pantalla configurado en careyess
Exec=$BIN/careyess-redshift
Terminal=false
NoDisplay=true
X-GNOME-Autostart-enabled=true
EOF
fi

if have update-desktop-database; then
    update-desktop-database "$APPS" >/dev/null 2>&1 || true
fi
if have gtk-update-icon-cache; then
    gtk-update-icon-cache -qtf "$DATA_HOME/icons/hicolor" >/dev/null 2>&1 || true
fi

if [ "$START_NOW" -eq 1 ]; then
    "$BIN/careyess-redshift" || true
    say "Redshift arrancado con tu configuración."
fi

say ""
say "Listo. Abrí «Careyess» desde el menú, o ejecutá: $BIN/careyess"
