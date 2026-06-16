"""
OCR-Korrekturschicht fuer Kennzeichen-Ergebnisse.

Das Modul verbessert OCR-Rohtexte fuer das feste Projektformat:
1 Buchstabe + Leerzeichen + 4 Ziffern, z.B. "B 3456".

Die Logik orientiert sich an fuenf Regeln:
1. Feste Positionsregeln fuer das Kennzeichenformat.
2. Positionsabhaengige Verwechslungsregeln (z.B. O/0, I/1).
3. Nur minimale Korrekturen zulassen.
4. Das plausibelste Ergebnis aus Kandidaten auswaehlen.
5. Bekannte Kennzeichen bevorzugen, wenn sie uebergeben werden.
"""

from dataclasses import dataclass
from itertools import product
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from backend.database.validators import PlateValidator


@dataclass(frozen=True)
class CorrectionCandidate:
    """Repraesentiert einen moeglichen korrigierten Kandidaten."""

    plate: str
    changes: int
    matched_known_plate: bool
    score: int
    reason: str


class OCRCorrectionService:
    """Korrigiert OCR-Ergebnisse fuer das feste Kennzeichenformat."""

    EXPECTED_FORMAT_LENGTH = 6
    MAX_CORRECTIONS = 2

    # Typische OCR-Verwechslungen an der Buchstabenposition.
    LETTER_SUBSTITUTIONS: Dict[str, Tuple[str, ...]] = {
        "0": ("O",),
        "1": ("I",),
        "2": ("Z",),
        "5": ("S",),
        "8": ("B",),
    }

    # Typische OCR-Verwechslungen an den Ziffernpositionen.
    DIGIT_SUBSTITUTIONS: Dict[str, Tuple[str, ...]] = {
        "B": ("8",),
        "I": ("1",),
        "L": ("1",),
        "O": ("0",),
        "Q": ("0",),
        "S": ("5",),
        "Z": ("2",),
    }

    @classmethod
    def correct_plate(
        cls,
        raw_text: str,
        known_plates: Optional[Iterable[str]] = None
    ) -> dict:
        """
        Verbessert ein OCR-Ergebnis und liefert Zusatzinformationen.

        Args:
            raw_text: OCR-Rohtext.
            known_plates: Optional bekannte Kennzeichen aus der Datenbank
                oder aus Testdaten.

        Returns:
            Dictionary mit bestem Ergebnis und allen Kandidaten.
        """
        normalized_known_plates = cls._normalize_known_plates(known_plates)
        normalized_text = cls._normalize_ocr_text(raw_text)

        if not normalized_text:
            return cls._build_empty_result(raw_text, normalized_text)

        candidates = cls._build_candidates(normalized_text, normalized_known_plates)
        best_candidate = candidates[0] if candidates else None

        corrected_plate = best_candidate.plate if best_candidate else normalized_text
        is_valid = PlateValidator.is_valid(corrected_plate)

        return {
            "raw_text": raw_text,
            "normalized_text": normalized_text,
            "corrected_plate": corrected_plate,
            "is_valid": is_valid,
            "was_corrected": corrected_plate != normalized_text,
            "matched_known_plate": bool(best_candidate and best_candidate.matched_known_plate),
            "applied_changes": best_candidate.changes if best_candidate else 0,
            "confidence_level": cls._classify_confidence(best_candidate, is_valid),
            "best_reason": best_candidate.reason if best_candidate else "Kein Kandidat gefunden",
            "candidates": [
                {
                    "plate": candidate.plate,
                    "changes": candidate.changes,
                    "matched_known_plate": candidate.matched_known_plate,
                    "score": candidate.score,
                    "reason": candidate.reason,
                }
                for candidate in candidates
            ],
        }

    @classmethod
    def _build_candidates(
        cls,
        normalized_text: str,
        known_plates: Set[str]
    ) -> List[CorrectionCandidate]:
        """
        Erzeugt und bewertet Kandidaten anhand der Projektregeln.
        """
        raw_candidates = cls._generate_plate_candidates(normalized_text)
        valid_candidates: List[CorrectionCandidate] = []

        for plate, changes, reason in raw_candidates:
            if not PlateValidator.is_valid(plate):
                continue

            matched_known_plate = plate in known_plates if known_plates else False
            score = cls._score_candidate(changes, matched_known_plate, plate == normalized_text)

            valid_candidates.append(
                CorrectionCandidate(
                    plate=plate,
                    changes=changes,
                    matched_known_plate=matched_known_plate,
                    score=score,
                    reason=reason,
                )
            )

        valid_candidates.sort(
            key=lambda candidate: (
                candidate.score,
                candidate.changes,
                candidate.plate,
            )
        )
        return valid_candidates

    @classmethod
    def _generate_plate_candidates(cls, normalized_text: str) -> List[Tuple[str, int, str]]:
        """
        Baut moegliche Kennzeichenkandidaten aus dem OCR-Text.

        Der Ablauf folgt den ersten vier Regeln:
        - Zeichen bereinigen und Struktur herstellen.
        - Nur positionskonforme Zeichen zulassen.
        - Typische OCR-Verwechslungen positionsabhaengig aufloesen.
        - Kandidaten mit moeglichst wenigen Aenderungen bevorzugen.
        """
        compact_text = cls._compact_text(normalized_text)
        if len(compact_text) != 5:
            return []

        letter_options = cls._get_letter_options(compact_text[0])
        digit_option_sets = [cls._get_digit_options(char) for char in compact_text[1:]]

        candidates: Dict[str, Tuple[int, str]] = {}

        for combination in product(letter_options, *digit_option_sets):
            letter_choice = combination[0]
            digit_choices = combination[1:]
            plate = f"{letter_choice} {''.join(digit_choices)}"

            changes = 0
            reasons: List[str] = []

            if letter_choice != compact_text[0]:
                changes += 1
                reasons.append(f"Buchstabe {compact_text[0]}->{letter_choice}")

            for index, digit_choice in enumerate(digit_choices, start=1):
                source_char = compact_text[index]
                if digit_choice != source_char:
                    changes += 1
                    reasons.append(f"Ziffer {source_char}->{digit_choice}")

            if changes > cls.MAX_CORRECTIONS:
                continue

            reason = ", ".join(reasons) if reasons else "Bereits formatkonform"
            previous = candidates.get(plate)
            if previous is None or changes < previous[0]:
                candidates[plate] = (changes, reason)

        return [(plate, changes, reason) for plate, (changes, reason) in candidates.items()]

    @classmethod
    def _compact_text(cls, text: str) -> str:
        """
        Entfernt Trennzeichen und bringt den OCR-Text in die 5-Zeichen-Form.
        Beispiel: "B-3456" -> "B3456"
        """
        cleaned = []
        for char in text:
            if char.isalnum():
                cleaned.append(char)
        return "".join(cleaned)

    @classmethod
    def _get_letter_options(cls, char: str) -> Sequence[str]:
        """
        Erlaubt an Position 1 nur Buchstaben und typische OCR-Korrekturen.
        """
        options: List[str] = []
        if char.isalpha():
            options.append(char)

        options.extend(cls.LETTER_SUBSTITUTIONS.get(char, ()))
        return cls._deduplicate(options)

    @classmethod
    def _get_digit_options(cls, char: str) -> Sequence[str]:
        """
        Erlaubt an Ziffernpositionen nur Ziffern und typische OCR-Korrekturen.
        """
        options: List[str] = []
        if char.isdigit():
            options.append(char)

        options.extend(cls.DIGIT_SUBSTITUTIONS.get(char, ()))
        return cls._deduplicate(options)

    @classmethod
    def _score_candidate(
        cls,
        changes: int,
        matched_known_plate: bool,
        unchanged: bool
    ) -> int:
        """
        Niedrigerer Score ist besser.

        Bewertungslogik:
        - Bekannte Kennzeichen bekommen starken Bonus.
        - Weniger Aenderungen sind besser.
        - Bereits gueltige, unveraenderte OCR-Ergebnisse bleiben vorne.
        """
        score = changes * 10
        if not unchanged:
            score += 2
        if matched_known_plate:
            score -= 15
        return score

    @classmethod
    def _classify_confidence(
        cls,
        candidate: Optional[CorrectionCandidate],
        is_valid: bool
    ) -> str:
        """Ordnet das Ergebnis grob in eine Vertrauensstufe ein."""
        if not candidate or not is_valid:
            return "low"
        if candidate.matched_known_plate and candidate.changes <= 2:
            return "high"
        if candidate.changes == 0:
            return "high"
        if candidate.changes == 1:
            return "medium"
        return "low"

    @staticmethod
    def _normalize_ocr_text(raw_text: str) -> str:
        """
        Normalisiert OCR-Rohtext fuer die weitere Verarbeitung.
        """
        if not raw_text:
            return ""

        normalized = raw_text.strip().upper()
        normalized = normalized.replace("-", " ")
        normalized = normalized.replace("_", " ")
        normalized = " ".join(normalized.split())
        return normalized

    @staticmethod
    def _normalize_known_plates(known_plates: Optional[Iterable[str]]) -> Set[str]:
        """
        Normalisiert bekannte Kennzeichen fuer den spaeteren Abgleich.
        """
        normalized: Set[str] = set()
        if not known_plates:
            return normalized

        for plate in known_plates:
            if not plate:
                continue

            plate_text = plate.strip().upper()
            if PlateValidator.is_valid(plate_text):
                normalized.add(plate_text)

        return normalized

    @staticmethod
    def _deduplicate(values: Sequence[str]) -> List[str]:
        """Entfernt Duplikate, behaelt aber die Reihenfolge."""
        seen = set()
        result = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            result.append(value)
        return result

    @staticmethod
    def _build_empty_result(raw_text: str, normalized_text: str) -> dict:
        """Rueckgabe fuer leere oder unbrauchbare OCR-Ergebnisse."""
        return {
            "raw_text": raw_text,
            "normalized_text": normalized_text,
            "corrected_plate": normalized_text,
            "is_valid": False,
            "was_corrected": False,
            "matched_known_plate": False,
            "applied_changes": 0,
            "confidence_level": "low",
            "best_reason": "Leerer oder unbrauchbarer OCR-Text",
            "candidates": [],
        }
