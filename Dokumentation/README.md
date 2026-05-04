# Schulprojekt-Parkhaus
In diesem Projekt wird eine Art Steuerung für ein Parkhaus mithilfe eines ESP32 und RaspberryPi5 programmiert. Es gibt ein Dashboard in dem alles angezeigt werden soll und der ESP32 soll die Schranke und die Ampel steuern.

## Raspberry Pi Kamera-Tool
Dieses Repository enthält außerdem `camera_capture.py`, ein Skript für die Raspberry Pi Kamera, um Bilder für dein YOLO-Training zu machen.

### Installation auf dem Pi
Die Hardware-spezifischen Pakete musst du auf dem Raspberry Pi selbst installieren, nachdem du das Repository geklont hast.

Empfohlen:
```bash
sudo apt update
sudo apt install -y python3-picamera2 python3-opencv
```

Falls du ein virtuelles Python-Environment verwenden möchtest, kannst du das so einrichten:

```bash
# Repository klonen
git clone <dein-repo-url>
cd Schulprojekt-Parkhaus

# Virtuelle Umgebung erzeugen
python3 -m venv venv

# Aktivieren (Linux / Raspberry Pi)
source venv/bin/activate

# Abhängigkeiten installieren
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

Wenn die virtuelle Umgebung aktiviert ist, sollte sich die Shell-Eingabe ändern und den Namen `venv` anzeigen. Zum Beispiel:

```bash
(venv) pi@raspberrypi:~/Schulprojekt-Parkhaus $
```

Zum Deaktivieren der `venv` verwendest du:

```bash
deactivate
```

`requirements.txt` enthält die reine Python-Abhängigkeit für OpenCV.

### Repository klonen und verwenden
Auf dem Pi kannst du dann das Repository klonen und das Skript starten:
```bash
git clone <dein-repo-url>
cd Schulprojekt-Parkhaus
source venv/bin/activate
python3 camera_capture.py
```
