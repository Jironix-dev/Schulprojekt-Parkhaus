# 🚨 Kennzeichen-Erkennungssystem

## Übersicht

Das Kennzeichen-Erkennungssystem integriert **YOLO-basierte Lokalisierung** mit **OCR (Tesseract)** zur automatischen Erkennung von Fahrzeug-Kennzeichen. Das System wurde vollständig in das Dashboard integriert und ermöglicht:

- ✅ **Live-Erkennung** aus dem Live-Feed
- ✅ **Upload-Erkennung** für einzelne Bilder
- ✅ **Snapshot-Erfassung** des ganzen Fahrzeugs
- ✅ **Kennzeichen-Ausschnitt** in hoher Qualität
- ✅ **Bounding Box Visualization** mit Rahmen
- ✅ **Konfidenz-Scores** für Erkennung und OCR
- ✅ **Statistiken** über Erkennungen

---

## 📁 Projektstruktur

```
AI/
├── __init__.py                    # Package Initialisierung
├── plate_recognizer.py            # Hauptmodul (YOLO + OCR)
├── image_processor.py             # Bildverarbeitung & Snapshots
├── ocr_handler.py                 # OCR mit Tesseract
├── plate_detection_models.py      # Datenklassen & Modelle
├── YOLO-Modell/
│   └── train/
│       └── weights/
│           └── best.pt            # Trainiertes YOLO-Modell
└── detection_results/             # Speicherort für Erkennungsergebnisse
    ├── snapshots/                 # Fahrzeug-Snapshots
    ├── plates/                    # Ausgeschnittene Kennzeichen
    └── annotated/                 # Bilder mit Bounding Boxes

backend/
└── services/
    └── plate_recognition_service.py   # Service für Dashboard-Integration
```

---

## 🔧 Installation & Setup

### 1. Abhängigkeiten installieren

Alle neuen Abhängigkeiten wurden zu `requirements.txt` hinzugefügt:

```bash
pip install -r requirements.txt
```

**Neue Pakete:**
- `ultralytics` - YOLO Framework
- `pytesseract` - Python Wrapper für Tesseract
- `pillow` - Bildverarbeitung
- `numpy` - Numerische Berechnungen

### 2. Tesseract OCR installieren

**Windows:**
```powershell
# Downloaden: https://github.com/UB-Mannheim/tesseract/wiki
# Oder mit Chocolatey:
choco install tesseract
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get install tesseract-ocr
```

**macOS:**
```bash
brew install tesseract
```

### 3. YOLO-Modell konfigurieren

Das trainierte YOLO-Modell muss sich unter folgendem Pfad befinden:
```
AI/YOLO-Modell/train/weights/best.pt
```

Das System versucht automatisch, das Modell zu laden. Falls es nicht gefunden wird, wird eine Warnung angezeigt.

---

## 🚀 Nutzung

### Im Dashboard

#### Live-Erkennung
1. Klicke auf den Button **"🔍 Jetzt erkennen"** im Recognition Panel
2. Das System erkennt das Kennzeichen im aktuellen Live-Feed
3. Ergebnisse werden sofort angezeigt

#### Bild-Upload
1. Klicke auf **"📤 Bild hochladen"**
2. Wähle ein Bild mit einem Fahrzeug aus
3. Das System verarbeitet das Bild und zeigt Ergebnisse

#### Details anzeigen
1. Klicke auf eines der Erkennungs-Bilder
2. Ein Modal öffnet sich mit:
   - Fahrzeug-Snapshot (großes Bild)
   - Ausgeschnittenes Kennzeichen
   - Annotiertes Bild mit Bounding Box
   - Detaillierte Konfidenz-Scores
   - Erkanntes Kennzeichen als Text

### Programmatische Nutzung

```python
from AI import PlateRecognizer
import cv2

# Initialisiere den Recognizer
recognizer = PlateRecognizer(conf_threshold=0.5)

# Lade ein Bild
frame = cv2.imread("path/to/image.jpg")

# Erkenne Kennzeichen
result = recognizer.detect_plate_in_frame(frame)

# Zugriff auf Ergebnisse
if result.success:
    print(f"Kennzeichen: {result.detected_plate}")
    print(f"YOLO Konfidenz: {result.plate_confidence:.2%}")
    print(f"OCR Konfidenz: {result.ocr_confidence:.2%}")
    print(f"Kombiniert: {result.get_combined_confidence():.2%}")
```

---

## 📊 API-Endpoints

### Erkennungs-Endpoints

#### 1. Live-Erkennung
```http
POST /api/recognition/detect-plate
```

