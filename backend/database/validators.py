"""
Validierungsfunktionen für Parkhaus-Datenbank
Akzeptiert nur Kennzeichen im Format: 1 Buchstabe + Leerzeichen + 4 Ziffern (z.B. "A 1234")
"""

import re
from typing import Tuple


class PlateValidator:
    """Validiert Kennzeichen nach dem vorgegebenen Schema"""
    
    # Schema: 1 Buchstabe (A-Z), Leerzeichen, 4 Ziffern
    PATTERN = re.compile(r'^[A-Z]\s\d{4}$')
    
    @classmethod
    def is_valid(cls, license_plate: str) -> bool:
        """
        Prüft ob Kennzeichen dem Schema entspricht.
        
        Args:
            license_plate: Kennzeichen (z.B. "A 1234")
        
        Returns:
            True wenn gültig, False sonst
        """
        if not license_plate:
            return False
        
        # Entfernt Leerzeichen am Anfang/Ende und normalisiert
        plate = license_plate.strip().upper()
        
        return bool(cls.PATTERN.match(plate))
    
    @classmethod
    def normalize(cls, license_plate: str) -> str:
        """
        Normalisiert Kennzeichen (Großbuchstaben, trimmt Whitespace).
        
        Args:
            license_plate: Kennzeichen
        
        Returns:
            Normalisiertes Kennzeichen oder Original wenn ungültig
        """
        if not license_plate:
            return license_plate
        
        normalized = license_plate.strip().upper()
        return normalized if cls.is_valid(normalized) else license_plate
    
    @classmethod
    def validate_and_normalize(cls, license_plate: str) -> Tuple[bool, str]:
        """
        Validiert und normalisiert Kennzeichen in einem Schritt.
        
        Args:
            license_plate: Kennzeichen
        
        Returns:
            Tuple (ist_gueltig, normalisiertes_kennzeichen)
        """
        normalized = license_plate.strip().upper()
        is_valid = cls.is_valid(normalized)
        return is_valid, normalized


# Gültige Beispiele für Tests
VALID_PLATES = [
    "A 1234",
    "Z 9999",
    "M 0000",
    "B 5678",
    "a 1234",  # wird normalisiert zu "A 1234"
]

# Ungültige Beispiele
INVALID_PLATES = [
    "AB 1234",        # 2 Buchstaben (ungültig)
    "1 1234",         # Ziffer statt Buchstabe
    "A1234",          # Kein Leerzeichen
    "A  1234",        # 2 Leerzeichen
    "AA-BB 1234",     # Falsches Format
    "A 123",          # Nur 3 Ziffern
    "A 12345",        # 5 Ziffern
    "",               # Leer
    "AB-CD 123",      # Altes Format
    "XY-ZA 456",      # Altes Format
]
