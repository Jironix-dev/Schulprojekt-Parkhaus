"""
Image Processor: Bildbearbeitung und Snapshot-Verwaltung
Verarbeitet Bilder, erstellt Snapshots und konvertiert Formate
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Optional, Tuple
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class ImageProcessor:
    """
    Verarbeitet Bilder für Kennzeichen-Erkennung
    - Snapshots speichern
    - Bilder zuschneiden
    - Format-Konvertierung
    """
    
    def __init__(self, output_dir: str = None):
        """
        Initialisiert ImageProcessor
        
        Args:
            output_dir: Verzeichnis für Snapshots. Wenn None, nutze default
        """
        if output_dir is None:
            output_dir = str(Path(__file__).parent / "detection_results")
        
        self.output_dir = Path(output_dir)
        self.snapshots_dir = self.output_dir / "snapshots"
        self.plates_dir = self.output_dir / "plates"
        self.annotated_dir = self.output_dir / "annotated"
        
        self._create_directories()
    
    def _create_directories(self) -> None:
        """Erstellt Output-Verzeichnisse"""
        for dir_path in [self.snapshots_dir, self.plates_dir, self.annotated_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"✓ Verzeichnis: {dir_path}")
    
    def crop_region(self, frame: np.ndarray, region: 'PlateRegion',
                   padding: int = 0) -> Optional[np.ndarray]:
        """
        Schneidet eine Region aus dem Frame aus
        
        Args:
            frame: OpenCV Frame (BGR)
            region: PlateRegion mit Koordinaten
            padding: Zusätzliche Pixel um die Region
            
        Returns:
            Zugeschnittenes Bild oder None bei Fehler
        """
        try:
            h, w = frame.shape[:2]
            
            # Mit Padding berechnen
            x1 = max(0, region.x1 - padding)
            y1 = max(0, region.y1 - padding)
            x2 = min(w, region.x2 + padding)
            y2 = min(h, region.y2 + padding)
            
            cropped = frame[y1:y2, x1:x2]
            
            if cropped.size == 0:
                logger.warning("Zugeschnittenes Bild ist leer")
                return None
            
            return cropped
        except Exception as e:
            logger.error(f"Fehler beim Zuschneiden: {e}")
            return None
    
    def save_snapshot(self, frame: np.ndarray, plate_text: str,
                     plate_confidence: float) -> Optional[Path]:
        """
        Speichert Snapshot des kompletten Fahrzeugs
        
        Args:
            frame: Komplettes Frame
            plate_text: Erkanntes Kennzeichen
            plate_confidence: Erkennungs-Konfidenz
            
        Returns:
            Pfad zum gespeicherten Bild oder None
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            filename = f"{plate_text.replace(' ', '_')}_{timestamp}.jpg"
            filepath = self.snapshots_dir / filename
            
            # Metadaten als Text hinzufügen
            annotated = frame.copy()
            text = f"Plate: {plate_text} | Conf: {plate_confidence:.2%}"
            cv2.putText(
                annotated, text,
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2
            )
            
            cv2.imwrite(str(filepath), annotated, [cv2.IMWRITE_JPEG_QUALITY, 95])
            logger.info(f"✓ Snapshot gespeichert: {filename}")
            return filepath
        except Exception as e:
            logger.error(f"Fehler beim Speichern des Snapshots: {e}")
            return None
    
    def save_plate_image(self, plate_image: np.ndarray, plate_text: str) -> Optional[Path]:
        """
        Speichert ausgeschnittenes Kennzeichen-Bild
        
        Args:
            plate_image: Ausgeschnittenes Kennzeichen-Bild
            plate_text: Erkannter Text
            
        Returns:
            Pfad zum gespeicherten Bild oder None
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            filename = f"plate_{plate_text.replace(' ', '_')}_{timestamp}.jpg"
            filepath = self.plates_dir / filename
            
            cv2.imwrite(str(filepath), plate_image, [cv2.IMWRITE_JPEG_QUALITY, 95])
            logger.info(f"✓ Kennzeichen-Bild gespeichert: {filename}")
            return filepath
        except Exception as e:
            logger.error(f"Fehler beim Speichern des Kennzeichen-Bildes: {e}")
            return None
    
    def save_annotated_frame(self, annotated_frame: np.ndarray,
                            plate_text: str) -> Optional[Path]:
        """
        Speichert annotiertes Frame mit Bounding Box
        
        Args:
            annotated_frame: Frame mit gezeichnetem Bounding Box
            plate_text: Erkannter Text
            
        Returns:
            Pfad zum gespeicherten Bild oder None
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            filename = f"annotated_{plate_text.replace(' ', '_')}_{timestamp}.jpg"
            filepath = self.annotated_dir / filename
            
            cv2.imwrite(str(filepath), annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
            logger.info(f"✓ Annotiertes Frame gespeichert: {filename}")
            return filepath
        except Exception as e:
            logger.error(f"Fehler beim Speichern des annotierten Frames: {e}")
            return None
    
    def resize_image(self, image: np.ndarray, width: int = None,
                    height: int = None, keep_aspect: bool = True) -> np.ndarray:
        """
        Ändert Bildgröße
        
        Args:
            image: Eingabebild
            width: Zielbreite (None = berechnet)
            height: Zielhöhe (None = berechnet)
            keep_aspect: Seitenverhältnis beibehalten
            
        Returns:
            Verändertes Bild
        """
        h, w = image.shape[:2]
        
        if width is None and height is None:
            return image
        
        if keep_aspect:
            if width is not None and height is None:
                aspect = w / h
                height = int(width / aspect)
            elif height is not None and width is None:
                aspect = w / h
                width = int(height * aspect)
        
        return cv2.resize(image, (width, height), interpolation=cv2.INTER_AREA)
    
    def enhance_contrast(self, image: np.ndarray, alpha: float = 1.5,
                        beta: float = 0) -> np.ndarray:
        """
        Verbessert Kontrast für bessere OCR
        Formel: output = alpha * input + beta
        
        Args:
            image: Eingabebild
            alpha: Kontrast-Multiplikator
            beta: Helligkeit-Offset
            
        Returns:
            Verbessertes Bild
        """
        enhanced = cv2.convertScaleAbs(image, alpha=alpha, beta=beta)
        return enhanced
    
    def convert_to_grayscale(self, image: np.ndarray) -> np.ndarray:
        """Konvertiert zu Grayscale für OCR"""
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    def apply_morphological_ops(self, image: np.ndarray) -> np.ndarray:
        """
        Wendet morphologische Operationen an zur Bildbereinigung
        Nützlich für OCR-Preprocessing
        """
        gray = self.convert_to_grayscale(image)
        
        # Schwellenwert
        _, binary = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
        
        # Morphologische Operationen
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        
        return cleaned
    
    def get_image_dimensions(self, image: np.ndarray) -> Tuple[int, int]:
        """Gibt Breite und Höhe des Bildes zurück"""
        h, w = image.shape[:2]
        return w, h
    
    def create_grid_display(self, images: dict, title: str = "Detection Results") -> np.ndarray:
        """
        Erstellt Grid-Anzeige mehrerer Bilder
        
        Args:
            images: Dict mit {"name": image}
            title: Titel des Grids
            
        Returns:
            Kombiniertes Bild
        """
        try:
            if not images:
                return None
            
            # Bilder auf gleiche Größe skalieren
            target_size = (300, 300)
            resized_images = []
            names = []
            
            for name, img in images.items():
                resized = self.resize_image(img, width=target_size[0], height=target_size[1])
                # Zu BGR konvertieren falls Grayscale
                if len(resized.shape) == 2:
                    resized = cv2.cvtColor(resized, cv2.COLOR_GRAY2BGR)
                resized_images.append(resized)
                names.append(name)
            
            # Grid erstellen (2x2 bei 4 Bildern, 1xN sonst)
            rows = (len(resized_images) + 1) // 2
            cols = min(2, len(resized_images))
            
            grid = np.zeros((target_size[1] * rows, target_size[0] * cols, 3), dtype=np.uint8)
            
            for idx, (img, name) in enumerate(zip(resized_images, names)):
                row = idx // cols
                col = idx % cols
                y = row * target_size[1]
                x = col * target_size[0]
                
                grid[y:y+target_size[1], x:x+target_size[0]] = img
                
                # Name hinzufügen
                cv2.putText(grid, name, (x + 10, y + 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            
            return grid
        except Exception as e:
            logger.error(f"Fehler beim Grid-Erstellen: {e}")
            return None