**Response:**
```json
{
  "success": true,
  "detected_plate": "B-AB 1234",
  "plate_confidence": 0.95,
  "ocr_confidence": 0.92,
  "combined_confidence": 0.9383,
  "vehicle_snapshot": "data:image/jpeg;base64,...",
  "plate_image": "data:image/jpeg;base64,...",
  "annotated_frame": "data:image/jpeg;base64,...",
  "plate_region": {
    "x1": 100,
    "y1": 200,
    "x2": 300,
    "y2": 280,
    "confidence": 0.95,
    "width": 200,
    "height": 80
  },
  "timestamp": "2024-05-18T14:30:45.123456"
}
```

#### 2. Bild-Upload
```http
POST /api/recognition/upload-image
Content-Type: multipart/form-data

file: [JPEG/PNG image]
```

**Response:** Wie Live-Erkennung

#### 3. Statistiken
```http
GET /api/recognition/statistics
```

**Response:**
```json
{
  "status": "success",
  "statistics": {
    "total_detections": 42,
    "successful_detections": 38,
    "failed_detections": 4,
    "success_rate": 90.48,
    "average_plate_confidence": 0.935,
    "average_ocr_confidence": 0.892,
    "average_combined_confidence": 0.9194
  }
}
```

#### 4. Service Status
```http
GET /api/recognition/status
```

**Response:**
```json
{
  "service_ready": true,
  "status": "ready",
  "message": "Plate Recognition Service läuft"
}
```

#### 5. Statistiken zurücksetzen
```http
POST /api/recognition/reset-statistics
```

---

## 🎯 Erkanntes Kennzeichen Verarbeitung

### Konfidenz-Scores

Das System gibt zwei verschiedene Konfidenz-Scores zurück:

1. **YOLO Konfidenz** (0.0-1.0)
   - Wie sicher ist die Lokalisierung des Kennzeichens?
   - Basierend auf YOLO Object Detection
   - Wichtig für Bounding Box Genauigkeit

2. **OCR Konfidenz** (0.0-1.0)
   - Wie gut ist der erkannte Text?
   - Basierend auf Tesseract OCR Preprocessing
   - Höher = weniger Fehler beim Text

3. **Kombinierte Konfidenz** (Gewichtet)
   - Formel: `YOLO * 0.6 + OCR * 0.4`
   - Empfohlener Wert für Business-Logik

### Bildausgaben

Drei verschiedene Bilder werden zurückgegeben:

1. **vehicle_snapshot**
   - Komplettes Fahrzeug-Foto aus dem Frame
   - Verwendet für Dokumentation
   - Mit Metadaten-Overlay

2. **plate_image**
   - Ausgeschnittenes Kennzeichen
   - Höhere Auflösung für OCR
   - Mit Preprocessing optimiert

3. **annotated_frame**
   - Originalframe mit Bounding Box
   - Grüner Rahmen um erkanntes Kennzeichen
   - Mit Konfidenz-Text-Overlay

---

## ⚙️ Konfiguration

### Konfidenz-Schwellenwert

Setze den Schwellenwert für YOLO-Detektionen:

```python
from backend.services.plate_recognition_service import PlateRecognitionService

service = PlateRecognitionService.get_instance()
service.set_confidence_threshold(0.5)  # 50% Mindest-Konfidenz
```

### OCR Sprache

Standard ist Deutsch (`deu`). Um auf Englisch zu wechseln:

```python
from AI import OCRHandler

ocr = OCRHandler(lang='eng')  # 'eng' für Englisch
```

### Modell-Pfad

Manuell Modell-Pfad setzen:

```python
from AI import PlateRecognizer

recognizer = PlateRecognizer(
    model_path="/custom/path/to/best.pt",
    conf_threshold=0.6
)
```

---

## 📈 Statistiken & Metriken

Das System trackt automatisch:

- **Gesamterkennungen**: Anzahl aller Erkennungsversuche
- **Erfolgreiche Erkennungen**: Detektionen mit `success=true`
- **Fehlgeschlagene Erkennungen**: Detektionen mit `success=false`
- **Erfolgsrate**: Prozentsatz erfolgreicher Erkennungen
- **Durchschnittliche YOLO-Konfidenz**: Durchschnittliche Lokalisierungsgenauigkeit
- **Durchschnittliche OCR-Konfidenz**: Durchschnittliche Text-Erkennungsgenauigkeit
- **Durchschnittliche kombinierte Konfidenz**: Gesamtgenauigkeit

Statistiken können über Dashboard oder API abgerufen werden.

---

## 🐛 Troubleshooting

### Tesseract nicht gefunden

**Problem:** `TesseractNotFoundError`

**Lösung:**
1. Installiere Tesseract (siehe Installation)
2. Setze Umgebungsvariable (Windows):
```powershell
$env:TESSDATA_PREFIX = "C:\Program Files\Tesseract-OCR\tessdata"
```

### YOLO-Modell nicht geladen

**Problem:** Warning: "Modell nicht geladen"

