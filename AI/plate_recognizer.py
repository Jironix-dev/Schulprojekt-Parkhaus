"""
Kennzeichen-Erkennungssystem
Integriert YOLO (Ultralytics) für optimierte Kennzeichen-Lokalisierung mit OCR für Text-Extraktion
Vereinfachte Version für bessere Stabilität
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List
import logging
import re
import time
from datetime import datetime

# Ultralytics YOLO
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO = None  # type: ignore
    YOLO_AVAILABLE = False

from .image_processor import ImageProcessor
from .ocr_handler import OCRHandler
from .plate_detection_models import PlateDetectionResult, PlateRegion

# Logging konfigurieren
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# YOLO Modell Konfiguration
YOLO_CONF_THRESHOLD = 0.45
YOLO_IOU_THRESHOLD = 0.5
MODEL_PATH = Path(__file__).parent / "YOLO-Modell" / "train" / "weights" / "best.pt"


class PlateRecognizer:
    """
    Kennzeichen-Erkennungssystem basierend auf YOLO + OCR
    Nutzt Ultralytics YOLO für robuste und schnelle Erkennung
    """
    
    def __init__(self, model_path: Optional[str] = None):
        """
        Initialisiert PlateRecognizer
        
        Args:
            model_path: Pfad zum YOLO best.pt Modell. Wenn None, nutze default
        """
        if not YOLO_AVAILABLE:
            logger.error("Ultralytics YOLO nicht installiert! Führe aus: pip install ultralytics")
            self.model = None
            return
        
        # Verwende übergebenen Pfad oder default
        if model_path is None:
            model_path = str(MODEL_PATH)
        
        self.model_path = model_path
        self.model = None
        self.image_processor = ImageProcessor()
        self.ocr_handler = OCRHandler()
        self.recognition_count = 0
        self.success_count = 0
        
        self._load_model()
    
    def _load_model(self) -> bool:
        """
        Lädt das YOLO Modell
        
        Returns:
            True wenn erfolgreich, False sonst
        """
        if not YOLO_AVAILABLE or YOLO is None:
            logger.error("YOLO nicht verfügbar!")
            return False
        
        try:
            model_path_obj = Path(self.model_path)
            
            # Falls Modell nicht existiert, versuche es zu laden/herunterladen
            if not model_path_obj.exists():
                logger.warning(f"Modell nicht gefunden: {self.model_path}")
                logger.info("Versuche Standard-YOLO Modell zu laden...")
                
                # Fallback: Lade ein Standard-YOLO Modell (wird heruntergeladen)
                # Versuche, das beste Modell zu laden (wird von Ultralytics verwaltet)
                try:
                    self.model = YOLO('yolov8n.pt')  # Nano-Version für RPi
                    logger.info("✓ Standard YOLO8n Modell geladen (heruntergeladen)")
                except:
                    # Noch fallback: Lade von pretrained Punkt
                    self.model = YOLO('yolov8s.pt')  # Small version
                    logger.info("✓ Standard YOLO8s Modell geladen")
            else:
                logger.info(f"Lade YOLO Modell: {self.model_path}")
                self.model = YOLO(self.model_path)
                logger.info("✓ YOLO Modell erfolgreich geladen (custom)")
            
            logger.info(f"✓ YOLO Modell bereit")
            logger.info(f"  - Device: {self.model.device}")
            logger.info(f"  - Confidence Threshold: {YOLO_CONF_THRESHOLD}")
            
            return True
            
        except Exception as e:
            logger.error(f"Fehler beim Laden des YOLO-Modells: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def detect_plate_in_frame(self, frame: np.ndarray) -> PlateDetectionResult:
        """
        Erkennt Kennzeichen in einem Frame
        
        Args:
            frame: OpenCV BGR Frame
            
        Returns:
            PlateDetectionResult mit allen Erkenntnis-Daten
        """
        self.recognition_count += 1
        timing_start = time.time()
        
        try:
            if self.model is None:
                return PlateDetectionResult(
                    success=False,
                    error="YOLO Modell nicht geladen"
                )
            
            # ===== YOLO Detection =====
            yolo_start = time.time()
            results = self.model(
                frame,
                conf=YOLO_CONF_THRESHOLD,
                iou=YOLO_IOU_THRESHOLD,
                verbose=False
            )
            yolo_time = time.time() - yolo_start
            logger.debug(f"⏱️ YOLO Inference: {yolo_time*1000:.1f}ms")
            
            if not results or len(results) == 0:
                return PlateDetectionResult(
                    success=False,
                    error="Keine Kennzeichen erkannt"
                )
            
            result = results[0]
            
            # Überprüfe ob Detektionen vorhanden sind
            if result.boxes is None or len(result.boxes) == 0:
                return PlateDetectionResult(
                    success=False,
                    error="Keine Kennzeichen erkannt"
                )
            
            # Nutze die erste (beste) Detection
            box = result.boxes[0]
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            yolo_conf = float(box.conf[0])
            
            logger.debug(f"YOLO Detection: conf={yolo_conf:.3f}, box=({x1},{y1},{x2},{y2})")
            
            # Schneide Kennzeichen aus
            plate_region = PlateRegion(
                x1=x1, y1=y1, x2=x2, y2=y2,
                confidence=yolo_conf
            )
            
            crop_start = time.time()
            plate_image = self.image_processor.crop_region(frame, plate_region)
            crop_time = time.time() - crop_start
            logger.debug(f"⏱️ Crop: {crop_time*1000:.1f}ms")
            
            if plate_image is None or plate_image.size == 0:
                return PlateDetectionResult(
                    success=False,
                    error="Kennzeichen konnte nicht ausgeschnitten werden"
                )
            
            # ===== OCR Extraktion =====
            ocr_start = time.time()
            text, ocr_conf = self.ocr_handler.extract_text(plate_image)
            ocr_time = time.time() - ocr_start
            logger.debug(f"⏱️ OCR: {ocr_time*1000:.1f}ms")
            
            # Falls OCR nichts erkannt hat, fehlerhafte Rückgabe
            if not text or text.strip() == "":
                return PlateDetectionResult(
                    success=False,
                    error="Kennzeichen konnte nicht erkannt werden (OCR fehlgeschlagen)"
                )
            
            # Validiere Kennzeichen-Format
            valid = self._validate_plate_format(text)
            
            # Erstelle annotiertes Bild
            annotated_frame = frame.copy()
            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(annotated_frame, text, (x1, max(y1 - 10, 20)),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
            
            # Gesamt-Zeit
            total_time = time.time() - timing_start
            logger.info(f"⏱️ TOTAL: {total_time*1000:.1f}ms (YOLO: {yolo_time*1000:.1f}ms, OCR: {ocr_time*1000:.1f}ms)")
            
            if valid:
                self.success_count += 1
                logger.info(f"✓ Kennzeichen erkannt: {text} (YOLO: {yolo_conf:.2%}, OCR: {ocr_conf:.2%}, Valid: {valid})")
            else:
                logger.info(f"⚠️  Ungültiges Kennzeichen erkannt: {text} (YOLO: {yolo_conf:.2%}, OCR: {ocr_conf:.2%})")
            
            return PlateDetectionResult(
                success=valid,
                detected_plate=text,
                plate_confidence=yolo_conf,
                ocr_confidence=ocr_conf,
                plate_region=plate_region,
                plate_image=plate_image,
                annotated_frame=annotated_frame,
                detection_timestamp=datetime.now().isoformat(),
                plate_valid=valid,
                error="" if valid else "Kennzeichen-Format ungültig"
            )
            
        except Exception as e:
            logger.error(f"Fehler bei Kennzeichen-Erkennung: {e}")
            import traceback
            traceback.print_exc()
            
            return PlateDetectionResult(
                success=False,
                error=str(e)
            )
    
    def _validate_plate_format(self, text: str) -> bool:
        """
        Validiert Kennzeichen-Format (Deutsch und vereinfacht)
        Unterstützt:
        - Deutsches Format: [1-2 Buchstaben] [1-4 Ziffern] [1-2 Buchstaben]
        - Vereinfachtes Format: [1 Buchstabe] [4 Ziffern] (z.B. "R 7539" -> "R7539")
        z.B.: "A 1234 B" oder "AB 12 CD" oder "R7539"
        """
        if not text or len(text) < 2:
            return False
        
        # Entferne Leerzeichen und Bindestriche
        clean_text = text.upper().replace(" ", "").replace("-", "")
        
        # Kennzeichen-Patterns
        patterns = [
            r'^[A-Z]{2}\d{1,3}[A-Z]{1,2}$',  # AA 1234 B (Standard-Deutsch)
            r'^[A-Z]{1,2}\d{1,4}[A-Z]{1,2}$',  # A 123 BC (Deutsch variabel)
            r'^[A-Z]{1,3}\d{1,3}[A-Z]{1,2}$',  # ABC 123 DE (Deutsch erweitert)
            r'^[A-Z]{1}\d{4}$',                # R7539 (Vereinfachtes Format)
        ]
        
        for pattern in patterns:
            if re.match(pattern, clean_text):
                return True
        
        return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Gibt Erkennungs-Statistiken zurück
        """
        success_rate = (self.success_count / self.recognition_count * 100) if self.recognition_count > 0 else 0
        
        return {
            "total_recognitions": self.recognition_count,
            "successful_recognitions": self.success_count,
            "success_rate": round(success_rate, 2)
        }
    
    def reset_statistics(self):
        """
        Setzt Statistiken zurück
        """
        self.recognition_count = 0
        self.success_count = 0
        logger.info("Statistiken zurückgesetzt")
