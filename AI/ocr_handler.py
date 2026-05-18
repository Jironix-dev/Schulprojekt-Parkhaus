"""
OCR Handler: Optische Zeichenerkennung für Kennzeichen
Nutzt Tesseract oder pytesseract zur Text-Erkennung
"""

import cv2
import numpy as np
from typing import Tuple, Optional
import logging
import re

logger = logging.getLogger(__name__)

# Versuche pytesseract zu importieren
try:
    import pytesseract
    from PIL import Image
    TESSERACT_AVAILABLE = True
    logger.info("✓ Tesseract OCR verfügbar")
except ImportError:
    TESSERACT_AVAILABLE = False
    logger.warning("Tesseract OCR nicht installiert!")


class OCRHandler:
    """
    Verarbeitet optische Zeichenerkennung für Kennzeichen
    Nutzt Tesseract/pytesseract mit Preprocessing
    """
    
    # Muster für deutsche Kennzeichen: z.B. "B-AB 1234" oder "BAB1234"
    PLATE_PATTERN = re.compile(r'^[A-ZÄÖÜ]{1,3}\s?-?\s?[A-Z]{2}\s?-?\s?\d{1,4}$')
    
    def __init__(self, lang: str = 'deu', cleanup: bool = True):
        """
        Initialisiert OCRHandler
        
        Args:
            lang: Sprache für Tesseract ('deu' für Deutsch, 'eng' für Englisch, usw.)
            cleanup: Bildvorverarbeitung durchführen
        """
        self.lang = lang
        self.cleanup = cleanup
        self.confidence_threshold = 0.3  # Minimale Konfidenz
        
        if not TESSERACT_AVAILABLE:
            logger.warning("Warnung: Tesseract nicht verfügbar!")
    
    def extract_text(self, plate_image: np.ndarray) -> Tuple[str, float]:
        """
        Extrahiert Text aus Kennzeichen-Bild mit OCR
        
        Args:
            plate_image: OpenCV Image des Kennzeichens (BGR)
            
        Returns:
            Tuple (detected_text, confidence_score)
        """
        if not TESSERACT_AVAILABLE:
            logger.error("Tesseract nicht installiert!")
            return "", 0.0
        
        try:
            if plate_image is None or plate_image.size == 0:
                logger.error("Ungültiges Eingabebild")
                return "", 0.0
            
            # Preprocessing
            processed = self._preprocess_image(plate_image)
            
            # OCR mit Tesseract
            try:
                # Tesseract Konfiguration
                custom_config = r'--oem 3 --psm 8'  # PSM 8 = Single line
                
                extracted_text = pytesseract.image_to_string(
                    processed,
                    lang=self.lang,
                    config=custom_config
                )
                
                extracted_text = extracted_text.strip()
                
                # Postprocessing: Cleanup und Normalisierung
                cleaned_text = self._clean_text(extracted_text)
                
                # Konfidenz berechnen
                confidence = self._calculate_confidence(cleaned_text, extracted_text)
                
                logger.info(f"OCR: '{extracted_text}' -> '{cleaned_text}' (Conf: {confidence:.2%})")
                
                return cleaned_text, confidence
                
            except pytesseract.TesseractNotFoundError:
                logger.error("Tesseract-Executable nicht gefunden!")
                return "", 0.0
            
        except Exception as e:
            logger.error(f"Fehler bei OCR: {e}")
            return "", 0.0
    
    def _preprocess_image(self, image: np.ndarray) -> Image:
        """
        Bereitet Bild für OCR vor
        - Grayscale
        - Kontrastverbesserung
        - Rauschentfernung
        - Scharfzeichnen
        
        Args:
            image: OpenCV BGR Image
            
        Returns:
            PIL Image für Tesseract
        """
        # Zu Grayscale konvertieren
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        
        # Rauschentfernung
        denoised = cv2.fastNlMeansDenoising(gray, None, h=10, templateWindowSize=7, searchWindowSize=21)
        
        # Kontrastverbesserung mit CLAHE
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(denoised)
        
        # Morphologische Operationen zur Bereinigung
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        cleaned = cv2.morphologyEx(enhanced, cv2.MORPH_CLOSE, kernel, iterations=1)
        
        # Scharfzeichnen
        kernel_sharpen = np.array([[-1, -1, -1],
                                   [-1,  9, -1],
                                   [-1, -1, -1]])
        sharpened = cv2.filter2D(cleaned, -1, kernel_sharpen)
        
        # Zu PIL konvertieren für Tesseract
        pil_image = Image.fromarray(sharpened)
        
        return pil_image
    
    def _clean_text(self, text: str) -> str:
        """
        Bereinigt erkannten Text
        - Entfernt ungültige Zeichen
        - Normalisiert Abstände
        - Konvertiert zu Großbuchstaben
        
        Args:
            text: Roher OCR-Output
            
        Returns:
            Gereinigter Text
        """
        # Zu Großbuchstaben
        text = text.upper().strip()
        
        # Ersetze Zahlen die wie Buchstaben aussehen
        replacements = {
            'O': '0',  # Letter O -> 0 (nicht immer richtig!)
            'I': '1',  # Letter I -> 1 (nicht immer richtig!)
            'Z': '2',  # Letter Z -> 2
            'B': '8',  # Letter B -> 8 (nicht immer richtig!)
        }
        
        # Vorsichtig ersetzen - nur am Ende wenn es eine Zahl sein sollte
        # Deutsche KFZ-Kennzeichen: 1-3 Buchstaben - 1-4 Ziffern
        
        # Entferne Sonderzeichen außer Bindestrich und Leerzeichen
        text = re.sub(r'[^A-Z0-9\s\-ÄÖÜ]', '', text)
        
        # Mehrfache Leerzeichen normalisieren
        text = re.sub(r'\s+', ' ', text)
        
        # Entferne führende/nachfolgende Leerzeichen
        text = text.strip()
        
        # Normalisiere Format: "AB-CD 1234" oder "ABCD1234"
        if text:
            # Entferne alle Leerzeichen zuerst
            text_no_space = text.replace(' ', '').replace('-', '')
            
            # Versuche Muster zu erkennen: 1-3 Buchstaben + 1-4 Ziffern
            match = re.match(r'([A-ZÄÖÜ]+)(\d+)', text_no_space)
            if match:
                letters = match.group(1)
                numbers = match.group(2)
                # Formatiere: "ABC-XY 1234" Style
                text = f"{letters[:1]}-{letters[1:]} {numbers}"
        
        return text
    
    def _calculate_confidence(self, cleaned_text: str, raw_text: str) -> float:
        """
        Berechnet Konfidenz des erkannten Textes
        Basiert auf Länge, Vollständigkeit und Validität
        
        Args:
            cleaned_text: Gereinigter Text
            raw_text: Roher OCR-Output
            
        Returns:
            Confidence Score (0.0-1.0)
        """
        if not cleaned_text:
            return 0.0
        
        confidence = 0.5  # Base
        
        # Ist es ein valides Kennzeichen?
        if self._is_valid_plate(cleaned_text):
            confidence += 0.4
        else:
            confidence -= 0.2
        
        # Länge prüfen (deutsche KFZ ca. 8 Zeichen)
        if 7 <= len(cleaned_text.replace(' ', '').replace('-', '')) <= 10:
            confidence += 0.1
        
        # Ähnlichkeit zwischen raw und cleaned
        similarity = self._text_similarity(cleaned_text, raw_text)
        confidence += similarity * 0.1
        
        # Auf 0.0-1.0 begrenzen
        confidence = max(0.0, min(1.0, confidence))
        
        return confidence
    
    def _is_valid_plate(self, text: str) -> bool:
        """Prüft ob Text ein valides Kennzeichen-Format hat"""
        # Deutsche KFZ: 1-3 Buchstaben, dann 1-4 Ziffern
        pattern = re.compile(r'^[A-ZÄÖÜ]{1,3}\s*-?\s*[A-Z]{0,2}\s*\d{1,4}$')
        return bool(pattern.match(text))
    
    def _text_similarity(self, text1: str, text2: str) -> float:
        """Berechnet Ähnlichkeit zwischen zwei Strings (0.0-1.0)"""
        # Einfache Levenshtein-ähnlich Metrik
        text1 = text1.replace(' ', '').replace('-', '')
        text2 = text2.replace(' ', '').replace('-', '')
        
        if not text1 or not text2:
            return 0.0
        
        matches = sum(c1 == c2 for c1, c2 in zip(text1, text2))
        return matches / max(len(text1), len(text2))
    
    def extract_with_fallback(self, plate_image: np.ndarray,
                             fallback_method: callable = None) -> Tuple[str, float]:
        """
        Extrahiert Text mit Fallback-Methode bei Fehler
        
        Args:
            plate_image: Eingabebild
            fallback_method: Fallback-Funktion wenn OCR fehlschlägt
            
        Returns:
            Tuple (text, confidence)
        """
        text, confidence = self.extract_text(plate_image)
        
        if not text and fallback_method:
            logger.info("OCR fehlgeschlagen, nutze Fallback...")
            text, confidence = fallback_method(plate_image)
        
        return text, confidence
