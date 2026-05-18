"""
OCR Handler: Optische Zeichenerkennung für Kennzeichen
Nutzt Tesseract oder pytesseract zur Text-Erkennung
"""

import cv2
import numpy as np
from typing import Tuple, Optional, List
import logging
import re
import string

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

# Versuche EasyOCR zu importieren
try:
    import easyocr
    EASYOCR_AVAILABLE = True
    logger.info("✓ EasyOCR verfügbar")
except ImportError:
    EASYOCR_AVAILABLE = False
    logger.warning("EasyOCR nicht installiert!")


class OCRHandler:
    """
    Verarbeitet optische Zeichenerkennung für Kennzeichen
    Nutzt Tesseract/pytesseract mit Preprocessing
    Custom Format: A 1234 (ein Buchstabe, Leerzeichen, 4 Ziffern)
    """
    
    # Muster für custom Kennzeichen: z.B. "A 1234"
    PLATE_PATTERN = re.compile(r'^[A-ZÄÖÜ]\s\d{4}$')
    
    def __init__(self, lang: str = 'deu', cleanup: bool = True, use_easyocr: bool = False):
        """
        Initialisiert OCRHandler
        
        Args:
            lang: Sprache für Tesseract ('deu' für Deutsch, 'eng' für Englisch, usw.)
            cleanup: Bildvorverarbeitung durchführen
            use_easyocr: EasyOCR verwenden (langsam, aber genauer - nur bei Bedarf)
        """
        self.lang = lang
        self.cleanup = cleanup
        self.confidence_threshold = 0.3  # Minimale Konfidenz
        self.easyocr_reader = None
        self.use_easyocr = use_easyocr
        self._easyocr_loaded = False
        
        if not TESSERACT_AVAILABLE:
            logger.warning("Warnung: Tesseract nicht verfügbar!")
        
        logger.info(f"[OCR] EasyOCR aktiviert: {use_easyocr}")
    
    def _load_easyocr(self):
        """Lazy Loading für EasyOCR Reader - nur bei Bedarf"""
        if self._easyocr_loaded or self.easyocr_reader is not None:
            return
        
        if not EASYOCR_AVAILABLE:
            logger.warning("[EasyOCR] Nicht installiert!")
            self._easyocr_loaded = True
            return
        
        try:
            logger.info("[EasyOCR] Lade Reader (erste Nutzung)...")
            self.easyocr_reader = easyocr.Reader(['de', 'en'], gpu=False)
            logger.info("✓ [EasyOCR] Reader erfolgreich geladen")
            self._easyocr_loaded = True
        except Exception as e:
            logger.warning(f"[EasyOCR] Konnte Reader nicht laden: {e}")
            self._easyocr_loaded = True
    
    def extract_text(self, plate_image: np.ndarray) -> Tuple[str, float]:
        """
        Extrahiert Text aus Kennzeichen-Bild mit OCR (optimiert für Geschwindigkeit)
        
        Schnelle Strategie (Standard):
        1. Tesseract mit 2 schnellen Preprocessing-Varianten
        2. Wähle beste Erkennung
        3. Fertig in <2 Sekunden
        
        Args:
            plate_image: OpenCV Image des Kennzeichens (BGR)
            
        Returns:
            Tuple (detected_text, confidence_score)
        """
        if plate_image is None or plate_image.size == 0:
            logger.error("❌ Ungültiges Eingabebild")
            return "", 0.0
        
        logger.info(f"[OCR] Eingabe-Bildgröße: {plate_image.shape}")
        
        results = []
        
        # ===== TESSERACT ERKENNUNG (SCHNELL) =====
        if TESSERACT_AVAILABLE:
            logger.info("[OCR] Starte Tesseract-Erkennung (2 Varianten)...")
            tess_results = self._tesseract_multi_variant(plate_image)
            results.extend(tess_results)
        
        # ===== EASYOCR NUR BEI BEDARF =====
        # EasyOCR ist sehr langsam - nur wenn explizit angefordert
        if self.use_easyocr and EASYOCR_AVAILABLE:
            logger.info("[OCR] EasyOCR angefordert - lade Reader...")
            self._load_easyocr()
            if self.easyocr_reader:
                logger.info("[OCR] Starte EasyOCR-Erkennung...")
                easy_results = self._easyocr_recognize(plate_image)
                results.extend(easy_results)
        
        if not results:
            logger.warning("[OCR] ⚠️ Keine verwertbaren Ergebnisse!")
            return "", 0.0
        
        # Sortiere nach Validität und Konfidenz
        results.sort(key=lambda x: (
            self._is_valid_format(x[0]) or self._is_invalid_plate_format(x[0]),
            self._is_valid_format(x[0]),
            x[1]
        ), reverse=True)
        
        best_text, best_conf, engine = results[0]
        logger.info(f"✓ [OCR] Beste Erkennung aus {engine}: '{best_text}' (Conf: {best_conf:.2%})")
        
        cleaned_text = self._clean_text(best_text)
        final_conf = self._calculate_confidence(cleaned_text, best_text)
        
        logger.info(f"✓ [OCR] Final: '{cleaned_text}' (Conf: {final_conf:.2%})")
        
        return cleaned_text, final_conf
    
    def _tesseract_multi_variant(self, plate_image: np.ndarray) -> List[Tuple[str, float, str]]:
        """
        Tesseract mit smartem Fallback-System (sehr schnell)
        
        1. Versuche nur Variante 1 (Standard - 1 Sekunde)
        2. Wenn Konfidenz < 0.5, versuche auch Variante 2 (Aggressiv - +2 Sekunden)
        3. Nutze beste Erkennung
        """
        results = []
        
        # Variante 1: Standard Preprocessing (IMMER)
        logger.info("[OCR] Variante 1: Standard Preprocessing")
        text_1, conf_1 = self._extract_with_tesseract(plate_image, 1)
        if text_1:
            results.append((text_1, conf_1, "Tesseract-Standard"))
            logger.info(f"[OCR] Standard-Erkennung: '{text_1}' (Conf: {conf_1:.2%})")
            
            # Fallback: Nur versuchen wenn Standard schlecht war
            if conf_1 < 0.5:
                logger.info("[OCR] Konfidenz niedrig - versuche Variante 2")
                text_2, conf_2 = self._extract_with_tesseract(plate_image, 2)
                if text_2:
                    results.append((text_2, conf_2, "Tesseract-Aggressiv"))
                    logger.info(f"[OCR] Aggressiv-Erkennung: '{text_2}' (Conf: {conf_2:.2%})")
        
        return results
    
    def _extract_with_tesseract(self, plate_image: np.ndarray, variant: int) -> Tuple[str, float]:
        """Tesseract OCR mit spezieller Preprocessing-Variante (schnell)"""
        try:
            if variant == 1:
                # Standard: Schnell und zuverlässig
                processed = self._preprocess_image(plate_image, aggressive=False)
            elif variant == 2:
                # Aggressiv: Besserer Kontrast für schwierige Bilder
                processed = self._preprocess_image(plate_image, aggressive=True)
            else:
                processed = self._preprocess_image(plate_image, aggressive=False)
            
            # OCR mit Tesseract
            custom_config = r'--oem 3 --psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÜ0123456789 '
            
            extracted_text = pytesseract.image_to_string(
                processed,
                lang=self.lang,
                config=custom_config
            ).strip()
            
            logger.info(f"[Tesseract] Variante {variant} Raw: '{extracted_text}'")
            
            if not extracted_text:
                return "", 0.0
            
            # Berechne Konfidenz basierend auf Format
            confidence = self._calculate_confidence(self._clean_text(extracted_text), extracted_text)
            
            return extracted_text, confidence
            
        except Exception as e:
            logger.error(f"[Tesseract] Fehler in Variante {variant}: {e}")
            return "", 0.0
    
    def _easyocr_recognize(self, plate_image: np.ndarray) -> List[Tuple[str, float, str]]:
        """EasyOCR Erkennung mit zwei Preprocessing-Varianten"""
        results = []
        
        if not self.easyocr_reader:
            return results
        
        try:
            # Variante 1: Standard
            logger.info("[EasyOCR] Variante 1: Standard")
            processed_std = self._preprocess_image(plate_image, aggressive=False)
            
            # Konvertiere PIL zu OpenCV
            if isinstance(processed_std, Image.Image):
                processed_std = cv2.cvtColor(np.array(processed_std), cv2.COLOR_RGB2BGR)
            
            text_1, conf_1 = self._extract_with_easyocr(processed_std)
            if text_1:
                results.append((text_1, conf_1, "EasyOCR-Standard"))
            
            # Variante 2: Aggressiv
            logger.info("[EasyOCR] Variante 2: Aggressiv")
            processed_agg = self._preprocess_image(plate_image, aggressive=True)
            
            if isinstance(processed_agg, Image.Image):
                processed_agg = cv2.cvtColor(np.array(processed_agg), cv2.COLOR_RGB2BGR)
            
            text_2, conf_2 = self._extract_with_easyocr(processed_agg)
            if text_2:
                results.append((text_2, conf_2, "EasyOCR-Aggressiv"))
            
        except Exception as e:
            logger.warning(f"[EasyOCR] Fehler: {e}")
        
        return results
    
    def _extract_with_easyocr(self, image: np.ndarray) -> Tuple[str, float]:
        """Extrahiert Text mit EasyOCR"""
        try:
            # EasyOCR benötigt BGR OpenCV format
            results = self.easyocr_reader.readtext(image, detail=1)
            
            if not results:
                return "", 0.0
            
            # Kombiniere alle erkannten Texte
            extracted_texts = []
            confidences = []
            
            for (bbox, text, conf) in results:
                extracted_texts.append(text)
                confidences.append(conf)
            
            combined_text = " ".join(extracted_texts).strip()
            avg_confidence = np.mean(confidences) if confidences else 0.0
            
            logger.info(f"[EasyOCR] Raw: '{combined_text}' (Conf: {avg_confidence:.2%})")
            
            return combined_text, avg_confidence
            
        except Exception as e:
            logger.error(f"[EasyOCR] Fehler: {e}")
            return "", 0.0
    
    def _is_valid_format(self, text: str) -> bool:
        """
        Überprüft ob Text dem custom Kennzeichen-Format entspricht: A 1234
        
        Args:
            text: Zu überprüfender Text
            
        Returns:
            True wenn Format gültig (A 1234), False sonst
        """
        if not text:
            return False
        
        # Normalisiere zuerst
        normalized = text.upper().strip()
        
        # Überprüfe Format: ein Buchstabe, Leerzeichen, 4 Ziffern
        match = re.match(r'^([A-ZÄÖÜ])\s(\d{4})$', normalized)
        
        is_valid = match is not None
        logger.info(f"[VALID] '{normalized}' -> Valid Format: {is_valid}")
        
        return is_valid
    
    def _is_invalid_plate_format(self, text: str) -> bool:
        """
        Überprüft ob Text die Form eines FALSCHEN Kennzeichens hat (z.B. A ABCD)
        Also: 1 Buchstabe + Leerzeichen + 4 Buchstaben statt Ziffern
        
        Args:
            text: Zu überprüfender Text
            
        Returns:
            True wenn falsches Kennzeichen-Format erkannt, False sonst
        """
        if not text:
            return False
        
        # Normalisiere zuerst
        normalized = text.upper().strip()
        
        # Überprüfe falsches Format: ein Buchstabe, Leerzeichen, 4 Buchstaben (statt Ziffern!)
        match = re.match(r'^([A-ZÄÖÜ])\s([A-ZÄÖÜ]{4})$', normalized)
        
        is_invalid = match is not None
        if is_invalid:
            logger.warning(f"❌ [INVALID PLATE] Erkanntes FALSCHES Kennzeichen: '{normalized}'")
        
        return is_invalid
    
    def _preprocess_image(self, image: np.ndarray, aggressive: bool = False) -> Image:
        """
        Bereitet Bild für OCR vor
        - Grayscale
        - Kontrastverbesserung
        - Rauschentfernung
        - Scharfzeichnen
        
        Args:
            image: OpenCV BGR Image
            aggressive: True für aggressivere Kontrastverbesserung
            
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
        if aggressive:
            # Aggressivere Einstellungen
            clahe = cv2.createCLAHE(clipLimit=5.0, tileGridSize=(6, 6))
            logger.info("[PREPROCESS] Verwende aggressive CLAHE")
        else:
            # Standard-Einstellungen
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
    
    def _preprocess_adaptive_threshold(self, image: np.ndarray) -> Image:
        """
        Preprocessing mit adaptivem Threshold (für schwierige Lichtverhältnisse)
        
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
        
        # Adaptiver Threshold
        thresh = cv2.adaptiveThreshold(
            denoised,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11,
            2
        )
        
        logger.info("[PREPROCESS] Verwende Adaptive Threshold")
        
        # Zu PIL konvertieren für Tesseract
        pil_image = Image.fromarray(thresh)
        
        return pil_image
    
    def _preprocess_for_character_distinction(self, image: np.ndarray) -> Image:
        """
        Spezielle Vorverarbeitung für bessere Zahlen/Buchstaben-Unterscheidung
        Optimiert für Falsche Kennzeichen (A ABCD)
        
        Args:
            image: OpenCV BGR Image
            
        Returns:
            PIL Image für Tesseract
        """
        try:
            # Zu Grayscale konvertieren
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image
            
            # Rauschentfernung (aggressiver für klare Kanten)
            denoised = cv2.fastNlMeansDenoising(
                gray, None, h=15, templateWindowSize=7, searchWindowSize=21
            )
            
            # Kontrastverbesserung mit höherem clipLimit für klare Unterscheidung
            clahe = cv2.createCLAHE(clipLimit=6.0, tileGridSize=(4, 4))
            enhanced = clahe.apply(denoised)
            
            # Lokales Threshold für bessere Kanten-Erkennung
            # Dies hilft, zwischen ähnlich geformten Zahlen und Buchstaben zu unterscheiden
            block_size = 15
            thresh = cv2.adaptiveThreshold(
                enhanced,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                block_size,
                3
            )
            
            # Morphologische Operationen zur Verbesserung der Zeichenform
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            # Dilatation für Teile, die zu dünn sind
            dilated = cv2.dilate(thresh, kernel, iterations=1)
            # Erosion zum Entfernen von Rauschen
            eroded = cv2.erode(dilated, kernel, iterations=1)
            
            # Scharfzeichnen für klare Kanten
            kernel_sharpen = np.array([[-1, -1, -1],
                                       [-1, 10, -1],
                                       [-1, -1, -1]])
            sharpened = cv2.filter2D(eroded, -1, kernel_sharpen)
            
            logger.info("[PREPROCESS] Character Distinction: Angewendet")
            
            # Zu PIL konvertieren für Tesseract
            pil_image = Image.fromarray(sharpened)
            
            return pil_image
        except Exception as e:
            logger.error(f"[PREPROCESS] Fehler bei Character Distinction: {e}")
            return self._preprocess_image(image, aggressive=True)
    
    def _clean_text(self, text: str) -> str:
        """
        Bereinigt erkannten Text für Format: A 1234 ODER A ABCD (falsch)
        - Entfernt ungültige Zeichen
        - Normalisiert Leerzeichen
        - Konvertiert zu Großbuchstaben
        - Extrahiert sowohl gültige als auch ungültige Formate
        
        Args:
            text: Roher OCR-Output
            
        Returns:
            Gereinigter Text im Format "A 1234" oder "A ABCD"
        """
        if not text:
            return ""
        
        # Zu Großbuchstaben
        text = text.upper().strip()
        logger.info(f"[CLEAN] Schritt 1 (Upper): '{text}'")
        
        # Entferne Sonderzeichen außer Bindestrich und Leerzeichen
        text = re.sub(r'[^A-ZÄÖÜ0-9\s\-]', '', text)
        logger.info(f"[CLEAN] Schritt 2 (Remove special): '{text}'")
        
        # Mehrfache Leerzeichen/Bindestriche normalisieren
        text = re.sub(r'[\s\-]+', ' ', text).strip()
        logger.info(f"[CLEAN] Schritt 3 (Normalize spaces): '{text}'")
        
        # Suche nach exaktem Format: 1 Buchstabe + Leerzeichen + exakt 4 Zeichen
        # Das sollte alle Varianten matchen:
        # - A 1234 (gültig - 4 Ziffern)
        # - A ABCD (ungültig - 4 Buchstaben)
        # - A 5BCG (hybrid/falsch erkannt - gemischt)
        match = re.search(r'([A-ZÄÖÜ])\s+([A-Z0-9]{4})', text)
        
        if match:
            letter = match.group(1)
            chars = match.group(2)
            
            formatted = f"{letter} {chars}"
            logger.info(f"[CLEAN] Formatiert (mit Leerzeichen): '{formatted}'")
            return formatted
        
        # ===== WICHTIG: FALLBACK FÜR FEHLENDE LEERZEICHEN =====
        # OCR erkannte das Leerzeichen nicht → "A1234" statt "A 1234"
        match_no_space = re.search(r'^([A-ZÄÖÜ])([A-Z0-9]{4})', text)
        if match_no_space:
            letter = match_no_space.group(1)
            chars = match_no_space.group(2)
            
            formatted = f"{letter} {chars}"  # WICHTIG: Leerzeichen einfügen!
            logger.info(f"[CLEAN] Formatiert (OCR ohne Leerzeichen): '{formatted}'")
            return formatted
        
        # Fallback: Falls exakt 4 Zeichen nicht funktioniert
        # Versuche beliebig viele Zeichen und nimm die ersten 4
        fallback_match = re.search(r'([A-ZÄÖÜ])\s+([A-Z0-9]+)', text)
        if fallback_match:
            letter = fallback_match.group(1)
            chars = fallback_match.group(2)
            
            # Nimm exakt 4 Zeichen
            first_four = chars[:4]
            
            formatted = f"{letter} {first_four}"
            logger.info(f"[CLEAN] Formatiert (beliebig lange + Leerzeichen): '{formatted}'")
            return formatted
        
        # Finaler Fallback: Buchstabe + 4+ Zeichen ohne Leerzeichen
        fallback_no_space = re.search(r'^([A-ZÄÖÜ])([A-Z0-9]+)', text)
        if fallback_no_space:
            letter = fallback_no_space.group(1)
            chars = fallback_no_space.group(2)[:4]  # Nimm erste 4
            
            formatted = f"{letter} {chars}"
            logger.info(f"[CLEAN] Formatiert (beliebig lange, kein Leerzeichen): '{formatted}'")
            return formatted
        
        logger.warning(f"[CLEAN] ⚠️ Konnte Format nicht extrahieren aus: '{text}'")
        return text
    
    def _calculate_confidence(self, cleaned_text: str, raw_text: str) -> float:
        """
        Berechnet Konfidenz des erkannten Textes
        Optimiert für Unterscheidung gültig/ungültig
        
        Berücksichtigt:
        1. Format-Gültigkeit (A 1234 vs A ABCD)
        2. Charakter-Analyse (Zahlen vs Buchstaben in Position)
        3. Ähnlichkeit raw/cleaned
        
        Args:
            cleaned_text: Gereinigter Text
            raw_text: Roher OCR-Output
            
        Returns:
            Confidence Score (0.0-1.0)
        """
        if not cleaned_text:
            return 0.0
        
        confidence = 0.3  # Base
        
        # 1. Format-Überprüfung
        is_valid = self._is_valid_format(cleaned_text)
        is_invalid = self._is_invalid_plate_format(cleaned_text)
        
        if is_valid:
            confidence += 0.5  # Gültig = höhere Base-Konfidenz
            logger.info(f"[CONF] '{cleaned_text}' ist GÜLTIG (A 1234)")
        elif is_invalid:
            confidence += 0.3  # Ungültig = mittlere Konfidenz
            logger.info(f"[CONF] '{cleaned_text}' ist UNGÜLTIG (A ABCD)")
        else:
            confidence -= 0.1  # Unbekanntes Format = niedrig
            logger.info(f"[CONF] '{cleaned_text}' Format UNBEKANNT")
        
        # 2. Character-by-Character Analyse
        char_analysis = self._analyze_character_types(cleaned_text)
        
        # Wenn Format A XXXX, überprüfe ob X wirklich nur Zahlen/Buchstaben
        if len(cleaned_text.replace(' ', '')) >= 5:
            # Position 0: Ein Buchstabe
            if cleaned_text[0].isalpha():
                confidence += 0.05
            else:
                confidence -= 0.1
            
            # Positionen 2+: Sollten Zahlen oder Buchstaben sein
            char_part = cleaned_text.split()[-1] if ' ' in cleaned_text else cleaned_text[1:]
            
            # Alle Positionen nach dem Leerzeichen sollten gleich sein (alle Zahlen ODER alle Buchstaben)
            digits = sum(1 for c in char_part if c.isdigit())
            letters = sum(1 for c in char_part if c.isalpha())
            
            # Wenn gemischt, ist es wahrscheinlich ein Fehler
            if digits > 0 and letters > 0:
                confidence -= 0.2
                logger.info(f"[CONF] Gemischte Zeichen in '{char_part}' - Fehler wahrscheinlich")
            elif digits == 4 or digits == len(char_part):
                confidence += 0.1  # Alle Ziffern = gut
            elif letters == 4 or letters == len(char_part):
                confidence += 0.05  # Alle Buchstaben = möglich aber wahrscheinlich falsch
        
        # 3. Ähnlichkeit zwischen raw und cleaned
        similarity = self._text_similarity(cleaned_text, raw_text)
        if similarity > 0.8:
            confidence += 0.1
        elif similarity < 0.5:
            confidence -= 0.05
        
        # 4. Länge-Check
        char_count = len(cleaned_text.replace(' ', '').replace('-', ''))
        if char_count == 5:  # Perfekt: A XXXX
            confidence += 0.05
        elif 4 <= char_count <= 6:
            confidence += 0.02
        else:
            confidence -= 0.1
        
        # Auf 0.0-1.0 begrenzen
        confidence = max(0.0, min(1.0, confidence))
        
        logger.info(f"[CONF] Final Confidence für '{cleaned_text}': {confidence:.2%}")
        
        return confidence
    
    def _analyze_character_types(self, text: str) -> dict:
        """
        Analysiert Charaktertypen im Text
        
        Returns:
            Dict mit Statistics über Zahlen, Buchstaben, etc.
        """
        clean = text.replace(' ', '').replace('-', '')
        return {
            'digits': sum(1 for c in clean if c.isdigit()),
            'letters': sum(1 for c in clean if c.isalpha()),
            'special': len(clean) - sum(1 for c in clean if c.isalnum()),
            'total': len(clean)
        }
    
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
