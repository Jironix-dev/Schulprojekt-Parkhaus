# 🚀 Setup-Anleitung: Kennzeichen-Erkennungssystem

Dein Kennzeichen-Erkennungssystem ist nun vollständig implementiert! Hier ist die Schritt-für-Schritt Setup-Anleitung.

## ✅ Was wurde implementiert

### 1. **AI-Module** (im Ordner `AI/`)
- ✅ `plate_recognizer.py` - YOLO + OCR Integration
- ✅ `image_processor.py` - Bildbearbeitung und Snapshots
- ✅ `ocr_handler.py` - Tesseract OCR mit Preprocessing
- ✅ `plate_detection_models.py` - Datenstrukturen
- ✅ `__init__.py` - Package-Exporte

### 2. **Backend-Service**
- ✅ `backend/services/plate_recognition_service.py` - Dashboard Integration

### 3. **Dashboard-Integration**
- ✅ Neue Routes in `Dashboard/routes.py`
- ✅ Recognition Panel in `Dashboard/templates/index.html`
- ✅ CSS Styles in `Dashboard/static/style.css`
- ✅ JavaScript Functions in `Dashboard/static/script.js`

### 4. **API-Endpoints**
- ✅ `POST /api/recognition/detect-plate` - Live-Feed Erkennung
- ✅ `POST /api/recognition/upload-image` - Bild-Upload
- ✅ `GET /api/recognition/status` - Service Status
- ✅ `GET /api/recognition/statistics` - Erkennungs-Statistiken
- ✅ `POST /api/recognition/reset-statistics` - Statistiken zurücksetzen

### 5. **Tools & Tests**
- ✅ `AI/demo_recognition.py` - 5 Demo-Beispiele
- ✅ `AI/test_integration.py` - Integrations-Tests
- ✅ `AI/README.md` - Modul-Dokumentation
- ✅ `Dokumentation/KENNZEICHEN_ERKENNUNGSSYSTEM.md` - Vollständige Dokumentation

---

## 📋 Installation

### **Schritt 1: Dependencies installieren**

```bash
# Wechsle zum Projekt-Verzeichnis
cd Schulprojekt-Parkhaus

# Aktiviere Virtual Environment
.\.venv\Scripts\Activate.ps1

# Installiere Abhängigkeiten
pip install -r requirements.txt
```

**Neu installierte Pakete:**
- `ultralytics` - YOLO Framework
- `pytesseract` - Python OCR Wrapper
- `pillow` - Bildverarbeitung
- `numpy` - Numerische Berechnungen

### **Schritt 2: Tesseract OCR installieren**

**Windows:**
1. Gehe zu: https://github.com/UB-Mannheim/tesseract/wiki
2. Downloade und installiere das neueste Tesseract-Installer
3. Oder mit Chocolatey:
```powershell
choco install tesseract
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr
```

**macOS:**
```bash
brew install tesseract
```

### **Schritt 3: YOLO-Modell einrichten**

Kopiere dein trainiertes `best.pt` Modell hier hin:
```
AI/YOLO-Modell/train/weights/best.pt
```

Falls der Ordner nicht existiert, erstelle ihn:
```powershell
mkdir -Path "AI/YOLO-Modell/train/weights" -Force
```

### **Schritt 4: System testen**

Führe die Integrations-Tests durch:
```bash
python AI/test_integration.py
```

**Erwartetes Ergebnis:**
```
[1] Teste Imports... ✓ PASS
[2] Teste YOLO Loading... ✓ PASS
[3] Teste Tesseract OCR... ✓ PASS
[4] Teste Datenmodelle... ✓ PASS
[5] Teste ImageProcessor... ✓ PASS
[6] Teste Singleton Pattern... ✓ PASS
[7] Teste API Endpoints... ✓ PASS

Gesamt: 7/7 Tests bestanden
✓ Alle Tests bestanden! System ist einsatzbereit.
```

---

## 🎬 Erste Schritte

### **Option 1: Dashboard starten**

```bash
# Starte das Dashboard
python Dashboard/app.py
```

Öffne Browser: http://localhost:8000