**Lösung:**
1. Prüfe Pfad zu `best.pt`
2. Stelle sicher, dass Datei existiert: `AI/YOLO-Modell/train/weights/best.pt`
3. Überprüfe `ultralytics` Installation: `pip install --upgrade ultralytics`

### Schlechte OCR-Ergebnisse

**Problem:** Erkannte Text enthält Fehler

**Lösung:**
1. Verbessere Bildqualität (höhere Auflösung)
2. Erhöhe Kontrast mit `enhance_contrast()`
3. Nutze preprocessing mit `apply_morphological_ops()`
4. Überprüfe Kennzeichen-Format

### Schlecht erkannte Regionen

**Problem:** Bounding Box ist ungenau

**Lösung:**
1. Erhöhe YOLO-Konfidenz-Schwellenwert
2. Überprüfe YOLO-Modell-Training
3. Stelle sicher, dass Training-Daten repräsentativ sind

---

## 📝 Beispiel-Workflow

```python
import cv2
from AI import PlateRecognizer
from backend.services.plate_recognition_service import PlateRecognitionService

# 1. Lade Bild
frame = cv2.imread("parkhaus_capture.jpg")

# 2. Erkenne Kennzeichen
recognizer = PlateRecognizer()
result = recognizer.detect_plate_in_frame(frame)

# 3. Verarbeite Ergebnis
if result.success:
    plate_text = result.detected_plate
    confidence = result.get_combined_confidence()
    
    print(f"✓ Kennzeichen: {plate_text}")
    print(f"  Konfidenz: {confidence:.2%}")
    
    # 4. Speichere Bilder
    if result.plate_image is not None:
        cv2.imwrite(f"plate_{plate_text}.jpg", result.plate_image)
    
    if result.annotated_frame is not None:
        cv2.imwrite(f"annotated_{plate_text}.jpg", result.annotated_frame)
        
    # 5. Nutze im Dashboard
    service = PlateRecognitionService.get_instance()
    service.recognize_frame(frame)
    
else:
    print(f"✗ Fehler: {result.error}")
```

---

## 🔐 Performance-Tipps

1. **GPU-Beschleunigung** (falls NVIDIA GPU vorhanden):
   ```python
   recognizer = PlateRecognizer()
   recognizer.device = "cuda"
   ```

2. **Batch-Processing** für mehrere Frames:
   ```python
   frames = [frame1, frame2, frame3]
   results = recognizer.process_frame_batch(frames)
   ```

3. **Bildgröße anpassen** für schnellere Verarbeitung:
   ```python
   from AI import ImageProcessor
   
   processor = ImageProcessor()
   resized = processor.resize_image(frame, width=640)
   ```

---

## 📚 Module-Dokumentation

### PlateRecognizer
Hauptklasse für Kennzeichen-Erkennung mit YOLO + OCR.

**Methoden:**
- `detect_plate_in_frame(frame)` - Erkenne Kennzeichen in Frame
- `process_frame_batch(frames)` - Verarbeite mehrere Frames

### ImageProcessor
Bildverarbeitung und Snapshot-Verwaltung.

**Methoden:**
- `crop_region(frame, region)` - Schneide Region aus
- `save_snapshot()` - Speichere Fahrzeug-Snapshot
- `save_plate_image()` - Speichere Kennzeichen-Bild
- `enhance_contrast()` - Verbessere Bildkontrast
- `apply_morphological_ops()` - Morphologische Operationen

### OCRHandler
Optische Zeichenerkennung mit Tesseract.

**Methoden:**
- `extract_text(plate_image)` - Extrahiere Text aus Kennzeichen
- `_preprocess_image()` - Bildvorverarbeitung

### PlateRecognitionService
Service-Integration für Dashboard.

**Methoden:**
- `recognize_frame(frame)` - Erkenne und gebe JSON zurück
- `get_statistics()` - Gebe Statistiken zurück
- `reset_statistics()` - Setze Statistiken zurück

---

## 📄 Dateiübersicht

| Datei | Funktion |
|-------|----------|
| `plate_recognizer.py` | Zentrale Erkennungslogik |
| `image_processor.py` | Bildbearbeitung & Storage |
| `ocr_handler.py` | Tesseract-Integration |
| `plate_detection_models.py` | Datenstrukturen |
| `__init__.py` | Package-Exporte |
| `plate_recognition_service.py` | Dashboard-Service |

---

## 🎓 Weitere Ressourcen

- **YOLO Dokumentation**: https://docs.ultralytics.com/
- **Tesseract OCR**: https://github.com/tesseract-ocr/tesseract
- **OpenCV Doku**: https://docs.opencv.org/
- **pytesseract**: https://github.com/madmaze/pytesseract

---

**Version:** 1.0.0  
**Letztes Update:** 2024-05-18  
**Status:** ✅ Produktionsreif
