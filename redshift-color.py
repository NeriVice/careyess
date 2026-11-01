#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Color de pantalla — control gráfico de Redshift para Xfce.

Permite elegir la temperatura de color y el brillo con vista previa
inmediata, y guardar el ajuste en ~/.config/redshift.conf para que
Redshift lo mantenga (fijo o siguiendo la hora del día).
"""

import os
import re
import shutil
import subprocess
import tempfile
import time

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

__version__ = "1.0.0"

APP_ID = "org.local.RedshiftColor"
CONF = os.environ.get(
    "REDSHIFT_CONF",
    os.path.join(
        os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
        "redshift.conf",
    ),
)


def _find_launcher():
    """Ruta del lanzador de una sola instancia (o 'redshift-gtk' del sistema)."""
    here = os.path.dirname(os.path.realpath(__file__))
    for candidate in (
        os.path.join(here, "redshift-gtk-single"),
        os.path.expanduser("~/.local/bin/redshift-gtk-single"),
        "/usr/local/bin/redshift-gtk-single",
    ):
        if os.access(candidate, os.X_OK):
            return candidate
    return "redshift-gtk"


LAUNCHER = _find_launcher()
TEMP_MIN, TEMP_MAX = 1000.0, 6500.0
DEVNULL = subprocess.DEVNULL

TEMP_RE = re.compile(r"(\d{3,5})\s*K\b")
BRIGHT_RE = re.compile(r"(?:Brillo|Brightness)[^:]*:\s*([\d.,]+)")
PERIOD_RE = re.compile(r"(?:Per[ií]odo|Period)[^:]*:\s*(\S+)")

PRESETS = (2700, 3400, 4000, 5500, 6500)

CSS = b"""
.app-title { font-size: 19px; font-weight: 700; }
.hero-temp { font-size: 40px; font-weight: 800; }
.hint { font-size: 11px; color: alpha(@theme_fg_color, 0.62); }
.section { font-size: 12px; font-weight: 600; color: alpha(@theme_fg_color, 0.75); }
.card { background-color: alpha(@theme_fg_color, 0.06); border-radius: 12px; }
.preset { font-size: 11px; padding: 3px 6px; border-radius: 7px;
          background-color: alpha(@theme_fg_color, 0.07); }
.preset-active { background-color: alpha(@theme_selected_bg_color, 0.85);
                 color: @theme_selected_fg_color; font-weight: 700; }
