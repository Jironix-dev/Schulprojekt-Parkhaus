"""
SQL-Abfragefunktionen für häufig benötigte Operationen
Kennzeichen-Validierung: 1 Buchstabe + Leerzeichen + 4 Ziffern (z.B. "A 1234")
"""

import sqlite3
from datetime import datetime
from typing import Optional, List, Tuple
from .db import db
from .validators import PlateValidator


class VehicleQueries:
    """Abfragen für Fahrzeugverwaltung"""
    
    @staticmethod
    def add_vehicle(license_plate: str, notes: str = '') -> Optional[int]:
        """Fügt neues Fahrzeug hinzu - nur gültige Kennzeichen akzeptiert"""
        cursor = db.get_cursor()
        
        # Validierung und Normalisierung
        is_valid, normalized_plate = PlateValidator.validate_and_normalize(license_plate)
        
        if not is_valid:
            print(f"[FEHLER] Ungültiges Kennzeichen: '{license_plate}'")
            print(f"[INFO] Schema erforderlich: 1 Buchstabe + Leerzeichen + 4 Ziffern (z.B. 'A 1234')")
            return None
        
        try:
            cursor.execute(
                """INSERT INTO vehicles 
                   (license_plate, is_valid_format, status, first_seen_at, notes)
                   VALUES (?, ?, ?, ?, ?)""",
                (normalized_plate, 1 if is_valid else 0, 'pending', datetime.now(), notes)
            )
            db.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            print(f"Fahrzeug mit Kennzeichen '{normalized_plate}' existiert bereits")
            return None
            
    @staticmethod
    def get_vehicle_by_plate(license_plate: str) -> Optional[dict]:
        """Findet Fahrzeug nach Kennzeichen (mit Validierung)"""
        cursor = db.get_cursor()
        
        # Normalisiert Kennzeichen
        _, normalized_plate = PlateValidator.validate_and_normalize(license_plate)
        
        cursor.execute("SELECT * FROM vehicles WHERE license_plate = ?", (normalized_plate,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    @staticmethod
    def get_vehicle_by_id(vehicle_id: int) -> Optional[dict]:
        """Findet Fahrzeug nach ID"""
        cursor = db.get_cursor()
        cursor.execute("SELECT * FROM vehicles WHERE id = ?", (vehicle_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    @staticmethod
    def approve_vehicle(vehicle_id: int) -> bool:
        """Gibt Fahrzeug frei"""
        cursor = db.get_cursor()
        cursor.execute(
            "UPDATE vehicles SET status = ?, last_seen_at = ? WHERE id = ?",
            ('approved', datetime.now(), vehicle_id)
        )
        db.commit()
        return cursor.rowcount > 0
    
    @staticmethod
    def block_vehicle(vehicle_id: int, reason: str = '') -> bool:
        """Sperrt Fahrzeug"""
        cursor = db.get_cursor()
        cursor.execute(
            "UPDATE vehicles SET status = ?, is_blocked = 1, notes = ? WHERE id = ?",
            ('blocked', reason, vehicle_id)
        )
        db.commit()
        return cursor.rowcount > 0
    
    @staticmethod
    def get_all_vehicles() -> List[dict]:
        """Gibt alle Fahrzeuge zurück"""
        cursor = db.get_cursor()
        cursor.execute("SELECT * FROM vehicles ORDER BY registered_at DESC")
        return [dict(row) for row in cursor.fetchall()]
    
    @staticmethod
    def get_pending_vehicles() -> List[dict]:
        """Gibt alle Fahrzeuge mit Status 'pending' zurück"""
        cursor = db.get_cursor()
        cursor.execute("SELECT * FROM vehicles WHERE status = 'pending' ORDER BY first_seen_at")
        return [dict(row) for row in cursor.fetchall()]


class ParkingQueries:
    """Abfragen für Parkplatz-Verwaltung"""
    
    @staticmethod
    def create_session(vehicle_id: int, entry_image_id: Optional[int] = None) -> int:
        """Erstellt neue Parkplatz-Session"""
        cursor = db.get_cursor()
        cursor.execute(
            """INSERT INTO parking_sessions 
               (vehicle_id, entry_time, entry_image_id, status)
               VALUES (?, ?, ?, ?)""",
            (vehicle_id, datetime.now(), entry_image_id, 'parked')
        )
        db.commit()
        return cursor.lastrowid
    
    @staticmethod
    def get_active_session(vehicle_id: int) -> Optional[dict]:
        """Findet aktive Session für Fahrzeug"""
        cursor = db.get_cursor()
        cursor.execute(
            """SELECT * FROM parking_sessions 
               WHERE vehicle_id = ? AND exit_time IS NULL
               ORDER BY entry_time DESC LIMIT 1""",
            (vehicle_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    
    @staticmethod
    def end_session(session_id: int, exit_image_id: Optional[int] = None, cost: Optional[float] = None) -> bool:
        """Beendet Parkplatz-Session. Kostenberechnung optional."""
        cursor = db.get_cursor()
        
        # Berechne Parkdauer
        cursor.execute("SELECT entry_time FROM parking_sessions WHERE id = ?", (session_id,))
        row = cursor.fetchone()
        if not row:
            return False
        
        entry_time = datetime.fromisoformat(row[0])
        exit_time = datetime.now()
        duration = int((exit_time - entry_time).total_seconds() / 60)
        
        # Berechne Kosten falls nicht übergeben
        calculated_cost = cost
        if calculated_cost is None:
            # Importiere hier um zirkuläre Abhängigkeiten zu vermeiden
            try:
                from backend.services.payment import PaymentCalculator
                parking_seconds = int((exit_time - entry_time).total_seconds())
                calculated_cost = PaymentCalculator.calculate_from_seconds(parking_seconds)
            except Exception as e:
                print(f"[WARNUNG] Fehler bei Kostenberechnung: {e}, nutze 0.0 EUR")
                calculated_cost = 0.0
        
        cursor.execute(
            """UPDATE parking_sessions 
               SET exit_time = ?, exit_image_id = ?, 
                   status = ?, parking_duration_minutes = ?, cost_calculated = ?
               WHERE id = ?""",
            (exit_time, exit_image_id, 'payment_pending', duration, calculated_cost, session_id)
        )
        db.commit()
        return cursor.rowcount > 0
    
    @staticmethod
    def confirm_payment(session_id: int, amount: float) -> bool:
        """Bestätigt Bezahlung"""
        cursor = db.get_cursor()
        cursor.execute(
            """UPDATE parking_sessions 
               SET payment_confirmed = 1, cost_paid = ?, 
                   payment_confirmed_at = ?, status = 'payment_confirmed'
               WHERE id = ?""",
            (amount, datetime.now(), session_id)
        )
        db.commit()
        return cursor.rowcount > 0
    
    @staticmethod
    def get_occupied_spaces() -> int:
        """Zählt aktuelle belegte Parkplätze"""
        cursor = db.get_cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM parking_sessions WHERE exit_time IS NULL AND status = 'parked'"
        )
        return cursor.fetchone()[0]
    
    @staticmethod
    def update_capacity():
        """Aktualisiert Parkplatz-Kapazität"""
        occupied = ParkingQueries.get_occupied_spaces()
        cursor = db.get_cursor()
        cursor.execute(
            "UPDATE parking_capacity SET occupied_spaces = ?, last_updated = ? WHERE id = 1",
            (occupied, datetime.now())
        )
        db.commit()
    
    @staticmethod
    def get_capacity() -> Optional[dict]:
        """Gibt Kapazitätsinformationen zurück"""
        cursor = db.get_cursor()
        cursor.execute("SELECT * FROM parking_capacity WHERE id = 1")
        row = cursor.fetchone()
        return dict(row) if row else None


class ImageQueries:
    """Abfragen für Bildverwaltung"""
    
    @staticmethod
    def add_image(image_path: str, image_type: str, 
                  detected_plate: str = '', confidence: float = 0.0) -> int:
        """Fügt neues Bild hinzu"""
        cursor = db.get_cursor()
        
        # Validiert erkanntes Kennzeichen falls vorhanden
        valid_plate = ''
        if detected_plate:
            is_valid, normalized_plate = PlateValidator.validate_and_normalize(detected_plate)
            valid_plate = normalized_plate if is_valid else detected_plate
        
        cursor.execute(
            """INSERT INTO images 
               (image_path, captured_at, image_type, detected_plate, confidence_score)
               VALUES (?, ?, ?, ?, ?)""",
            (image_path, datetime.now(), image_type, valid_plate, confidence)
        )
        db.commit()
        return cursor.lastrowid
    
    @staticmethod
    def add_detection(image_id: int, detected_plate: str, raw_text: str, confidence: float) -> int:
        """Fügt Kennzeichen-Erkennung hinzu"""
        cursor = db.get_cursor()
        
        # Validiert erkanntes Kennzeichen
        is_valid, normalized_plate = PlateValidator.validate_and_normalize(detected_plate)
        
        cursor.execute(
            """INSERT INTO plate_detections 
               (image_id, detected_plate, raw_ocr_text, confidence_score, is_valid)
               VALUES (?, ?, ?, ?, ?)""",
            (image_id, normalized_plate, raw_text, confidence, 1 if is_valid else 0)
        )
        db.commit()
        return cursor.lastrowid
    
    @staticmethod
    def get_image_detections(image_id: int) -> List[dict]:
        """Gibt alle Erkennungen für ein Bild zurück"""
        cursor = db.get_cursor()
        cursor.execute(
            "SELECT * FROM plate_detections WHERE image_id = ? ORDER BY confidence_score DESC",
            (image_id,)
        )
        return [dict(row) for row in cursor.fetchall()]


class SystemQueries:
    """Abfragen für Systemverwaltung"""
    
    @staticmethod
    def log_event(event_type: str, message: str, vehicle_id: Optional[int] = None):
        """Speichert Systemevent"""
        cursor = db.get_cursor()
        cursor.execute(
            """INSERT INTO system_logs 
               (event_type, vehicle_id, message, timestamp)
               VALUES (?, ?, ?, ?)""",
            (event_type, vehicle_id, message, datetime.now())
        )
        db.commit()
    
    @staticmethod
    def get_logs(limit: int = 100) -> List[dict]:
        """Gibt letzte Systemevents zurück"""
        cursor = db.get_cursor()
        cursor.execute(
            "SELECT * FROM system_logs ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        )
        return [dict(row) for row in cursor.fetchall()]
    
    @staticmethod
    def get_statistics() -> dict:
        """Gibt Statistiken zurück"""
        cursor = db.get_cursor()
        
        cursor.execute("SELECT COUNT(*) FROM vehicles")
        total_vehicles = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM vehicles WHERE status = 'approved'")
        approved_vehicles = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM parking_sessions WHERE exit_time IS NULL")
        active_sessions = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM parking_sessions")
        total_sessions = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(cost_paid) FROM parking_sessions WHERE cost_paid > 0")
        total_revenue = cursor.fetchone()[0] or 0.0
        
        return {
            'total_vehicles': total_vehicles,
            'approved_vehicles': approved_vehicles,
            'active_sessions': active_sessions,
            'total_sessions': total_sessions,
            'total_revenue': total_revenue
        }
