#!/usr/bin/env python3
"""
Integrations-Test: Validiert dass alle Recognition-Komponenten funktionieren
"""

import sys
from pathlib import Path

def test_imports():
    """Test 1: Alle Module können importiert werden"""
    print("\n[1] Teste Imports...")
    
    try:
        # AI-Module
        from AI import (
            PlateRecognizer,
            OCRHandler,
            ImageProcessor,
            PlateDetectionResult,
            PlateRegion,
            RecognitionStatistics
        )
        print("  ✓ AI-Module importiert")
        
        # Backend Service
        sys.path.insert(0, str(Path(__file__).parent))
        from backend.services.plate_recognition_service import PlateRecognitionService
        print("  ✓ PlateRecognitionService importiert")
        
        return True
    except ImportError as e:
        print(f"  ✗ Import-Fehler: {e}")
        return False


def test_yolo_loading():
    """Test 2: YOLO-Modell kann geladen werden"""
    print("\n[2] Teste YOLO-Modell Laden...")
    
    try:
        from AI import PlateRecognizer
        recognizer = PlateRecognizer()
        
        if recognizer.model is None:
            print("  ⚠️  Warnung: YOLO-Modell nicht gefunden")
            print("     Stelle sicher, dass best.pt unter AI/YOLO-Modell/train/weights/ liegt")
            return False
        else:
            print("  ✓ YOLO-Modell geladen")
            return True
    except Exception as e:
        print(f"  ✗ Fehler: {e}")
        return False


def test_tesseract():
    """Test 3: Tesseract OCR ist installiert"""
    print("\n[3] Teste Tesseract OCR...")
    
    try:
        import pytesseract
        print("  ✓ pytesseract importiert")
        
        # Versuche Tesseract zu nutzen
        from PIL import Image
        import numpy as np
        
        # Erstelle Test-Bild
        test_img = Image.new('RGB', (100, 30), color='white')
        pytesseract.image_to_string(test_img)
        print("  ✓ Tesseract funktioniert")
        return True
    except pytesseract.TesseractNotFoundError:
        print("  ✗ Tesseract nicht installiert")
        print("     Installiere: https://github.com/UB-Mannheim/tesseract/wiki")
        return False
    except ImportError as e:
        print(f"  ✗ pytesseract nicht installiert: {e}")
        return False
    except Exception as e:
        print(f"  ✗ Fehler: {e}")
        return False


def test_data_models():
    """Test 4: Datenmodelle funktionieren"""
    print("\n[4] Teste Datenmodelle...")
    
    try:
        from AI import PlateRegion, PlateDetectionResult
        
        # Test PlateRegion
        region = PlateRegion(x1=10, y1=20, x2=310, y2=100, confidence=0.95)
        assert region.get_width() == 300
        assert region.get_height() == 80
        assert region.get_area() == 24000
        print("  ✓ PlateRegion funktioniert")
        
        # Test PlateDetectionResult
        result = PlateDetectionResult(
            success=True,
            detected_plate="B-AB 1234",
            plate_confidence=0.95,
            ocr_confidence=0.90,
            plate_region=region
        )
        assert result.get_combined_confidence() > 0
        result_dict = result.to_dict()
        assert "detected_plate" in result_dict
        print("  ✓ PlateDetectionResult funktioniert")
        
        return True
    except Exception as e:
        print(f"  ✗ Fehler: {e}")
        return False


def test_image_processor():
    """Test 5: ImageProcessor funktioniert"""
    print("\n[5] Teste ImageProcessor...")
    
    try:
        import cv2
        import numpy as np
        from AI import ImageProcessor
        
        processor = ImageProcessor()
        
        # Test resize
        test_img = np.zeros((100, 100, 3), dtype=np.uint8)
        resized = processor.resize_image(test_img, width=50)
        assert resized.shape[0] == 50  # Höhe sollte auch 50 sein (keep_aspect=True)
        print("  ✓ Resize funktioniert")
        
        # Test enhance_contrast
        enhanced = processor.enhance_contrast(test_img)
        assert enhanced.shape == test_img.shape
        print("  ✓ Enhance contrast funktioniert")
        
        # Test convert to grayscale
        gray = processor.convert_to_grayscale(test_img)
        assert len(gray.shape) == 2
        print("  ✓ Grayscale konvertierung funktioniert")
        
        return True
    except Exception as e:
        print(f"  ✗ Fehler: {e}")
        return False


def test_service_singleton():
    """Test 6: PlateRecognitionService Singleton"""
    print("\n[6] Teste PlateRecognitionService Singleton...")
    
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from backend.services.plate_recognition_service import PlateRecognitionService
        
        service1 = PlateRecognitionService.get_instance()
        service2 = PlateRecognitionService.get_instance()
        
        assert service1 is service2, "Service sollte Singleton sein"
        print("  ✓ Singleton Pattern funktioniert")
        
        assert isinstance(service1.is_ready(), bool)
        print("  ✓ Service.is_ready() funktioniert")
        
        return True
    except Exception as e:
        print(f"  ✗ Fehler: {e}")
        return False


def test_api_endpoints():
    """Test 7: API-Endpoints sind registriert"""
    print("\n[7] Teste API-Endpoints...")
    
    try:
        sys.path.insert(0, str(Path(__file__).parent / "Dashboard"))
        from routes import router
        
        # Prüfe ob Routes registriert sind
        routes_str = str(router.routes)
        
        expected_endpoints = [
            "/api/recognition/detect-plate",
            "/api/recognition/upload-image",
            "/api/recognition/statistics",
            "/api/recognition/status",
            "/api/recognition/reset-statistics"
        ]
        
        found = 0
        for endpoint in expected_endpoints:
            if endpoint in routes_str:
                found += 1
        
        print(f"  ✓ {found}/{len(expected_endpoints)} Endpoints registriert")
        return found == len(expected_endpoints)
        
    except Exception as e:
        print(f"  ✗ Fehler: {e}")
        return False


def run_tests():
    """Führe alle Tests durch"""
    print("\n" + "="*60)
    print("INTEGRATIONS-TEST FÜR KENNZEICHEN-ERKENNUNGSSYSTEM")
    print("="*60)
    
    tests = [
        ("Imports", test_imports),
        ("YOLO Loading", test_yolo_loading),
        ("Tesseract OCR", test_tesseract),
        ("Data Models", test_data_models),
        ("ImageProcessor", test_image_processor),
        ("Service Singleton", test_service_singleton),
        ("API Endpoints", test_api_endpoints),
    ]
    
    results = {}
    
    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            print(f"\n✗ Unerwarteter Fehler in {name}: {e}")
            results[name] = False
    
    # Zusammenfassung
    print("\n" + "="*60)
    print("ZUSAMMENFASSUNG")
    print("="*60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}  {name}")
    
    print(f"\nGesamt: {passed}/{total} Tests bestanden")
    
    if passed == total:
        print("\n✓ Alle Tests bestanden! System ist einsatzbereit.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} Test(s) fehlgeschlagen.")
        print("Bitte überprüfe die Fehler oben.")
        return 1


if __name__ == "__main__":
    exit_code = run_tests()
    sys.exit(exit_code)