"""


# --------------------------------------------------------------------------
# Configuración de Redshift
# --------------------------------------------------------------------------
def read_conf():
    values = {}
    try:
        with open(CONF, encoding="utf-8") as handle:
            section = None
            for raw in handle:
                line = raw.strip()
                if not line or line[0] in "#;":
                    continue
                if line.startswith("["):
                    section = line.strip("[]").strip().lower()
                    continue
                if section == "redshift" and "=" in line:
                    key, value = line.split("=", 1)
                    values[key.strip()] = value.strip()
    except OSError:
        pass
    return values


def as_int(value, default):
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def as_float(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def write_conf(updates):
    """Actualiza claves de [redshift] conservando el resto del archivo."""
    lines = []
    if os.path.exists(CONF):
        with open(CONF, encoding="utf-8") as handle:
            lines = handle.read().splitlines()
        shutil.copy2(CONF, CONF + ".bak")

    start = None
    end = None
    for index, raw in enumerate(lines):
        stripped = raw.strip()
        if not stripped.startswith("["):
            continue
        name = stripped.strip("[]").strip().lower()
        if name == "redshift" and start is None:
            start = index
        elif start is not None:
            end = index
            break
    if start is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append("[redshift]")
        start, end = len(lines) - 1, len(lines)
    if end is None:
        end = len(lines)

    pending = dict(updates)
    for index in range(start + 1, end):
        stripped = lines[index].strip()
        if not stripped or stripped[0] in "#;" or "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in pending:
            lines[index] = "{0}={1}".format(key, pending.pop(key))

    position = end
    while position - 1 > start and not lines[position - 1].strip():
        position -= 1
    for key, value in pending.items():
        lines.insert(position, "{0}={1}".format(key, value))
        position += 1

    directory = os.path.dirname(CONF) or "."
    handle_fd, tmp_path = tempfile.mkstemp(prefix=".redshift.", dir=directory)
    try:
        with os.fdopen(handle_fd, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines).rstrip("\n") + "\n")
        if os.path.exists(CONF):
            shutil.copymode(CONF, tmp_path)
        else:
            os.chmod(tmp_path, 0o644)
        os.replace(tmp_path, CONF)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# --------------------------------------------------------------------------
# Estado de Redshift
# --------------------------------------------------------------------------
def redshift_running():
    """True si hay un Redshift vivo (los zombis no cuentan)."""
    try:
        result = subprocess.run(
            ["ps", "-C", "redshift", "-o", "stat="],
            stdout=subprocess.PIPE,
            stderr=DEVNULL,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return any(
        state and not state.startswith("Z") for state in result.stdout.split()
    )


def current_state():
    state = {"temp": None, "brightness": None, "period": ""}
    try:
        result = subprocess.run(
            ["redshift", "-p"],
            stdout=subprocess.PIPE,
            stderr=DEVNULL,
            text=True,
            timeout=6,
        )
    except (OSError, subprocess.SubprocessError):
        return state
    for line in (result.stdout or "").splitlines():
        temp_match = TEMP_RE.search(line)
        if temp_match and state["temp"] is None:
            state["temp"] = int(temp_match.group(1))
            continue
        bright_match = BRIGHT_RE.search(line)
        if bright_match:
            state["brightness"] = as_float(
                bright_match.group(1).replace(",", "."), None
            )
            continue
        period_match = PERIOD_RE.search(line)
        if period_match:
            state["period"] = period_match.group(1)
    return state


def restart_daemon():
    """Reinicia Redshift para que aplique la configuración guardada."""
    try:
        subprocess.run(
            ["pkill", "-x", "redshift"], stdout=DEVNULL, stderr=DEVNULL, timeout=4
        )
        subprocess.run(
            ["pkill", "-f", "/usr/bin/redshift-gtk"],
            stdout=DEVNULL,
            stderr=DEVNULL,
            timeout=4,
        )
    except (OSError, subprocess.SubprocessError):
        pass
    time.sleep(0.3)
    # Neutralizar la rampa antes de arrancar: si queda una rampa cálida
    # aplicada, Redshift la vuelve a multiplicar y la pantalla se oscurece.
    try:
        subprocess.run(
            ["redshift", "-x"], stdout=DEVNULL, stderr=DEVNULL, timeout=6
        )
    except (OSError, subprocess.SubprocessError):
        pass
    launcher = LAUNCHER if os.access(LAUNCHER, os.X_OK) else "redshift-gtk"
    try:
        subprocess.Popen(
            [launcher],
            stdout=DEVNULL,
            stderr=DEVNULL,
            start_new_session=True,
        )
    except OSError:
        return
    for _ in range(25):
        time.sleep(0.1)
        if redshift_running():
            return


def describe(temp):
    if temp < 2700:
        return "Muy cálido"
    if temp < 3500:
        return "Cálido"
    if temp < 4500:
        return "Cálido suave"
    if temp < 5500:
        return "Neutro"
    if temp < 6300:
        return "Luz de día"
    return "Sin filtro"


# --------------------------------------------------------------------------
# Interfaz
# --------------------------------------------------------------------------
class ColorWindow(Gtk.ApplicationWindow):
    def __init__(self, application):
        super().__init__(application=application, title="Color de pantalla")
        self.set_default_size(560, 530)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_icon_name("redshift")

        self._dirty = False

        conf = read_conf()
        state = current_state()

        now_temp = state["temp"] or as_int(conf.get("temp-day"), 6500)
        now_temp = max(TEMP_MIN, min(TEMP_MAX, float(now_temp)))
        now_bright = state["brightness"]
        if now_bright is None:
            now_bright = as_float(conf.get("brightness-day"), 1.0)
        now_bright = max(0.3, min(1.0, float(now_bright)))

        self.day_temp = as_int(conf.get("temp-day"), 6500)
        self.night_temp = as_int(conf.get("temp-night"), 3500)

        self._install_css()
        self._build(now_temp, now_bright, conf)
        self.connect("key-press-event", self._on_key)
        GLib.idle_add(self._update_status)

    # -- construcción -----------------------------------------------------
    def _install_css(self):
        try:
            provider = Gtk.CssProvider()
            provider.load_from_data(CSS)
            Gtk.StyleContext.add_provider_for_screen(
                Gdk.Screen.get_default(),
                provider,
                Gtk.STYLE_PROVIDER_PRIORITY_USER,
            )
        except Exception:
            pass

    def _build(self, now_temp, now_bright, conf):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(outer)

        header = Gtk.Box(spacing=12)
        header.set_margin_top(20)
        header.set_margin_bottom(14)
        header.set_margin_start(20)
        header.set_margin_end(20)

        titles = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        title = Gtk.Label(label="Color de pantalla", xalign=0)
        title.get_style_context().add_class("app-title")
        subtitle = Gtk.Label(label="Filtro de luz azul · Redshift", xalign=0)
        subtitle.get_style_context().add_class("hint")
        titles.pack_start(title, False, False, 0)
        titles.pack_start(subtitle, False, False, 0)

        self.saved_label = Gtk.Label(label="guardado: {0} K".format(int(now_temp)))
        self.saved_label.get_style_context().add_class("hint")
        self.saved_label.set_valign(Gtk.Align.CENTER)

        header.pack_start(titles, True, True, 0)
        header.pack_end(self.saved_label, False, False, 0)
        outer.pack_start(header, False, False, 0)

        notebook = Gtk.Notebook()
        notebook.set_margin_start(18)
        notebook.set_margin_end(18)
        outer.pack_start(notebook, True, True, 0)

        notebook.append_page(
            self._build_quick_page(now_temp, now_bright), Gtk.Label(label="Ajuste rápido")
        )
        notebook.append_page(
            self._build_auto_page(conf), Gtk.Label(label="Automático")
        )

        self.status = Gtk.Label(label="", xalign=0)
        self.status.get_style_context().add_class("hint")
        self.status.set_margin_top(10)
        self.status.set_margin_bottom(14)
        self.status.set_margin_start(20)
        self.status.set_margin_end(20)
        outer.pack_start(self.status, False, False, 0)

    def _card(self, spacing=8):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=spacing)
        card.get_style_context().add_class("card")
        card.set_margin_top(4)
        card.set_margin_bottom(4)
        return card

    def _build_quick_page(self, now_temp, now_bright):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        page.set_margin_top(14)
        page.set_margin_bottom(14)

        card = self._card()
        self.temp_label = Gtk.Label(label="{0} K".format(int(now_temp)))
        self.temp_label.get_style_context().add_class("hero-temp")
        self.temp_desc = Gtk.Label(label=describe(int(now_temp)))
        self.temp_desc.get_style_context().add_class("hint")
        card.pack_start(self.temp_label, False, False, 0)
        card.pack_start(self.temp_desc, False, False, 0)

        self.temp_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, TEMP_MIN, TEMP_MAX, 100
        )
        self.temp_scale.set_draw_value(False)
        self.temp_scale.set_increments(100, 500)
        self.temp_scale.set_hexpand(True)
        self.temp_scale.set_value(now_temp)
        self.temp_scale.connect("value-changed", self.on_temp_changed)
        card.pack_start(self.temp_scale, False, False, 0)

        presets = Gtk.Box(spacing=6, homogeneous=True)
        self.preset_buttons = {}
        for value in PRESETS:
            button = Gtk.Button(label=str(value))
            button.set_relief(Gtk.ReliefStyle.NONE)
            button.get_style_context().add_class("preset")
            button.set_tooltip_text("{0} K · {1}".format(value, describe(value)))
            button.connect("clicked", self.on_preset_clicked, value)
            presets.pack_start(button, True, True, 0)
            self.preset_buttons[value] = button
        card.pack_start(presets, False, False, 0)
        page.pack_start(card, False, False, 0)

        bright_card = self._card()
        bright_title = Gtk.Label(label="Brillo", xalign=0)
        bright_title.get_style_context().add_class("section")
        bright_card.pack_start(bright_title, False, False, 0)

        bright_row = Gtk.Box(spacing=10)
        bright_icon = Gtk.Image.new_from_icon_name(
            "display-brightness-symbolic", Gtk.IconSize.BUTTON
        )
        self.bright_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 30, 100, 1
        )
        self.bright_scale.set_draw_value(False)
        self.bright_scale.set_hexpand(True)
        self.bright_scale.set_value(round(now_bright * 100))
        self.bright_scale.connect("value-changed", self.on_bright_changed)
        self.bright_label = Gtk.Label(label="{0} %".format(int(round(now_bright * 100))))
        self.bright_label.set_width_chars(5)
        self.bright_label.set_xalign(1)
        bright_row.pack_start(bright_icon, False, False, 0)
        bright_row.pack_start(self.bright_scale, True, True, 0)
        bright_row.pack_start(self.bright_label, False, False, 0)
        bright_card.pack_start(bright_row, False, False, 0)
        page.pack_start(bright_card, False, False, 0)

        hint = Gtk.Label(
            label="Elige el tono y pulsa Guardar. Si cierras sin guardar, no cambia nada.",
            justify=Gtk.Justification.CENTER,
            wrap=True,
        )
        hint.get_style_context().add_class("hint")
        page.pack_start(hint, False, False, 0)

        save = Gtk.Button(label="Guardar como color fijo")
        save.get_style_context().add_class("suggested-action")
        save.connect("clicked", self.on_save_quick)
        page.pack_end(save, False, False, 0)

        self._update_preset_classes(int(now_temp))
        return page

    def _build_auto_page(self, conf):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        page.set_margin_top(14)
        page.set_margin_bottom(14)

        hint = Gtk.Label(
            label="Cambia solo, siguiendo la hora local: más cálido de noche y "
            "más neutro de día.",
            wrap=True,
            justify=Gtk.Justification.LEFT,
            xalign=0,
        )
        hint.get_style_context().add_class("hint")
        page.pack_start(hint, False, False, 0)

        self.day_card, self.day_scale, self.day_value = self._slider_card(
            "Temperatura de día", self.day_temp
        )
        self.night_card, self.night_scale, self.night_value = self._slider_card(
            "Temperatura de noche", self.night_temp
        )
        self.day_scale.connect("value-changed", self.on_auto_changed)
        self.night_scale.connect("value-changed", self.on_auto_changed)
        page.pack_start(self.day_card, False, False, 0)
        page.pack_start(self.night_card, False, False, 0)

        transition_value = as_int(conf.get("transition"), 1) != 0
        self.transition = Gtk.CheckButton(
            label="Transición gradual (aprox. 1 hora en cada cambio)"
        )
        self.transition.set_active(transition_value)
        page.pack_start(self.transition, False, False, 0)

        buttons = Gtk.Box(spacing=8)
        reset = Gtk.Button(label="Valores por defecto")
        reset.set_relief(Gtk.ReliefStyle.NONE)
        reset.connect("clicked", self.on_reset_auto)
        save = Gtk.Button(label="Guardar programación")
        save.get_style_context().add_class("suggested-action")
        save.connect("clicked", self.on_save_auto)
        buttons.pack_start(reset, False, False, 0)
        buttons.pack_end(save, False, False, 0)
        page.pack_end(buttons, False, False, 0)

        return page

    def _slider_card(self, title, value):
        card = self._card(spacing=2)
        top = Gtk.Box(spacing=8)
        label = Gtk.Label(label=title, xalign=0)
        label.get_style_context().add_class("section")
        value_label = Gtk.Label(label="{0} K".format(value), xalign=1)
        value_label.set_hexpand(True)
        top.pack_start(label, False, False, 0)
        top.pack_end(value_label, False, False, 0)

        scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, TEMP_MIN, TEMP_MAX, 100
        )
        scale.set_draw_value(False)
        scale.set_increments(100, 500)
        scale.set_hexpand(True)
        scale.set_value(value)

        card.pack_start(top, False, False, 0)
        card.pack_start(scale, False, False, 0)
        return card, scale, value_label

    # -- comportamiento ---------------------------------------------------
    def _set_status(self, text):
        self.status.set_text(text)

    def _update_preset_classes(self, value):
        for preset, button in self.preset_buttons.items():
            context = button.get_style_context()
            if abs(preset - value) <= 50:
                context.add_class("preset-active")
            else:
                context.remove_class("preset-active")

    def on_temp_changed(self, scale):
        value = int(round(scale.get_value() / 100.0)) * 100
        self.temp_label.set_text("{0} K".format(value))
        self.temp_desc.set_text(describe(value))
        self._update_preset_classes(value)
        self.queue_preview()

    def on_bright_changed(self, scale):
        self.bright_label.set_text("{0} %".format(int(round(scale.get_value()))))
        self.queue_preview()

    def on_preset_clicked(self, _button, value):
        self.temp_scale.set_value(value)

    def on_auto_changed(self, scale):
        value = int(round(scale.get_value() / 100.0)) * 100
        if scale is self.day_scale:
            self.day_value.set_text("{0} K".format(value))
        else:
            self.night_value.set_text("{0} K".format(value))

    def queue_preview(self):
        """Marca cambios pendientes; no toca la pantalla hasta guardar."""
        self._dirty = True
        self._update_status()

    def _restart(self):
        restart_daemon()
        self._dirty = False
        self._update_status()

    def on_save_quick(self, _button):
        temp = int(round(self.temp_scale.get_value() / 100.0)) * 100
        percent = int(round(self.bright_scale.get_value()))
        brightness = percent / 100.0
        try:
            write_conf(
                {
                    "temp-day": temp,
                    "temp-night": temp,
                    "brightness-day": "{0:.2f}".format(brightness),
                    "brightness-night": "{0:.2f}".format(brightness),
                    "transition": 0,
                }
            )
        except OSError as error:
            self._set_status("No se pudo guardar: {0}".format(error))
            return
        self.day_temp = self.night_temp = temp
        self.day_scale.set_value(temp)
        self.night_scale.set_value(temp)
        self._restart()
        self.saved_label.set_text("guardado: {0} K".format(temp))
        self._set_status(
            "Guardado ✓ {0} K fijo · brillo {1} %".format(temp, percent))

    def on_save_auto(self, _button):
        day = int(round(self.day_scale.get_value() / 100.0)) * 100
        night = int(round(self.night_scale.get_value() / 100.0)) * 100
        brightness = int(round(self.bright_scale.get_value())) / 100.0
        try:
            write_conf(
                {
                    "temp-day": day,
                    "temp-night": night,
                    "brightness-day": "{0:.2f}".format(brightness),
                    "brightness-night": "{0:.2f}".format(brightness),
                    "transition": 1 if self.transition.get_active() else 0,
                }
            )
        except OSError as error:
            self._set_status("No se pudo guardar: {0}".format(error))
            return
        self.day_temp, self.night_temp = day, night
        self._restart()
        self.saved_label.set_text("guardado: día {0} / noche {1} K".format(day, night))
        self._set_status(
            "Programación guardada ✓ día {0} K · noche {1} K".format(day, night)
        )

    def on_reset_auto(self, _button):
        self.day_scale.set_value(6500)
        self.night_scale.set_value(3500)
        self.transition.set_active(True)

    def _update_status(self, *_args):
        if self._dirty:
            temp = int(round(self.temp_scale.get_value() / 100.0)) * 100
            self.status.set_text(
                "Elegido: {0} K · brillo {1} % — pulsa Guardar para aplicarlo".format(
                    temp, int(round(self.bright_scale.get_value()))
                )
            )
            return False
        state = current_state()
        parts = []
        if state["temp"]:
            parts.append("{0} K".format(state["temp"]))
        if state["brightness"] is not None:
            parts.append("brillo {0} %".format(int(round(state["brightness"] * 100))))
        if state["period"]:
            parts.append(state["period"].lower())
        self.status.set_text("Ahora: " + " · ".join(parts) + " · guardado")
        return False

    def _on_key(self, _widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False


class ColorApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)
        GLib.set_prgname("redshift-color")
        GLib.set_application_name("Color de pantalla")
        self.window = None

    def do_activate(self):
        if self.window is None:
            self.window = ColorWindow(self)
            self.window.connect("destroy", self._on_destroy)
            self.window.show_all()
        self.window.present()

    def _on_destroy(self, _window):
        self.window = None
        self.quit()


def main():
    return ColorApp().run([])


if __name__ == "__main__":
    raise SystemExit(main())
