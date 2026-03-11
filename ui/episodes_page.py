"""
Episodenliste - Alle Episoden im Feed anzeigen und bearbeiten
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib
from feed_manager import sanitize_for_gtk


class EpisodesPage(Gtk.Box):
    def __init__(self, feed_manager, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.fm = feed_manager
        self.win = window
        self._build()

    def _build(self):
        header = Adw.HeaderBar()
        title = Adw.WindowTitle()
        title.set_title("Episodenliste")
        title.set_subtitle("Alle Folgen im Feed")
        header.set_title_widget(title)
        self.append(header)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.content_box.set_margin_start(32)
        self.content_box.set_margin_end(32)
        self.content_box.set_margin_top(24)
        self.content_box.set_margin_bottom(32)

        scroll.set_child(self.content_box)
        self.append(scroll)

        # Platzhalter
        self.empty_page = Adw.StatusPage()
        self.empty_page.set_icon_name('audio-podcast-symbolic')
        self.empty_page.set_title("Noch keine Folgen")
        self.empty_page.set_description("Füge Folgen über \"Folgen hinzufügen\" zum Feed hinzu.")
        add_btn = Gtk.Button(label="Folgen hinzufügen")
        add_btn.add_css_class('suggested-action')
        add_btn.add_css_class('pill')
        add_btn.connect('clicked', lambda b: self.win.navigate_to('add_episodes'))
        self.empty_page.set_child(add_btn)

        self.episodes_group = Adw.PreferencesGroup()
        self.episodes_group.set_title("Folgen")

        self.content_box.append(self.empty_page)
        self.content_box.append(self.episodes_group)

    def refresh(self):
        episodes = sorted(self.fm.episodes, key=lambda e: e.number, reverse=True)
        has_episodes = len(episodes) > 0

        self.empty_page.set_visible(not has_episodes)
        self.episodes_group.set_visible(has_episodes)

        # Alte Zeilen entfernen
        while True:
            child = self.episodes_group.get_first_child()
            if child is None:
                break
            # PreferencesGroup children are not directly removable this way
            break

        # Neu aufbauen mit neuer Gruppe
        parent = self.episodes_group.get_parent()
        if parent:
            idx = 0
            for i, child in enumerate(list(self._iter_children(self.content_box))):
                if child == self.episodes_group:
                    idx = i
                    break
            self.content_box.remove(self.episodes_group)

        self.episodes_group = Adw.PreferencesGroup()
        self.episodes_group.set_title(f"Folgen ({len(episodes)} gesamt)")
        self.episodes_group.set_visible(has_episodes)
        self.content_box.append(self.episodes_group)

        for ep in episodes:
            row = Adw.ExpanderRow()
            row.set_title(sanitize_for_gtk(f"Folge {ep.number}: {ep.title or '(kein Titel)'}"))
            row.set_subtitle(ep.pub_date or "")

            def make_detail_row(label, value):
                r = Adw.ActionRow()
                r.set_title(label)
                r.set_subtitle(sanitize_for_gtk(str(value)) if value else "–")
                r.set_subtitle_lines(3)
                return r

            row.add_row(make_detail_row("🔗 Shownotes-URL", ep.shownotes_url))
            row.add_row(make_detail_row("🎵 Datei", ep.file_path))
            row.add_row(make_detail_row("🌐 Datei-URL", ep.file_url))
            row.add_row(make_detail_row("⏱️ Dauer", ep.duration))
            row.add_row(make_detail_row("📦 Größe", f"{ep.file_size // 1024 // 1024} MB" if ep.file_size else "–"))

            # Löschen-Button
            del_btn = Gtk.Button()
            del_btn.set_icon_name('user-trash-symbolic')
            del_btn.add_css_class('flat')
            del_btn.add_css_class('destructive-action')
            del_btn.set_valign(Gtk.Align.CENTER)
            del_btn.set_tooltip_text("Folge aus Feed entfernen")
            ep_num = ep.number
            del_btn.connect('clicked', lambda b, n=ep_num: self._delete_episode(n))
            row.add_action(del_btn)

            self.episodes_group.add(row)

    def _iter_children(self, box):
        child = box.get_first_child()
        while child:
            yield child
            child = child.get_next_sibling()

    def _delete_episode(self, ep_num):
        dialog = Adw.MessageDialog(transient_for=self.win)
        dialog.set_heading(f"Folge {ep_num} entfernen?")
        dialog.set_body("Die Episode wird aus dem Feed gelöscht. Die Mediendatei bleibt erhalten.")
        dialog.add_response("cancel", "Abbrechen")
        dialog.add_response("delete", "Entfernen")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")

        def on_response(d, response):
            if response == "delete":
                self.fm.episodes = [ep for ep in self.fm.episodes if ep.number != ep_num]
                self.fm.save_config()
                self.win.refresh_status()
                self.win.show_toast(f"🗑️ Folge {ep_num} entfernt")
                self.refresh()

        dialog.connect('response', on_response)
        dialog.present()
