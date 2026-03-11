"""
About-Dialog - Logo, Versionsnummer, Entwicklerinfo
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GdkPixbuf, Gio, GLib
import os

APP_VERSION = "1.0.0"
APP_DEVELOPER = "JohnJayMcKaye"
APP_WEBSITE = "https://github.com/JohnJayMcKaye"
APP_DESCRIPTION = (
    "Erstellt und verwaltet RSS\u00a02.0\u202f+\u202fiTunes/Spotify-kompatible\n"
    "Podcast-Feeds direkt auf dem Desktop.\n\n"
    "Mediendateien werden automatisch erkannt,\n"
    "Shownotes aus dem Blog-RSS-Feed geladen."
)


def show_about_dialog(parent_window):
    """Zeigt den About-Dialog an"""

    # Modernes Adw.AboutDialog (Adwaita >= 1.2)
    try:
        dialog = Adw.AboutDialog()
        dialog.set_application_name("Podcast Feed Generator")
        dialog.set_version(APP_VERSION)
        dialog.set_developer_name(APP_DEVELOPER)
        dialog.set_developers([APP_DEVELOPER])
        dialog.set_copyright(f"\u00a9 2025 {APP_DEVELOPER}")
        dialog.set_license_type(Gtk.License.MIT_X11)
        dialog.set_website(APP_WEBSITE)
        dialog.set_comments(APP_DESCRIPTION)
        dialog.set_application_icon("audio-podcast-symbolic")

        # Logo laden falls vorhanden
        logo_path = _find_logo()
        if logo_path:
            try:
                texture = _load_svg_texture(logo_path)
                if texture:
                    dialog.set_application_icon("audio-podcast-symbolic")
                    # Paintable setzen wenn moeglich
            except Exception:
                pass

        dialog.present(parent_window)

    except AttributeError:
        # Fallback fuer aeltere Adwaita-Versionen: Adw.AboutWindow
        _show_about_window(parent_window)


def _show_about_window(parent_window):
    """Fallback: klassisches About-Fenster"""
    dialog = Adw.AboutWindow(transient_for=parent_window)
    dialog.set_application_name("Podcast Feed Generator")
    dialog.set_version(APP_VERSION)
    dialog.set_developer_name(APP_DEVELOPER)
    dialog.set_developers([APP_DEVELOPER])
    dialog.set_copyright(f"\u00a9 2025 {APP_DEVELOPER}")
    dialog.set_license_type(Gtk.License.MIT_X11)
    dialog.set_website(APP_WEBSITE)
    dialog.set_comments(APP_DESCRIPTION)

    # Logo als Paintable laden
    logo_path = _find_logo()
    if logo_path:
        try:
            paintable = _svg_to_paintable(logo_path, 128)
            if paintable:
                dialog.set_application_icon("audio-podcast-symbolic")
        except Exception:
            pass

    dialog.set_application_icon("audio-podcast-symbolic")
    dialog.present()


def _find_logo():
    """Sucht die logo.svg relativ zur Quelldatei"""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base, "logo.svg")
    return path if os.path.exists(path) else None


def _svg_to_paintable(svg_path, size=128):
    """Laedt SVG als GdkPixbuf.Pixbuf Paintable"""
    try:
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(svg_path, size, size)
        from gi.repository import Gdk
        return Gdk.Texture.new_for_pixbuf(pixbuf)
    except Exception:
        return None


def _load_svg_texture(svg_path):
    try:
        from gi.repository import Gdk, GdkPixbuf
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(svg_path, 128, 128)
        return Gdk.Texture.new_for_pixbuf(pixbuf)
    except Exception:
        return None
