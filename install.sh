#!/bin/sh
# Instala «Color de pantalla» en el directorio del usuario.
set -eu

SRC=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PREFIX=${PREFIX:-$HOME/.local}
BIN="$PREFIX/bin"
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"

command -v python3 >/dev/null 2>&1 || {
    echo "Error: falta python3." >&2
    exit 1
}
python3 -c "import gi" 2>/dev/null || {
    echo "Error: falta PyGObject (paquete python3-gi)." >&2
    exit 1
}
command -v redshift >/dev/null 2>&1 || {
    echo "Aviso: 'redshift' no está en el PATH. Instálalo con:" >&2
    echo "  sudo apt install redshift redshift-gtk" >&2
}

install -d "$BIN" "$APPS"
install -m 755 "$SRC/redshift-color.py" "$BIN/redshift-color"
install -m 755 "$SRC/redshift-gtk-single" "$BIN/redshift-gtk-single"
install -m 644 "$SRC/redshift-color.desktop" "$APPS/redshift-color.desktop"

# El lanzador del menú apunta a la ruta real de instalación.
sed -i "s|^Exec=.*|Exec=$BIN/redshift-color|; s|^TryExec=.*|TryExec=$BIN/redshift-color|" \
    "$APPS/redshift-color.desktop"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APPS" >/dev/null 2>&1 || true
fi

echo "Listo. Abre «Color de pantalla» desde el menú (busca «color» o «redshift»)."
