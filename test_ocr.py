#!/usr/bin/env python
"""Test script für OCR Handler"""

import cv2
import numpy as np
import logging
from pathlib import Path

# Logging konfigurieren
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

print("=" * 60)
print("🧪 OCR Handler Test Suite")
print("=" * 60)

# Test 1: Import
print("\n1️⃣ Testing imports...")
try:
    from AI.ocr_handler import OCRHandler, TESSERACT_AVAILABLE, PADDLEOCR_AVAILABLE
    print(f"✓ OCRHandler imported")
    print(f"  - Tesseract available: {TESSERACT_AVAILABLE}")
    print(f"  - PaddleOCR available: {PADDLEOCR_AVAILABLE}")
except ImportError as e:
    print(f"❌ Import error: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# Test 2: Handler initialization
print("\n2️⃣ Testing OCRHandler initialization...")
try:
    ocr = OCRHandler()
    print(f"✓ OCRHandler initialized")
    print(f"  - Cache size: {len(ocr._recognition_cache)}")
    print(f"  - Fallback to PaddleOCR: {ocr.use_paddle_fallback}")
except Exception as e:
    print(f"❌ Initialization error: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# Test 3: Test with synthetic image
print("\n3️⃣ Testing OCR with synthetic license plate image...")
try:
    # Erstelle ein synthetisches Kennzeichen-Bild
    # Einfaches schwarzes Bild mit weißem Text
    synthetic_plate = np.zeros((60, 200, 3), dtype=np.uint8)
    synthetic_plate[:] = (255, 255, 255)  # Weißer Hintergrund
    
    # Schreibe Text darauf
    cv2.putText(synthetic_plate, "A 1234", (30, 45), 
                cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0), 2)
    
    # Speichere für Debug
    test_image_path = Path("test_plate.jpg")
    cv2.imwrite(str(test_image_path), synthetic_plate)
    print(f"  - Test image saved to: {test_image_path}")
    
    # Teste OCR
    print(f"  - Extracting text...")
    text, confidence = ocr.extract_text(synthetic_plate)
    print(f"✓ OCR completed")
    print(f"  - Text: '{text}'")
    print(f"  - Confidence: {confidence:.2%}")
    
except Exception as e:
    print(f"❌ OCR test error: {e}")
    import traceback
    traceback.print_exc()

# Test 4: Tesseract direct test
print("\n4️⃣ Testing Tesseract directly...")
try:
    import pytesseract
    print(f"✓ pytesseract imported")
    
    # Erstelle Test-Bild
    test_img = np.ones((100, 300, 3), dtype=np.uint8) * 255
    cv2.putText(test_img, "TEST A 1234", (20, 60), 
                cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 0), 2)
    
    # Tesseract config
    custom_config = r'--psm 6 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÜ0123456789'
    
    result = pytesseract.image_to_string(test_img, config=custom_config, lang='eng')
    print(f"  - Tesseract output: '{result.strip()}'")
    
except Exception as e:
    print(f"❌ Tesseract direct test error: {e}")
    import traceback
    traceback.print_exc()

# Test 5: Statistics
print("\n5️⃣ Testing statistics...")
try:
    stats = ocr.get_statistics()
    print(f"✓ Statistics retrieved:")
    for key, value in stats.items():
        print(f"  - {key}: {value}")
except Exception as e:
    print(f"❌ Statistics error: {e}")

print("\n" + "=" * 60)
print("✅ Test suite completed!")
print("=" * 60)
