"""
Alle Podcasts – Profile verwalten, wechseln, exportieren/importieren
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Gio
import os, json, shutil
from feed_manager import sanitize_for_gtk

PROFILE_DIR = os.path.expanduser("~/.config/podcast-feed-generator/profiles")


def list_profiles():
    os.makedirs(PROFILE_DIR, exist_ok=True)
    profiles = []
    for name in sorted(os.listdir(PROFILE_DIR)):
        cfg_path = os.path.join(PROFILE_DIR, name, "config.json")
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path) as f:
                    data = json.load(f)
                title = data.get("config", {}).get("title", name)
                ep_count = len(data.get("episodes", []))
                profiles.append({"name": name, "path": cfg_path, "title": title, "episodes": ep_count})
            except Exception:
                pass
    return profiles


def save_current_as_profile(feed_manager, profile_name):
    """Speichert die aktuelle Config als benanntes Profil."""
    safe_name = profile_name.strip().replace("/", "-").replace(" ", "_")
    profile_path = os.path.join(PROFILE_DIR, safe_name)
    os.makedirs(profile_path, exist_ok=True)
    cfg_path = os.path.join(profile_path, "config.json")
    data = {
        "config": feed_manager.config.to_dict(),
        "episodes": [ep.to_dict() for ep in feed_manager.episodes],
    }
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return cfg_path


class PodcastsPage(Gtk.Box):
    def __init__(self, feed_manager, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.fm  = feed_manager
        self.win = window
        self._build()

    def _build(self):
        header = Adw.HeaderBar()
        t = Adw.WindowTitle()
        t.set_title("Alle Podcasts")
        t.set_subtitle("Profile verwalten")
        header.set_title_widget(t)

        # Neu-Button
        new_btn = Gtk.Button(label="Neuer Podcast")
        new_btn.add_css_class("suggested-action")
        new_btn.connect("clicked", self._on_new_podcast)
        header.pack_end(new_btn)

        self.append(header)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        self.box.set_margin_start(32); self.box.set_margin_end(32)
        self.box.set_margin_top(24);   self.box.set_margin_bottom(32)
        scroll.set_child(self.box)
        self.append(scroll)

        # ── Aktiver Podcast speichern ─────────────────────────────────────────
        save_group = Adw.PreferencesGroup()
        save_group.set_title("Aktuellen Podcast als Profil speichern")
        self.box.append(save_group)

        save_row = Adw.ActionRow()
        save_row.set_title("Profil-Name")
        save_row.set_subtitle("Speichert den aktuellen Podcast als benanntes Profil")

        self.profile_name_entry = Gtk.Entry()
        self.profile_name_entry.set_placeholder_text("z.B. DWSK")
        self.profile_name_entry.set_valign(Gtk.Align.CENTER)
        self.profile_name_entry.set_hexpand(True)

        save_btn = Gtk.Button(label="Speichern")
        save_btn.add_css_class("suggested-action")
        save_btn.set_valign(Gtk.Align.CENTER)
        save_btn.connect("clicked", self._on_save_profile)

        save_row.add_suffix(self.profile_name_entry)
        save_row.add_suffix(save_btn)
        save_group.add(save_row)

        # ── Export / Import ───────────────────────────────────────────────────
        io_group = Adw.PreferencesGroup()
        io_group.set_title("Einstellungen exportieren / importieren")
        self.box.append(io_group)

        export_row = Adw.ActionRow()
        export_row.set_title("Einstellungen exportieren")
        export_row.set_subtitle("Config als JSON-Datei speichern")
        export_btn = Gtk.Button(label="Exportieren")
        export_btn.set_valign(Gtk.Align.CENTER)
        export_btn.connect("clicked", self._on_export)
        export_row.add_suffix(export_btn)
        io_group.add(export_row)

        import_row = Adw.ActionRow()
        import_row.set_title("Einstellungen importieren")
        import_row.set_subtitle("Config aus JSON-Datei laden")
        import_btn = Gtk.Button(label="Importieren")
        import_btn.set_valign(Gtk.Align.CENTER)
        import_btn.connect("clicked", self._on_import)
        import_row.add_suffix(import_btn)
        io_group.add(import_row)

        # ── Profil-Liste ──────────────────────────────────────────────────────
        self.profiles_group = Adw.PreferencesGroup()
        self.profiles_group.set_title("Gespeicherte Profile")
        self.box.append(self.profiles_group)

        self.empty_label = Adw.StatusPage()
        self.empty_label.set_icon_name("folder-symbolic")
        self.empty_label.set_title("Keine Profile")
        self.empty_label.set_description(
            "Speichere den aktuellen Podcast als Profil um mehrere Podcasts zu verwalten."
        )
        self.box.append(self.empty_label)

    def refresh(self):
        # Profiles-Gruppe neu aufbauen
        parent = self.profiles_group.get_parent()
        if parent:
            parent.remove(self.profiles_group)
        self.profiles_group = Adw.PreferencesGroup()
        self.profiles_group.set_title("Gespeicherte Profile")
        self.box.append(self.profiles_group)

        profiles = list_profiles()
        self.empty_label.set_visible(len(profiles) == 0)
        self.profiles_group.set_visible(len(profiles) > 0)

        for p in profiles:
            row = Adw.ActionRow()
            row.set_title(sanitize_for_gtk(p["title"]))
            row.set_subtitle(f"{p['episodes']} Folge(n) · {p['name']}")
            row.set_activatable(True)

            load_btn = Gtk.Button(label="Laden")
            load_btn.add_css_class("flat")
            load_btn.set_valign(Gtk.Align.CENTER)
            load_btn.connect("clicked", lambda b, path=p["path"]: self.win.switch_podcast(path))
            row.add_suffix(load_btn)

            del_btn = Gtk.Button()
            del_btn.set_icon_name("user-trash-symbolic")
            del_btn.add_css_class("flat")
            del_btn.add_css_class("destructive-action")
            del_btn.set_valign(Gtk.Align.CENTER)
            del_btn.set_tooltip_text("Profil loeschen")
            del_btn.connect("clicked", lambda b, n=p["name"]: self._on_delete_profile(n))
            row.add_suffix(del_btn)

            self.profiles_group.add(row)

        # Profil-Name-Vorschlag aus aktuellem Podcast
        if self.fm.config.title and not self.profile_name_entry.get_text():
            self.profile_name_entry.set_text(
                self.fm.config.title.replace(" ", "_")[:30]
            )

    def _on_save_profile(self, btn):
        name = self.profile_name_entry.get_text().strip()
        if not name:
            self.win.show_toast("Bitte einen Profil-Namen eingeben")
            return
        if not self.fm.is_configured():
            self.win.show_toast("Kein Podcast konfiguriert")
            return
        try:
            save_current_as_profile(self.fm, name)
            self.win.show_toast(f"Profil '{name}' gespeichert")
            self.refresh()
        except Exception as e:
            self.win.show_toast(f"Fehler: {e}")

    def _on_new_podcast(self, btn):
        """Leeren Feed-Manager erstellen und zu Einstellungen navigieren."""
        from feed_manager import FeedManager
        self.win.feed_manager = FeedManager()  # sauberer neuer FeedManager

        self.win.setup_page.fm        = self.win.feed_manager
        self.win.episodes_page.fm     = self.win.feed_manager
        self.win.add_episodes_page.fm = self.win.feed_manager
        self.win.settings_page.fm     = self.win.feed_manager
        self.fm                       = self.win.feed_manager

        self.win.settings_page._load_values()
        self.win.refresh_status()
        self.win.navigate_to("settings")
        self.win.show_toast("Neuer Podcast – bitte Einstellungen ausfuellen")

    def _on_delete_profile(self, name):
        dialog = Adw.MessageDialog(transient_for=self.win)
        dialog.set_heading(f"Profil '{name}' loeschen?")
        dialog.set_body("Das Profil wird unwiderruflich geloescht. Die Feed-XML-Datei bleibt erhalten.")
        dialog.add_response("cancel", "Abbrechen")
        dialog.add_response("delete", "Loeschen")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")

        def on_response(d, response):
            if response == "delete":
                profile_path = os.path.join(PROFILE_DIR, name)
                try:
                    shutil.rmtree(profile_path)
                    self.win.show_toast(f"Profil '{name}' geloescht")
                    self.refresh()
                except Exception as e:
                    self.win.show_toast(f"Fehler: {e}")

        dialog.connect("response", on_response)
        dialog.present()

    # ── Export / Import ───────────────────────────────────────────────────────

    def _on_export(self, btn):
        dialog = Gtk.FileDialog()
        dialog.set_title("Einstellungen exportieren")
        dialog.set_initial_name("podcast-config.json")
        dialog.save(self.win, None, self._on_export_done)

    def _on_export_done(self, dialog, result):
        try:
            f = dialog.save_finish(result)
            if not f:
                return
            path = f.get_path()
            import json
            data = {
                "config":   self.fm.config.to_dict(),
                "episodes": [ep.to_dict() for ep in self.fm.episodes],
            }
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
            self.win.show_toast(f"Exportiert: {os.path.basename(path)}")
        except Exception as e:
            self.win.show_toast(f"Export-Fehler: {e}")

    def _on_import(self, btn):
        dialog = Gtk.FileDialog()
        dialog.set_title("Einstellungen importieren")
        f = Gtk.FileFilter()
        f.set_name("JSON-Dateien")
        f.add_pattern("*.json")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(f)
        dialog.set_filters(filters)
        dialog.open(self.win, None, self._on_import_done)

    def _on_import_done(self, dialog, result):
        try:
            f = dialog.open_finish(result)
            if not f:
                return
            path = f.get_path()
            import json
            from feed_manager import FeedManager, PodcastConfig, Episode
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)

            self.fm.config   = PodcastConfig.from_dict(data.get("config", {}))
            self.fm.episodes = [Episode.from_dict(e) for e in data.get("episodes", [])]
            self.fm.save_config()

            self.win.settings_page._load_values()
            self.win.setup_page.refresh()
            self.win.refresh_status()
            self.win.show_toast(
                f"Importiert: {self.fm.config.title} ({self.fm.get_episode_count()} Folgen)"
            )
        except Exception as e:
            self.win.show_toast(f"Import-Fehler: {e}")
