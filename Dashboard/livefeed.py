"""
Hochoptimierter Live-Feed Handler für RPi - Stabil und flüssig
- Adaptive Framerate je nach Kameratyp
- Background-Thread nur für USB-Kameras (Picamera2 ist nativ schnell)
- Bessere Timing-Kontrolle und Fehlerbehandlung
- Motion JPEG Stream optimiert für Bandbreite
"""

from __future__ import annotations

import cv2
import numpy as np
from typing import Optional, Generator, Any, Callable
import time
import threading
import platform

# Try to import picamera2 (only available on Raspberry Pi)
try:
    from picamera2 import Picamera2
    PICAMERA2_AVAILABLE = True
    print("[LiveFeed] ✓ picamera2 importiert!")
except (ImportError, ModuleNotFoundError) as e:
    PICAMERA2_AVAILABLE = False
    Picamera2 = None  # type: ignore

# Kamera-Konfiguration
# Optimiert für flüssiges Streaming mit guter Qualität
IMAGE_WIDTH = 1280      # Full HD width behalten
IMAGE_HEIGHT = 720      # Full HD height behalten
JPEG_QUALITY = 65       # Vernünftige Kompression
TARGET_FPS = 20         # 20 FPS für stabile Performance
AUTO_DETECTION_INTERVAL = 1.0
AUTO_PRESENCE_CHECK_INTERVAL = 0.75
AUTO_ABSENCE_CONFIRMATIONS = 2
AUTO_BOX_TTL = 2.5
AUTO_PLATE_COOLDOWN = 20.0
AUTO_INVALID_RETRY_INTERVAL = 5.0


