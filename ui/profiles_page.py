"""
Profil-Verwaltung – Mehrere Podcasts, Export/Import
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib
import os
import re
import threading
import profile_manager as pm


class ProfilesPage(Gtk.Box):
    def __init__(self, feed_manager, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.fm = feed_manager
        self.win = window
        self._build()

    def _build(self):
        header = Adw.HeaderBar()
        t = Adw.WindowTitle()
        t.set_title("Podcast-Profile")
        t.set_subtitle("Mehrere Podcasts verwalten")
        header.set_title_widget(t)

        new_btn = Gtk.Button(label="Neues Profil")
        new_btn.add_css_class('suggested-action')
        new_btn.connect('clicked', self._on_new_profile)
        header.pack_end(new_btn)
        self.append(header)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        self.content.set_margin_start(32)
        self.content.set_margin_end(32)
        self.content.set_margin_top(24)
        self.content.set_margin_bottom(32)
        scroll.set_child(self.content)
        self.append(scroll)

        # Profile-Liste
        self.profiles_group = Adw.PreferencesGroup()
        self.profiles_group.set_title("Vorhandene Profile")
        self.content.append(self.profiles_group)

        # Import/Export
        io_group = Adw.PreferencesGroup()
        io_group.set_title("Export / Import")
        io_group.set_description(
            "Profile als JSON-Datei sichern oder auf einem anderen Rechner wiederherstellen"
        )
        self.content.append(io_group)

        export_row = Adw.ActionRow()
        export_row.set_title("Aktives Profil exportieren")
        export_row.set_subtitle("Speichert Einstellungen und Episodenliste als .json")
        export_btn = Gtk.Button(label="Exportieren")
        export_btn.set_valign(Gtk.Align.CENTER)
        export_btn.connect('clicked', self._on_export)
        export_row.add_suffix(export_btn)
        io_group.add(export_row)

        import_row = Adw.ActionRow()
        import_row.set_title("Profil importieren")
        import_row.set_subtitle("Laedt eine zuvor exportierte .json Datei")
        import_btn = Gtk.Button(label="Importieren")
        import_btn.set_valign(Gtk.Align.CENTER)
        import_btn.connect('clicked', self._on_import)
        import_row.add_suffix(import_btn)
        io_group.add(import_row)

    def refresh(self):
        # Alte Eintraege leeren
        old = self.profiles_group
        new_group = Adw.PreferencesGroup()
        new_group.set_title("Vorhandene Profile")

        parent = old.get_parent()
        if parent:
            parent.remove(old)
            self.content.prepend(new_group)
        self.profiles_group = new_group

        active_id = pm.get_active_profile_id()
        profiles = pm.list_profiles()

        if not profiles:
            row = Adw.ActionRow()
            row.set_title("Keine Profile gefunden")
            row.set_subtitle("Erstelle ein neues Profil oder migriere die bestehende Konfiguration")
            new_group.add(row)
            return

        for p in profiles:
            is_active = p['id'] == active_id
            row = Adw.ActionRow()

            title = p['title'] or p['id']
            if is_active:
                row.set_title(f"[Aktiv] {title}")
            else:
                row.set_title(title)
            row.set_subtitle(f"{p['episode_count']} Folge(n) · zuletzt: {p['modified']}")

            btn_box = Gtk.Box(spacing=8)
            btn_box.set_valign(Gtk.Align.CENTER)

            if not is_active:
                switch_btn = Gtk.Button(label="Wechseln")
                switch_btn.add_css_class('flat')
                switch_btn.connect('clicked', lambda b, pid=p['id']: self._on_switch(pid))
                btn_box.append(switch_btn)

            del_btn = Gtk.Button()
            del_btn.set_icon_name('user-trash-symbolic')
            del_btn.add_css_class('flat')
            if is_active:
                del_btn.set_sensitive(False)
                del_btn.set_tooltip_text("Aktives Profil kann nicht geloescht werden")
            else:
                del_btn.add_css_class('destructive-action')
                del_btn.connect('clicked', lambda b, pid=p['id']: self._on_delete(pid))

            btn_box.append(del_btn)
            row.add_suffix(btn_box)
            new_group.add(row)

    # ─── Aktionen ─────────────────────────────────────────────────────────────

    def _on_new_profile(self, btn):
        dialog = Adw.MessageDialog(transient_for=self.win)
        dialog.set_heading("Neues Podcast-Profil")
        dialog.set_body("Gib einen Namen fuer den neuen Podcast ein:")

        entry = Gtk.Entry()
        entry.set_placeholder_text("z.B. Mein zweiter Podcast")
        entry.set_margin_top(8)
        dialog.set_extra_child(entry)

        dialog.add_response("cancel", "Abbrechen")
        dialog.add_response("create", "Erstellen")
        dialog.set_response_appearance("create", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("create")

        def on_response(d, resp):
            if resp == "create":
                name = entry.get_text().strip()
                if not name:
                    name = "Neuer Podcast"
                profile_id = re.sub(r'[^a-zA-Z0-9_-]', '_', name.lower())[:32]
                profile_id = pm._unique_profile_id(profile_id)
                pm.create_profile(profile_id, name)
                self._switch_to_profile(profile_id)

        dialog.connect('response', on_response)
        dialog.present()

    def _on_switch(self, profile_id):
        self._switch_to_profile(profile_id)

    def _switch_to_profile(self, profile_id):
        # Aktuelles Profil speichern
        try:
            self.fm.save_config()
        except Exception:
            pass

        pm.set_active_profile(profile_id)

        # FeedManager neu laden
        self.fm.__init__()
        self.win.refresh_status()
        self.win.show_toast(f"Profil gewechselt")
        self.refresh()

        # Zur Uebersicht navigieren
        self.win.navigate_to('overview')

    def _on_delete(self, profile_id):
        dialog = Adw.MessageDialog(transient_for=self.win)
        dialog.set_heading("Profil loeschen?")
        dialog.set_body(f"Das Profil '{profile_id}' wird dauerhaft geloescht.\nDie Mediendateien bleiben erhalten.")
        dialog.add_response("cancel", "Abbrechen")
        dialog.add_response("delete", "Loeschen")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)

        def on_response(d, resp):
            if resp == "delete":
                try:
                    pm.delete_profile(profile_id)
                    self.win.show_toast(f"Profil geloescht")
                    self.refresh()
                except Exception as e:
                    self.win.show_toast(f"Fehler: {e}")

        dialog.connect('response', on_response)
        dialog.present()

    def _on_export(self, btn):
        active_id = pm.get_active_profile_id()
        dialog = Gtk.FileDialog()
        dialog.set_title("Profil exportieren")
        dialog.set_initial_name(f"{active_id}_backup.json")
        dialog.save(self.win, None, lambda d, r: self._do_export(d, r, active_id))

    def _do_export(self, dialog, result, profile_id):
        try:
            f = dialog.save_finish(result)
            if f:
                path = f.get_path()
                pm.export_profile(profile_id, path)
                self.win.show_toast(f"Exportiert nach: {os.path.basename(path)}")
        except Exception as e:
            if 'dismiss' not in str(e).lower():
                self.win.show_toast(f"Export-Fehler: {e}")

    def _on_import(self, btn):
        dialog = Gtk.FileDialog()
        dialog.set_title("Profil importieren")
        dialog.open(self.win, None, self._do_import)

    def _do_import(self, dialog, result):
        try:
            f = dialog.open_finish(result)
            if f:
                path = f.get_path()
                new_id = pm.import_profile(path)
                self.win.show_toast(f"Profil importiert als '{new_id}'")
                self.refresh()
        except Exception as e:
            if 'dismiss' not in str(e).lower():
                self.win.show_toast(f"Import-Fehler: {e}")
