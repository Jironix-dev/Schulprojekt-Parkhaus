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
from typing import Optional, Generator, Any
import time
import threading

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
        thread = threading.Thread(target=self._capture_loop, daemon=True)
        thread.start()
    
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
                
                # JPEG Encoding - vernünftige Settings
                success, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
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
                    
                    # Jetzt zu JPEG speichern mit korrektem Format
                    success, jpeg = cv2.imencode(
                        '.jpg', 
                        bgr_frame,
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
