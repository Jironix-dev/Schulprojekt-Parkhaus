import re
import sys
from pathlib import Path

import cv2

# Try to import picamera2 (only available on Raspberry Pi)
try:
    from picamera2 import Picamera2
    PICAMERA2_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    PICAMERA2_AVAILABLE = False
    # Note: Falls picamera2 nicht verfügbar ist, nutze OpenCV fallback

IMAGE_DIR = Path("images")
IMAGE_PATTERN = re.compile(r"^(\d{4})\.jpg$")
IMAGE_FORMAT = "jpg"
IMAGE_WIDTH = 1280
IMAGE_HEIGHT = 720


def ensure_image_folder() -> Path:
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    return IMAGE_DIR


def get_next_image_index(image_dir: Path) -> int:
    highest = 0
    for path in image_dir.iterdir():
        if not path.is_file():
            continue
        match = IMAGE_PATTERN.match(path.name)
        if match:
            try:
                value = int(match.group(1))
            except ValueError:
                continue
            highest = max(highest, value)
    return highest + 1


def build_image_path(image_dir: Path, index: int) -> Path:
    filename = f"{index:04d}.{IMAGE_FORMAT}"
    return image_dir / filename


def add_overlay(frame, text: str) -> None:
    cv2.putText(
        frame,
        text,
        (10, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )


def trigger_autofocus(camera) -> None:
    """Triggert den Autofokus der Kamera neu (nur bei Picamera2)."""
    if not PICAMERA2_AVAILABLE:
        print("Autofokus nur auf Raspberry Pi verfügbar")
        return
    
    try:
        # AfMode 2 = Single-shot Autofokus, AfTrigger 1 = Trigger auslösen
        camera.set_controls({"AfMode": 2, "AfTrigger": 1})
        print("Autofokus wurde getriggert...")
    except Exception as e:
        print(f"Fehler beim Aktivieren des Autofokus: {e}")


def main() -> None:
    image_dir = ensure_image_folder()
    next_index = get_next_image_index(image_dir)

    if PICAMERA2_AVAILABLE:
        # Raspberry Pi mit picamera2
        print("Nutze Picamera2 (Raspberry Pi)...")
        picam2 = Picamera2()
        camera_config = picam2.create_preview_configuration(
            main={"size": (IMAGE_WIDTH, IMAGE_HEIGHT)}
        )
        picam2.configure(camera_config)
        
        # Autofokus vor dem Start aktivieren
        picam2.set_controls({"AfMode": 2})  # 2 = Continuous autofocus
        picam2.start()
        camera = picam2
    else:
        # Fallback: USB-Kamera mit OpenCV
        print("Nutze OpenCV mit USB-Kamera (Fallback für Linux/Windows)...")
        
        # Versuche verschiedene Kamera-Indizes (0, 1, 2...)
        camera = None
        for cam_index in range(5):
            print(f"Versuche Kamera-Index {cam_index}...")
            cap = cv2.VideoCapture(cam_index)
            if cap.isOpened():
                # Prüfe ob tatsächlich ein Frame gelesen werden kann
                ret, _ = cap.read()
                if ret:
                    print(f"✓ Kamera gefunden bei Index {cam_index}")
                    camera = cap
                    break
                else:
                    print(f"  Kamera {cam_index} kann nicht lesen")
                    cap.release()
            else:
                print(f"  Index {cam_index} nicht verfügbar")
        
        if camera is None:
            print("ERROR: Keine funktionierende Kamera gefunden!")
            print("Tipps:")
            print("1. USB-Kamera angeschlossen?")
            print("2. Kamera-Berechtigung überprüfen: ls -la /dev/video*")
            print("3. Versuche: v4l2-ctl --list-devices")
            return
        
        # Kamera-Auflösung setzen
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, IMAGE_WIDTH)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, IMAGE_HEIGHT)
        camera.set(cv2.CAP_PROP_FPS, 30)
        
        print(f"Kamera-Einstellungen: {int(camera.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(camera.get(cv2.CAP_PROP_FRAME_HEIGHT))}")

    window_name = "Live Feed - Drücke ENTER zum Speichern, F für Autofokus, ESC zum Beenden"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    try:
        while True:
            if PICAMERA2_AVAILABLE:
                frame = camera.capture_array()
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            else:
                ret, frame = camera.read()
                if not ret:
                    print("ERROR: Frame konnte nicht gelesen werden!")
                    break
                rgb_frame = frame

            add_overlay(rgb_frame, f"Bild {next_index:04d} | ENTER=Speichern | F=Autofokus | ESC=Beenden")
            cv2.imshow(window_name, rgb_frame)

            key = cv2.waitKey(10) & 0xFF
            if key == 27:  # ESC
                print("Programm wird beendet...")
                break
            if key in (13, 10):  # ENTER
                image_path = build_image_path(image_dir, next_index)
                saved = cv2.imwrite(str(image_path), rgb_frame)
                if saved:
                    print(f"Bild gespeichert: {image_path}")
                    next_index += 1
                else:
                    print(f"Fehler beim Speichern von {image_path}")
            if key == ord("f") or key == ord("F"):  # F-Taste für Autofokus
                trigger_autofocus(camera)
    finally:
        if PICAMERA2_AVAILABLE:
            camera.close()
        else:
            camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
