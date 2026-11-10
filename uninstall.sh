#!/bin/sh
# Desinstala careye (no toca ~/.config/redshift.conf).
set -eu

PREFIX=${PREFIX:-$HOME/.local}
BIN="$PREFIX/bin"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
APPS="$DATA_HOME/applications"
ICONS="$DATA_HOME/icons/hicolor/scalable/apps"
AUTOSTART="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"

rm -f "$BIN/careye" "$BIN/careye-redshift" \
      "$APPS/careye.desktop" \
      "$ICONS/careye.svg" \
      "$AUTOSTART/careye-redshift.desktop"

# Restos de la versión anterior, que se llamaba «Color de pantalla».
rm -f "$BIN/redshift-color" "$BIN/redshift-gtk-single" \
      "$APPS/redshift-color.desktop" \
      "$AUTOSTART/redshift-color.desktop"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APPS" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -qtf "$DATA_HOME/icons/hicolor" >/dev/null 2>&1 || true
fi

echo "careye desinstalado. Tu ~/.config/redshift.conf sigue intacto."
