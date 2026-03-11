#!/usr/bin/env python3
"""
Podcast Feed Generator
GTK4 + Adwaita Desktop App für Fedora/GNOME
Erzeugt und erweitert RSS 2.0 + iTunes-kompatible Podcast-Feeds
"""

import sys
import os

# GTK4 + Adwaita
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Gio, GObject

from feed_manager import FeedManager
from ui.main_window import MainWindow


class PodcastFeedApp(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id='de.podcast.feedgenerator',
            flags=Gio.ApplicationFlags.FLAGS_NONE
        )
        self.connect('activate', self.on_activate)

    def on_activate(self, app):
        self.win = MainWindow(application=app)
        self.win.present()


def main():
    app = PodcastFeedApp()
    return app.run(sys.argv)


if __name__ == '__main__':
    sys.exit(main())
