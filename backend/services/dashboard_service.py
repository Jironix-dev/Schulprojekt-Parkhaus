"""
Dashboard-Service: Ruft relevante Daten von der Datenbank für das Dashboard ab
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from backend.database.db import db
from backend.services.payment import PaymentCalculator


class DashboardService:
    @staticmethod
    def _now_db() -> str:
        """Lokaler Zeitstempel fuer SQLite, damit Parkdauer nicht mit UTC startet."""
        return datetime.now().replace(microsecond=0).isoformat(sep=' ')

    """Service für Dashboard-Datenabfragen"""
    
    @staticmethod
    def get_parking_capacity() -> Dict[str, Any]:
        """Ruft aktuelle Parkplatz-Kapazität ab"""
        cursor = db.get_cursor()
        cursor.execute("""
            UPDATE parking_capacity
            SET occupied_spaces = (
                SELECT COUNT(*)
                FROM parking_sessions
                WHERE exit_time IS NULL
            ),
            last_updated = datetime('now', 'localtime')
            WHERE id = 1
        """)
        db.commit()
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
            duration = max(0, (datetime.now() - entry_time).total_seconds() / 60)  # Minuten
            
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
        pending_payments = DashboardService.get_cost_details()
        
        return {
            'pending_count': len(pending_payments),
            'total_amount_pending': round(sum(v['cost_calculated'] for v in pending_payments), 2)
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
            duration = max(0, (datetime.now() - entry_time).total_seconds() / 60)
            
            vehicles.append({
                'session_id': row[0],
                'vehicle_id': row[1],
                'license_plate': row[2],
                'vehicle_status': row[3],
                'entry_time': row[4],
                'session_status': row[6],
                'parking_duration_minutes': round(duration, 1),
                'parking_duration_formatted': f"{int(duration)} Min {int((duration % 1) * 60)} Sek",
                'cost_calculated': row[8],
                'cost_paid': row[9],
                'payment_confirmed': bool(row[10]),
                'confidence_score': row[11],
                'total_sessions': row[12],
                'is_dauerparker': row[3] == 'dauerparker'
            })
        
        return vehicles
    
    @staticmethod
    def get_parking_occupancy_details() -> Dict[str, Any]:
        """Ruft Kapazitaet und alle aktuell parkenden Fahrzeuge ab."""
        vehicles = DashboardService.get_all_parked_vehicles()
        return {
            'parking_capacity': DashboardService.get_parking_capacity(),
            'vehicles': vehicles,
            'count': len(vehicles)
        }

    @staticmethod
    def get_cost_details() -> list:
        """Ruft Kostendetails für alle parkenden Fahrzeuge ab"""
        vehicles = DashboardService.get_all_parked_vehicles()
        cost_details = []

        for v in vehicles:
            if v['is_dauerparker'] or v['payment_confirmed']:
                continue

            entry_time = datetime.fromisoformat(v['entry_time']) if isinstance(v['entry_time'], str) else v['entry_time']
            parking_seconds = max(0, int((datetime.now() - entry_time).total_seconds()))
            current_cost = PaymentCalculator.calculate_from_seconds(parking_seconds)

            cost_details.append({
                'session_id': v['session_id'],
                'license_plate': v['license_plate'],
                'entry_time': v['entry_time'],
                'parking_duration_minutes': v['parking_duration_minutes'],
                'parking_duration_formatted': v['parking_duration_formatted'],
                'cost_calculated': current_cost,
                'cost_paid': round(v['cost_paid'] or 0, 2),
                'payment_confirmed': v['payment_confirmed'],
                'status': v['session_status']
            })

        return cost_details
    
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
                    VALUES (?, 1, 'dauerparker', ?, 'Manuell als Dauerparker hinzugefügt')
                """, (license_plate, DashboardService._now_db()))
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
                datetime(pd.detected_at, 'localtime') AS detected_at,
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

            license_plate = PlateValidator.normalize(license_plate)

            cursor.execute("""
                SELECT id
                FROM entry_requests
                WHERE license_plate = ?
                  AND approval_status = 'pending'
                ORDER BY detected_at DESC
                LIMIT 1
            """, (license_plate,))
            pending_request = cursor.fetchone()

            if pending_request:
                return False, "Anfrage wartet bereits auf Bestätigung"

            cursor.execute("""
                SELECT ps.id
                FROM parking_sessions ps
                JOIN vehicles v ON ps.vehicle_id = v.id
                WHERE v.license_plate = ?
                  AND ps.exit_time IS NULL
                ORDER BY ps.entry_time DESC
                LIMIT 1
            """, (license_plate,))
            active_session = cursor.fetchone()

            if active_session:
                return False, "Auto ist bereits im Parkhaus"
            
            # Dauerparker und bereits einmal genehmigte Fahrzeuge duerfen automatisch einfahren.
            cursor.execute("""
                SELECT status
                FROM vehicles
                WHERE license_plate = ?
            """, (license_plate,))
            vehicle = cursor.fetchone()

            vehicle_status = vehicle[0] if vehicle else None
            is_dauerparker = vehicle_status == 'dauerparker'
            is_known_approved = vehicle_status == 'approved'
            auto_approved = is_dauerparker or is_known_approved

            approval_status = 'approved' if auto_approved else 'pending'
            approved_at = DashboardService._now_db() if auto_approved else None
            request_note = "Kennzeichen bekannt" if is_known_approved and not is_dauerparker else None
            started_session = False
            session_message = ""

            if auto_approved:
                started_session, session_message = DashboardService._start_parking_session_for_plate(
                    license_plate,
                    is_dauerparker=is_dauerparker
                )
            
            # Speichere Entry Request
            cursor.execute("""
                INSERT INTO entry_requests (
                    license_plate,
                    ocr_confidence,
                    approval_status,
                    is_dauerparker,
                    approved_at,
                    notes
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                license_plate,
                ocr_confidence,
                approval_status,
                1 if is_dauerparker else 0,
                approved_at,
                request_note
            ))
            db.commit()
            
            if is_dauerparker:
                status_msg = "(Auto-genehmigt: Dauerparker)"
            elif is_known_approved:
                status_msg = "(Auto-genehmigt: bekanntes Kennzeichen)"
            else:
                status_msg = "(Bestätigung erforderlich)"
            if started_session:
                status_msg = f"{status_msg} - {session_message}"
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
                datetime(detected_at, 'localtime') AS detected_at,
                ocr_confidence,
                approval_status,
                is_dauerparker,
                notes
            FROM entry_requests
            WHERE approval_status != 'pending'
               OR id IN (
                    SELECT MAX(id)
                    FROM entry_requests
                    WHERE approval_status = 'pending'
                    GROUP BY license_plate
               )
            ORDER BY detected_at DESC, id DESC
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
                'is_dauerparker': bool(row[5]),
                'message': row[6] or ('Dauerparker' if row[5] else '')
            }
            for row in results
        ]

    @staticmethod
    def get_latest_protocol_action() -> Optional[Dict[str, Any]]:
        """Ruft die letzte Protokollaktion aus Einfahrt oder Ausfahrt ab."""
        cursor = db.get_cursor()
        cursor.execute("""
            SELECT
                protocol_type,
                protocol_id,
                license_plate,
                action_time,
                status,
                message
            FROM (
                SELECT
                    'entry' AS protocol_type,
                    id AS protocol_id,
                    license_plate,
                    datetime(detected_at, 'localtime') AS action_time,
                    approval_status AS status,
                    CASE
                        WHEN notes = 'Kennzeichen bekannt' THEN 'Kennzeichen bekannt'
                        WHEN approval_status = 'pending' THEN 'Wartet auf Bestaetigung'
                        WHEN approval_status = 'approved' THEN 'Einfahrt genehmigt'
                        WHEN approval_status = 'rejected' THEN 'Einfahrt abgelehnt'
                        ELSE approval_status
                    END AS message
                FROM entry_requests
                UNION ALL
                SELECT
                    'exit' AS protocol_type,
                    id AS protocol_id,
                    license_plate,
                    detected_at AS action_time,
                    exit_status AS status,
                    message
                FROM exit_requests
            )
            ORDER BY action_time DESC, protocol_id DESC
            LIMIT 1
        """)
        row = cursor.fetchone()

        if not row:
            return None

        return {
            'type': row[0],
            'license_plate': row[2],
            'detected_at': row[3],
            'status': row[4],
            'message': row[5],
        }
    
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
                SELECT license_plate, is_dauerparker, approval_status
                FROM entry_requests
                WHERE id = ?
            """, (request_id,))
            request = cursor.fetchone()

            if not request:
                return False, "Entry Request nicht gefunden"
            
            approved_at = DashboardService._now_db()
            if request[2] == 'pending':
                cursor.execute("""
                    UPDATE entry_requests
                    SET approval_status = 'approved', approved_at = ?
                    WHERE license_plate = ?
                      AND approval_status = 'pending'
                """, (approved_at, request[0]))
            else:
                cursor.execute("""
                    UPDATE entry_requests
                    SET approval_status = 'approved', approved_at = ?
                    WHERE id = ?
                """, (approved_at, request_id))
            db.commit()

            _, session_message = DashboardService._start_parking_session_for_plate(
                request[0],
                is_dauerparker=bool(request[1])
            )
            
            return True, f"Entry genehmigt - {session_message}"
            
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
                SELECT license_plate, approval_status
                FROM entry_requests
                WHERE id = ?
            """, (request_id,))
            request = cursor.fetchone()

            if not request:
                return False, "Entry Request nicht gefunden"

            rejected_at = DashboardService._now_db()
            if request[1] == 'pending':
                cursor.execute("""
                    UPDATE entry_requests
                    SET approval_status = 'rejected', approved_at = ?
                    WHERE license_plate = ?
                      AND approval_status = 'pending'
                """, (rejected_at, request[0]))
            else:
                cursor.execute("""
                    UPDATE entry_requests
                    SET approval_status = 'rejected', approved_at = ?
                    WHERE id = ?
                """, (rejected_at, request_id))
            
            db.commit()
            
            return True, "Entry abgelehnt"
            
        except Exception as e:
            return False, f"Fehler: {str(e)}"

    @staticmethod
    def confirm_session_payment(session_id: int) -> Tuple[bool, str, Optional[float]]:
        """Bestaetigt die Zahlung und oeffnet das Ausfahrtsfenster."""
        try:
            cursor = db.get_cursor()
            cursor.execute("""
                SELECT
                    ps.entry_time,
                    ps.exit_time,
                    ps.payment_confirmed,
                    ps.payment_confirmed_at,
                    v.status,
                    v.license_plate
                FROM parking_sessions ps
                JOIN vehicles v ON ps.vehicle_id = v.id
                WHERE ps.id = ?
            """, (session_id,))
            row = cursor.fetchone()

            if not row:
                return False, "Park-Session nicht gefunden", None
            if row[4] == 'dauerparker':
                return False, "Dauerparker muessen keine Parkgebuehr bezahlen", None
            if row[1] is not None:
                return False, "Park-Session ist bereits beendet", None

            entry_time = datetime.fromisoformat(row[0]) if isinstance(row[0], str) else row[0]
            payment_time = datetime.now()
            previous_payment_time = datetime.fromisoformat(row[3]) if isinstance(row[3], str) else row[3]

            if row[2] and previous_payment_time:
                deadline = previous_payment_time + timedelta(minutes=3)
                if payment_time <= deadline:
                    return False, "Parkgebuehr wurde bereits bezahlt. Ausfahrtsfenster ist noch offen", None

            parking_seconds = int((payment_time - entry_time).total_seconds())
            parking_minutes = max(0, int(parking_seconds / 60))
            cost = PaymentCalculator.calculate_from_seconds(parking_seconds)

            cursor.execute("""
                UPDATE parking_sessions
                SET status = 'payment_confirmed',
                    parking_duration_minutes = ?,
                    cost_calculated = ?,
                    cost_paid = ?,
                    payment_confirmed = 1,
                    payment_confirmed_at = ?
                WHERE id = ?
            """, (
                parking_minutes,
                cost,
                cost,
                payment_time,
                session_id
            ))

            db.commit()
            return True, f"Zahlung fuer {row[5]} bestaetigt. Ausfahrt innerhalb von 3 Minuten moeglich", cost

        except Exception as e:
            return False, f"Fehler: {str(e)}", None

    @staticmethod
    def _start_parking_session_for_plate(license_plate: str, is_dauerparker: bool = False) -> Tuple[bool, str]:
        """Erstellt nach Freigabe eine aktive Parkplatz-Session fuer ein Kennzeichen."""
        cursor = db.get_cursor()

        cursor.execute("""
            SELECT v.id, ps.id
            FROM vehicles v
            LEFT JOIN parking_sessions ps
                ON ps.vehicle_id = v.id
                AND ps.exit_time IS NULL
            WHERE v.license_plate = ?
            ORDER BY ps.entry_time DESC
            LIMIT 1
        """, (license_plate,))
        existing = cursor.fetchone()

        if existing and existing[1]:
            return False, "Auto ist bereits im Parkhaus"

        now = DashboardService._now_db()
        vehicle_status = 'dauerparker' if is_dauerparker else 'approved'
        if existing:
            vehicle_id = existing[0]
            cursor.execute("""
                UPDATE vehicles
                SET status = ?,
                    is_valid_format = 1,
                    first_seen_at = COALESCE(first_seen_at, ?),
                    last_seen_at = ?
                WHERE id = ?
            """, (vehicle_status, now, now, vehicle_id))
        else:
            cursor.execute("""
                INSERT INTO vehicles (
                    license_plate,
                    is_valid_format,
                    status,
                    first_seen_at,
                    last_seen_at,
                    notes
                )
                VALUES (?, 1, ?, ?, ?, ?)
            """, (
                license_plate,
                vehicle_status,
                now,
                now,
                'Automatisch nach Einfahrtsfreigabe angelegt'
            ))
            vehicle_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO parking_sessions (vehicle_id, entry_time, status)
            VALUES (?, ?, 'parked')
        """, (vehicle_id, now))

        cursor.execute("""
            UPDATE parking_capacity
            SET occupied_spaces = (
                SELECT COUNT(*)
                FROM parking_sessions
                WHERE exit_time IS NULL
            ),
            last_updated = datetime('now', 'localtime')
            WHERE id = 1
        """)

        db.commit()
        return True, "Auto wurde ins Parkhaus eingetragen"
