"""
Kennzeichen-Erkennungssystem
Integriert YOLO für Kennzeichen-Lokalisierung mit OCR für Text-Extraktion
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
import logging
from dataclasses import dataclass
from datetime import datetime

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False

from .image_processor import ImageProcessor
from .ocr_handler import OCRHandler
from .plate_detection_models import PlateDetectionResult, PlateRegion

# Logging konfigurieren
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PlateRecognizer:
    """
    Hauptklasse für Kennzeichen-Erkennung
    Nutzt YOLO für Lokalisierung und OCR für Text-Erkennung
    """
    
    def __init__(self, model_path: str = None, conf_threshold: float = 0.5):
        """
        Initialisiert den PlateRecognizer
        
        Args:
            model_path: Pfad zum YOLO-Modell (best.pt). Wenn None, nutze default-Pfad
            conf_threshold: Konfidenz-Schwellenwert für Detektionen (0.0-1.0)
        """
        self.conf_threshold = conf_threshold
        self.model = None
        self.image_processor = ImageProcessor()
        self.ocr_handler = OCRHandler()
        self.device = "cpu"  # oder "cuda" für GPU
        
        # Standard-Modell-Pfad wenn nicht angegeben
        if model_path is None:
            model_path = str(Path(__file__).parent / "YOLO-Modell" / "train" / "weights" / "best.pt")
        
        self._load_model(model_path)
    
    def _load_model(self, model_path: str) -> None:
        """Lädt das YOLO-Modell"""
        if not YOLO_AVAILABLE:
            logger.error("YOLO nicht installiert! Installiere: pip install ultralytics")
            return
        
        try:
            model_path = Path(model_path)
            if not model_path.exists():
                logger.error(f"Modell nicht gefunden: {model_path}")
                return
            
            self.model = YOLO(str(model_path))
            logger.info(f"✓ YOLO-Modell geladen: {model_path}")
        except Exception as e:
            logger.error(f"Fehler beim Laden des Modells: {e}")
    
    def detect_plate_in_frame(self, frame: np.ndarray) -> PlateDetectionResult:
        """
        Erkennt Kennzeichen im übergebenen Frame
        
        Args:
            frame: OpenCV frame (BGR)
            
        Returns:
            PlateDetectionResult mit allen Erkennungsergebnissen
        """
        if self.model is None:
            logger.warning("Modell nicht geladen")
            return PlateDetectionResult(
                success=False,
                error="Modell nicht geladen"
            )
        
        try:
            # YOLO Inferenz
            results = self.model(frame, conf=self.conf_threshold, verbose=False)
            
            if not results or len(results) == 0:
                return PlateDetectionResult(
                    success=False,
                    error="Keine Kennzeichen erkannt"
                )
            
            # Verarbeite erste Detection
            detections = results[0]
            
            if len(detections.boxes) == 0:
                return PlateDetectionResult(
                    success=False,
                    error="Keine Kennzeichen erkannt"
                )
            
            # Beste Detection (höchste Konfidenz)
            best_detection = self._get_best_detection(detections)
            if best_detection is None:
                return PlateDetectionResult(
                    success=False,
                    error="Keine valide Detection"
                )
            
            confidence, box = best_detection
            x1, y1, x2, y2 = self._extract_coordinates(box)
            
            # Ausschneiden des Kennzeichens
            plate_region = PlateRegion(
                x1=int(x1), y1=int(y1),
                x2=int(x2), y2=int(y2),
                confidence=float(confidence)
            )
            
            plate_image = self.image_processor.crop_region(frame, plate_region)
            
            if plate_image is None or plate_image.size == 0:
                return PlateDetectionResult(
                    success=False,
                    error="Kennzeichen-Ausschnitt ungültig"
                )
            
            # OCR auf ausgeschnittenem Kennzeichen
            detected_text, ocr_confidence = self.ocr_handler.extract_text(plate_image)
            
            # Erstelle annotiertes Bild
            annotated_frame = frame.copy()
            annotated_frame = cv2.rectangle(
                annotated_frame,
                (plate_region.x1, plate_region.y1),
                (plate_region.x2, plate_region.y2),
                (0, 255, 0),  # Grüner Rahmen
                2
            )
            
            # Konfidenz-Text hinzufügen
            conf_text = f"Plate: {plate_region.confidence:.2%} | OCR: {ocr_confidence:.2%}"
            annotated_frame = cv2.putText(
                annotated_frame,
                conf_text,
                (plate_region.x1, max(plate_region.y1 - 10, 20)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )
            
            result = PlateDetectionResult(
                success=True,
                detected_plate=detected_text,
                plate_confidence=float(confidence),
                ocr_confidence=ocr_confidence,
                plate_region=plate_region,
                plate_image=plate_image,
                annotated_frame=annotated_frame,
                detection_timestamp=datetime.now().isoformat()
            )
            
            logger.info(f"✓ Kennzeichen erkannt: {detected_text} (Conf: {confidence:.2%})")
            return result
            
        except Exception as e:
            logger.error(f"Fehler bei Erkennung: {e}")
            return PlateDetectionResult(
                success=False,
                error=f"Erkennungsfehler: {str(e)}"
            )
    
    def _get_best_detection(self, detections) -> Optional[Tuple[float, Any]]:
        """Wählt die beste (höchste Konfidenz) Detection"""
        if len(detections.boxes) == 0:
            return None
        
        best_conf = 0
        best_box = None
        
        for box in detections.boxes:
            conf = float(box.conf[0])
            if conf > best_conf:
                best_conf = conf
                best_box = box
        
        return (best_conf, best_box) if best_box is not None else None
    
    def _extract_coordinates(self, box) -> Tuple[float, float, float, float]:
        """Extrahiert Koordinaten aus YOLO Box"""
        xyxy = box.xyxy[0].cpu().numpy()
        return float(xyxy[0]), float(xyxy[1]), float(xyxy[2]), float(xyxy[3])
    
    def process_frame_batch(self, frames: list) -> list:
        """
        Verarbeitet mehrere Frames hintereinander
        
        Args:
            frames: Liste von OpenCV Frames
            
        Returns:
            Liste von PlateDetectionResult
        """
        results = []
        for frame in frames:
            result = self.detect_plate_in_frame(frame)
            results.append(result)
        return results