**Im Dashboard:**
1. Gehe zur Erkennungs-Panel (unter dem Live-Feed)
2. Klick auf **"🔍 Jetzt erkennen"** für Live-Erkennung
3. Oder **"📤 Bild hochladen"** um ein Bild hochzuladen
4. Klick auf das Ergebnis für **Details-Modal**

### **Option 2: Demo ausführen**

```bash
python AI/demo_recognition.py
```

Die Demo zeigt:
- ✅ Demo 1: Grundlegende Erkennung mit YOLO
- ✅ Demo 2: Bildverarbeitung & Preprocessing
- ✅ Demo 3: OCR-Funktionalität
- ✅ Demo 4: Statistiken-Tracking
- ✅ Demo 5: API-Integration

### **Option 3: Python-Script verwenden**

```python
from AI import PlateRecognizer
import cv2

# Lade Bild
frame = cv2.imread("parkhaus_foto.jpg")

# Erkenne Kennzeichen
recognizer = PlateRecognizer()
result = recognizer.detect_plate_in_frame(frame)

# Gebe Ergebnis aus
if result.success:
    print(f"✓ Kennzeichen: {result.detected_plate}")
    print(f"  YOLO Konfidenz: {result.plate_confidence:.2%}")
    print(f"  OCR Konfidenz: {result.ocr_confidence:.2%}")
    print(f"  Kombiniert: {result.get_combined_confidence():.2%}")
else:
    print(f"✗ Fehler: {result.error}")
```

---

## 🎨 Dashboard Features

### **Recognition Panel** (unter Live-Feed)

```
┌─────────────────────────────────┐
│ 🚨 Kennzeichen-Erkennung       │
├─────────────────────────────────┤
│ [🔍 Jetzt erkennen] [📤 Upload] │
├─────────────────────────────────┤
│ Erkanntes Kennzeichen: B-AB 1234│
│ YOLO Konfidenz: 95%             │
│ OCR Konfidenz: 92%              │
│ Kombiniert: 93.8%               │
└─────────────────────────────────┘
```

### **Details-Modal**

Zeigt:
- 📷 Fahrzeug-Snapshot (ganzes Auto)
- 📸 Ausgeschnittenes Kennzeichen
- 🔲 Annotiertes Bild mit Bounding Box
- 📊 Detaillierte Informationen (Koordinaten, Zeitstempel, etc.)

---

## 📊 API-Beispiele

### **Erkennung im Live-Feed**
```bash
curl -X POST http://localhost:8000/api/recognition/detect-plate
```

### **Bild hochladen**
```bash
curl -X POST -F "file=@image.jpg" http://localhost:8000/api/recognition/upload-image
```

### **Service-Status prüfen**
```bash
curl http://localhost:8000/api/recognition/status
```

**Response:**
```json
{
  "service_ready": true,
  "status": "ready",
  "message": "Plate Recognition Service läuft"
}
```

### **Statistiken abrufen**
```bash
curl http://localhost:8000/api/recognition/statistics
```

---

## 📁 Dateistruktur

```
Schulprojekt-Parkhaus/
├── AI/                                    # ← ALLE ERKENNUNGS-MODULE
│   ├── __init__.py
│   ├── plate_recognizer.py               # Hauptmodul
│   ├── image_processor.py                # Bildbearbeitung
│   ├── ocr_handler.py                    # OCR
│   ├── plate_detection_models.py         # Datenmodelle
│   ├── demo_recognition.py               # Demo
│   ├── test_integration.py               # Tests
│   ├── README.md                         # Modul-Doku
│   ├── YOLO-Modell/
│   │   └── train/
│   │       └── weights/
│   │           └── best.pt               # ← DEIN MODELL
│   └── detection_results/                # Output-Verzeichnis
│       ├── snapshots/
│       ├── plates/
│       └── annotated/
│
├── Dashboard/
│   ├── app.py
│   ├── routes.py                         # ← NEUE ENDPOINTS
│   ├── templates/
│   │   └── index.html                    # ← RECOGNITION PANEL
│   └── static/
│       ├── style.css                     # ← NEU: Recognition Styles
│       └── script.js                     # ← NEU: Recognition Functions
│
├── backend/
│   └── services/
│       └── plate_recognition_service.py  # ← NEU: Service
│
└── Dokumentation/
    ├── KENNZEICHEN_ERKENNUNGSSYSTEM.md   # ← VOLLSTÄNDIGE DOKU
    └── ...
```

