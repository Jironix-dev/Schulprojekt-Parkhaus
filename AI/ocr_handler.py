"""
OCR Handler: Optische Zeichenerkennung für Kennzeichen
Nutzt Tesseract OCR für ultra-schnelle Text-Erkennung (optimiert für ARM/RPi5)
Fallback: PaddleOCR für komplexere Szenen
"""

import cv2
import numpy as np
from typing import Tuple, Optional
import logging
import re
import time

logger = logging.getLogger(__name__)

# Versuche pytesseract zu importieren
try:
    import pytesseract
    TESSERACT_AVAILABLE = True
    logger.info("✓ Tesseract OCR verfügbar")
except ImportError:
    pytesseract = None  # type: ignore
    TESSERACT_AVAILABLE = False
    logger.warning("⚠️ Tesseract OCR nicht installiert!")

# Fallback: PaddleOCR
try:
    from paddleocr import PaddleOCR
    PADDLEOCR_AVAILABLE = True
    logger.info("✓ PaddleOCR verfügbar (Fallback)")
except ImportError:
    PaddleOCR = None  # type: ignore
    PADDLEOCR_AVAILABLE = False
    logger.info("ℹ️ PaddleOCR nicht verfügbar (nur Tesseract)")


class OCRHandler:
    """
    Optische Zeichenerkennung für Kennzeichen
    Primär: Tesseract OCR (ultra-schnell)
    Fallback: PaddleOCR (genauer bei komplexen Bildern)
    """
    
    # Muster für Kennzeichen-Validierung
    PLATE_PATTERN = re.compile(r'^[A-ZÄÖÜ]\s\d{4}$')
    
    def __init__(self, lang: str = 'en', cleanup: bool = True):
        """
        Initialisiert OCRHandler mit Tesseract
        
        Args:
            lang: Sprache ('en' für Englisch)
            cleanup: Bildvorverarbeitung durchführen
        """
        self.lang = lang
        self.cleanup = cleanup
        self.confidence_threshold = 0.3
        self.tesseract_reader = None
        self.paddle_reader = None
        self._recognition_cache = {}  # Cache für häufig erkannte Kennzeichen
        self.use_paddle_fallback = PADDLEOCR_AVAILABLE
        
        logger.info("[Tesseract] Handler initialisiert")
        logger.info(f"[Tesseract] Fallback zu PaddleOCR: {self.use_paddle_fallback}")
    
    def _load_ocr(self):
        """Lazy Loading für OCR - nur wenn nötig"""
        if self.paddle_reader is not None or not PADDLEOCR_AVAILABLE:
            return
        
        if PaddleOCR is None:
            logger.warning("[PaddleOCR] PaddleOCR nicht verfügbar")
            return
        
        try:
            logger.info("[PaddleOCR] Lade Reader (erste Nutzung als Fallback)...")
            self.paddle_reader = PaddleOCR(
                use_angle_cls=False,
                lang='en',
                use_gpu=False,
            )
            logger.info("✓ [PaddleOCR] Reader erfolgreich geladen")
        except Exception as e:
            logger.error(f"[PaddleOCR] Fehler beim Laden: {e}")
            self.paddle_reader = None
    
    def extract_text(self, plate_image: np.ndarray) -> Tuple[str, float]:
        """
        Extrahiert Text aus Kennzeichen-Bild mit Tesseract (ultra-schnell!)
        
        Strategie:
        1. Cache prüfen (0ms) 🚀
        2. Tesseract RAW (50-150ms) ⚡
        3. Tesseract mit Preprocessing (100-200ms) 
        4. Fallback zu PaddleOCR wenn konfiguriert (200-400ms)
        
        Args:
            plate_image: OpenCV Image des Kennzeichens (BGR)
            
        Returns:
            Tuple (detected_text, confidence_score)
        """
        if plate_image is None or plate_image.size == 0:
            logger.error("❌ Ungültiges Eingabebild")
            return "", 0.0
        
        h, w = plate_image.shape[:2]
        logger.info(f"[Tesseract] Eingabe-Bildgröße: {w}x{h}px")
        
        # ===== UPSCALING: Falls zu klein, vergrößere das Bild =====
        if w < 100 or h < 30:
            logger.info(f"[Tesseract] Bild zu klein ({w}x{h}), skaliere hoch...")
            scale_factor = max(100 / w, 30 / h) * 1.5
            new_w = int(w * scale_factor)
            new_h = int(h * scale_factor)
            plate_image = cv2.resize(plate_image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            logger.info(f"[Tesseract] Nach Upscaling: {new_w}x{new_h}px")
        
        # ===== CACHING: Prüfe ob dieses Bild bereits erkannt wurde =====
        image_hash = hash(plate_image.tobytes())
        if image_hash in self._recognition_cache:
            cached_result = self._recognition_cache[image_hash]
            logger.info(f"[CACHE-HIT] ✓ Ergebnis aus Cache: '{cached_result[0]}' (Conf: {cached_result[1]:.2%})")
            return cached_result
        
        if not TESSERACT_AVAILABLE:
            logger.error("❌ Tesseract nicht verfügbar!")
            return "", 0.0
        
        # ===== VERSUCH 1: TESSERACT RAW (SUPER SCHNELL!) =====
        logger.info("[Tesseract] Versuch 1: RAW image ohne Preprocessing")
        
        try:
            text, confidence = self._extract_with_tesseract(plate_image)
            
            if text and text.strip():
                cleaned_text = self._clean_text(text)
                final_conf = self._calculate_confidence(cleaned_text, text, confidence)
                
                logger.info(f"✓ [Tesseract] SUCCESS: '{cleaned_text}' (Conf: {final_conf:.2%})")
                
                # Cache
                self._recognition_cache[image_hash] = (cleaned_text, final_conf)
                if len(self._recognition_cache) > 100:
                    keys_to_remove = list(self._recognition_cache.keys())[:-50]
                    for key in keys_to_remove:
                        del self._recognition_cache[key]
                
                return cleaned_text, final_conf
        except Exception as e:
            logger.warning(f"[Tesseract] RAW Fehler: {e}")
        
        # ===== VERSUCH 2: TESSERACT MIT PREPROCESSING =====
        logger.info("[Tesseract] Versuch 2: Mit Preprocessing")
        
        try:
            processed = self._preprocess_image(plate_image, aggressive=False)
            text, confidence = self._extract_with_tesseract(processed)
            
            if text and text.strip():
                cleaned_text = self._clean_text(text)
                final_conf = self._calculate_confidence(cleaned_text, text, confidence)
                
                logger.info(f"✓ [Tesseract] PREPROCESSED SUCCESS: '{cleaned_text}' (Conf: {final_conf:.2%})")
                
                # Cache
                self._recognition_cache[image_hash] = (cleaned_text, final_conf)
                if len(self._recognition_cache) > 100:
                    keys_to_remove = list(self._recognition_cache.keys())[:-50]
                    for key in keys_to_remove:
                        del self._recognition_cache[key]
                
                return cleaned_text, final_conf
        except Exception as e:
            logger.warning(f"[Tesseract] Preprocessing Fehler: {e}")
        
        # ===== VERSUCH 3: TESSERACT MIT AGGRESSIVEM PREPROCESSING =====
        logger.info("[Tesseract] Versuch 3: Aggressive Preprocessing")
        
        try:
            processed = self._preprocess_image(plate_image, aggressive=True)
            text, confidence = self._extract_with_tesseract(processed)
            
            if text and text.strip():
                cleaned_text = self._clean_text(text)
                final_conf = self._calculate_confidence(cleaned_text, text, confidence)
                
                logger.info(f"✓ [Tesseract] AGGRESSIVE SUCCESS: '{cleaned_text}' (Conf: {final_conf:.2%})")
                
                # Cache
                self._recognition_cache[image_hash] = (cleaned_text, final_conf)
                if len(self._recognition_cache) > 100:
                    keys_to_remove = list(self._recognition_cache.keys())[:-50]
                    for key in keys_to_remove:
                        del self._recognition_cache[key]
                
                return cleaned_text, final_conf
        except Exception as e:
            logger.warning(f"[Tesseract] Aggressive Fehler: {e}")
        
        # ===== FALLBACK: PADDLEOCR (wenn konfiguriert) =====
        if self.use_paddle_fallback:
            logger.info("[PaddleOCR] Fallback zu PaddleOCR (Tesseract war erfolglos)")
            
            self._load_ocr()
            if self.paddle_reader is not None:
                try:
                    text, paddle_confidence = self._extract_with_paddle(plate_image)
                    
                    if text and text.strip():
                        cleaned_text = self._clean_text(text)
                        final_conf = self._calculate_confidence(cleaned_text, text, paddle_confidence)
                        
                        logger.info(f"✓ [PaddleOCR] FALLBACK SUCCESS: '{cleaned_text}' (Conf: {final_conf:.2%})")
                        
                        # Cache
                        self._recognition_cache[image_hash] = (cleaned_text, final_conf)
                        if len(self._recognition_cache) > 100:
                            keys_to_remove = list(self._recognition_cache.keys())[:-50]
                            for key in keys_to_remove:
                                del self._recognition_cache[key]
                        
                        return cleaned_text, final_conf
                except Exception as e:
                    logger.error(f"[PaddleOCR] Fehler: {e}")
        
        logger.warning("[OCR] ⚠️ Keine OCR-Engine konnte Text erkennen")
        return "", 0.0
    
    def _extract_with_tesseract(self, image: np.ndarray) -> Tuple[str, float]:
        """
        Extrahiert Text mit Tesseract OCR
        
        Returns:
            Tuple (text, confidence_score)
        """
        try:
            if pytesseract is None:
                logger.error("[Tesseract] pytesseract nicht verfügbar")
                return "", 0.0
            
            # Tesseract Config für Kennzeichen-Erkennung
            # --psm 6: Nehme an ein Block Text
            # --oem 3: Test klassische + LSTM
            # -c tessedit_char_whitelist: Nur Ziffern + Buchstaben
            custom_config = r'--psm 6 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÜ0123456789'
            
            # Extrahiere mit Tesseract
            text = pytesseract.image_to_string(image, config=custom_config, lang='eng')
            
            # Tesseract gibt keine native Confidence zurück, daher nutzen wir eine Heuristik
            # Basierend auf Text-Länge und Zeichen-Vielfalt
            text_clean = text.strip()
            
            if text_clean:
                # Heuristik für Konfidenz
                has_letters = any(c.isalpha() for c in text_clean)
                has_digits = any(c.isdigit() for c in text_clean)
                
                # Idealerweise: 1 Buchstabe + 4 Ziffern = hohe Konfidenz
                if has_letters and has_digits:
                    confidence = 0.85
                elif len(text_clean) >= 4:
                    confidence = 0.75
                else:
                    confidence = 0.60
                
                logger.debug(f"[Tesseract] Text: '{text_clean}', Conf: {confidence:.2%}")
                return text_clean, confidence
            
            return "", 0.0
            
        except Exception as e:
            logger.error(f"[Tesseract] Fehler: {e}")
            return "", 0.0
    
    def _extract_with_paddle(self, image: np.ndarray) -> Tuple[str, float]:
        """
        Extrahiert Text mit PaddleOCR (Fallback)
        
        Returns:
            Tuple (text, confidence_score)
        """
        if self.paddle_reader is None:
            return "", 0.0
        
        try:
            result = self.paddle_reader.ocr(image, cls=False)
            
            if result and result[0]:
                texts = [item[1][0] for item in result[0]]
                confidences = [item[1][1] for item in result[0]]
                
                combined_text = "".join(texts).strip()
                avg_confidence = float(np.mean(confidences)) if confidences else 0.0
                
                logger.debug(f"[PaddleOCR] Text: '{combined_text}', Conf: {avg_confidence:.2%}")
                return combined_text, avg_confidence
            
            return "", 0.0
            
        except Exception as e:
            logger.error(f"[PaddleOCR] Fehler: {e}")
            return "", 0.0
    
    def _preprocess_image(self, image: np.ndarray, aggressive: bool = False) -> np.ndarray:
        """
        Optimiertes Preprocessing für Tesseract + RPi5
        
        Strategie:
        - Grayscale
        - CLAHE (Kontrastverbesserung)
        - Scharfzeichnen
        - Optional: Binarisierung für aggressive Mode
        """
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        
        # Kontrastverbesserung mit CLAHE
        if aggressive:
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            logger.debug("[PREPROCESS] Aggressive CLAHE (clip=3.0)")
        else:
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            logger.debug("[PREPROCESS] Standard CLAHE (clip=2.0)")
        
        enhanced = clahe.apply(gray)
        
        # Scharfzeichnen
        kernel_sharpen = np.array([[-1, -1, -1], [-1, 5, -1], [-1, -1, -1]])
        sharpened = cv2.filter2D(enhanced, -1, kernel_sharpen)
        
        # Aggressive Mode: Binarisierung (schwarz/weiß)
        if aggressive:
            # Adaptiver Threshold für bessere Unterscheidung
            binary = cv2.adaptiveThreshold(sharpened, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                           cv2.THRESH_BINARY, 11, 2)
            logger.debug("[PREPROCESS] Adaptive Threshold angewendet")
            return binary
        
        return sharpened
    
    def _clean_text(self, text: str) -> str:
        """
        Bereinigt und normalisiert erkannten Text
        
        Unterstützt:
        - Gültiges Format: A 1234
        - Variationen: A1234, A  1234, etc.
        """
        if not text or not text.strip():
            return ""
        
        text = text.upper().strip()
        logger.debug(f"[CLEAN] Start: '{text}'")
        
        # Entferne ungültige Zeichen
        text = re.sub(r'[^A-ZÄÖÜ0-9\s]', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        
        if not text:
            return ""
        
        # Versuch 1: Mit Leerzeichen, exakt 4 Ziffern (gültiges Format: A 1234)
        match = re.search(r'([A-ZÄÖÜ])\s*([0-9]{4})', text)
        if match:
            result = f"{match.group(1)} {match.group(2)}"
            logger.debug(f"[CLEAN] Match (gültig): '{result}'")
            return result
        
        # Versuch 2: Ohne Leerzeichen, exakt 5 Zeichen (z.B. A1234)
        text_no_space = text.replace(' ', '')
        match = re.search(r'^([A-ZÄÖÜ])([0-9]{4})$', text_no_space)
        if match:
            result = f"{match.group(1)} {match.group(2)}"
            logger.debug(f"[CLEAN] Match (kein Space): '{result}'")
            return result
        
        # Versuch 3: Beliebiges Format mit mindestens 1 Buchstabe + 2 Ziffern
        if len(text_no_space) >= 3:
            result = text  # Gib bereinigten Text zurück
            logger.debug(f"[CLEAN] Match (fallback): '{result}'")
            return result
        
        logger.warning(f"[CLEAN] Text zu kurz: '{text}'")
        return ""
    
    def _calculate_confidence(self, cleaned_text: str, raw_text: str, ocr_confidence: float) -> float:
        """
        Berechnet finale Konfidenz basierend auf mehreren Faktoren
        
        Faktoren:
        - OCR native Konfidenz (50%)
        - Format-Validität (30%)
        - Text-Länge (20%)
        """
        confidence = ocr_confidence * 0.5  # 50% basierend auf OCR
        
        # Format-Validität (30%)
        if self._is_valid_format(cleaned_text):
            confidence += 0.3
        elif len(cleaned_text) >= 4:
            confidence += 0.15
        else:
            confidence -= 0.1
        
        # Text-Länge (20%)
        if len(cleaned_text) == 5:  # Ideal: "A 1234"
            confidence += 0.20
        elif 4 <= len(cleaned_text) <= 6:
            confidence += 0.10
        else:
            confidence -= 0.05
        
        # Zeichen-Analyse
        has_letters = any(c.isalpha() for c in cleaned_text)
        has_digits = any(c.isdigit() for c in cleaned_text)
        if has_letters and has_digits:
            confidence += 0.05
        
        return max(0.0, min(1.0, confidence))
    
    def _is_valid_format(self, text: str) -> bool:
        """Prüft ob Text gültiges Kennzeichen-Format hat"""
        if not text:
            return False
        normalized = text.upper().strip().replace(' ', '')
        
        # Pattern: 1-2 Buchstaben + 1-4 Ziffern (oder umgekehrt)
        patterns = [
            r'^[A-Z]{1}\d{4}$',  # A 1234
            r'^[A-Z]{2}\d{3,4}$',  # AA 123 / AA 1234
            r'^[A-Z]{1}\d{3,4}$',  # A 123 / A 1234
        ]
        
        for pattern in patterns:
            if re.match(pattern, normalized):
                return True
        
        return False
    
    def get_statistics(self) -> dict:
        """Gibt Statistiken zurück (wenn implementiert)"""
        return {
            "cache_size": len(self._recognition_cache),
            "tesseract_available": TESSERACT_AVAILABLE,
            "paddleocr_available": PADDLEOCR_AVAILABLE,
        }
    
    def reset_cache(self):
        """Setzt den Cache zurück"""
        self._recognition_cache.clear()
        logger.info("Cache zurückgesetzt")
