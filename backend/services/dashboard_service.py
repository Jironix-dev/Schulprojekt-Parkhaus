"""
Dashboard-Service: Ruft relevante Daten von der Datenbank für das Dashboard ab
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from backend.database.db import db


class DashboardService:
    """Service für Dashboard-Datenabfragen"""
    
    @staticmethod
    def get_parking_capacity() -> Dict[str, Any]:
        """Ruft aktuelle Parkplatz-Kapazität ab"""
        cursor = db.get_cursor()
        cursor.execute("""
            SELECT total_spaces, occupied_spaces, last_updated 
            FROM parking_capacity 
            LIMIT 1
        """)
        result = cursor.fetchone()
        
        if result:
            return {
                'total_spaces': result[0],
                'occupied_spaces': result[1],
                'available_spaces': result[0] - result[1],
                'occupancy_rate': round((result[1] / result[0] * 100) if result[0] > 0 else 0, 1),
                'last_updated': result[2]
            }
        return {
            'total_spaces': 0,
            'occupied_spaces': 0,
            'available_spaces': 0,
            'occupancy_rate': 0.0,
            'last_updated': None
        }
    
    @staticmethod
    def get_active_session() -> Optional[Dict[str, Any]]:
        """Ruft aktuelle aktive Parkplatz-Session ab (Fahrzeug mit Exit-Zeit = NULL)"""
        cursor = db.get_cursor()
        cursor.execute("""
            SELECT 
                ps.id,
                v.license_plate,
                ps.entry_time,
                ps.exit_time,
                ps.status,
                ps.cost_calculated,
                ps.cost_paid,
                ps.payment_confirmed,
                pd.confidence_score,
                pd.detected_plate
            FROM parking_sessions ps
            JOIN vehicles v ON ps.vehicle_id = v.id
            LEFT JOIN plate_detections pd ON ps.entry_image_id = pd.image_id
            WHERE ps.exit_time IS NULL
            ORDER BY ps.entry_time DESC
            LIMIT 1
        """)
        result = cursor.fetchone()
        
        if result:
            entry_time = datetime.fromisoformat(result[2]) if isinstance(result[2], str) else result[2]
            duration = (datetime.now() - entry_time).total_seconds() / 60  # Minuten
            
            return {
                'session_id': result[0],
                'license_plate': result[1],
                'entry_time': result[2],
                'exit_time': result[3],
                'status': result[4],
                'cost_calculated': result[5],
                'cost_paid': result[6],
                'payment_confirmed': bool(result[7]),
                'confidence_score': result[8],
                'detected_plate': result[9],
                'parking_duration_minutes': round(duration, 1)
            }
        return None
    
    @staticmethod
    def get_pending_payments() -> Dict[str, Any]:
        """Ruft ausstehende Zahlungen ab"""
        cursor = db.get_cursor()
        cursor.execute("""
            SELECT COUNT(*), COALESCE(SUM(cost_calculated - cost_paid), 0)
            FROM parking_sessions
            WHERE payment_confirmed = 0 AND exit_time IS NOT NULL
        """)
        result = cursor.fetchone()
        
        return {
            'pending_count': result[0],
            'total_amount_pending': round(result[1], 2) if result[1] else 0.0
        }
    
    @staticmethod
    def get_todays_statistics() -> Dict[str, Any]:
        """Ruft Statistiken für heute ab"""
        cursor = db.get_cursor()
        today = datetime.now().date()
        start_of_day = datetime.combine(today, datetime.min.time()).isoformat()
        end_of_day = datetime.combine(today, datetime.max.time()).isoformat()
        
        # Eingänge heute
        cursor.execute("""
            SELECT COUNT(*) FROM parking_sessions
            WHERE DATE(entry_time) = DATE(?)
        """, (start_of_day,))
        entries_today = cursor.fetchone()[0]
        
        # Ausgänge heute (abgeschlossene Sessions)
        cursor.execute("""
            SELECT COUNT(*) FROM parking_sessions
            WHERE DATE(exit_time) = DATE(?) AND exit_time IS NOT NULL
        """, (start_of_day,))
        exits_today = cursor.fetchone()[0]
        
        # Gesamteinnahmen heute
        cursor.execute("""
            SELECT COALESCE(SUM(cost_paid), 0) FROM parking_sessions
            WHERE DATE(payment_confirmed_at) = DATE(?) AND payment_confirmed = 1
        """, (start_of_day,))
        revenue_today = cursor.fetchone()[0]
        
        return {
            'entries_today': entries_today,
            'exits_today': exits_today,
            'revenue_today': round(revenue_today, 2) if revenue_today else 0.0
        }
    
    @staticmethod
    def get_recent_vehicles(limit: int = 5) -> list:
        """Ruft zuletzt erkannte Fahrzeuge ab"""
        cursor = db.get_cursor()
        cursor.execute("""
            SELECT 
                v.id,
                v.license_plate,
                v.status,
                v.last_seen_at,
                COUNT(ps.id) as total_sessions
            FROM vehicles v
            LEFT JOIN parking_sessions ps ON v.id = ps.vehicle_id
            ORDER BY v.last_seen_at DESC
            LIMIT ?
        """, (limit,))
        
        results = cursor.fetchall()
        return [
            {
                'vehicle_id': row[0],
                'license_plate': row[1],
                'status': row[2],
                'last_seen_at': row[3],
                'total_sessions': row[4]
            }
            for row in results
        ]
    
    @staticmethod
    def get_dashboard_summary() -> Dict[str, Any]:
        """Ruft alle wichtigen Dashboard-Informationen ab"""
        return {
            'parking_capacity': DashboardService.get_parking_capacity(),
            'active_session': DashboardService.get_active_session(),
            'pending_payments': DashboardService.get_pending_payments(),
            'today_stats': DashboardService.get_todays_statistics(),
            'recent_vehicles': DashboardService.get_recent_vehicles(),
            'timestamp': datetime.now().isoformat()
        }
    
    @staticmethod
    def get_all_parked_vehicles() -> list:
        """Ruft alle aktuell parkenden Fahrzeuge mit vollständigen Daten ab"""
        cursor = db.get_cursor()
        cursor.execute("""
            SELECT 
                ps.id as session_id,
                v.id as vehicle_id,
                v.license_plate,
                v.status as vehicle_status,
                ps.entry_time,
                ps.exit_time,
                ps.status as session_status,
                ps.parking_duration_minutes,
                ps.cost_calculated,
                ps.cost_paid,
                ps.payment_confirmed,
                pd.confidence_score,
                COUNT(*) OVER (PARTITION BY v.id) as total_sessions
            FROM parking_sessions ps
            JOIN vehicles v ON ps.vehicle_id = v.id
            LEFT JOIN plate_detections pd ON ps.entry_image_id = pd.image_id
            WHERE ps.exit_time IS NULL
            ORDER BY ps.entry_time DESC
        """)
        
        results = cursor.fetchall()
        vehicles = []
        for row in results:
            entry_time = datetime.fromisoformat(row[4]) if isinstance(row[4], str) else row[4]
            duration = (datetime.now() - entry_time).total_seconds() / 60
            
            vehicles.append({
                'session_id': row[0],
                'vehicle_id': row[1],
                'license_plate': row[2],
                'vehicle_status': row[3],
                'entry_time': row[4],
                'session_status': row[6],
                'parking_duration_minutes': round(duration, 1),
                'cost_calculated': row[8],
                'cost_paid': row[9],
                'payment_confirmed': bool(row[10]),
                'confidence_score': row[11],
                'total_sessions': row[12]
            })
        
        return vehicles
    
    @staticmethod
    def get_cost_details() -> list:
        """Ruft Kostendetails für alle parkenden Fahrzeuge ab"""
        vehicles = DashboardService.get_all_parked_vehicles()
        return [
            {
                'license_plate': v['license_plate'],
                'entry_time': v['entry_time'],
                'cost_calculated': round(v['cost_calculated'], 2),
                'cost_paid': round(v['cost_paid'], 2),
                'payment_confirmed': v['payment_confirmed'],
                'status': v['session_status']
            }
            for v in vehicles
        ]
    
    @staticmethod
    def get_duration_details() -> list:
        """Ruft Parkdauer-Details für alle parkenden Fahrzeuge ab"""
        vehicles = DashboardService.get_all_parked_vehicles()
        return [
            {
                'license_plate': v['license_plate'],
                'entry_time': v['entry_time'],
                'parking_duration_minutes': v['parking_duration_minutes'],
                'parking_duration_formatted': f"{int(v['parking_duration_minutes'])} Min {int((v['parking_duration_minutes'] % 1) * 60)} Sek"
            }
            for v in vehicles
        ]
    
    @staticmethod
    def get_plate_recognition_details() -> list:
        """Ruft Details zur Kennzeichen-Erkennung ab"""
        cursor = db.get_cursor()
        cursor.execute("""
            SELECT 
                v.license_plate,
                pd.detected_plate,
                pd.confidence_score,
                pd.detected_at,
                COUNT(*) as detection_count
            FROM vehicles v
            LEFT JOIN parking_sessions ps ON v.id = ps.vehicle_id
            LEFT JOIN plate_detections pd ON ps.entry_image_id = pd.image_id
            WHERE ps.exit_time IS NULL
            GROUP BY v.id
            ORDER BY pd.detected_at DESC
        """)
        
        results = cursor.fetchall()
        return [
            {
                'license_plate': row[0],
                'detected_plate': row[1],
                'confidence_score': round(row[2] * 100, 1) if row[2] else 0,
                'detected_at': row[3],
                'detection_count': row[4]
            }
            for row in results
        ]
    
    @staticmethod
    def get_vehicle_status_details() -> list:
        """Ruft Fahrzeug-Status-Details ab"""
        vehicles = DashboardService.get_all_parked_vehicles()
        return [
            {
                'license_plate': v['license_plate'],
                'vehicle_status': v['vehicle_status'],
                'session_status': v['session_status'],
                'total_sessions': v['total_sessions'],
                'first_seen': v['entry_time']
            }
            for v in vehicles
        ]
    
    @staticmethod
    def get_known_vehicles() -> list:
        """
        Ruft alle gültig erkannten Kennzeichen aus der Datenbank ab.
        Nur Fahrzeuge mit is_valid_format = 1 (oder status = 'approved')
        """
        cursor = db.get_cursor()
        cursor.execute("""
            SELECT 
                v.id,
                v.license_plate,
                v.status,
                v.first_seen_at,
                v.last_seen_at,
                COUNT(ps.id) as total_sessions
            FROM vehicles v
            LEFT JOIN parking_sessions ps ON v.id = ps.vehicle_id
            WHERE v.is_valid_format = 1 OR v.status = 'approved'
            GROUP BY v.id
            ORDER BY v.last_seen_at DESC NULLS LAST
        """)
        
        results = cursor.fetchall()
        return [
            {
                'vehicle_id': row[0],
                'license_plate': row[1],
                'status': row[2],
                'first_seen_at': row[3],
                'last_seen_at': row[4],
                'total_sessions': row[5]
            }
            for row in results
        ]
    
    @staticmethod
    def get_dauerparker() -> list:
        """
        Ruft alle Dauerparker ab (manuell eingegebene Kennzeichen mit status='dauerparker').
        
        Returns:
            Liste der Dauerparker
        """
        cursor = db.get_cursor()
        cursor.execute("""
            SELECT 
                id,
                license_plate,
                registered_at,
                notes
            FROM vehicles
            WHERE status = 'dauerparker'
            ORDER BY registered_at DESC
        """)
        
        results = cursor.fetchall()
        return [
            {
                'vehicle_id': row[0],
                'license_plate': row[1],
                'registered_at': row[2],
                'notes': row[3]
            }
            for row in results
        ]
    
    @staticmethod
    def add_dauerparker(license_plate: str) -> Tuple[bool, str]:
        """
        Fügt einen neuen Dauerparker hinzu (nur manuell eingegeben).
        
        Args:
            license_plate: Kennzeichen im Format "X 1234"
        
        Returns:
            Tuple (success: bool, message: str)
        """
        from backend.database.validators import PlateValidator
        
        # Validiere Format
        if not PlateValidator.is_valid(license_plate):
            return False, "Ungültiges Format! Verwende: Buchstabe Leerzeichen 4 Ziffern (z.B. A 1234)"
        
        try:
            cursor = db.get_cursor()
            
            # Prüfe ob Kennzeichen bereits als Dauerparker existiert
            cursor.execute("SELECT id FROM vehicles WHERE license_plate = ? AND status = 'dauerparker'", (license_plate,))
            existing = cursor.fetchone()
            
            if existing:
                return False, f"Dauerparker '{license_plate}' existiert bereits"
            
            # Prüfe ob Kennzeichen überhaupt existiert (aber mit anderem Status)
            cursor.execute("SELECT id FROM vehicles WHERE license_plate = ?", (license_plate,))
            existing_other = cursor.fetchone()
            
            if existing_other:
                # Update zu Dauerparker
                cursor.execute("""
                    UPDATE vehicles 
                    SET status = 'dauerparker', is_valid_format = 1
                    WHERE license_plate = ?
                """, (license_plate,))
                message = f"Kennzeichen '{license_plate}' als Dauerparker registriert"
            else:
                # Neuer Dauerparker
                cursor.execute("""
                    INSERT INTO vehicles (license_plate, is_valid_format, status, registered_at, notes)
                    VALUES (?, 1, 'dauerparker', datetime('now'), 'Manuell als Dauerparker hinzugefügt')
                """, (license_plate,))
                message = f"Dauerparker '{license_plate}' hinzugefügt"
            
            db.commit()
            return True, message
            
        except Exception as e:
            return False, f"Fehler beim Speichern: {str(e)}"
    
    @staticmethod
    def delete_dauerparker(license_plate: str) -> Tuple[bool, str]:
        """
        Löscht einen Dauerparker aus der Liste.
        
        Args:
            license_plate: Kennzeichen im Format "X 1234"
        
        Returns:
            Tuple (success: bool, message: str)
        """
        try:
            cursor = db.get_cursor()
            
            # Prüfe ob Dauerparker existiert
            cursor.execute("SELECT id FROM vehicles WHERE license_plate = ? AND status = 'dauerparker'", (license_plate,))
            existing = cursor.fetchone()
            
            if not existing:
                return False, f"Dauerparker '{license_plate}' nicht gefunden"
            
            # Lösche Kennzeichen komplett
            cursor.execute("DELETE FROM vehicles WHERE license_plate = ? AND status = 'dauerparker'", (license_plate,))
            db.commit()
            
            return True, f"Dauerparker '{license_plate}' gelöscht"
            
        except Exception as e:
            return False, f"Fehler beim Löschen: {str(e)}"
    
    @staticmethod
    def get_detection_protocol(limit: int = 100) -> list:
        """
        Ruft das Erkennungsprotokoll ab (alle erkannten Kennzeichen).
        Zeigt alle plate_detections mit Status (valid/invalid).
        
        Args:
            limit: Maximale Anzahl der anzuzeigenden Einträge (neueste zuerst)
        
        Returns:
            Liste der Erkennungen mit Zeitstempel, Kennzeichen und Status
        """
        cursor = db.get_cursor()
        cursor.execute("""
            SELECT 
                pd.id,
                pd.detected_plate,
                pd.detected_at,
                pd.is_valid,
                pd.confidence_score,
                pd.raw_ocr_text,
                i.image_path
            FROM plate_detections pd
            LEFT JOIN images i ON pd.image_id = i.id
            ORDER BY pd.detected_at DESC
            LIMIT ?
        """, (limit,))
        
        results = cursor.fetchall()
        return [
            {
                'id': row[0],
                'detected_plate': row[1],
                'detected_at': row[2],
                'is_valid': bool(row[3]),
                'confidence_score': round(row[4] * 100, 1) if row[4] else 0,
            }
            for row in results
        ]
    
    @staticmethod
    def save_entry_request(license_plate: str, ocr_confidence: float = 0.0) -> Tuple[bool, str]:
        """
        Speichert eine erkannte Kennzeichen-Anfrage (Entry Request).
        Wird aufgerufen wenn OCR ein gültiges Kennzeichen erkennt.
        
        Args:
            license_plate: Erkanntes Kennzeichen im Format \"X 1234\"
            ocr_confidence: OCR Konfidenz (0-1)
        
        Returns:
            Tuple (success: bool, message: str)
        """
        from backend.database.validators import PlateValidator
        
        # Validiere Format
        if not PlateValidator.is_valid(license_plate):
            return False, "Format ungültig"
        
        try:
            cursor = db.get_cursor()
            
            # Prüfe ob es ein Dauerparker ist
            cursor.execute("SELECT id FROM vehicles WHERE license_plate = ? AND status = 'dauerparker'", (license_plate,))
            is_dauerparker = cursor.fetchone() is not None
            
            # Bestimme Approval Status: Dauerparker werden automatisch genehmigt
            approval_status = 'approved' if is_dauerparker else 'pending'
            
            # Speichere Entry Request
            cursor.execute("""
                INSERT INTO entry_requests (license_plate, ocr_confidence, approval_status, is_dauerparker, approved_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                license_plate,
                ocr_confidence,
                approval_status,
                1 if is_dauerparker else 0,
                datetime.now() if is_dauerparker else None
            ))
            db.commit()
            
            status_msg = "(Auto-genehmigt: Dauerparker)" if is_dauerparker else "(Bestätigung erforderlich)"
            return True, f"Anfrage gespeichert {status_msg}"
            
        except Exception as e:
            return False, f"Fehler beim Speichern: {str(e)}"
    
    @staticmethod
    def get_entry_requests(limit: int = 50) -> list:
        """
        Ruft alle offenen Entry Requests ab (erkannte Kennzeichen).
        
        Args:
            limit: Maximale Anzahl
        
        Returns:
            Liste der Entry Requests
        """
        cursor = db.get_cursor()
        cursor.execute("""
            SELECT 
                id,
                license_plate,
                detected_at,
                ocr_confidence,
                approval_status,
                is_dauerparker
            FROM entry_requests
            ORDER BY detected_at DESC
            LIMIT ?
        """, (limit,))
        
        results = cursor.fetchall()
        return [
            {
                'id': row[0],
                'license_plate': row[1],
                'detected_at': row[2],
                'ocr_confidence': round(row[3] * 100, 1) if row[3] else 0,
                'approval_status': row[4],
                'is_dauerparker': bool(row[5])
            }
            for row in results
        ]
    
    @staticmethod
    def approve_entry_request(request_id: int) -> Tuple[bool, str]:
        """
        Genehmigt einen Entry Request (Auto darf einfahren).
        
        Args:
            request_id: ID der Entry Request
        
        Returns:
            Tuple (success: bool, message: str)
        """
        try:
            cursor = db.get_cursor()
            
            cursor.execute("""
                UPDATE entry_requests
                SET approval_status = 'approved', approved_at = datetime('now')
                WHERE id = ?
            """, (request_id,))
            db.commit()
            
            return True, "Entry genehmigt"
            
        except Exception as e:
            return False, f"Fehler: {str(e)}"
    
    @staticmethod
    def reject_entry_request(request_id: int) -> Tuple[bool, str]:
        """
        Lehnt einen Entry Request ab (Auto darf NICHT einfahren).
        
        Args:
            request_id: ID der Entry Request
        
        Returns:
            Tuple (success: bool, message: str)
        """
        try:
            cursor = db.get_cursor()
            
            cursor.execute("""
                UPDATE entry_requests
                SET approval_status = 'rejected', approved_at = datetime('now')
                WHERE id = ?
            """, (request_id,))
            db.commit()
            
            return True, "Entry abgelehnt"
            
        except Exception as e:
            return False, f"Fehler: {str(e)}"