class LiveFeedHandler:
    """Hochoptimiert für flüssiges Streaming mit weniger Ruckeln"""
    
    def __init__(self):
        self.camera_active = False
        self.frame: Optional[bytes] = None
        self.frame_lock = threading.Lock()
        self.camera: Optional[Any] = None
        self.running = False
        self.fallback_frame: bytes = b''
        self.last_frame_time = 0.0
        self.frame_count = 0
        self.is_usb_camera = False
        self.capture_thread: Optional[threading.Thread] = None
        self.auto_detection_enabled = True
        self.auto_detection_callback: Optional[Callable[[dict], None]] = None
        self.auto_detection_lock = threading.Lock()
        self.last_auto_detection_time = 0.0
        self.last_presence_check_time = 0.0
        self.plate_presence_locked = False
        self.plate_absence_count = 0
        self.last_box_until = 0.0
        self.last_plate_region: Optional[dict] = None
        self.last_auto_result: dict = {
            "status": "waiting",
            "detected_plate": "",
            "plate_confidence": 0.0,
            "ocr_confidence": 0.0,
            "combined_confidence": 0.0,
            "plate_valid": None,
            "timestamp": "",
            "error": ""
        }
        self.last_auto_image_result: dict = {}
        self.last_processed_plate = ""
        self.last_processed_plate_time = 0.0
        
        self._init_fallback_frame()
        self._init_camera()
        
        # Starte Background-Thread NUR für USB-Kameras
        if self.camera is not None and self.is_usb_camera:
            self._start_capture_thread()
            print("[LiveFeed] ✓ Background-Thread für USB-Kamera gestartet")
        elif self.camera is not None and PICAMERA2_AVAILABLE:
            print("[LiveFeed] ✓ Picamera2 lädt Frames direkt (kein Thread nötig)")
    
    def _init_fallback_frame(self) -> None:
        """Erstellt Fallback-Frame wenn Kamera nicht aktiv ist"""
        try:
            fallback = np.zeros((IMAGE_HEIGHT, IMAGE_WIDTH, 3), dtype=np.uint8)
            font = cv2.FONT_HERSHEY_SIMPLEX
            text = "Kamera inaktiv"
            font_scale = 1.5
            color = (255, 255, 255)
            thickness = 2
            
            text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
            x = (IMAGE_WIDTH - text_size[0]) // 2
            y = (IMAGE_HEIGHT - text_size[1]) // 2 + text_size[1]
            
            cv2.putText(fallback, text, (x, y), font, font_scale, color, thickness)
            
            success, jpeg = cv2.imencode('.jpg', fallback, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
            if success:
                self.fallback_frame = jpeg.tobytes()
                print(f"[LiveFeed] ✓ Fallback-Frame erstellt ({len(self.fallback_frame)} bytes)")
        except Exception as e:
            print(f"[LiveFeed] ✗ Fehler bei Fallback-Frame: {e}")
            self.fallback_frame = b''
    
    def _init_camera(self) -> None:
        """Initialisiert die Kamera"""
        try:
            if PICAMERA2_AVAILABLE and Picamera2 is not None:
                print("[LiveFeed] Nutze Picamera2 (Raspberry Pi)...")
                self.camera = Picamera2()
                
                # Optimierte Config für Performance
                config = self.camera.create_preview_configuration(
                    main={"size": (IMAGE_WIDTH, IMAGE_HEIGHT)},
                    buffer_count=2  # Double buffering für smoothness
                )
                self.camera.configure(config)
                self.camera.set_controls({"AfMode": 2})  # Autofocus
                self.camera.start()
                
                self.camera_active = True
                self.is_usb_camera = False
                print(f"[LiveFeed] ✓ Picamera2 aktiviert ({IMAGE_WIDTH}x{IMAGE_HEIGHT})")
            else:
                # OpenCV Fallback für USB-Kamera
                print("[LiveFeed] Suche USB-Kamera...")
                camera = None
                for idx in range(5):
                    if platform.system() == "Windows":
                        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
                    else:
                        cap = cv2.VideoCapture(idx)
                    if cap.isOpened():
                        ret, _ = cap.read()
                        if ret:
                            print(f"[LiveFeed] ✓ Kamera Index {idx} gefunden!")
                            camera = cap
                            break
                        cap.release()
                
                if camera is None:
                    print("[LiveFeed] ✗ Keine Kamera gefunden - Fallback aktiv")
                    self.camera_active = False
                    return
                
                # USB-Kamera Settings
                camera.set(cv2.CAP_PROP_FRAME_WIDTH, IMAGE_WIDTH)
                camera.set(cv2.CAP_PROP_FRAME_HEIGHT, IMAGE_HEIGHT)
                camera.set(cv2.CAP_PROP_FPS, 30)
                camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimize latency
                camera.set(cv2.CAP_PROP_AUTOFOCUS, 1)
                
                self.camera = camera
                self.camera_active = True
                self.is_usb_camera = True
                print(f"[LiveFeed] ✓ USB-Kamera aktiviert ({IMAGE_WIDTH}x{IMAGE_HEIGHT})")
        
        except Exception as e:
            print(f"[LiveFeed] ✗ Fehler: {e}")
            self.camera_active = False
    
    def _start_capture_thread(self) -> None:
        """Starte Background-Thread für USB-Kameras"""
        self.running = True
        self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.capture_thread.start()
    
    def _capture_loop(self) -> None:
        """Background-Thread: USB-Capture + JPEG Encoding"""
        frame_time = 1.0 / 30  # 30 FPS capture rate
        
        while self.running and self.camera is not None and self.is_usb_camera:
            try:
                start = time.time()
                
                # Capture Frame von USB-Kamera
                ret, frame = self.camera.read()  # type: ignore
                if not ret:
                    time.sleep(0.01)
                    continue

                stream_frame = self._process_frame_for_stream(frame)
                
                # JPEG Encoding - vernünftige Settings
                success, jpeg = cv2.imencode('.jpg', stream_frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
                if success:
                    with self.frame_lock:
                        self.frame = jpeg.tobytes()
                        self.last_frame_time = time.time()
                        self.frame_count += 1
                
                # Stabiles Timing
                elapsed = time.time() - start
                sleep_time = max(0.001, frame_time - elapsed)
                time.sleep(sleep_time)
                
            except Exception as e:
                print(f"[LiveFeed] Capture-Fehler: {e}")
                time.sleep(0.05)

    def set_auto_detection_callback(self, callback: Callable[[dict], None]) -> None:
        """Registriert die bestehende Dashboard-Verarbeitung für Auto-Erkennungen."""
        self.auto_detection_callback = callback

    def get_auto_detection_state(self) -> dict:
        """Gibt den letzten automatischen Erkennungsstatus zurück."""
        with self.frame_lock:
            state = dict(self.last_auto_result)
            state["auto_detection_enabled"] = self.auto_detection_enabled
            state["box_visible"] = bool(self.last_plate_region and time.time() < self.last_box_until)
            state["waiting_for_plate_to_leave"] = self.plate_presence_locked
            return state

    def get_latest_detection_result(self) -> dict:
        """Gibt den letzten vollständigen Erkennungs-Result inklusive Bildern zurück."""
        with self.frame_lock:
            return dict(self.last_auto_image_result)

    def _process_frame_for_stream(self, frame: np.ndarray) -> np.ndarray:
        """
        Prüft den Live-Frame gedrosselt mit YOLO/OCR und zeichnet die letzte Box ein.
        Die eigentliche Einfahrt/Ausfahrt-Logik wird per Callback aus routes.py genutzt.
        """
        if frame is None or frame.size == 0:
            return frame

        now = time.time()
        interval = AUTO_PRESENCE_CHECK_INTERVAL if self.plate_presence_locked else AUTO_DETECTION_INTERVAL
        last_check_time = self.last_presence_check_time if self.plate_presence_locked else self.last_auto_detection_time

        if (
            self.auto_detection_enabled
            and now - last_check_time >= interval
            and self.auto_detection_lock.acquire(blocking=False)
        ):
            try:
                if self.plate_presence_locked:
                    self.last_presence_check_time = now
                    self._run_plate_presence_check(frame)
                else:
                    self.last_auto_detection_time = now
                    self._run_auto_detection(frame)
            finally:
                self.auto_detection_lock.release()

        return self._draw_latest_plate_box(frame)

    def _run_auto_detection(self, frame: np.ndarray) -> None:
        """Fuehrt den vorhandenen YOLO -> OCR Ablauf auf einem Live-Frame aus."""
        try:
            from backend.services.plate_recognition_service import PlateRecognitionService

            plate_service = PlateRecognitionService.get_instance()
            if not plate_service.is_ready():
                self._set_auto_result({
                    "status": "not_ready",
                    "detected_plate": "",
                    "error": "Plate Recognition Service nicht bereit"
                })
                return

            result = plate_service.recognize_frame(frame)
            self._update_box_from_result(result)

            detected_plate = (result.get("detected_plate") or "").strip()
            if detected_plate:
                result["status"] = "detected"
                self.plate_presence_locked = True
                self.plate_absence_count = 0
                self.last_presence_check_time = time.time()
                self._set_auto_result(result)
            else:
                self._set_auto_result({
                    "status": "searching",
                    "detected_plate": "",
                    "plate_confidence": 0.0,
                    "ocr_confidence": 0.0,
                    "combined_confidence": 0.0,
                    "plate_valid": None,
                    "timestamp": result.get("timestamp", ""),
                    "error": result.get("error", "")
                })
                return

            if result.get("success") and self._should_process_plate(detected_plate):
                self.last_processed_plate = detected_plate
                self.last_processed_plate_time = time.time()
                if self.auto_detection_callback:
                    self.auto_detection_callback(result)
                    self._set_auto_result(result)
        except Exception as e:
            print(f"[LiveFeed] Auto-Erkennung Fehler: {e}")
            self._set_auto_result({
                "status": "error",
                "detected_plate": "",
                "error": str(e)
            })

    def _run_plate_presence_check(self, frame: np.ndarray) -> None:
        """Prueft ohne OCR, ob das erkannte Kennzeichen/Fahrzeug noch im Live-Feed ist."""
        try:
            from backend.services.plate_recognition_service import PlateRecognitionService

            plate_service = PlateRecognitionService.get_instance()
            presence = plate_service.detect_plate_presence(frame)

            if presence.get("present"):
                self.plate_absence_count = 0
                self._update_box_from_result(presence)
                if self._should_retry_invalid_plate():
                    self.last_auto_detection_time = time.time()
                    self._run_auto_detection(frame)
                    return
                with self.frame_lock:
                    self.last_auto_result["status"] = "occupied"
                    self.last_auto_result["plate_confidence"] = presence.get(
                        "plate_confidence",
                        self.last_auto_result.get("plate_confidence", 0.0)
                    )
                    self.last_auto_result["error"] = ""
                return

            self.plate_absence_count += 1
            if self.plate_absence_count >= AUTO_ABSENCE_CONFIRMATIONS:
                self._release_auto_detection_after_plate_left()
        except Exception as e:
            print(f"[LiveFeed] Presence-Check Fehler: {e}")

    def _release_auto_detection_after_plate_left(self) -> None:
        """Gibt die volle Erkennung frei, sobald das letzte Kennzeichen aus dem Bild ist."""
        self.plate_presence_locked = False
        self.plate_absence_count = 0
        self.last_auto_detection_time = 0.0
        with self.frame_lock:
            self.last_plate_region = None
            self.last_box_until = 0.0
        self._set_auto_result({
            "status": "searching",
            "detected_plate": "",
            "plate_confidence": 0.0,
            "ocr_confidence": 0.0,
            "combined_confidence": 0.0,
            "plate_valid": None,
            "timestamp": "",
            "error": ""
        })

    def _set_auto_result(self, result: dict) -> None:
        """Speichert einen kompakten Status fuer das Frontend."""
        with self.frame_lock:
            previous_result = dict(self.last_auto_result)

        parking_flow = result.get("parking_flow")
        if (
            not parking_flow
            and result.get("detected_plate")
            and result.get("detected_plate") == previous_result.get("detected_plate")
        ):
            parking_flow = previous_result.get("parking_flow")

        compact_result = {
            "status": result.get("status", "detected" if result.get("detected_plate") else "searching"),
            "detected_plate": result.get("detected_plate", ""),
            "raw_detected_plate": result.get("raw_detected_plate", result.get("detected_plate", "")),
            "plate_confidence": result.get("plate_confidence", 0.0),
            "ocr_confidence": result.get("ocr_confidence", 0.0),
            "combined_confidence": result.get("combined_confidence", 0.0),
            "plate_valid": result.get("plate_valid"),
            "timestamp": result.get("timestamp", ""),
            "error": result.get("error", ""),
            "parking_flow": parking_flow
        }
        with self.frame_lock:
            self.last_auto_result = compact_result
            if self._result_has_images(result):
                self.last_auto_image_result = self._build_image_result(result)

    def _result_has_images(self, result: dict) -> bool:
        """Prüft, ob ein Erkennungsresultat die Bilddaten fuer das Widget enthält."""
        return any(result.get(key) for key in ("vehicle_snapshot", "annotated_frame", "plate_image"))

    def _build_image_result(self, result: dict) -> dict:
        """Reduziert das vollständige Resultat auf die Daten, die das Widget anzeigen soll."""
        return {
            "success": result.get("success", False),
            "status": result.get("status", "detected"),
            "detected_plate": result.get("detected_plate", ""),
            "raw_detected_plate": result.get("raw_detected_plate", result.get("detected_plate", "")),
            "plate_confidence": result.get("plate_confidence", 0.0),
            "ocr_confidence": result.get("ocr_confidence", 0.0),
            "combined_confidence": result.get("combined_confidence", 0.0),
            "timestamp": result.get("timestamp", ""),
            "error": result.get("error", ""),
            "plate_valid": result.get("plate_valid"),
            "plate_region": result.get("plate_region"),
            "vehicle_snapshot": result.get("vehicle_snapshot", ""),
            "annotated_frame": result.get("annotated_frame", ""),
            "plate_image": result.get("plate_image", ""),
            "parking_flow": result.get("parking_flow")
        }

    def _update_box_from_result(self, result: dict) -> None:
        """Merkt sich die letzte Kennzeichen-Region fuer die Live-Box."""
        plate_region = result.get("plate_region")
        if not plate_region:
            return

        with self.frame_lock:
            self.last_plate_region = dict(plate_region)
            self.last_box_until = time.time() + AUTO_BOX_TTL

    def _should_process_plate(self, detected_plate: str) -> bool:
        """Verhindert, dass dasselbe Kennzeichen im Live-Feed dauernd neu gespeichert wird."""
        now = time.time()
        return (
            detected_plate != self.last_processed_plate
            or now - self.last_processed_plate_time >= AUTO_PLATE_COOLDOWN
        )

    def _should_retry_invalid_plate(self) -> bool:
        """Erlaubt nach kurzer Wartezeit einen neuen OCR-Versuch bei ungueltiger Erkennung."""
        with self.frame_lock:
            result = dict(self.last_auto_result)

        return (
            result.get("plate_valid") is False
            and bool(result.get("detected_plate"))
            and time.time() - self.last_auto_detection_time >= AUTO_INVALID_RETRY_INTERVAL
        )

    def _draw_latest_plate_box(self, frame: np.ndarray) -> np.ndarray:
        """Zeichnet die zuletzt erkannte Kennzeichen-Box in den Stream."""
        with self.frame_lock:
            plate_region = dict(self.last_plate_region) if self.last_plate_region else None
            box_visible = time.time() < self.last_box_until
            result = dict(self.last_auto_result)

        if not plate_region or not box_visible:
            return frame

        annotated = frame.copy()
        height, width = annotated.shape[:2]
        x1 = max(0, min(width - 1, int(plate_region.get("x1", 0))))
        y1 = max(0, min(height - 1, int(plate_region.get("y1", 0))))
        x2 = max(0, min(width - 1, int(plate_region.get("x2", 0))))
        y2 = max(0, min(height - 1, int(plate_region.get("y2", 0))))

        color = (0, 220, 0) if result.get("plate_valid") else (0, 200, 255)
        label = result.get("detected_plate") or "Kennzeichen"
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 3)
        cv2.putText(
            annotated,
            label,
            (x1, max(y1 - 12, 24)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            color,
            2
        )
        return annotated
    
    def get_frame(self) -> bytes:
        """Schneller Frame-Abruf mit minimaler Latenz - RGB korrekt zu JPEG"""
        try:
            # Für Picamera2: Capture im Main-Thread mit minimaler Latenz
            if PICAMERA2_AVAILABLE and Picamera2 is not None and isinstance(self.camera, Picamera2):
                try:
                    # Picamera2 gibt RGB zurück
                    raw_frame = self.camera.capture_array()
                    
                    # RGB zu BGR konvertieren für cv2.imencode (das erwartet BGR!)
                    bgr_frame = cv2.cvtColor(raw_frame, cv2.COLOR_RGB2BGR)
                    stream_frame = self._process_frame_for_stream(bgr_frame)
                    
                    # Jetzt zu JPEG speichern mit korrektem Format
                    success, jpeg = cv2.imencode(
                        '.jpg', 
                        stream_frame,
                        [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
                    )
                    if success:
                        self.frame_count += 1
                        return jpeg.tobytes()
                except Exception as e:
                    print(f"[LiveFeed] Picamera2 Frame-Fehler: {e}")
            
            # Fallback zu gepuffertem Frame (USB-Kamera)
            with self.frame_lock:
                if self.camera_active and self.frame is not None:
                    return self.frame
                else:
                    return self.fallback_frame
        except Exception as e:
            print(f"[LiveFeed] get_frame Fehler: {e}")
            return self.fallback_frame
    
    def is_active(self) -> bool:
        """Gibt an ob Kamera aktiv ist"""
        return self.camera_active
    
    def shutdown(self) -> None:
        """Beendet die Kamera"""
        self.running = False
        if self.camera is not None:
            try:
                if PICAMERA2_AVAILABLE and Picamera2 is not None and isinstance(self.camera, Picamera2):
                    self.camera.close()
                else:
                    self.camera.release()
                print(f"[LiveFeed] Kamera geschlossen. {self.frame_count} Frames versendet.")
            except Exception as e:
                print(f"[LiveFeed] Fehler beim Schließen: {e}")


# Globale Instanz
live_feed = LiveFeedHandler()


def register_auto_detection_callback(callback: Callable[[dict], None]) -> None:
    """Registriert die Verarbeitung fuer automatisch erkannte Kennzeichen."""
    live_feed.set_auto_detection_callback(callback)


def get_auto_detection_state() -> dict:
    """Gibt den Status der automatischen Kennzeichen-Erkennung zurück."""
    return live_feed.get_auto_detection_state()


def get_latest_detection_result() -> dict:
    """Gibt das letzte automatische Erkennungsresultat inklusive Bildern zurück."""
    return live_feed.get_latest_detection_result()


def generate_stream() -> Generator[bytes, None, None]:
    """
    Motion JPEG Stream Generator
    - Stabile Framerate
    - Minimales Ruckeln
    """
    frame_interval = 1.0 / TARGET_FPS
    
    try:
        while True:
            start_time = time.time()
            
            # Hole aktuellen Frame
            frame = live_feed.get_frame()
            
            if frame:
                # Standard Motion JPEG Format
                yield (
                    b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n'
                    b'Content-Length: ' + str(len(frame)).encode() + b'\r\n\r\n'
                    + frame + b'\r\n'
                )
                
                # Stabile Framerate Control
                elapsed = time.time() - start_time
                sleep_time = frame_interval - elapsed
                if sleep_time > 0.001:
                    time.sleep(sleep_time)
    
    except GeneratorExit:
        print("[LiveFeed] Stream beendet")
    except Exception as e:
        print(f"[LiveFeed] Stream-Fehler: {e}")


def get_static_frame() -> bytes:
    """Gibt aktuellen Frame zurück"""
    return live_feed.get_frame()
