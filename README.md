# DWSK-feedgenerator
Generiert den Feed für daswarschonkaputt.de mit unserem Hugo Workflow

# Podcast Feed Generator

GTK4 + Adwaita Desktop-App für Linux
Erstellt und verwaltet RSS 2.0 + iTunes/Spotify-kompatible Podcast-Feeds.

---

## Funktionen

- **Neuen Podcast einrichten** – Alle Metadaten konfigurieren (Titel, Beschreibung, URLs, Cover-Bild …)
- **Episoden automatisch erkennen** – MP3-Dateien nach dem Schema `DWSK-Folge42.mp3` automatisch scannen
- **Shownotes laden** – Blog-RSS/Atom-Feed abrufen und Episodennummern automatisch zuordnen
- **Feed exportieren** – Vollständige `podcast.xml` mit iTunes + Spotify-Kompatibilität
- **Feed erweitern** – Neue Folgen zu bestehenden Feeds hinzufügen
- **Episoden verwalten** – Einzelne Folgen ansehen oder entfernen

---

## Systemvoraussetzungen (Fedora)

```bash
sudo dnf install python3-gobject gtk4 libadwaita
```

---

## Starten

```bash
chmod +x run.sh
./run.sh
```

Oder direkt:
```bash
python3 main.py
```

---

## Projektstruktur

```
podcast_feed_generator/
├── main.py                  # App-Einstiegspunkt
├── feed_manager.py          # Kernlogik: Feed, Episoden, XML
├── run.sh                   # Startskript mit Abhängigkeitsprüfung
├── podcast-feed-generator.desktop  # GNOME-App-Eintrag
├── ui/
│   ├── main_window.py       # Hauptfenster mit Navigation
│   ├── setup_page.py        # Übersicht & Feed exportieren
│   ├── episodes_page.py     # Episodenliste
│   ├── add_episodes_page.py # Folgen hinzufügen (Scan + Shownotes)
│   └── settings_page.py    # Alle Einstellungen
└── README.md
```

---

## Konfiguration

Die App speichert die Konfiguration unter:
```
~/.config/podcast-feed-generator/config.json
```

### Dateinamen-Schema

Standard: `DWSK-Folge42.mp3`
→ Präfix: `DWSK-Folge`
→ Episodennummer wird automatisch erkannt

Anpassbar in den Einstellungen unter **Dateinamen-Schema**.

---

## Generierter Feed

Der Feed ist kompatibel mit:
- ✅ Apple Podcasts (iTunes-Namespace)
- ✅ Spotify
- ✅ Pocket Casts, Overcast, und alle anderen Standard-Podcast-Apps
- ✅ RSS 2.0

---

## GNOME-Integration (optional)

```bash
# App global installieren
sudo mkdir -p /opt/podcast-feed-generator
sudo cp -r . /opt/podcast-feed-generator/

# Desktop-Eintrag installieren
cp podcast-feed-generator.desktop ~/.local/share/applications/
update-desktop-database ~/.local/share/applications/
```
