"""
Plate Recognition Service: Verwaltet Kennzeichen-Erkennung
Integriert PlateRecognizer mit Dashboard-Logik
"""

import sys
from pathlib import Path
import cv2
import numpy as np
import logging
from typing import Optional, Dict, Any
from io import BytesIO
import base64

# Füge AI zum Pfad hinzu
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "AI"))

from AI.plate_recognizer import PlateRecognizer
from AI.plate_detection_models import PlateDetectionResult, RecognitionStatistics
from AI.image_processor import ImageProcessor
from backend.database.db import db
from .ocr_correction import OCRCorrectionService

logger = logging.getLogger(__name__)


class PlateRecognitionService:
    """Service für Kennzeichen-Erkennung im Dashboard"""
    
    _instance = None
    _recognizer: Optional[PlateRecognizer] = None
    _statistics: RecognitionStatistics = RecognitionStatistics()
    
    def __new__(cls):
        """Singleton Pattern - nur eine Instanz"""
        if cls._instance is None:
            cls._instance = super(PlateRecognitionService, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self) -> None:
        """Initialisiert den Plate Recognizer und wärmt OCR vor"""
        try:
            logger.info("Initialisiere PlateRecognitionService...")
            self._recognizer = PlateRecognizer()
            if self._recognizer.model is None:
                logger.warning("YOLO-Modell konnte nicht geladen werden")
            else:
                logger.info("✓ YOLO-Modell geladen")
            
            # Wärme OCR-Handler vor (wichtig für Performance!)
            if self._recognizer and self._recognizer.ocr_handler:
                logger.info("Wärme OCR-Handler vor (EasyOCR laden)...")
                self._recognizer.ocr_handler._load_ocr()
                logger.info("✓ OCR-Handler vorgewärmt - Erste Erkennung wird jetzt schnell!")
            
            logger.info("✓ PlateRecognitionService vollständig initialisiert")
        except Exception as e:
            logger.error(f"Fehler bei Initialisierung: {e}")
            self._recognizer = None
    
    @staticmethod
    def get_instance() -> 'PlateRecognitionService':
        """Gibt Singleton-Instanz zurück"""
        if PlateRecognitionService._instance is None:
            PlateRecognitionService()
        return PlateRecognitionService._instance
    
    def is_ready(self) -> bool:
        """Prüft ob Service bereit ist"""
        return self._recognizer is not None and self._recognizer.model is not None
    
    def recognize_frame(self, frame: np.ndarray) -> Dict[str, Any]:
        """
        Erkennt Kennzeichen in Frame
        
        Args:
            frame: OpenCV BGR Frame
            
        Returns:
            Dictionary mit Erkennungsergebnissen
        """
        if not self.is_ready():
            return self._error_response("Service nicht verfügbar")
        
        try:
            # Erkenne Kennzeichen
            result = self._recognizer.detect_plate_in_frame(frame)
            result = self._apply_ocr_correction(result)
            
            # Aktualisiere Statistiken
            self._statistics.update(result)
            
            # Konvertiere Bilder zu Base64 für JSON
            response = self._build_response(result, frame)
            
            return response
            
        except Exception as e:
            logger.error(f"Fehler bei Erkennung: {e}")
            return self._error_response(str(e))

    def _apply_ocr_correction(self, result: PlateDetectionResult) -> PlateDetectionResult:
        """
        Verbessert OCR-Rohtexte vor der Rueckgabe ans Dashboard.
        """
        if not result.detected_plate or not result.detected_plate.strip():
            return result

        correction = OCRCorrectionService.correct_plate(
            raw_text=result.detected_plate,
            known_plates=self._get_known_plates()
        )

        result.detected_plate = correction["corrected_plate"]
        result.plate_valid = correction["is_valid"]
        result.success = correction["is_valid"]

        if correction["is_valid"]:
            result.error = ""
            logger.info(
                "[OCR-KORREKTUR] '%s' -> '%s' (%s)",
                correction["raw_text"],
                correction["corrected_plate"],
                correction["best_reason"],
            )
        elif not result.error:
            result.error = "Kennzeichen konnte nicht in gueltiges Format korrigiert werden"

        setattr(result, "raw_detected_plate", correction["raw_text"])
        setattr(result, "correction_applied", correction["was_corrected"])
        setattr(result, "correction_confidence", correction["confidence_level"])
        setattr(result, "correction_reason", correction["best_reason"])
        setattr(result, "correction_candidates", correction["candidates"])
        setattr(result, "matched_known_plate", correction["matched_known_plate"])
        return result

    def _get_known_plates(self) -> list:
        """Liest bekannte Kennzeichen aus der Datenbank fuer die Korrekturschicht."""
        try:
            cursor = db.get_cursor()
            cursor.execute("SELECT license_plate FROM vehicles WHERE license_plate IS NOT NULL")
            return [row[0] for row in cursor.fetchall() if row[0]]
        except Exception as e:
            logger.warning(f"Bekannte Kennzeichen konnten nicht geladen werden: {e}")
            return []
    
    def _build_response(self, result: PlateDetectionResult, 
                        original_frame: np.ndarray) -> Dict[str, Any]:
        """Erstellt Response-Dictionary mit Base64-kodierten Bildern
        
        Wichtig: Zeigt ALL Daten auch wenn Kennzeichen ungültig ist!
        """
        # Basis-Response mit allen Daten, ob gültig oder ungültig
        response = {
            "success": result.success,
            "detected_plate": result.detected_plate,
            "raw_detected_plate": getattr(result, "raw_detected_plate", result.detected_plate),
            "plate_confidence": round(result.plate_confidence, 4),
            "ocr_confidence": round(result.ocr_confidence, 4),
            "combined_confidence": round(result.get_combined_confidence(), 4),
            "timestamp": result.detection_timestamp,
            "error": result.error,
            "plate_valid": result.plate_valid,
            "correction_applied": getattr(result, "correction_applied", False),
            "correction_confidence": getattr(result, "correction_confidence", "low"),
            "correction_reason": getattr(result, "correction_reason", ""),
            "matched_known_plate": getattr(result, "matched_known_plate", False),
            "correction_candidates": getattr(result, "correction_candidates", []),
        }
        
        # WICHTIG: Zeige Bilder wenn Kennzeichen erkannt wurde (gültig ODER ungültig!)
        if result.detected_plate and result.detected_plate.strip():
            logger.debug(f"[SERVICE] Baue Response für: '{result.detected_plate}' (valid={result.plate_valid})")
            
            # Original-Snapshot (ganzes Fahrzeug)
            if original_frame is not None and original_frame.size > 0:
                response["vehicle_snapshot"] = self._frame_to_base64(original_frame)
            
            # Ausgeschnittenes Kennzeichen
            if result.plate_image is not None and result.plate_image.size > 0:
                response["plate_image"] = self._frame_to_base64(result.plate_image)
                logger.debug(f"[SERVICE] plate_image hinzugefügt")
            
            # Annotiertes Frame mit Bounding Box
            if result.annotated_frame is not None and result.annotated_frame.size > 0:
                response["annotated_frame"] = self._frame_to_base64(result.annotated_frame)
                logger.debug(f"[SERVICE] annotated_frame hinzugefügt")
            
            # Region-Daten
            if result.plate_region:
                response["plate_region"] = result.plate_region.to_dict()
                logger.debug(f"[SERVICE] plate_region hinzugefügt")
        else:
            logger.debug(f"[SERVICE] Keine Kennzeichen erkannt oder leer")
        
        return response
    
    def _frame_to_base64(self, frame: np.ndarray) -> str:
        """Konvertiert OpenCV Frame zu Base64-String"""
        try:
            success, buffer = cv2.imencode('.jpg', frame)
            if success:
                frame_b64 = base64.b64encode(buffer).decode('utf-8')
                return f"data:image/jpeg;base64,{frame_b64}"
        except Exception as e:
            logger.error(f"Fehler bei Base64-Konvertierung: {e}")
        return ""
    
    def _error_response(self, error_message: str) -> Dict[str, Any]:
        """Erstellt Error-Response"""
        return {
            "success": False,
            "error": error_message,
            "detected_plate": "",
            "plate_confidence": 0.0,
            "ocr_confidence": 0.0,
            "combined_confidence": 0.0,
            "timestamp": ""
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Gibt Erkennungs-Statistiken zurück"""
        return self._statistics.to_dict()
    
    def reset_statistics(self) -> None:
        """Setzt Statistiken zurück"""
        self._statistics = RecognitionStatistics()
        logger.info("Statistiken zurückgesetzt")
    
    def set_confidence_threshold(self, threshold: float) -> None:
        """Setzt YOLO Konfidenz-Schwellenwert"""
        if self._recognizer:
            self._recognizer.conf_threshold = threshold
            logger.info(f"Konfidenz-Schwellenwert gesetzt: {threshold}")
    
    def get_recognition_history(self, limit: int = 10) -> list:
        """
        Gibt zuletzt erkannte Kennzeichen zurück
        
        Args:
            limit: Maximale Anzahl
            
        Returns:
            Liste von Erkennungsergebnissen
        """
        # Diese Methode würde Ergebnisse aus Datenbank abrufen
        # Für jetzt nur leere Liste
        return []
    
    @staticmethod
    def save_detection_result(result: PlateDetectionResult, 
                             vehicle_id: int = None) -> bool:
        """
        Speichert Erkennungsergebnis in Datenbank
        
        Args:
            result: PlateDetectionResult
            vehicle_id: Fahrzeug-ID
            
        Returns:
            True bei erfolgreicher Speicherung
        """
        try:
            # Diese Funktion würde mit der Datenbank interagieren
            # Placeholder für DB-Integration
            logger.info(f"Erkennungsergebnis würde gespeichert: {result.detected_plate}")
            return True
        except Exception as e:
            logger.error(f"Fehler beim Speichern: {e}")
            return False
    
    def process_recognition_batch(self, frames: list) -> list:
        """
        Verarbeitet mehrere Frames
        
        Args:
            frames: Liste von OpenCV Frames
            
        Returns:
            Liste von Response-Dictionaries
        """
        responses = []
        for frame in frames:
            response = self.recognize_frame(frame)
            responses.append(response)
        return responses
