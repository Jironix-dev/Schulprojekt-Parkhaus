"""
Services-Modul für Parkhaus-System
"""

from .payment import PaymentCalculator, DatabasePaymentCalculator
from .ocr_correction import OCRCorrectionService

__all__ = [
    'PaymentCalculator',
    'DatabasePaymentCalculator',
    'OCRCorrectionService'
]
