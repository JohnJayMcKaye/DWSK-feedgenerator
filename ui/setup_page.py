"""
Setup/Übersichtsseite - Ersteinrichtung und Podcast-Übersicht
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib


class SetupPage(Gtk.Box):
    def __init__(self, feed_manager, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.fm = feed_manager
        self.win = window
        self._build()

    def _build(self):
        # Header
        header = Adw.HeaderBar()
        title = Adw.WindowTitle()
        title.set_title("Mein Podcast")
        title.set_subtitle("Ubersicht und Feed verwalten")
        header.set_title_widget(title)

        # Feed exportieren Button
        export_btn = Gtk.Button(label="Feed exportieren")
        export_btn.add_css_class('suggested-action')
        export_btn.connect('clicked', self._on_export)
        header.pack_end(export_btn)

        self.append(header)

        # Scrollbarer Inhalt
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        content.set_margin_start(32)
        content.set_margin_end(32)
        content.set_margin_top(24)
        content.set_margin_bottom(32)

        scroll.set_child(content)
        self.append(scroll)

        # ── Status-Banner (wenn nicht konfiguriert) ──
        self.setup_banner = Adw.Banner()
        self.setup_banner.set_title("Podcast noch nicht eingerichtet – jetzt konfigurieren!")
        self.setup_banner.set_button_label("Einrichten")
        self.setup_banner.connect('button-clicked', lambda b: self.win.navigate_to('settings'))
        content.append(self.setup_banner)

        # ── Podcast-Info-Karte ──
        info_group = Adw.PreferencesGroup()
        info_group.set_title("Podcast-Informationen")

        self.title_row = Adw.ActionRow()
        self.title_row.set_title("Titel")
        self.title_row.set_subtitle("–")
        info_group.add(self.title_row)

        self.url_row = Adw.ActionRow()
        self.url_row.set_title("Website")
        self.url_row.set_subtitle("–")
        info_group.add(self.url_row)

        self.media_row = Adw.ActionRow()
        self.media_row.set_title("Medienordner")
        self.media_row.set_subtitle("–")
        info_group.add(self.media_row)

        self.feed_row = Adw.ActionRow()
        self.feed_row.set_title("Feed-Datei")
        self.feed_row.set_subtitle("–")
        info_group.add(self.feed_row)

        content.append(info_group)

        # ── Statistiken ──
        stats_group = Adw.PreferencesGroup()
        stats_group.set_title("Feed-Statistik")

        self.ep_count_row = Adw.ActionRow()
        self.ep_count_row.set_title("Folgen im Feed")
        self.ep_count_row.set_subtitle("0")
        stats_group.add(self.ep_count_row)

        self.ep_numbers_row = Adw.ActionRow()
        self.ep_numbers_row.set_title("Episodennummern")
        self.ep_numbers_row.set_subtitle("–")
        self.ep_numbers_row.set_subtitle_lines(2)
        stats_group.add(self.ep_numbers_row)

        content.append(stats_group)

        # ── Schnellzugriff ──
        actions_group = Adw.PreferencesGroup()
        actions_group.set_title("Schnellzugriff")

        add_row = Adw.ActionRow()
        add_row.set_title("Neue Folgen hinzufügen")
        add_row.set_subtitle("Mediendateien scannen und Feed erweitern")
        add_row.set_activatable(True)
        add_row.connect('activated', lambda r: self.win.navigate_to('add_episodes'))
        arrow1 = Gtk.Image.new_from_icon_name('go-next-symbolic')
        add_row.add_suffix(arrow1)
        actions_group.add(add_row)

        settings_row = Adw.ActionRow()
        settings_row.set_title("Podcast-Einstellungen")
        settings_row.set_subtitle("Titel, Beschreibung, URLs anpassen")
        settings_row.set_activatable(True)
        settings_row.connect('activated', lambda r: self.win.navigate_to('settings'))
        arrow2 = Gtk.Image.new_from_icon_name('go-next-symbolic')
        settings_row.add_suffix(arrow2)
        actions_group.add(settings_row)

        content.append(actions_group)

    def refresh(self):
        fm = self.fm
        configured = fm.is_configured()

        self.setup_banner.set_revealed(not configured)

        cfg = fm.config
        self.title_row.set_subtitle(cfg.title or "–")
        self.url_row.set_subtitle(cfg.base_url or "–")
        self.media_row.set_subtitle(cfg.media_base_path or "–")

        import os
        feed_path = os.path.join(cfg.output_directory or "~", cfg.feed_filename or "podcast.xml")
        self.feed_row.set_subtitle(feed_path)

        count = fm.get_episode_count()
        self.ep_count_row.set_subtitle(str(count))

        numbers = fm.get_episode_numbers()
        if numbers:
            nums_str = ", ".join(str(n) for n in numbers[-20:])
            if len(numbers) > 20:
                nums_str = "… " + nums_str
            self.ep_numbers_row.set_subtitle(nums_str)
        else:
            self.ep_numbers_row.set_subtitle("Noch keine Folgen")

    def _on_export(self, btn):
        if not self.fm.is_configured():
            self.win.show_toast("❌ Bitte erst den Podcast konfigurieren")
            return
        if self.fm.get_episode_count() == 0:
            self.win.show_toast("❌ Keine Episoden im Feed")
            return

        try:
            path = self.fm.save_feed()
            self.fm.save_config()
            self.win.show_toast(f"✅ Feed gespeichert: {path}")
        except Exception as e:
            self.win.show_toast(f"❌ Fehler: {e}")
