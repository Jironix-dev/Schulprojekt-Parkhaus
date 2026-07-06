# 🚗 Schulprojekt-Parkhaus - Startanleitung

## ✅ Status: Vollständig konfiguriert mit UV + Python 3.11

### 📋 Was wurde eingerichtet:
- ✅ **UV Paketmanager** installiert (v0.11.13)
- ✅ **Python 3.11** konfiguriert (in `.python-version`)
- ✅ **Virtuelle Umgebung** (.venv) erstellt
- ✅ **Alle Abhängigkeiten** installiert:
  - FastAPI
  - Uvicorn (Server)
  - Jinja2
  - OpenCV
  - Und alle weiteren Dependencies
- ✅ **Datenbank** vollständig initialisiert
- ✅ **Dashboard** getestet und funktionsfähig

---

## 🚀 Dashboard starten

### Option 1: Mit dem Start-Script (einfach)
```bash
./start.sh
```

### Option 2: Manuell
```bash
# UV PATH aktivieren
source $HOME/.local/bin/env

# Dashboard starten
uv run python Dashboard/app.py
```

Das Dashboard läuft dann auf: **http://localhost:8000**

---

## 📦 UV Kommandos für dein Projekt

### Neue Abhängigkeit installieren
```bash
uv add package-name
```

### Alle Abhängigkeiten synchronisieren
```bash
uv sync
```

### Python-Skript mit UV ausführen
```bash
uv run python script.py
```

### In der virtuellen Umgebung arbeiten
```bash
source .venv/bin/activate
```

---

## 🗄️ Datenbank verwenden

### Datenbank neu initialisieren
```bash
uv run python init_database.py
```

Die Datenbank wird in `data/parkhaus.db` gespeichert.

---

## 📂 Projektstruktur
```
├── Dashboard/           # FastAPI Dashboard
│   ├── app.py          # Main App
│   ├── routes.py       # API Routes
│   ├── livefeed.py     # Live Feed
│   └── templates/      # HTML Templates
├── backend/            # Backend Services
│   ├── database/       # Database Layer
│   └── services/       # Business Logic
├── data/               # Datenbank & Daten
├── pyproject.toml      # Project Config
├── uv.lock             # Lock File
└── requirements.txt    # Alte Abhängigkeiten
```

---

## ✨ Das ist bereit zum Einsatz!

Dein Parkhaus-System ist vollständig eingerichtet und ready to go! 🎉

Viel Spaß beim Projekt!
