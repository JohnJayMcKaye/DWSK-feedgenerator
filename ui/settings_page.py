"""
Einstellungsseite - Alle Podcast-Konfigurationsoptionen
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Gio
import os


class SettingsPage(Gtk.Box):
    def __init__(self, feed_manager, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.fm = feed_manager
        self.win = window
        self._build()
        self._load_values()

    def _build(self):
        header = Adw.HeaderBar()
        title = Adw.WindowTitle()
        title.set_title("Einstellungen")
        title.set_subtitle("Podcast-Konfiguration")
        header.set_title_widget(title)

        save_btn = Gtk.Button(label="Speichern")
        save_btn.add_css_class('suggested-action')
        save_btn.connect('clicked', self._on_save)
        header.pack_end(save_btn)
        self.append(header)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        prefs = Adw.PreferencesPage()
        scroll.set_child(prefs)
        self.append(scroll)

        # ── Podcast-Grundinfo ──────────────────────────────────────────────────
        basic = Adw.PreferencesGroup()
        basic.set_title("Podcast-Informationen")
        basic.set_description("Grundlegende Angaben (erscheinen im Feed)")
        prefs.add(basic)

        self.title_entry    = self._entry("Podcast-Titel *",       basic)
        self.desc_entry     = self._entry("Beschreibung *",        basic)
        self.author_entry   = self._entry("Autor / Podcast-Name",  basic)
        self.email_entry    = self._entry("E-Mail (iTunes)",       basic)
        self.language_entry = self._entry("Sprache (de, en ...)",  basic)
        self.image_entry    = self._entry("Cover-Bild URL",        basic)

        explicit_row = Adw.ComboRow()
        explicit_row.set_title("Expliziter Inhalt")
        explicit_row.set_model(Gtk.StringList.new(["no (false)", "yes (true)"]))
        self.explicit_combo = explicit_row
        basic.add(explicit_row)

        # ── Kategorie ─────────────────────────────────────────────────────────
        cat = Adw.PreferencesGroup()
        cat.set_title("iTunes-Kategorie")
        prefs.add(cat)
        self.category_entry    = self._entry("Hauptkategorie",  cat)
        self.subcategory_entry = self._entry("Unterkategorie",  cat)

        # ── URLs und Pfade ─────────────────────────────────────────────────────
        url_group = Adw.PreferencesGroup()
        url_group.set_title("URLs und Pfade")
        url_group.set_description("Basis-URLs und lokale Speicherorte")
        prefs.add(url_group)

        self.base_url_entry       = self._entry("Webseiten-URL *",       url_group)
        self.media_url_path_entry = self._entry("Medien-URL-Pfad",       url_group)
        self.feed_filename_entry  = self._entry("Feed-Dateiname",        url_group)

        # Medienordner
        self.media_path_label, _ = self._folder_row(
            "Lokaler Medienordner *", "Ordner mit den MP3-Dateien",
            url_group, self._on_choose_media_folder
        )
        # Ausgabeordner
        self.output_path_label, _ = self._folder_row(
            "Feed-Ausgabeordner", "Wo die podcast.xml gespeichert wird",
            url_group, self._on_choose_output_folder
        )

        # ── Dateinamen-Schema ──────────────────────────────────────────────────
        file_group = Adw.PreferencesGroup()
        file_group.set_title("Dateinamen-Schema")
        file_group.set_description("Praefix der MP3-Dateien vor der Episodennummer")
        prefs.add(file_group)

        self.file_prefix_entry = self._entry("Datei-Praefix", file_group)

        preview_row = Adw.ActionRow()
        preview_row.set_title("Erkennungs-Vorschau")
        self.preview_label = Gtk.Label(label="DWSK-Folge42.mp3 -> Folge 42")
        self.preview_label.add_css_class('caption')
        self.preview_label.add_css_class('dim-label')
        preview_row.add_suffix(self.preview_label)
        file_group.add(preview_row)
        self.file_prefix_entry.connect('changed', self._update_preview)

        # ── Blog/Shownotes-Quellen ─────────────────────────────────────────────
        blog_group = Adw.PreferencesGroup()
        blog_group.set_title("Shownotes-Quelle (RSS/XML)")
        blog_group.set_description(
            "Blog-RSS/Atom-Feed fuer automatische Shownotes – online oder lokal"
        )
        prefs.add(blog_group)

        # Online / Lokal Umschalter
        source_row = Adw.ActionRow()
        source_row.set_title("Quelle")
        source_row.set_subtitle("Online-URL oder lokale XML-Datei")

        self.source_toggle = Gtk.ToggleButton(label="Online")
        self.source_toggle_local = Gtk.ToggleButton(label="Lokal")
        self.source_toggle_local.set_group(self.source_toggle)

        toggle_box = Gtk.Box(spacing=4)
        toggle_box.set_valign(Gtk.Align.CENTER)
        toggle_box.append(self.source_toggle)
        toggle_box.append(self.source_toggle_local)
        source_row.add_suffix(toggle_box)
        blog_group.add(source_row)

        self.blog_rss_entry = self._entry("Online RSS/Atom URL", blog_group)

        # Lokale XML-Datei
        self.local_xml_label, self.local_xml_row = self._file_row(
            "Lokale XML-Datei", "Lokale RSS/Atom .xml Datei",
            blog_group, self._on_choose_local_xml,
            filters=[("XML-Dateien", "*.xml"), ("Alle Dateien", "*")]
        )

        self.source_toggle.connect('toggled', self._on_source_toggled)
        self.source_toggle_local.connect('toggled', self._on_source_toggled)

        # ── Markdown-Shownotes ─────────────────────────────────────────────────
        md_group = Adw.PreferencesGroup()
        md_group.set_title("Shownotes als Markdown (Hugo)")
        md_group.set_description(
            "Ordner mit Markdown-Dateien (42.md) – Hugo TOML/YAML Frontmatter wird automatisch gelesen"
        )
        prefs.add(md_group)

        self.markdown_path_label, _ = self._folder_row(
            "Markdown-Ordner", "Ordner mit den .md Shownotes-Dateien",
            md_group, self._on_choose_markdown_folder
        )

        md_info_row = Adw.ActionRow()
        md_info_row.set_title("Erwartetes Format")
        md_info_row.set_subtitle("42.md mit +++ title = ... +++ Frontmatter")
        md_info_row.add_css_class('dim-label')
        md_group.add(md_info_row)

    # ─── Hilfsfunktionen ──────────────────────────────────────────────────────

    def _entry(self, title, group):
        row = Adw.EntryRow()
        row.set_title(title)
        group.add(row)
        return row

    def _folder_row(self, title, subtitle, group, callback):
        row = Adw.ActionRow()
        row.set_title(title)
        row.set_subtitle(subtitle)

        label = Gtk.Label(label="Nicht ausgewaehlt")
        label.add_css_class('caption')
        label.add_css_class('dim-label')
        label.set_ellipsize(3)
        label.set_max_width_chars(28)

        btn = Gtk.Button(label="Auswaehlen...")
        btn.add_css_class('flat')
        btn.set_valign(Gtk.Align.CENTER)
        btn.connect('clicked', callback)

        row.add_suffix(label)
        row.add_suffix(btn)
        group.add(row)
        return label, row

    def _file_row(self, title, subtitle, group, callback, filters=None):
        row = Adw.ActionRow()
        row.set_title(title)
        row.set_subtitle(subtitle)

        label = Gtk.Label(label="Nicht ausgewaehlt")
        label.add_css_class('caption')
        label.add_css_class('dim-label')
        label.set_ellipsize(3)
        label.set_max_width_chars(28)

        btn = Gtk.Button(label="Auswaehlen...")
        btn.add_css_class('flat')
        btn.set_valign(Gtk.Align.CENTER)
        btn.connect('clicked', lambda b: callback(b, filters))

        row.add_suffix(label)
        row.add_suffix(btn)
        group.add(row)
        return label, row

    # ─── Werte laden / speichern ───────────────────────────────────────────────

    def _load_values(self):
        cfg = self.fm.config
        self.title_entry.set_text(cfg.title or "")
        self.desc_entry.set_text(cfg.description or "")
        self.author_entry.set_text(cfg.author or "")
        self.email_entry.set_text(cfg.email or "")
        self.language_entry.set_text(cfg.language or "de")
        self.image_entry.set_text(cfg.image_url or "")
        self.category_entry.set_text(cfg.category or "Technology")
        self.subcategory_entry.set_text(cfg.subcategory or "")
        self.base_url_entry.set_text(cfg.base_url or "")
        self.media_url_path_entry.set_text(cfg.media_url_path or "/podcast/")
        self.feed_filename_entry.set_text(cfg.feed_filename or "podcast.xml")
        self.file_prefix_entry.set_text(cfg.file_prefix or "DWSK-Folge")
        self.blog_rss_entry.set_text(cfg.blog_rss_url or "")

        if cfg.media_base_path:
            self.media_path_label.set_text(cfg.media_base_path)
        if cfg.output_directory:
            self.output_path_label.set_text(cfg.output_directory)
        if cfg.blog_rss_local_path:
            self.local_xml_label.set_text(cfg.blog_rss_local_path)
        if cfg.markdown_path:
            self.markdown_path_label.set_text(cfg.markdown_path)

        explicit_map = {"no": 0, "yes": 1, "false": 0, "true": 1, "clean": 0}
        self.explicit_combo.set_selected(explicit_map.get(cfg.explicit, 0))

        # Quelle-Toggle
        if cfg.blog_rss_source == "local":
            self.source_toggle_local.set_active(True)
        else:
            self.source_toggle.set_active(True)
        self._update_source_ui()
        self._update_preview()

    def _on_save(self, btn):
        cfg = self.fm.config
        cfg.title             = self.title_entry.get_text().strip()
        cfg.description       = self.desc_entry.get_text().strip()
        cfg.author            = self.author_entry.get_text().strip()
        cfg.email             = self.email_entry.get_text().strip()
        cfg.language          = self.language_entry.get_text().strip() or "de"
        cfg.image_url         = self.image_entry.get_text().strip()
        cfg.category          = self.category_entry.get_text().strip()
        cfg.subcategory       = self.subcategory_entry.get_text().strip()
        cfg.base_url          = self.base_url_entry.get_text().strip().rstrip('/')
        cfg.media_url_path    = self.media_url_path_entry.get_text().strip()
        cfg.feed_filename     = self.feed_filename_entry.get_text().strip() or "podcast.xml"
        cfg.file_prefix       = self.file_prefix_entry.get_text().strip()
        cfg.blog_rss_url      = self.blog_rss_entry.get_text().strip()
        cfg.blog_rss_source   = "local" if self.source_toggle_local.get_active() else "online"

        explicit_values = ["no", "yes"]
        cfg.explicit = explicit_values[self.explicit_combo.get_selected()]

        if not cfg.title:
            self.win.show_toast("Bitte einen Podcast-Titel eingeben")
            return
        if not cfg.base_url:
            self.win.show_toast("Bitte die Webseiten-URL eingeben")
            return

        try:
            self.fm.save_config()
            self.win.refresh_status()

            # Falls bereits Episoden vorhanden: Feed sofort neu generieren
            # -> URLs, GUID, Titel etc. werden mit neuer Config aktualisiert
            if self.fm.get_episode_count() > 0:
                saved_path = self.fm.save_feed()
                self.win.show_toast(
                    f"Einstellungen gespeichert – Feed aktualisiert ({self.fm.get_episode_count()} Folgen)"
                )
            else:
                self.win.show_toast("Einstellungen gespeichert")
        except Exception as e:
            self.win.show_toast(f"Fehler: {e}")

    # ─── Ordner/Datei-Dialoge ──────────────────────────────────────────────────

    def _on_choose_media_folder(self, btn):
        d = Gtk.FileDialog()
        d.set_title("Medienordner auswaehlen")
        d.select_folder(self.win, None, lambda d, r: self._folder_done(
            d, r, d.select_folder_finish, self.fm.config.__setattr__,
            'media_base_path', self.media_path_label
        ))

    def _on_choose_output_folder(self, btn):
        d = Gtk.FileDialog()
        d.set_title("Ausgabeordner auswaehlen")
        d.select_folder(self.win, None, lambda d, r: self._folder_done(
            d, r, d.select_folder_finish, self.fm.config.__setattr__,
            'output_directory', self.output_path_label
        ))

    def _on_choose_markdown_folder(self, btn):
        d = Gtk.FileDialog()
        d.set_title("Markdown-Ordner auswaehlen")
        d.select_folder(self.win, None, lambda d, r: self._folder_done(
            d, r, d.select_folder_finish, self.fm.config.__setattr__,
            'markdown_path', self.markdown_path_label
        ))

    def _on_choose_local_xml(self, btn, filters=None):
        d = Gtk.FileDialog()
        d.set_title("Lokale XML-Datei auswaehlen")
        d.open(self.win, None, lambda d, r: self._file_done(
            d, r, self.fm.config.__setattr__,
            'blog_rss_local_path', self.local_xml_label
        ))

    def _folder_done(self, dialog, result, finish_fn, setter, attr, label):
        try:
            folder = finish_fn(result)
            if folder:
                path = folder.get_path()
                setter(attr, path)
                label.set_text(path)
        except Exception:
            pass

    def _file_done(self, dialog, result, setter, attr, label):
        try:
            f = dialog.open_finish(result)
            if f:
                path = f.get_path()
                setter(attr, path)
                label.set_text(path)
        except Exception:
            pass

    # ─── Quelle-Toggle ────────────────────────────────────────────────────────

    def _on_source_toggled(self, btn):
        self._update_source_ui()

    def _update_source_ui(self):
        is_local = self.source_toggle_local.get_active()
        self.blog_rss_entry.set_sensitive(not is_local)
        self.local_xml_row.set_sensitive(is_local)

    def _update_preview(self, *args):
        prefix = self.file_prefix_entry.get_text().strip() or "DWSK-Folge"
        self.preview_label.set_text(f"{prefix}42.mp3 -> Folge 42")
