"""
Datenmodelle für Kennzeichen-Erkennung
Definiert Strukturen für Erkennungsergebnisse
"""

from dataclasses import dataclass, field
from typing import Optional
import numpy as np
from datetime import datetime


@dataclass
class PlateRegion:
    """Enthält Koordinaten einer erkannten Kennzeichen-Region"""
    x1: int  # Top-Left X
    y1: int  # Top-Left Y
    x2: int  # Bottom-Right X
    y2: int  # Bottom-Right Y
    confidence: float  # YOLO Confidence
    
    def get_width(self) -> int:
        """Breite der Region"""
        return self.x2 - self.x1
    
    def get_height(self) -> int:
        """Höhe der Region"""
        return self.y2 - self.y1
    
    def get_area(self) -> int:
        """Fläche der Region"""
        return self.get_width() * self.get_height()
    
    def to_dict(self) -> dict:
        """Konvertiert zu Dictionary"""
        return {
            'x1': self.x1, 'y1': self.y1,
            'x2': self.x2, 'y2': self.y2,
            'confidence': round(self.confidence, 4),
            'width': self.get_width(),
            'height': self.get_height(),
            'area': self.get_area()
        }


@dataclass
class PlateDetectionResult:
    """Enthält komplettes Erkennungsergebnis"""
    success: bool = False
    detected_plate: str = ""
    plate_confidence: float = 0.0  # YOLO Confidence (0.0-1.0)
    ocr_confidence: float = 0.0    # OCR Confidence (0.0-1.0)
    plate_region: Optional[PlateRegion] = None
    
    # Bilder (als numpy arrays, nicht in dict/JSON serialisiert)
    plate_image: Optional[np.ndarray] = field(default=None, repr=False)
    annotated_frame: Optional[np.ndarray] = field(default=None, repr=False)
    
    # Metadaten
    detection_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    error: str = ""
    
    # Validierungsstatus
    plate_valid: bool = True  # True: gültig (A 1234), False: ungültig (A ABCD), None: unbekannt
    
    # Pfade (falls Bilder gespeichert wurden)
    snapshot_path: Optional[str] = None
    plate_image_path: Optional[str] = None
    annotated_path: Optional[str] = None
    
    def get_combined_confidence(self) -> float:
        """Kombinierte Konfidenz aus YOLO und OCR"""
        if self.success:
            # Gewichtung: YOLO 60%, OCR 40%
            return (self.plate_confidence * 0.6) + (self.ocr_confidence * 0.4)
        return 0.0
    
    def to_dict(self) -> dict:
        """Konvertiert zu Dictionary für JSON-Serialisierung"""
        return {
            'success': self.success,
            'detected_plate': self.detected_plate,
            'plate_confidence': round(self.plate_confidence, 4),
            'ocr_confidence': round(self.ocr_confidence, 4),
            'combined_confidence': round(self.get_combined_confidence(), 4),
            'plate_region': self.plate_region.to_dict() if self.plate_region else None,
            'detection_timestamp': self.detection_timestamp,
            'error': self.error,
            'plate_valid': self.plate_valid,
            'snapshot_path': self.snapshot_path,
            'plate_image_path': self.plate_image_path,
            'annotated_path': self.annotated_path
        }
    
    def __str__(self) -> str:
        """String-Repräsentation"""
        if self.success:
            return f"PlateDetection(plate='{self.detected_plate}', conf={self.get_combined_confidence():.2%})"
        return f"PlateDetection(error='{self.error}')"


@dataclass
class DetectionBatch:
    """Enthält mehrere Erkennungsergebnisse für Batch-Processing"""
    results: list = field(default_factory=list)
    batch_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    batch_id: str = ""
    
    def add_result(self, result: PlateDetectionResult) -> None:
        """Fügt Ergebnis hinzu"""
        self.results.append(result)
    
    def get_successful_detections(self) -> list:
        """Gibt nur erfolgreiche Erkennungen zurück"""
        return [r for r in self.results if r.success]
    
    def get_success_rate(self) -> float:
        """Erfolgsquote in Prozent"""
        if not self.results:
            return 0.0
        successful = len(self.get_successful_detections())
        return (successful / len(self.results)) * 100
    
    def get_average_confidence(self) -> float:
        """Durchschnittliche Konfidenz"""
        if not self.get_successful_detections():
            return 0.0
        total_conf = sum(r.get_combined_confidence() for r in self.get_successful_detections())
        return total_conf / len(self.get_successful_detections())
    
    def to_dict(self) -> dict:
        """Konvertiert zu Dictionary"""
        return {
            'batch_id': self.batch_id,
            'batch_timestamp': self.batch_timestamp,
            'total_detections': len(self.results),
            'successful_detections': len(self.get_successful_detections()),
            'success_rate': round(self.get_success_rate(), 2),
            'average_confidence': round(self.get_average_confidence(), 4),
            'results': [r.to_dict() for r in self.results]
        }


@dataclass
class RecognitionStatistics:
    """Sammelt Statistiken über Erkennungen"""
    total_detections: int = 0
    successful_detections: int = 0
    failed_detections: int = 0
    average_plate_confidence: float = 0.0
    average_ocr_confidence: float = 0.0
    average_combined_confidence: float = 0.0
    
    update_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def update(self, result: PlateDetectionResult) -> None:
        """Aktualisiert Statistiken mit neuem Ergebnis"""
        self.total_detections += 1
        
        if result.success:
            self.successful_detections += 1
            # Laufende Durchschnitte berechnen
            n = self.successful_detections
            self.average_plate_confidence = (
                (self.average_plate_confidence * (n - 1) + result.plate_confidence) / n
            )
            self.average_ocr_confidence = (
                (self.average_ocr_confidence * (n - 1) + result.ocr_confidence) / n
            )
            self.average_combined_confidence = (
                (self.average_combined_confidence * (n - 1) + result.get_combined_confidence()) / n
            )
        else:
            self.failed_detections += 1
        
        self.update_timestamp = datetime.now().isoformat()
    
    def get_success_rate(self) -> float:
        """Erfolgsquote"""
        if self.total_detections == 0:
            return 0.0
        return (self.successful_detections / self.total_detections) * 100
    
    def to_dict(self) -> dict:
        """Konvertiert zu Dictionary"""
        return {
            'total_detections': self.total_detections,
            'successful_detections': self.successful_detections,
            'failed_detections': self.failed_detections,
            'success_rate': round(self.get_success_rate(), 2),
            'average_plate_confidence': round(self.average_plate_confidence, 4),
            'average_ocr_confidence': round(self.average_ocr_confidence, 4),
            'average_combined_confidence': round(self.average_combined_confidence, 4),
            'update_timestamp': self.update_timestamp
        }
