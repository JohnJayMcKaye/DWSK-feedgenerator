"""
Feed Manager - Kernlogik für Podcast-Feed-Verwaltung
Erstellt und erweitert RSS 2.0 + iTunes/Spotify kompatible Feeds
"""

import os
import re
import json
import uuid
import hashlib
import urllib.request
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime, timezone
import locale as _locale
from pathlib import Path



def sanitize_for_gtk(text):
    """Bereinigt Text fuer GTK Pango: entfernt HTML, Hugo-Shortcodes, escaped &."""
    if not text:
        return ""
    import html as _html
    import re as _re
    # 1. HTML-Entities dekodieren (&ldquo; -> ", &amp; -> & usw.)
    text = _html.unescape(text)
    # 2. Hugo-Shortcodes {{< ... >}} und {{ ... }} entfernen
    text = _re.sub(r'\{\{.*?\}\}', '', text, flags=_re.DOTALL)
    # 3. Vollstaendige HTML-Tags entfernen: <tag>, </tag>, <tag/>
    text = _re.sub(r'</?[a-zA-Z][^>]*/?>', '', text)
    # 4. Unvollstaendige Tags entfernen: z.B. "<br" am Zeilenende, "</h2" usw.
    text = _re.sub(r'</?[a-zA-Z][a-zA-Z0-9]*', '', text)
    # 5. Noch verbliebene spitze Klammern entfernen
    text = _re.sub(r'[<>]', '', text)
    # 6. & fuer GTK Pango Markup escapen
    text = text.replace('&', '&amp;')
    # 7. Whitespace normalisieren
    text = _re.sub(r'\s+', ' ', text).strip()
    return text


# CONFIG_FILE wird dynamisch aus dem aktiven Profil geladen (siehe load_config/save_config)
CONFIG_FILE = os.path.expanduser("~/.config/podcast-feed-generator/config.json")  # Legacy-Fallback


class Episode:
    """Repräsentiert eine einzelne Podcast-Episode"""
    def __init__(self):
        self.number = 0
        self.title = ""
        self.description = ""
        self.file_path = ""
        self.file_url = ""
        self.file_size = 0
        self.duration = ""
        self.pub_date = ""
        self.teaser = ""
        self.shownotes_url = ""
        self.guid = ""

    def to_dict(self):
        return self.__dict__

    @classmethod
    def from_dict(cls, d):
        ep = cls()
        ep.__dict__.update(d)
        # Rueckwaertskompatibilitaet: aeltere Configs ohne teaser-Feld
        if not hasattr(ep, 'teaser'):
            ep.teaser = ""
        return ep


class PodcastConfig:
    """Podcast-Konfiguration"""
    def __init__(self):
        self.title = ""
        self.description = ""
        self.base_url = ""
        self.media_base_path = ""
        self.media_url_path = "/podcast/"
        self.feed_filename = "podcast.xml"
        self.author = ""
        self.email = ""
        self.language = "de"
        self.category = "Technology"
        self.subcategory = ""
        self.image_url = ""
        self.explicit = "no"
        # Blog/Shownotes-Quellen
        self.blog_rss_url = ""           # Online RSS/Atom URL
        self.blog_rss_local_path = ""    # Lokale XML-Datei
        self.blog_rss_source = "online"  # "online" | "local"
        self.markdown_path = ""          # Ordner mit 42.md Dateien
        # Dateinamen-Schema
        self.file_prefix = "DWSK-Folge"
        self.episode_number_pattern = r"(\d+)"
        self.output_directory = os.path.expanduser("~/podcast-feed")

    def to_dict(self):
        return self.__dict__

    @classmethod
    def from_dict(cls, d):
        cfg = cls()
        cfg.__dict__.update(d)
        return cfg


