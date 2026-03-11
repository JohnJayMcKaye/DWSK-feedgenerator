"""
Hauptfenster - GTK4 + Adwaita
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Gio

from feed_manager import FeedManager
from ui.setup_page import SetupPage
from ui.episodes_page import EpisodesPage
from ui.add_episodes_page import AddEpisodesPage
from ui.settings_page import SettingsPage
from ui.podcasts_page import PodcastsPage


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.feed_manager = FeedManager()
        self.set_title("Podcast Feed Generator")
        self.set_default_size(980, 700)
        self._build_ui()
        self._update_status()

    def _build_ui(self):
        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self.toast_overlay)

        self.nav_view = Adw.NavigationView()
        self.toast_overlay.set_child(self.nav_view)

        self.split_view = Adw.NavigationSplitView()
        self.split_view.set_min_sidebar_width(220)
        self.split_view.set_max_sidebar_width(260)

        # ── Sidebar ──────────────────────────────────────────────────────────
        sidebar_page = Adw.NavigationPage()
        sidebar_page.set_title("Podcast Feed Generator")
        sidebar_page.set_tag("sidebar")

        sidebar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        sidebar_header = Adw.HeaderBar()
        sidebar_header.set_show_end_title_buttons(False)

        # Info-Button (Fragezeichen)
        info_btn = Gtk.Button()
        info_btn.set_icon_name("help-about-symbolic")
        info_btn.add_css_class("flat")
        info_btn.set_tooltip_text("Ueber diese App")
        info_btn.connect("clicked", self._on_show_about)
        sidebar_header.pack_end(info_btn)

        sidebar_box.append(sidebar_header)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.sidebar_list = Gtk.ListBox()
        self.sidebar_list.add_css_class("navigation-sidebar")
        self.sidebar_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.sidebar_list.connect("row-selected", self._on_nav_row_selected)

        nav_items = [
            ("audio-podcast-symbolic",      "Mein Podcast",       "overview"),
            ("view-list-symbolic",          "Episodenliste",       "episodes"),
            ("list-add-symbolic",           "Folgen hinzufügen",  "add_episodes"),
            ("preferences-system-symbolic", "Einstellungen",       "settings"),
            ("folder-symbolic",             "Alle Podcasts",       "podcasts"),
        ]

        self.nav_rows = []
        for icon_name, label, page_tag in nav_items:
            row = Gtk.ListBoxRow()
            row.set_margin_start(4); row.set_margin_end(4)
            row.set_margin_top(2);   row.set_margin_bottom(2)

            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            hbox.set_margin_start(12); hbox.set_margin_end(12)
            hbox.set_margin_top(10);   hbox.set_margin_bottom(10)

            icon = Gtk.Image.new_from_icon_name(icon_name)
            icon.set_pixel_size(16)
            lbl = Gtk.Label(label=label)
            lbl.set_halign(Gtk.Align.START)
            lbl.set_hexpand(True)

            hbox.append(icon)
            hbox.append(lbl)
            row.set_child(hbox)
            row._tag = page_tag
            self.sidebar_list.append(row)
            self.nav_rows.append(row)

        scroll.set_child(self.sidebar_list)
        sidebar_box.append(scroll)

        # Status-Label
        self.status_label = Gtk.Label()
        self.status_label.add_css_class("caption")
        self.status_label.add_css_class("dim-label")
        self.status_label.set_margin_start(16); self.status_label.set_margin_end(16)
        self.status_label.set_margin_top(8);    self.status_label.set_margin_bottom(12)
        self.status_label.set_wrap(True)
        self.status_label.set_halign(Gtk.Align.START)
        sidebar_box.append(self.status_label)

        sidebar_page.set_child(sidebar_box)
        self.split_view.set_sidebar(sidebar_page)

        # ── Content ───────────────────────────────────────────────────────────
        content_page = Adw.NavigationPage()
        content_page.set_title("Inhalt")
        content_page.set_tag("content")

        self.content_stack = Gtk.Stack()
        self.content_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

        self.setup_page        = SetupPage(self.feed_manager, self)
        self.episodes_page     = EpisodesPage(self.feed_manager, self)
        self.add_episodes_page = AddEpisodesPage(self.feed_manager, self)
        self.settings_page     = SettingsPage(self.feed_manager, self)
        self.podcasts_page     = PodcastsPage(self.feed_manager, self)

        self.content_stack.add_named(self.setup_page,        "overview")
        self.content_stack.add_named(self.episodes_page,     "episodes")
        self.content_stack.add_named(self.add_episodes_page, "add_episodes")
        self.content_stack.add_named(self.settings_page,     "settings")
        self.content_stack.add_named(self.podcasts_page,     "podcasts")

        content_page.set_child(self.content_stack)
        self.split_view.set_content(content_page)

        main_page = Adw.NavigationPage()
        main_page.set_tag("main")
        main_page.set_child(self.split_view)
        self.nav_view.add(main_page)

        self.sidebar_list.select_row(self.nav_rows[0])

    # ── Navigation ────────────────────────────────────────────────────────────

    def _on_nav_row_selected(self, listbox, row):
        if row is None:
            return
        tag = row._tag
        self.content_stack.set_visible_child_name(tag)
        if tag == "episodes":
            self.episodes_page.refresh()
        elif tag == "add_episodes":
            self.add_episodes_page.refresh()
        elif tag == "overview":
            self.setup_page.refresh()
        elif tag == "podcasts":
            self.podcasts_page.refresh()

    def navigate_to(self, tag):
        self.content_stack.set_visible_child_name(tag)
        for row in self.nav_rows:
            if row._tag == tag:
                row.get_parent().select_row(row)
                break

    # ── Podcast wechseln (von PodcastsPage aufgerufen) ────────────────────────

    def switch_podcast(self, config_path):
        """Lädt einen anderen Podcast und aktualisiert alle Seiten."""
        from feed_manager import FeedManager
        self.feed_manager = FeedManager(config_path=config_path)

        self.setup_page.fm        = self.feed_manager
        self.episodes_page.fm     = self.feed_manager
        self.add_episodes_page.fm = self.feed_manager
        self.settings_page.fm     = self.feed_manager

        self.settings_page._load_values()
        self.setup_page.refresh()
        self._update_status()
        self.navigate_to("overview")
        self.show_toast(f"Podcast geladen: {self.feed_manager.config.title or 'Unbekannt'}")

    # ── Toast / Status ─────────────────────────────────────────────────────────

    def show_toast(self, message, timeout=3):
        toast = Adw.Toast.new(message)
        toast.set_timeout(timeout)
        self.toast_overlay.add_toast(toast)

    def _update_status(self):
        fm = self.feed_manager
        if fm.is_configured():
            self.status_label.set_text(
                f"{fm.config.title}\n{fm.get_episode_count()} Folge(n)"
            )
        else:
            self.status_label.set_text("Noch kein Podcast konfiguriert")

    def refresh_status(self):
        self._update_status()
        try:
            self.settings_page._load_values()
        except Exception:
            pass

    # ── Ueber-Dialog ──────────────────────────────────────────────────────────

    def _on_show_about(self, btn):
        dialog = Adw.AboutDialog()
        dialog.set_application_name("Podcast Feed Generator")
        dialog.set_version("1.1")
        dialog.set_developer_name("JohnJayMcKaye")
        dialog.set_license_type(Gtk.License.MIT_X11)
        dialog.set_comments(
            "Erstellt und verwaltet RSS 2.0 + iTunes-kompatible Podcast-Feeds.\n"
            "Unterstuetzt Hugo-Markdown-Shownotes, lokale und Online RSS-Quellen."
        )
        dialog.set_website("https://daswarschonkaputt.de")
        dialog.present(self)
