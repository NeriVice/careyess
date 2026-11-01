#!/bin/sh
# Desinstala «Color de pantalla» (no toca ~/.config/redshift.conf).
set -eu

PREFIX=${PREFIX:-$HOME/.local}
BIN="$PREFIX/bin"
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"

rm -f "$BIN/redshift-color" "$BIN/redshift-gtk-single" \
      "$APPS/redshift-color.desktop"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APPS" >/dev/null 2>&1 || true
fi

echo "Desinstalado. Tu configuración de Redshift no se ha modificado."
