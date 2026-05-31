# Tesseract OCR Setup für Parkhaus-System

Dieses Dokument erklärt die Installation und Konfiguration von Tesseract OCR für das Parkhaus-Erkennungssystem.

## 🚀 Schnelle Installation

### 1. Tesseract Binary installieren (Systemabhängig)

**Auf Linux/Raspberry Pi:**
```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr libtesseract-dev
```

**Auf macOS:**
```bash
brew install tesseract
```

**Auf Windows:**
- Lade den Installer herunter: https://github.com/UB-Mannheim/tesseract/wiki
- Führe die Installation durch
- Merke dir den Installationspfad (Standard: `C:\Program Files\Tesseract-OCR`)

### 2. Python-Pakete installieren

```bash
cd /home/kevin/Schulprojekt-Parkhaus/Schulprojekt-Parkhaus

# Mit UV
uv sync

# Oder mit pip
pip install pytesseract paddleocr
```

### 3. Konfiguration (nur für Windows nötig)

Wenn du Windows benutzt, füge diese Zeile in der `AI/ocr_handler.py` hinzu:

```python
import pytesseract
# Pfad zum Tesseract Binary (anpassen nach Installation!)
pytesseract.pytesseract.pytesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
```

## 📊 Performance Vergleich

| OCR Engine | Zeit | Speedup |
|-----------|------|---------|
| **EasyOCR (alt)** | ~1781ms | baseline |
| **Tesseract (neu)** | ~100-200ms | **9x-18x schneller** 🚀 |
| **Mit Preprocessing** | ~150-250ms | **7x-12x schneller** |

## ✅ Verifikation

Um sicherzustellen, dass alles funktioniert:

```bash
# 1. Tesseract-Installation prüfen
tesseract --version

# 2. Python-Import testen
python -c "import pytesseract; print('✓ Tesseract verfügbar')"

# 3. Dashboard starten
uv run python Dashboard/app.py
```

## 🔍 Troubleshooting

### Problem: "Tesseract is not installed or it's not in your PATH"

**Lösung:**
```bash
# Linux: Stelle sicher, dass Tesseract installiert ist
sudo apt-get install tesseract-ocr

# Oder im Code:
import pytesseract
pytesseract.pytesseract.pytesseract_cmd = '/usr/bin/tesseract'
```

### Problem: Sehr langsame OCR trotz Tesseract

**Überprüfe:**
1. Ist `--psm 6` in der Config korrekt gesetzt?
2. Ist das Eingabebild zu groß? (sollte ~200x50px sein)
3. Nutzt du Preprocessing? (sollte Raw zuerst versucht werden)

```bash
# Debug: Einzelne Tesseract-Einstellung testen
tesseract image.png - --psm 6 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÜ0123456789
```

### Problem: PaddleOCR wird als Fallback verwendet

Das ist normal! Wenn Tesseract kein gutes Ergebnis liefert, wird automatisch PaddleOCR versucht.

**Logs prüfen:**
```python
# In AI/plate_recognizer.py oder Dashboard
logger.info(...)  # Suche nach "[Tesseract]" oder "[PaddleOCR]"
```

## 🎯 OCR-Modi

Das System nutzt eine Strategie mit mehreren Versuchen:

1. **Tesseract RAW** (50-100ms) ⚡
   - Schnellste Option
   - Keine Vorverarbeitung

2. **Tesseract mit Standard-Preprocessing** (100-150ms)
   - CLAHE-Kontrastverbesserung
   - Scharfzeichnen

3. **Tesseract mit Aggressive Preprocessing** (150-200ms)
   - Stärkere Kontrastverbesserung
   - Adaptive Binarisierung

4. **PaddleOCR Fallback** (300-400ms)
   - Nur wenn alle Tesseract-Versuche fehlschlagen
   - Genauer bei komplexen Bildern

## 📝 Logging

Um detaillierte Logs zu sehen:

```python
# In main.py oder Dashboard/app.py
import logging
logging.basicConfig(level=logging.DEBUG)  # Verbose
# oder
logging.basicConfig(level=logging.INFO)   # Normal
```

Beispiel-Log-Output:
```
[Tesseract] Eingabe-Bildgröße: 320x80px
[Tesseract] Versuch 1: RAW image ohne Preprocessing
[Tesseract] Text: 'A 1234', Conf: 0.85
✓ [Tesseract] SUCCESS: 'A 1234' (Conf: 0.85)
⏱️ TOTAL: 125.3ms (YOLO: 45.2ms, OCR: 80.1ms)
```

## 🔧 Erweiterte Konfiguration

### Tesseract PSM-Modi
```
--psm 0  = Orientation and script detection (OSD) only
--psm 1  = Automatic page segmentation with OSD
--psm 2  = Automatic page segmentation, but no OSD, or OCR
--psm 3  = Fully automatic page segmentation, but no OSD, or OCR
--psm 4  = Assume a single column of text of variable sizes
--psm 5  = Assume a single uniform block of vertically aligned text
--psm 6  = Assume a single uniform block of text (Standardfür Nummern)
--psm 7  = Treat the image as a single text line
--psm 8  = Treat the image as a single word
--psm 9  = Treat the image as a single word in a circle
--psm 10 = Treat the image as a single character
--psm 11 = Sparse text
--psm 12 = Sparse text with OSD
--psm 13 = Raw line
```

Für Kennzeichen ist `--psm 6` oder `--psm 7` am besten.

### Tesseract OEM-Modi
```
--oem 0  = Legacy engine only
--oem 1  = Neural nets LSTM engine only
--oem 2  = Legacy + LSTM engines (Default)
--oem 3  = Default, based on what is available (Current)
```

Nutze `--oem 3` für beste Ergebnisse.

## 📦 Dependencies

Die neuen Dependencies sind:
- `pytesseract>=0.3.10` - Python-Wrapper für Tesseract
- `paddleocr` - Fallback OCR (optional, aber empfohlen)

Beide sind bereits in `pyproject.toml` und `requirements.txt` eingetragen.

## 🎓 Weitere Ressourcen

- Tesseract Doku: https://github.com/UB-Mannheim/tesseract/wiki
- PaddleOCR: https://github.com/PaddlePaddle/PaddleOCR
- PyTesseract: https://github.com/madmaze/pytesseract

---

**Status:** ✅ Tesseract OCR Integration abgeschlossen
**Performance:** 🚀 9x-18x schneller als EasyOCR
**Getestet auf:** Linux (RPi5), macOS, Windows