class FeedManager:
    """Verwaltet den Podcast-Feed"""

    def __init__(self, config_path=None):
        self.config = PodcastConfig()
        self.episodes = []
        self._config_path = config_path  # None = Standard-Config
        self._load_config()

    # ─── Konfiguration ────────────────────────────────────────────────────────

    def _config_file(self):
        return self._config_path or CONFIG_FILE

    def _load_config(self):
        cfg_file = self._config_file()
        if os.path.exists(cfg_file):
            try:
                with open(cfg_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.config   = PodcastConfig.from_dict(data.get('config', {}))
                self.episodes = [Episode.from_dict(e) for e in data.get('episodes', [])]
            except Exception as e:
                print(f"Config laden fehlgeschlagen: {e}")

    def save_config(self):
        cfg_file = self._config_file()
        os.makedirs(os.path.dirname(cfg_file), exist_ok=True)
        data = {
            'config':   self.config.to_dict(),
            'episodes': [ep.to_dict() for ep in self.episodes],
        }
        with open(cfg_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def is_configured(self):
        return bool(self.config.title and self.config.base_url)

    # ─── Mediendateien scannen ─────────────────────────────────────────────────

    def scan_media_files(self):
        if not self.config.media_base_path:
            return [], ["Kein Medienordner konfiguriert"]

        found = []
        skipped = []
        existing_numbers = {ep.number for ep in self.episodes}
        media_path = Path(self.config.media_base_path)

        if not media_path.exists():
            return [], [f"Ordner nicht gefunden: {self.config.media_base_path}"]

        pattern = re.compile(
            re.escape(self.config.file_prefix) + self.config.episode_number_pattern,
            re.IGNORECASE
        )

        for mp3_file in sorted(media_path.glob("*.mp3")):
            match = pattern.search(mp3_file.name)
            if match:
                ep_num = int(match.group(1))
                if ep_num not in existing_numbers:
                    found.append((ep_num, mp3_file))
                else:
                    skipped.append(f"Folge {ep_num} bereits im Feed")
            else:
                skipped.append(f"Kein Muster erkannt: {mp3_file.name}")

        found.sort(key=lambda x: x[0])
        return found, skipped

    def get_file_size(self, file_path):
        try:
            return os.path.getsize(file_path)
        except:
            return 0

    def get_mp3_duration(self, file_path):
        """Schätzt MP3-Dauer anhand der Dateigröße (Fallback ohne mutagen)"""
        try:
            size = os.path.getsize(file_path)
            seconds = size // 16000
            h = seconds // 3600
            m = (seconds % 3600) // 60
            s = seconds % 60
            if h > 0:
                return f"{h:02d}:{m:02d}:{s:02d}"
            return f"{m:02d}:{s:02d}"
        except:
            return "00:00"

    # ─── GUID ─────────────────────────────────────────────────────────────────

    def compute_file_url(self, file_path):
        """Berechnet die Medien-URL aus der aktuellen Config – immer aktuell."""
        filename = os.path.basename(str(file_path))
        base     = self.config.base_url.rstrip('/')
        url_path = self.config.media_url_path.strip('/')
        if url_path:
            return f"{base}/{url_path}/{filename}"
        return f"{base}/{filename}"

    def make_guid(self, ep_num):
        """Erstellt eine stabile, eindeutige GUID für eine Episode"""
        base = f"{self.config.base_url}-episode-{ep_num}"
        return str(uuid.uuid5(uuid.NAMESPACE_URL, base))

    # ─── Hugo TOML/YAML Frontmatter parsen ────────────────────────────────────

    def parse_markdown_file(self, file_path):
        """
        Parst eine Hugo-Markdown-Datei mit TOML (+++) oder YAML (---) Frontmatter.
        Gibt dict mit title, date, description, author und body zurück.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            return {'error': str(e)}

        result = {}

        # TOML Frontmatter: +++ ... +++ (auch mit fuehrender Leerzeile)
        content_stripped = content.lstrip()
        toml_match = re.match(r'^\+\+\+\s*\n(.*?)\n\+\+\+\s*\n(.*)', content_stripped, re.DOTALL)
        # YAML Frontmatter: --- ... ---
        yaml_match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', content_stripped, re.DOTALL)

        if toml_match:
            fm_text = toml_match.group(1)
            body = toml_match.group(2).strip()
            result = self._parse_toml_simple(fm_text)
            result['body'] = self._trim_to_first_heading(body)
        elif yaml_match:
            fm_text = yaml_match.group(1)
            body = yaml_match.group(2).strip()
            result = self._parse_yaml_simple(fm_text)
            result['body'] = self._trim_to_first_heading(body)
        else:
            # Kein Frontmatter erkannt
            result['body'] = self._trim_to_first_heading(content_stripped.strip())

        return result

    def _parse_toml_simple(self, text):
        """Einfacher TOML-Parser für Hugo-Frontmatter (key = "value")"""
        result = {}
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            m = re.match(r'^(\w+)\s*=\s*"(.*)"$', line)
            if m:
                result[m.group(1)] = m.group(2)
            else:
                # Unquoted (z.B. date = 2024-01-15)
                m2 = re.match(r'^(\w+)\s*=\s*(.+)$', line)
                if m2:
                    result[m2.group(1)] = m2.group(2).strip().strip('"\'')
        return result

    def _parse_yaml_simple(self, text):
        """Einfacher YAML-Parser für Hugo-Frontmatter (key: value)"""
        result = {}
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            m = re.match(r'^(\w+):\s*"?(.*?)"?$', line)
            if m:
                result[m.group(1)] = m.group(2).strip()
        return result

    def scan_markdown_files(self):
        """
        Scannt den Markdown-Ordner nach Dateien wie 42.md.
        Gibt dict {ep_num: parsed_data} zurück.
        """
        if not self.config.markdown_path:
            return {}

        md_path = Path(self.config.markdown_path)
        if not md_path.exists():
            return {}

        result = {}
        for md_file in md_path.glob("*.md"):
            # Dateiname ist die Episodennummer: 42.md
            stem = md_file.stem
            if stem.isdigit():
                ep_num = int(stem)
                parsed = self.parse_markdown_file(md_file)
                parsed['_source_file'] = str(md_file)
                result[ep_num] = parsed

        return result

    # ─── Blog RSS/Atom Feed holen ──────────────────────────────────────────────

    def fetch_blog_feed(self, progress_callback=None):
        """
        Holt den Blog-RSS/Atom-Feed: entweder online oder lokal.
        Gibt dict {ep_num: {title, link, description, pub_date}} zurück.
        """
        source = self.config.blog_rss_source

        try:
            if source == "local":
                path = self.config.blog_rss_local_path
                if not path or not os.path.exists(path):
                    return {'error': f"Lokale XML nicht gefunden: {path}"}
                if progress_callback:
                    progress_callback("Lese lokale XML-Datei...")
                with open(path, 'rb') as f:
                    content = f.read()
            else:
                url = self.config.blog_rss_url
                if not url:
                    return {'error': "Keine Online-URL konfiguriert"}
                if progress_callback:
                    progress_callback("Lade Blog-Feed online...")
                req = urllib.request.Request(
                    url, headers={'User-Agent': 'PodcastFeedGenerator/1.0'}
                )
                with urllib.request.urlopen(req, timeout=15) as response:
                    content = response.read()

            if progress_callback:
                progress_callback("Analysiere Feed...")

            return self._parse_feed(content)

        except Exception as e:
            return {'error': str(e)}

    def _parse_feed(self, content):
        """Parst RSS oder Atom Feed"""
        try:
            root = ET.fromstring(content)
        except ET.ParseError as e:
            return {'error': f"XML-Fehler: {e}"}

        ns = {
            'atom': 'http://www.w3.org/2005/Atom',
            'content': 'http://purl.org/rss/1.0/modules/content/',
        }

        episodes_map = {}

        # RSS 2.0
        channel = root.find('channel')
        if channel is not None:
            for item in channel.findall('item'):
                title_el  = item.find('title')
                link_el   = item.find('link')
                desc_el   = item.find('description')
                cnt_el    = item.find('content:encoded', ns)
                date_el   = item.find('pubDate')

                title       = title_el.text  if title_el  is not None else ""
                link        = link_el.text   if link_el   is not None else ""
                pub_date    = date_el.text   if date_el   is not None else ""
                description = ""
                if cnt_el is not None and cnt_el.text:
                    description = self._html_to_text(cnt_el.text)
                elif desc_el is not None and desc_el.text:
                    description = self._html_to_text(desc_el.text)

                ep_num = self._extract_episode_number(title, link)
                if ep_num:
                    episodes_map[ep_num] = {
                        'title': title, 'link': link,
                        'description': description, 'pub_date': pub_date
                    }
        else:
            # Atom
            for entry in (root.findall('atom:entry', ns) or
                          root.findall('{http://www.w3.org/2005/Atom}entry')):
                def ft(tag):
                    el = (entry.find(f'atom:{tag}', ns) or
                          entry.find(f'{{http://www.w3.org/2005/Atom}}{tag}'))
                    return el.text if el is not None else ""

                title    = ft('title')
                link_el  = (entry.find('atom:link', ns) or
                             entry.find('{http://www.w3.org/2005/Atom}link'))
                link     = link_el.get('href', '') if link_el is not None else ""
                summary  = ft('summary') or ft('content')
                description = self._html_to_text(summary)
                pub_date = ft('published') or ft('updated')

                ep_num = self._extract_episode_number(title, link)
                if ep_num:
                    episodes_map[ep_num] = {
                        'title': title, 'link': link,
                        'description': description, 'pub_date': pub_date
                    }

        return episodes_map

    def _extract_episode_number(self, title, url):
        """Extrahiert Episodennummer aus Titel oder URL"""
        patterns = [
            r'[Ff]olge[-\s_#]*(\d+)',
            r'[Ee]pisode[-\s_#]*(\d+)',
            r'[Ee]p[-\s_#]*(\d+)',
            r'/(\d+)[-/]',
            r'[-_](\d{1,4})[-_.]',
            r'#(\d+)',
            r'\b(\d{1,4})\b',
        ]
        for text in [title, url]:
            if not text:
                continue
            for pat in patterns:
                m = re.search(pat, text)
                if m:
                    return int(m.group(1))
        return None

    def _html_to_text(self, html):
        """
        Konvertiert HTML zu plain text.
        Behandelt sowohl echtes HTML (<p>) als auch escaped HTML (&lt;p&gt;).
        Das Ergebnis enthaelt keinerlei HTML-Tags oder Entities.
        """
        if not html:
            return ""
        import html as _html_mod

        # Schritt 1: Zeilenumbrueche aus Block-Tags extrahieren (echtes HTML)
        text = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)
        text = re.sub(r'</?p[^>]*>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'</?h[1-6][^>]*>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'</li>', '\n', text, flags=re.IGNORECASE)

        # Schritt 2: Alle echten HTML-Tags entfernen
        text = re.sub(r'<[^>]+>', '', text)

        # Schritt 3: HTML-Entities vollstaendig dekodieren (inkl. &lt; &gt; &amp;)
        text = _html_mod.unescape(text)

        # Schritt 4: Nach dem Dekodieren nochmals Tags entfernen
        # (entstanden durch &lt;p&gt; → <p>)
        text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'</?p[^>]*>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'</?h[1-6][^>]*>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '', text)

        # Schritt 5: Abgeschnittene Tags am Ende entfernen (z.B. "<br" oder "</h")
        text = re.sub(r'\s*<[^>]*$', '', text)

        # Schritt 6: Whitespace bereinigen
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        return text.strip()

    def _trim_body_to_first_heading(self, body):
        """
        Gibt den Markdown-Body erst ab der ersten Ueberschrift (#) zurueck.
        Ueberspringt dabei Hugo-Frontmatter-Reste und leere Zeilen am Anfang.
        """
        if not body:
            return body
        lines = body.split('\n')
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('#'):
                return '\n'.join(lines[i:]).strip()
        # Keine Ueberschrift gefunden: Frontmatter-Zeilen (key = value) filtern
        clean = [l for l in lines if not re.match(r'^\w+\s*[=:]\s*', l.strip())]
        return '\n'.join(clean).strip()

    def _markdown_to_html(self, md_text):
        """
        Konvertiert Markdown zu HTML (einfache Implementierung ohne externe Libs).
        Unterstützt: Ueberschriften, Fettdruck, Links, Listen, Absaetze.
        Hugo-Shortcodes werden entfernt.
        """
        if not md_text:
            return ""

        # Hugo-Shortcodes entfernen: {{< shortcode ... >}} alle Varianten
        md_text = re.sub(r'\{\{[%<][^}]*[%>]\}\}', '', md_text)
        # Leere geschweifte Klammern-Reste
        md_text = re.sub(r'\{\{\s*\}\}', '', md_text)
        # Markdown-Bilder entfernen: ![alt](/path)
        md_text = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', md_text)

        lines = md_text.split('\n')
        html_lines = []
        in_list = False

        for line in lines:
            # Überschriften
            h_match = re.match(r'^(#{1,6})\s+(.*)', line)
            if h_match:
                if in_list:
                    html_lines.append('</ul>')
                    in_list = False
                level = len(h_match.group(1))
                content = self._md_inline(h_match.group(2))
                html_lines.append(f'<h{level}>{content}</h{level}>')
                continue

            # Listenelemente
            li_match = re.match(r'^[-*+]\s+(.*)', line)
            if li_match:
                if not in_list:
                    html_lines.append('<ul>')
                    in_list = True
                html_lines.append(f'<li>{self._md_inline(li_match.group(1))}</li>')
                continue

            # Nummerierte Liste
            oli_match = re.match(r'^\d+\.\s+(.*)', line)
            if oli_match:
                if not in_list:
                    html_lines.append('<ol>')
                    in_list = True
                html_lines.append(f'<li>{self._md_inline(oli_match.group(1))}</li>')
                continue

            if in_list and not li_match and not oli_match:
                html_lines.append('</ul>')
                in_list = False

            # Leerzeile
            if not line.strip():
                html_lines.append('<br/>')
                continue

            # Normaler Absatz
            html_lines.append(f'<p>{self._md_inline(line)}</p>')

        if in_list:
            html_lines.append('</ul>')

        return '\n'.join(html_lines)

    def _trim_to_first_heading(self, text):
        """Schneidet alles vor der ersten # Ueberschrift ab.
        So wird Hugo-Frontmatter-Restmuell am Anfang des Bodys entfernt."""
        if not text:
            return text
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if line.strip().startswith('#'):
                return '\n'.join(lines[i:])
        # Keine Ueberschrift gefunden – ab erster nicht-leerer Zeile
        for i, line in enumerate(lines):
            if line.strip():
                return '\n'.join(lines[i:])
        return text

    def _md_inline(self, text):
        """Inline-Markdown: fett, kursiv, links, code"""
        # Angle-Bracket-Autolinks <https://...> → <a href>
        text = re.sub(r'<(https?://[^>]+)>', r'<a href="\1">\1</a>', text)
        # Links [text](url) – URL aus Titel-Teil bereinigen
        def clean_link(m):
            link_text = m.group(1)
            url = m.group(2).split(' ')[0].strip('"\'')  # Titel-Teil entfernen
            if not url.startswith(('http','mailto','/')):
                return link_text  # relative URL als plain text
            return f'<a href="{url}">{link_text}</a>'
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', clean_link, text)
        # Fett **text** oder __text__
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'__(.+?)__', r'<strong>\1</strong>', text)
        # Kursiv – nur * verwenden, _ ist in URLs problematisch
        text = re.sub(r'\*([^*]+?)\*', r'<em>\1</em>', text)
        # Code `text`
        text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
        return text

    # ─── Shownotes zusammenführen ──────────────────────────────────────────────

    def merge_shownotes(self, ep_num, xml_data, md_data):
        """
        Führt XML-Feed-Daten und Markdown-Daten zusammen.
        Markdown-Body wird als Hauptinhalt genutzt, XML liefert Metadaten.
        """
        result = {
            'title': '',
            'description': '',
            'link': '',
            'pub_date': '',
        }

        # Metadaten bevorzugt aus XML (hat Link zur Seite)
        if xml_data:
            result['title']    = xml_data.get('title', '')
            result['link']     = xml_data.get('link', '')
            result['pub_date'] = xml_data.get('pub_date', '')

        # Titel aus Markdown-Frontmatter (falls besser)
        if md_data:
            if not result['title'] and md_data.get('title'):
                result['title'] = md_data['title']
            if not result['pub_date'] and md_data.get('date'):
                result['pub_date'] = md_data['date']

        # Teaser: Frontmatter-description oder erster Satz aus XML
        teaser = ""
        if md_data and md_data.get('description'):
            teaser = md_data['description']
        elif xml_data and xml_data.get('description'):
            teaser = xml_data['description']

        # Vollstaendiger HTML-Body aus Markdown
        full_html = ""
        if md_data and md_data.get('body'):
            full_html = self._markdown_to_html(md_data['body'])
        elif xml_data and xml_data.get('description'):
            full_html = xml_data['description']

        result['teaser']      = teaser        # kurze Beschreibung (plain text)
        result['description'] = full_html     # voller HTML-Inhalt fuer content:encoded

        return result

    # ─── Episode erstellen ─────────────────────────────────────────────────────

    def create_episode(self, ep_num, file_path, blog_data=None):
        ep = Episode()
        ep.number    = ep_num
        ep.file_path = str(file_path)
        ep.file_size = self.get_file_size(file_path)
        ep.duration  = self.get_mp3_duration(file_path)

        ep.file_url = self.compute_file_url(file_path)

        # Stabile GUID basierend auf Episodennummer + Base-URL
        ep.guid     = self.make_guid(ep_num)

        ep.pub_date = self._rfc822_now()

        if blog_data:
            ep.title         = blog_data.get('title', f"Folge {ep_num}")
            ep.teaser        = blog_data.get('teaser', '')
            ep.description   = blog_data.get('description', '')
            ep.shownotes_url = blog_data.get('link', '')
            if blog_data.get('pub_date'):
                ep.pub_date = self._normalize_date(blog_data['pub_date'])
        else:
            ep.title  = f"Folge {ep_num}"
            ep.teaser = ''

        return ep

    def _rfc822_now(self):
        """Gibt das aktuelle Datum als RFC-822 String auf Englisch zurueck."""
        dt = datetime.now(timezone.utc)
        # Explizit englische Abkuerzungen – unabhaengig von der Systemsprache
        days   = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
        months = ["Jan","Feb","Mar","Apr","May","Jun",
                  "Jul","Aug","Sep","Oct","Nov","Dec"]
        return (f"{days[dt.weekday()]}, {dt.day:02d} {months[dt.month-1]} "
                f"{dt.year} {dt.hour:02d}:{dt.minute:02d}:{dt.second:02d} +0000")

    def _normalize_date(self, date_str):
        """Normalisiert Datum zu RFC-822 mit englischen Wochentag/Monat-Abkuerzungen."""
        formats = [
            '%a, %d %b %Y %H:%M:%S %z',
            '%a, %d %b %Y %H:%M:%S +0000',
            '%Y-%m-%dT%H:%M:%S%z',
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d',
        ]
        days   = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
        months = ["Jan","Feb","Mar","Apr","May","Jun",
                  "Jul","Aug","Sep","Oct","Nov","Dec"]
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return (f"{days[dt.weekday()]}, {dt.day:02d} {months[dt.month-1]} "
                        f"{dt.year} {dt.hour:02d}:{dt.minute:02d}:{dt.second:02d} +0000")
            except:
                continue
        return date_str

    def add_episode(self, episode):
        existing_nums = {ep.number for ep in self.episodes}
        if episode.number not in existing_nums:
            self.episodes.append(episode)
            self.episodes.sort(key=lambda e: e.number, reverse=True)

    # ─── XML Feed generieren ───────────────────────────────────────────────────

    def _fix_relative_urls(self, html, base_url):
        """
        Wandelt alle relativen URLs (href= und src=) zu absoluten um.
        Entfernt auch Bilder (/img/...) da diese im Podcast-Feed keinen Sinn ergeben.
        """
        if not html or not base_url:
            return html
        from urllib.parse import urlparse
        base = base_url.rstrip('/')
        parsed_base = urlparse(base)
        base_domain = f"{parsed_base.scheme}://{parsed_base.netloc}"

        def fix_url(url):
            url = url.strip('<> \t')
            p = urlparse(url)
            if p.scheme in ('http', 'https', 'mailto', 'ftp'):
                return url  # bereits absolut
            elif url.startswith('/'):
                return f"{base_domain}{url}"
            elif url.startswith('#') or not url:
                return url  # Anker oder leer – unveraendert
            elif '.' in url.split('/')[0]:
                # Sieht aus wie domain/path ohne Schema
                return f"https://{url}"
            else:
                # Relativer Pfad – an Base-URL anhaengen
                return f"{base}/{url}"

        def fix_attr(m):
            attr = m.group(1)   # "href" oder "src"
            url  = m.group(2)
            fixed = fix_url(url)
            return f'{attr}="{fixed}"'

        # href= und src= beide behandeln
        html = re.sub(r'(href|src)="([^"]+)"', fix_attr, html)

        # <img ...> Tags komplett entfernen (Bilder sind im Podcast-Feed sinnlos
        # und erzeugen oft relative-URL-Warnungen)
        html = re.sub(r'<img[^>]*>', '', html, flags=re.IGNORECASE)

        return html

    def generate_feed_xml(self):
        cfg = self.config

        rss = ET.Element('rss')
        rss.set('version', '2.0')
        rss.set('xmlns:itunes',  'http://www.itunes.com/dtds/podcast-1.0.dtd')
        rss.set('xmlns:content', 'http://purl.org/rss/1.0/modules/content/')
        rss.set('xmlns:atom',    'http://www.w3.org/2005/Atom')

        channel = ET.SubElement(rss, 'channel')

        def add(parent, tag, text, **attrs):
            el = ET.SubElement(parent, tag, **attrs)
            if text:
                el.text = text
            return el

        add(channel, 'title',       cfg.title)
        add(channel, 'description', self._html_to_text(cfg.description) if cfg.description else '')
        add(channel, 'link',        cfg.base_url)
        add(channel, 'language',    cfg.language)
        add(channel, 'lastBuildDate',
            self._rfc822_now())

        feed_url = f"{cfg.base_url.rstrip('/')}/{cfg.feed_filename}"
        atom_link = ET.SubElement(channel, 'atom:link')
        atom_link.set('href', feed_url)
        atom_link.set('rel', 'self')
        atom_link.set('type', 'application/rss+xml')

        add(channel, 'itunes:author',   cfg.author)
        add(channel, 'itunes:explicit', 'true' if cfg.explicit == 'yes' else 'false')

        if cfg.email:
            owner = ET.SubElement(channel, 'itunes:owner')
            add(owner, 'itunes:name',  cfg.author)
            add(owner, 'itunes:email', cfg.email)

        if cfg.image_url:
            add(channel, 'itunes:image', None, href=cfg.image_url)
            image = ET.SubElement(channel, 'image')
            add(image, 'url',   cfg.image_url)
            add(image, 'title', cfg.title)
            add(image, 'link',  cfg.base_url)

        if cfg.category:
            cat = ET.SubElement(channel, 'itunes:category')
            cat.set('text', cfg.category)
            if cfg.subcategory:
                sub = ET.SubElement(cat, 'itunes:category')
                sub.set('text', cfg.subcategory)

        for ep in sorted(self.episodes, key=lambda e: e.number, reverse=True):
            item = ET.SubElement(channel, 'item')

            # URL und GUID immer aus aktueller Config neu berechnen
            # -> Aenderungen an base_url / media_url_path werden sofort uebernommen
            current_url  = self.compute_file_url(ep.file_path) if ep.file_path else ep.file_url
            current_guid = self.make_guid(ep.number)
            # Gespeicherte Werte aktualisieren
            ep.file_url = current_url
            ep.guid     = current_guid

            add(item, 'title',   ep.title or f"Folge {ep.number}")
            add(item, 'link',    ep.shownotes_url or cfg.base_url)
            add(item, 'pubDate', ep.pub_date)

            # GUID – stabil und eindeutig, basierend auf aktueller Base-URL
            guid_el = add(item, 'guid', current_guid)
            guid_el.set('isPermaLink', 'false')

            # <description>: Teaser-Text (plain text, kurz) fuer Podcast-Apps
            if ep.teaser:
                teaser_text = ep.teaser
            elif ep.description:
                teaser_text = self._html_to_text(ep.description)[:500]
            else:
                teaser_text = ep.title
            add(item, 'description', teaser_text)

            # <content:encoded>: Voller HTML-Inhalt, relative URLs zu absoluten
            if ep.description:
                clean_html = self._fix_relative_urls(ep.description, cfg.base_url)
                ce = ET.SubElement(item, 'content:encoded')
                ce.text = clean_html

            # Enclosure – die Audiodatei (immer aktuelle URL)
            enc = ET.SubElement(item, 'enclosure')
            enc.set('url',    current_url)
            enc.set('length', str(ep.file_size))
            enc.set('type',   'audio/mpeg')

            # iTunes-Felder
            add(item, 'itunes:title',       ep.title or f"Folge {ep.number}")
            add(item, 'itunes:author',      cfg.author)
            add(item, 'itunes:duration',    ep.duration or "00:00")
            add(item, 'itunes:explicit',    'true' if cfg.explicit == 'yes' else 'false')
            add(item, 'itunes:episode',     str(ep.number))
            add(item, 'itunes:episodeType', 'full')
            # itunes:summary: plain text, max 4000 Zeichen (iTunes-Limit)
            if ep.description:
                summary_plain = self._html_to_text(ep.description)
                if len(summary_plain) > 4000:
                    summary_plain = summary_plain[:3997] + '...'
                add(item, 'itunes:summary', summary_plain)

        xml_str = ET.tostring(rss, encoding='unicode', xml_declaration=False)
        dom = minidom.parseString(
            '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str
        )
        return dom.toprettyxml(indent='  ', encoding=None).replace(
            '<?xml version="1.0" ?>', '<?xml version="1.0" encoding="UTF-8"?>'
        )

    def save_feed(self):
        os.makedirs(self.config.output_directory, exist_ok=True)
        output_path = os.path.join(self.config.output_directory, self.config.feed_filename)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(self.generate_feed_xml())
        return output_path

    def get_episode_count(self):
        return len(self.episodes)

    def get_episode_numbers(self):
        return sorted([ep.number for ep in self.episodes])
