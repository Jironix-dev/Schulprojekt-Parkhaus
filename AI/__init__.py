"""
AI Module für Kennzeichen-Erkennung
Exportiert Hauptklassen für einfachen Import
"""

from .plate_recognizer import PlateRecognizer
from .ocr_handler import OCRHandler
from .image_processor import ImageProcessor
from .plate_detection_models import (
    PlateRegion,
    PlateDetectionResult,
    DetectionBatch,
    RecognitionStatistics
)

__all__ = [
    'PlateRecognizer',
    'OCRHandler',
    'ImageProcessor',
    'PlateRegion',
    'PlateDetectionResult',
    'DetectionBatch',
    'RecognitionStatistics'
]

__version__ = "1.0.0"
