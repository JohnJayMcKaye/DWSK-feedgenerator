"""
Podcast-Manager – mehrere Podcasts verwalten + Einstellungen Import/Export
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Gio
import json
import os
import shutil
from feed_manager import sanitize_for_gtk

CONFIG_DIR  = os.path.expanduser("~/.config/podcast-feed-generator")
PROFILE_DIR = os.path.join(CONFIG_DIR, "profiles")


def list_profiles():
    """Gibt alle gespeicherten Podcast-Profile zurück."""
    os.makedirs(PROFILE_DIR, exist_ok=True)
    profiles = []
    for f in sorted(os.listdir(PROFILE_DIR)):
        if f.endswith('.json'):
            path = os.path.join(PROFILE_DIR, f)
            try:
                with open(path) as fh:
                    data = json.load(fh)
                title = data.get('config', {}).get('title', f[:-5])
                profiles.append({'name': f[:-5], 'title': title, 'path': path})
            except Exception:
                pass
    return profiles


def save_profile(name, feed_manager):
    """Speichert den aktuellen FeedManager-Stand als benanntes Profil."""
    os.makedirs(PROFILE_DIR, exist_ok=True)
    path = os.path.join(PROFILE_DIR, f"{name}.json")
    data = {
        'config': feed_manager.config.to_dict(),
        'episodes': [ep.to_dict() for ep in feed_manager.episodes]
    }
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return path


def load_profile(name, feed_manager):
    """Lädt ein Profil in den FeedManager."""
    from feed_manager import PodcastConfig, Episode
    path = os.path.join(PROFILE_DIR, f"{name}.json")
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    feed_manager.config = PodcastConfig.from_dict(data.get('config', {}))
    feed_manager.episodes = [Episode.from_dict(e) for e in data.get('episodes', [])]
    feed_manager.save_config()


class PodcastManagerPage(Gtk.Box):
    def __init__(self, feed_manager, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.fm = feed_manager
        self.win = window
        self._build()

    def _build(self):
        header = Adw.HeaderBar()
        t = Adw.WindowTitle()
        t.set_title("Podcast-Profile")
        t.set_subtitle("Mehrere Podcasts und Import/Export")
        header.set_title_widget(t)
        self.append(header)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        prefs = Adw.PreferencesPage()
        scroll.set_child(prefs)
        self.append(scroll)

        # ── Aktuelles Profil speichern ─────────────────────────────────────────
        save_group = Adw.PreferencesGroup()
        save_group.set_title("Aktuellen Podcast als Profil speichern")
        save_group.set_description(
            "Speichert alle Einstellungen und Episoden als benanntes Profil."
        )
        prefs.add(save_group)

        self.save_name_entry = Adw.EntryRow()
        self.save_name_entry.set_title("Profilname")
        save_group.add(self.save_name_entry)

        save_row = Adw.ActionRow()
        save_row.set_title("Profil speichern")
        save_row.set_subtitle("Legt ein neues Profil an oder ueberschreibt ein bestehendes")
        save_btn = Gtk.Button(label="Speichern")
        save_btn.add_css_class('suggested-action')
        save_btn.set_valign(Gtk.Align.CENTER)
        save_btn.connect('clicked', self._on_save_profile)
        save_row.add_suffix(save_btn)
        save_group.add(save_row)

        # ── Gespeicherte Profile ───────────────────────────────────────────────
        self.profiles_group = Adw.PreferencesGroup()
        self.profiles_group.set_title("Gespeicherte Profile")
        prefs.add(self.profiles_group)

        # ── Import / Export ────────────────────────────────────────────────────
        ie_group = Adw.PreferencesGroup()
        ie_group.set_title("Einstellungen importieren / exportieren")
        ie_group.set_description(
            "Sichert alle Profile als ZIP oder stellt sie wieder her."
        )
        prefs.add(ie_group)

        export_row = Adw.ActionRow()
        export_row.set_title("Alle Profile exportieren")
        export_row.set_subtitle("Speichert alle Profile als .json Datei")
        export_btn = Gtk.Button(label="Exportieren")
        export_btn.set_valign(Gtk.Align.CENTER)
        export_btn.connect('clicked', self._on_export)
        export_row.add_suffix(export_btn)
        ie_group.add(export_row)

        import_row = Adw.ActionRow()
        import_row.set_title("Profil importieren")
        import_row.set_subtitle("Laedt eine exportierte .json Profildatei")
        import_btn = Gtk.Button(label="Importieren")
        import_btn.set_valign(Gtk.Align.CENTER)
        import_btn.connect('clicked', self._on_import)
        import_row.add_suffix(import_btn)
        ie_group.add(import_row)

        # ── Aktuellen Podcast-Config exportieren ──────────────────────────────
        cfg_group = Adw.PreferencesGroup()
        cfg_group.set_title("Nur Einstellungen (ohne Episoden)")
        prefs.add(cfg_group)

        cfg_export_row = Adw.ActionRow()
        cfg_export_row.set_title("Konfiguration exportieren")
        cfg_export_row.set_subtitle("Nur Podcast-Einstellungen, keine Episodenliste")
        cfg_exp_btn = Gtk.Button(label="Exportieren")
        cfg_exp_btn.set_valign(Gtk.Align.CENTER)
        cfg_exp_btn.connect('clicked', self._on_export_config_only)
        cfg_export_row.add_suffix(cfg_exp_btn)
        cfg_group.add(cfg_export_row)

        cfg_import_row = Adw.ActionRow()
        cfg_import_row.set_title("Konfiguration importieren")
        cfg_import_row.set_subtitle("Ueberschreibt aktuelle Einstellungen")
        cfg_imp_btn = Gtk.Button(label="Importieren")
        cfg_imp_btn.set_valign(Gtk.Align.CENTER)
        cfg_imp_btn.connect('clicked', self._on_import_config_only)
        cfg_import_row.add_suffix(cfg_imp_btn)
        cfg_group.add(cfg_import_row)

        self._refresh_profiles()

    def refresh(self):
        cfg = self.fm.config
        if cfg.title:
            # Profilname-Vorschlag aus Podcast-Titel
            safe = cfg.title.replace(' ', '_').replace('/', '-')[:30]
            self.save_name_entry.set_text(safe)
        self._refresh_profiles()

    def _refresh_profiles(self):
        """Baut die Profilliste neu auf."""
        # Gruppe leeren durch Neuerstellen
        parent = self.profiles_group.get_parent()
        if parent:
            self.profiles_group.set_visible(False)
            parent.remove(self.profiles_group)

        self.profiles_group = Adw.PreferencesGroup()
        self.profiles_group.set_title("Gespeicherte Profile")

        profiles = list_profiles()
        if not profiles:
            empty_row = Adw.ActionRow()
            empty_row.set_title("Noch keine Profile gespeichert")
            empty_row.add_css_class('dim-label')
            self.profiles_group.add(empty_row)
        else:
            for p in profiles:
                row = Adw.ActionRow()
                row.set_title(sanitize_for_gtk(p['title']))
                row.set_subtitle(p['name'])
                row.set_activatable(True)

                # Laden-Button
                load_btn = Gtk.Button(label="Laden")
                load_btn.add_css_class('flat')
                load_btn.set_valign(Gtk.Align.CENTER)
                load_btn.connect('clicked', lambda b, n=p['name']: self._on_load_profile(n))
                row.add_suffix(load_btn)

                # Loeschen-Button
                del_btn = Gtk.Button()
                del_btn.set_icon_name('user-trash-symbolic')
                del_btn.add_css_class('flat')
                del_btn.add_css_class('destructive-action')
                del_btn.set_valign(Gtk.Align.CENTER)
                del_btn.connect('clicked', lambda b, n=p['name']: self._on_delete_profile(n))
                row.add_suffix(del_btn)

                self.profiles_group.add(row)

        # Neu anhängen (vor dem ie_group, also einfach ans Ende)
        content = self.get_parent()
        scroll = self.get_first_child().get_next_sibling()  # nach HeaderBar
        if scroll:
            prefs = scroll.get_child()
            if prefs:
                prefs.add(self.profiles_group)

    def _on_save_profile(self, btn):
        name = self.save_name_entry.get_text().strip()
        if not name:
            self.win.show_toast("Bitte einen Profilnamen eingeben")
            return
        if not self.fm.is_configured():
            self.win.show_toast("Kein Podcast konfiguriert")
            return
        # Ungültige Zeichen entfernen
        import re
        name = re.sub(r'[^\w\-_]', '_', name)
        try:
            save_profile(name, self.fm)
            self.win.show_toast(f"Profil '{name}' gespeichert")
            self._refresh_profiles()
        except Exception as e:
            self.win.show_toast(f"Fehler: {e}")

    def _on_load_profile(self, name):
        dialog = Adw.MessageDialog(transient_for=self.win)
        dialog.set_heading(f"Profil '{name}' laden?")
        dialog.set_body("Der aktuelle Podcast wird ersetzt. Nicht gespeicherte Aenderungen gehen verloren.")
        dialog.add_response("cancel", "Abbrechen")
        dialog.add_response("load", "Laden")
        dialog.set_response_appearance("load", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("cancel")

        def on_response(d, response):
            if response == "load":
                try:
                    load_profile(name, self.fm)
                    self.win.refresh_status()
                    self.win.show_toast(f"Profil '{name}' geladen")
                    self.win.navigate_to('overview')
                except Exception as e:
                    self.win.show_toast(f"Fehler: {e}")

        dialog.connect('response', on_response)
        dialog.present()

    def _on_delete_profile(self, name):
        dialog = Adw.MessageDialog(transient_for=self.win)
        dialog.set_heading(f"Profil '{name}' loeschen?")
        dialog.set_body("Das Profil wird dauerhaft entfernt.")
        dialog.add_response("cancel", "Abbrechen")
        dialog.add_response("delete", "Loeschen")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")

        def on_response(d, response):
            if response == "delete":
                path = os.path.join(PROFILE_DIR, f"{name}.json")
                try:
                    os.remove(path)
                    self.win.show_toast(f"Profil '{name}' geloescht")
                    self._refresh_profiles()
                except Exception as e:
                    self.win.show_toast(f"Fehler: {e}")

        dialog.connect('response', on_response)
        dialog.present()

    # ── Export / Import ────────────────────────────────────────────────────────

    def _on_export(self, btn):
        """Exportiert alle Profile als JSON-Datei."""
        profiles = list_profiles()
        if not profiles:
            self.win.show_toast("Keine Profile zum Exportieren")
            return

        all_data = {}
        for p in profiles:
            with open(p['path'], encoding='utf-8') as f:
                all_data[p['name']] = json.load(f)

        dialog = Gtk.FileDialog()
        dialog.set_title("Profile exportieren")
        dialog.set_initial_name("podcast-profile.json")
        dialog.save(self.win, None, lambda d, r: self._save_export(d, r, all_data))

    def _save_export(self, dialog, result, data):
        try:
            f = dialog.save_finish(result)
            if f:
                with open(f.get_path(), 'w', encoding='utf-8') as fh:
                    json.dump(data, fh, indent=2, ensure_ascii=False)
                self.win.show_toast(f"Profile exportiert: {f.get_path()}")
        except Exception as e:
            self.win.show_toast(f"Export fehlgeschlagen: {e}")

    def _on_import(self, btn):
        """Importiert Profile aus einer JSON-Datei."""
        dialog = Gtk.FileDialog()
        dialog.set_title("Profile importieren")
        dialog.open(self.win, None, self._load_import)

    def _load_import(self, dialog, result):
        try:
            f = dialog.open_finish(result)
            if not f:
                return
            with open(f.get_path(), encoding='utf-8') as fh:
                data = json.load(fh)

            count = 0
            for name, profile_data in data.items():
                import re
                safe_name = re.sub(r'[^\w\-_]', '_', name)
                path = os.path.join(PROFILE_DIR, f"{safe_name}.json")
                os.makedirs(PROFILE_DIR, exist_ok=True)
                with open(path, 'w', encoding='utf-8') as fh:
                    json.dump(profile_data, fh, indent=2, ensure_ascii=False)
                count += 1

            self.win.show_toast(f"{count} Profil(e) importiert")
            self._refresh_profiles()
        except Exception as e:
            self.win.show_toast(f"Import fehlgeschlagen: {e}")

    def _on_export_config_only(self, btn):
        """Exportiert nur die Podcast-Konfiguration ohne Episoden."""
        if not self.fm.is_configured():
            self.win.show_toast("Kein Podcast konfiguriert")
            return
        data = {'config': self.fm.config.to_dict()}
        dialog = Gtk.FileDialog()
        dialog.set_title("Konfiguration exportieren")
        dialog.set_initial_name("podcast-config.json")
        dialog.save(self.win, None, lambda d, r: self._save_export(d, r, data))

    def _on_import_config_only(self, btn):
        """Importiert nur Konfiguration, behält Episoden."""
        dialog = Gtk.FileDialog()
        dialog.set_title("Konfiguration importieren")
        dialog.open(self.win, None, self._load_config_import)

    def _load_config_import(self, dialog, result):
        try:
            f = dialog.open_finish(result)
            if not f:
                return
            with open(f.get_path(), encoding='utf-8') as fh:
                data = json.load(fh)

            from feed_manager import PodcastConfig
            # Unterstützt sowohl vollständige Profile als auch reine Configs
            cfg_data = data.get('config', data)
            self.fm.config = PodcastConfig.from_dict(cfg_data)
            self.fm.save_config()
            self.win.refresh_status()
            self.win.show_toast("Konfiguration importiert")
        except Exception as e:
            self.win.show_toast(f"Import fehlgeschlagen: {e}")
