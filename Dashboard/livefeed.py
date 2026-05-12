"""
Live-Feed Handler für Kamera-Stream vom Raspberry Pi
Stellt Motion JPEG Stream oder Fallback-Bild bereit
"""

import io
import cv2
import numpy as np
from pathlib import Path
from typing import Optional
import threading
import time


class LiveFeedHandler:
    """Verwaltet den Live-Feed von der Kamera"""
    
    def __init__(self):
        self.camera_active = False
        self.frame = None
        self.frame_lock = threading.Lock()
        self._init_fallback_frame()
    
    def _init_fallback_frame(self):
        """Erstellt Fallback-Frame wenn Kamera nicht aktiv ist"""
        # Schwarzes Bild (1280x720)
        fallback = np.zeros((720, 1280, 3), dtype=np.uint8)
        
        # Füge Text hinzu
        font = cv2.FONT_HERSHEY_SIMPLEX
        text = "Kamera nicht aktiv"
        font_scale = 2.0
        color = (255, 255, 255)  # Weiß
        thickness = 3
        
        # Berechne Textposition (zentriert)
        text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
        x = (1280 - text_size[0]) // 2
        y = (720 - text_size[1]) // 2 + text_size[1]
        
        cv2.putText(fallback, text, (x, y), font, font_scale, color, thickness)
        
        # Konvertiere zu JPEG
        success, jpeg = cv2.imencode('.jpg', fallback)
        if success:
            self.fallback_frame = jpeg.tobytes()
        else:
            self.fallback_frame = b''
    
    def get_frame(self) -> bytes:
        """Gibt aktuellen Frame als JPEG zurück"""
        with self.frame_lock:
            if self.camera_active and self.frame is not None:
                return self.frame
            else:
                return self.fallback_frame
    
    def set_frame(self, frame: np.ndarray):
        """Setzt neuen Frame von Kamera"""
        success, jpeg = cv2.imencode('.jpg', frame)
        if success:
            with self.frame_lock:
                self.frame = jpeg.tobytes()
    
    def activate_camera(self):
        """Aktiviert Kamera-Feed"""
        self.camera_active = True
    
    def deactivate_camera(self):
        """Deaktiviert Kamera-Feed"""
        self.camera_active = False
    
    def is_active(self) -> bool:
        """Gibt an ob Kamera aktiv ist"""
        return self.camera_active


# Globale Instanz
live_feed = LiveFeedHandler()


def generate_stream():
    """
    Generator für Motion JPEG Stream
    Kann später mit echten Kamera-Frames gefüllt werden
    """
    while True:
        frame = live_feed.get_frame()
        yield (
            b'--frame\r\n'
            b'Content-Type: image/jpeg\r\n'
            b'Content-Length: ' + str(len(frame)).encode() + b'\r\n\r\n'
            + frame + b'\r\n'
        )
        time.sleep(0.033)  # ~30 FPS


def get_static_frame() -> bytes:
    """Gibt aktuellen Frame als statisches JPEG zurück"""
    return live_feed.get_frame()
