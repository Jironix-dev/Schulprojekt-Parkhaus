#!/usr/bin/env python3
"""
Quick-Start Demo für Kennzeichen-Erkennungssystem
Zeigt die Grundfunktionalität
"""

import sys
from pathlib import Path
import cv2
import numpy as np

# Füge AI zum Pfad hinzu
sys.path.insert(0, str(Path(__file__).parent / "AI"))

from plate_recognizer import PlateRecognizer
from image_processor import ImageProcessor
from ocr_handler import OCRHandler
from plate_detection_models import PlateDetectionResult


def demo_basic_recognition():
    """Demo 1: Grundlegende Erkennung"""
    print("\n" + "="*60)
    print("DEMO 1: Grundlegende Kennzeichen-Erkennung")
    print("="*60)
    
    # Initialisiere Recognizer
    recognizer = PlateRecognizer()
    
    if not recognizer.is_ready():
        print("❌ YOLO-Modell konnte nicht geladen werden!")
        print("   Stelle sicher, dass best.pt unter AI/YOLO-Modell/train/weights/ liegt")
        return
    
    print("✓ PlateRecognizer initialisiert")
    
    # Erstelle Test-Frame (Schwarz mit Text)
    test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(
        test_frame,
        "Test: Kennzeichen erkannt!",
        (50, 100),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.5,
        (0, 255, 0),
        2
    )
    
    print("\nVerarbeite Test-Frame...")
    result = recognizer.detect_plate_in_frame(test_frame)
    
    print(f"\nErgebnis:")
    print(f"  Success: {result.success}")
    print(f"  Erkanntes Kennzeichen: {result.detected_plate}")
    print(f"  YOLO Konfidenz: {result.plate_confidence:.2%}")
    print(f"  OCR Konfidenz: {result.ocr_confidence:.2%}")
    if result.success:
        print(f"  Kombiniert: {result.get_combined_confidence():.2%}")


def demo_image_processing():
    """Demo 2: Bildbearbeitung"""
    print("\n" + "="*60)
    print("DEMO 2: Bildverarbeitung")
    print("="*60)
    
    processor = ImageProcessor()
    print("✓ ImageProcessor initialisiert")
    
    # Erstelle Test-Bild
    test_image = np.zeros((200, 300, 3), dtype=np.uint8)
    cv2.rectangle(test_image, (50, 50), (250, 150), (0, 255, 0), -1)
    cv2.putText(
        test_image,
        "AB CD 1234",
        (70, 120),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (255, 255, 255),
        2
    )
    
    print("\n1. Größe ändern...")
    resized = processor.resize_image(test_image, width=600)
    print(f"   Original: {test_image.shape}, Resized: {resized.shape}")
    
    print("\n2. Kontrast verbessern...")
    enhanced = processor.enhance_contrast(test_image, alpha=1.5)
    print(f"   ✓ Kontrastverbesserung durchgeführt")
    
    print("\n3. Zu Grayscale konvertieren...")
    gray = processor.convert_to_grayscale(test_image)
    print(f"   Shape: {gray.shape}")
    
    print("\n4. Morphologische Operationen...")
    cleaned = processor.apply_morphological_ops(test_image)
    print(f"   ✓ Bildbereinigung durchgeführt")


def demo_ocr():
    """Demo 3: OCR-Funktionalität"""
    print("\n" + "="*60)
    print("DEMO 3: OCR-Erkennung")
    print("="*60)
    
    ocr = OCRHandler()
    
    # Erstelle Test-Kennzeichen-Bild
    plate_image = np.ones((60, 120, 3), dtype=np.uint8) * 255
    cv2.putText(
        plate_image,
        "AB CD 1234",
        (10, 45),
        cv2.FONT_HERSHEY_TRIPLEX,
        0.8,
        (0, 0, 0),
        1
    )
    
    print("Verarbeite Kennzeichen-Bild...")
    text, confidence = ocr.extract_text(plate_image)
    
    print(f"\nErgebnis:")
    print(f"  Erkannter Text: '{text}'")
    print(f"  Konfidenz: {confidence:.2%}")


def demo_statistics():
    """Demo 4: Statistiken"""
    print("\n" + "="*60)
    print("DEMO 4: Statistiken")
    print("="*60)
    
    from plate_detection_models import RecognitionStatistics
    
    stats = RecognitionStatistics()
    
    print("Erstelle Test-Ergebnisse...")
    
    # Simuliere mehrere Erkennungen
    test_results = [
        PlateDetectionResult(success=True, detected_plate="B-AB 1234", 
                            plate_confidence=0.95, ocr_confidence=0.92),
        PlateDetectionResult(success=True, detected_plate="B-XY 5678", 
                            plate_confidence=0.87, ocr_confidence=0.85),
        PlateDetectionResult(success=False, error="Kein Kennzeichen erkannt"),
    ]
    
    for result in test_results:
        stats.update(result)
    
    print(f"\nStatistiken:")
    print(f"  Gesamterkennungen: {stats.total_detections}")
    print(f"  Erfolgreiche: {stats.successful_detections}")
    print(f"  Fehlgeschlagene: {stats.failed_detections}")
    print(f"  Erfolgsrate: {stats.get_success_rate():.1f}%")
    print(f"  Ø YOLO Konfidenz: {stats.average_plate_confidence:.2%}")
    print(f"  Ø OCR Konfidenz: {stats.average_ocr_confidence:.2%}")
    print(f"  Ø Kombiniert: {stats.average_combined_confidence:.2%}")


def demo_api_integration():
    """Demo 5: API-Integration"""
    print("\n" + "="*60)
    print("DEMO 5: API-Integration (Dashboard Service)")
    print("="*60)
    
    try:
        from backend.services.plate_recognition_service import PlateRecognitionService
        
        service = PlateRecognitionService.get_instance()
        
        print(f"✓ PlateRecognitionService geladen")
        print(f"  Service bereit: {service.is_ready()}")
        print(f"  Statistiken: {service.get_statistics()}")
        
        print("\nAPI-Endpoints verfügbar:")
        print("  POST /api/recognition/detect-plate")
        print("  POST /api/recognition/upload-image")
        print("  GET  /api/recognition/status")
        print("  GET  /api/recognition/statistics")
        print("  POST /api/recognition/reset-statistics")
        
    except Exception as e:
        print(f"⚠️  Service-Demo konnte nicht geladen werden: {e}")


def main():
    """Starte alle Demos"""
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║" + " "*15 + "KENNZEICHEN-ERKENNUNGSSYSTEM DEMO" + " "*10 + "║")
    print("╚" + "="*58 + "╝")
    
    demos = [
        demo_basic_recognition,
        demo_image_processing,
        demo_ocr,
        demo_statistics,
        demo_api_integration,
    ]
    
    for demo in demos:
        try:
            demo()
        except Exception as e:
            print(f"\n❌ Fehler in {demo.__name__}: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*60)
    print("✓ Demo abgeschlossen!")
    print("="*60)
    print("\nWeitere Informationen:")
    print("  📖 Dokumentation: Dokumentation/KENNZEICHEN_ERKENNUNGSSYSTEM.md")
    print("  🚀 Dashboard: http://localhost:8000")
    print("  📊 API-Docs: http://localhost:8000/docs")
    print()


if __name__ == "__main__":
    main()