---

## ⚙️ Konfiguration

### **YOLO Konfidenz-Schwellenwert**

Setze in `plate_recognizer.py`:
```python
recognizer = PlateRecognizer(conf_threshold=0.5)  # 0.0-1.0
```

Höher = strenger, weniger false positives  
Niedriger = lockerer, mehr Erkennungen

### **OCR Sprache**

Standard ist Deutsch (`deu`). Für andere Sprachen:
```python
from AI import OCRHandler
ocr = OCRHandler(lang='eng')  # Englisch
```

Verfügbare Sprachen: `eng`, `deu`, `fra`, `ita`, `ita_old`, `spa`, etc.

### **GPU-Beschleunigung**

Falls NVIDIA GPU vorhanden:
```python
recognizer = PlateRecognizer()
recognizer.device = "cuda"  # Statt "cpu"
```

---

## 🐛 Troubleshooting

### **Problem: "Tesseract not found"**

```python
# Windows: Pfad manuell setzen
import pytesseract
pytesseract.pytesseract.pytesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
```

### **Problem: YOLO-Modell wird nicht geladen**

1. Prüfe Pfad: `AI/YOLO-Modell/train/weights/best.pt`
2. Upgrade ultralytics: `pip install --upgrade ultralytics`
3. Führe Tests aus: `python AI/test_integration.py`

### **Problem: Schlechte OCR-Ergebnisse**

- Nutze höhere Bildauflösung
- Verbessere Kontrast
- Nutze Preprocessing mit `enhance_contrast()` und `apply_morphological_ops()`

### **Problem: Erkennungen sind langsam**

- Nutze GPU (`device="cuda"`)
- Verkleinere Input-Größe
- Erhöhe `conf_threshold` um false positives zu vermeiden

---

## 📚 Dokumentation

### **Kurz-Dokumentation**
- `AI/README.md` - Modul-Übersicht
- `AI/demo_recognition.py` - Praktische Beispiele

### **Vollständige Dokumentation**
- `Dokumentation/KENNZEICHEN_ERKENNUNGSSYSTEM.md`

Enthält:
- Detailliertes Setup
- API-Referenz
- Konfigurationsoptionen
- Troubleshooting
- Performance-Tipps
- Code-Beispiele

---

## ✅ Checkliste

Nach dem Setup solltest du überprüfen:

- [ ] Python 3.8+ installiert
- [ ] Virtual Environment aktiviert
- [ ] Abhängigkeiten installiert (`pip install -r requirements.txt`)
- [ ] Tesseract OCR installiert
- [ ] `best.pt` im richtigen Ordner
- [ ] Integrations-Tests bestanden (`python AI/test_integration.py`)
- [ ] Dashboard startet (`python Dashboard/app.py`)
- [ ] Recognition Panel ist im Dashboard sichtbar
- [ ] Live-Erkennung funktioniert
- [ ] Bild-Upload funktioniert

---

## 🎯 Nächste Schritte

1. **Test:** Führe `test_integration.py` aus
2. **Demo:** Führe `demo_recognition.py` aus
3. **Dashboard:** Starte Dashboard und teste Erkennungs-Panel
4. **Integration:** Integriere mit deiner Business-Logik
5. **Optimierung:** Tune YOLO und OCR Parameter

---

## 📞 Support

Bei Fragen:
1. Überprüfe die Dokumentation: `Dokumentation/KENNZEICHEN_ERKENNUNGSSYSTEM.md`
2. Führe Tests aus: `python AI/test_integration.py`
3. Starte Demo: `python AI/demo_recognition.py`
4. Check Logs im Dashboard

---

**Status:** ✅ Vollständig implementiert und einsatzbereit!

**Version:** 1.0.0  
**Erstellt:** 2024-05-18  
**Autor:** GitHub Copilot
