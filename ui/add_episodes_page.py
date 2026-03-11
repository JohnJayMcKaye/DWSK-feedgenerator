"""
Folgen hinzufuegen - Mediendateien scannen, Shownotes laden, Feed erweitern
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib
import threading
from pathlib import Path
from feed_manager import sanitize_for_gtk


class AddEpisodesPage(Gtk.Box):
    def __init__(self, feed_manager, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.fm = feed_manager
        self.win = window
        self._found_files = []        # [(ep_num, Path)]
        self._xml_data    = {}        # {ep_num: {...}}
        self._md_data     = {}        # {ep_num: {...}}
        self._pending     = []        # [(ep_num, Path, merged_data)]
        self._build()

    def _build(self):
        header = Adw.HeaderBar()
        t = Adw.WindowTitle()
        t.set_title("Folgen hinzufuegen")
        t.set_subtitle("Neue Episoden erkennen und importieren")
        header.set_title_widget(t)
        self.append(header)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        self.box.set_margin_start(32)
        self.box.set_margin_end(32)
        self.box.set_margin_top(24)
        self.box.set_margin_bottom(32)
        scroll.set_child(self.box)
        self.append(scroll)

        # ── Schritt 1: MP3 scannen ─────────────────────────────────────────────
        g1 = Adw.PreferencesGroup()
        g1.set_title("Schritt 1 – Mediendateien scannen")
        self.box.append(g1)

        self.scan_row = Adw.ActionRow()
        self.scan_row.set_title("Medienordner durchsuchen")
        self.scan_row.set_subtitle(self.fm.config.media_base_path or "Kein Ordner konfiguriert")
        self.scan_btn = Gtk.Button(label="Scannen")
        self.scan_btn.add_css_class('suggested-action')
        self.scan_btn.set_valign(Gtk.Align.CENTER)
        self.scan_btn.connect('clicked', self._on_scan)
        self.scan_row.add_suffix(self.scan_btn)
        g1.add(self.scan_row)

        # ── Fortschrittsbalken ─────────────────────────────────────────────────
        self.progress_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.set_pulse_step(0.1)
        self.progress_lbl = Gtk.Label()
        self.progress_lbl.add_css_class('caption')
        self.progress_lbl.add_css_class('dim-label')
        self.progress_box.append(self.progress_bar)
        self.progress_box.append(self.progress_lbl)
        self.progress_box.set_visible(False)
        self.box.append(self.progress_box)

        # ── Schritt 2a: XML-Feed laden ─────────────────────────────────────────
        self.g2 = Adw.PreferencesGroup()
        self.g2.set_title("Schritt 2a – Shownotes aus RSS/XML laden (optional)")
        self.g2.set_visible(False)
        self.box.append(self.g2)

        self.xml_source_row = Adw.ActionRow()
        self.xml_source_row.set_title("RSS/XML-Quelle")
        self._update_xml_source_subtitle()
        self.fetch_btn = Gtk.Button(label="XML laden")
        self.fetch_btn.set_valign(Gtk.Align.CENTER)
        self.fetch_btn.connect('clicked', self._on_fetch_xml)
        self.xml_source_row.add_suffix(self.fetch_btn)
        self.g2.add(self.xml_source_row)

        # ── Schritt 2b: Markdown laden ─────────────────────────────────────────
        self.g3 = Adw.PreferencesGroup()
        self.g3.set_title("Schritt 2b – Shownotes aus Markdown laden (optional)")
        self.g3.set_visible(False)
        self.box.append(self.g3)

        self.md_row = Adw.ActionRow()
        self.md_row.set_title("Markdown-Ordner")
        self.md_row.set_subtitle(self.fm.config.markdown_path or "Kein Ordner konfiguriert")
        self.md_btn = Gtk.Button(label="Markdown laden")
        self.md_btn.set_valign(Gtk.Align.CENTER)
        self.md_btn.connect('clicked', self._on_load_markdown)
        self.md_row.add_suffix(self.md_btn)
        self.g3.add(self.md_row)

        # ── Schritt 3: Importieren ─────────────────────────────────────────────
        self.g4 = Adw.PreferencesGroup()
        self.g4.set_title("Schritt 3 – Zum Feed hinzufuegen")
        self.g4.set_visible(False)
        self.box.append(self.g4)

        import_row = Adw.ActionRow()
        import_row.set_title("Alle gefundenen Folgen importieren")
        import_row.set_subtitle("Episoden werden zum Feed hinzugefuegt und gespeichert")
        self.import_btn = Gtk.Button(label="Importieren und Speichern")
        self.import_btn.add_css_class('suggested-action')
        self.import_btn.set_valign(Gtk.Align.CENTER)
        self.import_btn.connect('clicked', self._on_import)
        import_row.add_suffix(self.import_btn)
        self.g4.add(import_row)

        # ── Trennlinie ────────────────────────────────────────────────────────
        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        separator.set_margin_top(8)
        separator.set_margin_bottom(8)
        self.separator = separator
        self.separator.set_visible(False)
        self.box.append(self.separator)

        # ── Scan-Ergebnisse (UNTER den Aktions-Buttons) ────────────────────────
        self.results_group = Adw.PreferencesGroup()
        self.results_group.set_title("Gefundene neue Folgen")
        self.results_group.set_visible(False)
        self.box.append(self.results_group)

        # ── Hinweise ──────────────────────────────────────────────────────────
        self.hint_group = Adw.PreferencesGroup()
        self.hint_group.set_title("Hinweise")
        self.hint_group.set_visible(False)
        self.box.append(self.hint_group)

    # ─── Refresh ──────────────────────────────────────────────────────────────

    def refresh(self):
        cfg = self.fm.config
        self.scan_row.set_subtitle(cfg.media_base_path or "Kein Ordner konfiguriert")
        self.md_row.set_subtitle(cfg.markdown_path or "Kein Ordner konfiguriert")
        self._update_xml_source_subtitle()
        self._reset_state()

    def _update_xml_source_subtitle(self):
        cfg = self.fm.config
        if cfg.blog_rss_source == "local":
            self.xml_source_row.set_subtitle(
                f"Lokal: {cfg.blog_rss_local_path or 'Keine Datei'}"
            )
        else:
            self.xml_source_row.set_subtitle(
                f"Online: {cfg.blog_rss_url or 'Keine URL'}"
            )

    def _reset_state(self):
        self._found_files = []
        self._xml_data    = {}
        self._md_data     = {}
        self._pending     = []
        self.g2.set_visible(False)
        self.g3.set_visible(False)
        self.g4.set_visible(False)
        self.separator.set_visible(False)
        self.results_group.set_visible(False)
        self.hint_group.set_visible(False)
        self._rebuild_results_group()

    # ─── Schritt 1: Scannen ───────────────────────────────────────────────────

    def _on_scan(self, btn):
        if not self.fm.config.media_base_path:
            self.win.show_toast("Bitte erst den Medienordner in den Einstellungen festlegen")
            return
        self.scan_btn.set_sensitive(False)
        self._set_progress(-1, "Scanne Medienordner...")
        self._reset_state()

        def do_scan():
            found, skipped = self.fm.scan_media_files()
            GLib.idle_add(self._show_scan_results, found, skipped)

        threading.Thread(target=do_scan, daemon=True).start()

    def _show_scan_results(self, found, skipped):
        self._hide_progress()
        self.scan_btn.set_sensitive(True)
        self._found_files = found

        if found:
            self.results_group.set_visible(True)
            self.results_group.set_title(f"Gefundene neue Folgen ({len(found)})")
            self._rebuild_results_group()
            self.g2.set_visible(True)
            self.g3.set_visible(True)
            self.g4.set_visible(True)
            self.separator.set_visible(True)
            self.win.show_toast(f"{len(found)} neue Folge(n) gefunden")
        else:
            self.win.show_toast("Keine neuen Folgen gefunden")

        if skipped:
            self.hint_group.set_visible(True)
            self.hint_group.set_title(f"Hinweise ({len(skipped)})")
            for msg in skipped[:8]:
                r = Adw.ActionRow()
                r.set_title(msg)
                self.hint_group.add(r)

        return False

    # ─── Schritt 2a: XML/RSS ──────────────────────────────────────────────────

    def _on_fetch_xml(self, btn):
        cfg = self.fm.config
        if cfg.blog_rss_source == "local" and not cfg.blog_rss_local_path:
            self.win.show_toast("Keine lokale XML-Datei konfiguriert")
            return
        if cfg.blog_rss_source == "online" and not cfg.blog_rss_url:
            self.win.show_toast("Keine Online-URL konfiguriert")
            return

        btn.set_sensitive(False)
        self._set_progress(-1, "Lade RSS/XML...")

        def do_fetch():
            result = self.fm.fetch_blog_feed(
                progress_callback=lambda m: GLib.idle_add(
                    lambda: self._set_progress(-1, m)
                )
            )
            GLib.idle_add(self._on_xml_loaded, result, btn)

        threading.Thread(target=do_fetch, daemon=True).start()

    def _on_xml_loaded(self, data, btn):
        self._hide_progress()
        btn.set_sensitive(True)

        if 'error' in data:
            self.win.show_toast(f"XML-Fehler: {data['error']}")
            return

        self._xml_data = data
        matched = sum(1 for n, _ in self._found_files if n in data)
        self.win.show_toast(f"XML geladen – {matched}/{len(self._found_files)} Folgen gefunden")
        self._rebuild_results_group()
        return False

    # ─── Schritt 2b: Markdown ─────────────────────────────────────────────────

    def _on_load_markdown(self, btn):
        if not self.fm.config.markdown_path:
            self.win.show_toast("Kein Markdown-Ordner konfiguriert")
            return

        btn.set_sensitive(False)
        self._set_progress(-1, "Lese Markdown-Dateien...")

        def do_md():
            result = self.fm.scan_markdown_files()
            GLib.idle_add(self._on_md_loaded, result, btn)

        threading.Thread(target=do_md, daemon=True).start()

    def _on_md_loaded(self, data, btn):
        self._hide_progress()
        btn.set_sensitive(True)
        self._md_data = data
        matched = sum(1 for n, _ in self._found_files if n in data)
        self.win.show_toast(f"Markdown geladen – {matched}/{len(self._found_files)} Folgen gefunden")
        self._rebuild_results_group()
        return False

    # ─── Ergebnisliste aktualisieren ──────────────────────────────────────────

    def _rebuild_results_group(self):
        """Baut die Ergebnisliste neu auf (mit aktuellem XML+MD Status)"""
        # PreferencesGroup leeren: neues Group-Objekt ersetzen
        old = self.results_group
        new_group = Adw.PreferencesGroup()
        new_group.set_title(old.get_title())
        new_group.set_visible(old.get_visible())

        parent = old.get_parent()
        if parent:
            # Ersetzen
            old.set_visible(False)
            parent.remove(old)
            # An gleicher Position einfügen (vor g2)
            new_group.insert_before(parent, self.g2) if hasattr(new_group, 'insert_before') else parent.append(new_group)

        self.results_group = new_group

        for ep_num, file_path in self._found_files:
            xml_d = self._xml_data.get(ep_num)
            md_d  = self._md_data.get(ep_num)

            has_xml = xml_d is not None
            has_md  = md_d  is not None

            if has_xml or has_md:
                icon = "OK"
            else:
                icon = "--"

            merged = self.fm.merge_shownotes(ep_num, xml_d, md_d)
            title_str = merged.get('title') or f"Folge {ep_num}"

            row = Adw.ExpanderRow()
            row.set_title(sanitize_for_gtk(f"[{icon}] Folge {ep_num}: {title_str}"))
            fname = Path(file_path).name if not isinstance(file_path, Path) else file_path.name
            row.set_subtitle(fname)

            def mr(lbl, val):
                r = Adw.ActionRow()
                r.set_title(lbl)
                r.set_subtitle(sanitize_for_gtk(str(val)[:300]) if val else "–")
                r.set_subtitle_lines(3)
                return r

            sources = []
            if has_xml:  sources.append("XML/RSS")
            if has_md:   sources.append("Markdown")
            row.add_row(mr("Quellen", ", ".join(sources) if sources else "Keine"))
            row.add_row(mr("Titel", merged.get('title', '')))
            row.add_row(mr("Datum", merged.get('pub_date', '')))
            row.add_row(mr("URL", merged.get('link', '')))
            if merged.get('description'):
                preview = merged['description'][:300].replace('\n', ' ')
                row.add_row(mr("Shownotes-Vorschau", preview + "..."))

            self.results_group.add(row)

    # ─── Schritt 3: Importieren ───────────────────────────────────────────────

    def _on_import(self, btn):
        if not self._found_files:
            self.win.show_toast("Keine Folgen zum Importieren")
            return

        btn.set_sensitive(False)
        count = 0

        for ep_num, file_path in self._found_files:
            xml_d  = self._xml_data.get(ep_num)
            md_d   = self._md_data.get(ep_num)
            merged = self.fm.merge_shownotes(ep_num, xml_d, md_d)

            episode = self.fm.create_episode(ep_num, file_path, merged if (xml_d or md_d) else None)
            self.fm.add_episode(episode)
            count += 1

        try:
            self.fm.save_config()
            saved = self.fm.save_feed()
            self.win.refresh_status()
            self.win.show_toast(f"{count} Folge(n) importiert – Feed gespeichert")
            self._reset_state()
        except Exception as e:
            self.win.show_toast(f"Fehler: {e}")

        btn.set_sensitive(True)

    # ─── Fortschritt ──────────────────────────────────────────────────────────

    def _set_progress(self, fraction, label=""):
        self.progress_box.set_visible(True)
        if fraction < 0:
            self.progress_bar.pulse()
        else:
            self.progress_bar.set_fraction(fraction)
        self.progress_lbl.set_text(label)

    def _hide_progress(self):
        self.progress_box.set_visible(False)
