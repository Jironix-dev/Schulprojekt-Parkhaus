"""
Dashboard-Service: Ruft relevante Daten von der Datenbank für das Dashboard ab
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
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
