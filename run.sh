#!/bin/bash
# Podcast Feed Generator – Startskript für Fedora/GNOME
# Stellt sicher, dass alle Abhängigkeiten installiert sind

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🎙️ Podcast Feed Generator"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━"

# Prüfe Python
if ! command -v python3 &>/dev/null; then
    echo "❌ Python3 nicht gefunden. Bitte installieren:"
    echo "   sudo dnf install python3"
    exit 1
fi

# Prüfe GTK4/Adwaita Python-Bindings
python3 -c "
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw
print('✅ GTK4 + Adwaita OK')
" 2>/dev/null || {
    echo "❌ GTK4/Adwaita Python-Bindings fehlen. Bitte installieren:"
    echo "   sudo dnf install python3-gobject gtk4 libadwaita"
    exit 1
}

echo "✅ Alle Abhängigkeiten vorhanden"
echo "🚀 Starte Anwendung..."

cd "$SCRIPT_DIR"
python3 main.py "$@"
