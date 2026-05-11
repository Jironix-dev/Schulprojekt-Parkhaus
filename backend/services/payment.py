"""Kostenberechnung für Parkhaus-System"""

import math
from datetime import datetime
from typing import Optional, Tuple


class PaymentCalculator:
    """Berechnet Parkgebühren basierend auf Sekunden"""
    
    TIER_1_SECONDS = 30
    TIER_1_COST = 2.00
    TIER_2_SECONDS = 60
    TIER_2_COST = 3.50
    TIER_3_SECONDS = 90
    TIER_3_COST = 5.00
    ADDITIONAL_SECONDS = 30
    ADDITIONAL_COST = 1.50
    
    @classmethod
    def calculate_from_seconds(cls, parking_seconds: int) -> float:
        """Berechnet Kosten basierend auf Parkdauer in Sekunden"""
        if parking_seconds <= 0:
            return 0.0
        if parking_seconds <= cls.TIER_1_SECONDS:
            return cls.TIER_1_COST
        if parking_seconds <= cls.TIER_2_SECONDS:
            return cls.TIER_2_COST
        if parking_seconds <= cls.TIER_3_SECONDS:
            return cls.TIER_3_COST
        
        additional_seconds = parking_seconds - cls.TIER_3_SECONDS
        additional_slots = math.ceil(additional_seconds / cls.ADDITIONAL_SECONDS)
        cost = cls.TIER_3_COST + (additional_slots * cls.ADDITIONAL_COST)
        return round(cost, 2)


class DatabasePaymentCalculator:
    """Berechnet Kosten direkt aus Datenbank-Einträgen"""
    
    @staticmethod
    def calculate_cost_for_session(session_id: int, db_connection=None) -> Optional[float]:
        """Berechnet Kosten aus Datenbank-Zeiten für eine Session"""
        try:
            if db_connection is None:
                from backend.database.db import db
                db_connection = db
            
            if not db_connection.connection:
                db_connection.connect()
            
            cursor = db_connection.get_cursor()
            cursor.execute(
                "SELECT entry_time, exit_time FROM parking_sessions WHERE id = ?",
                (session_id,)
            )
            result = cursor.fetchone()
            
            if not result:
                return None
            
            entry_time_str, exit_time_str = result
            
            if not exit_time_str:
                return None
            
            entry_time = datetime.fromisoformat(entry_time_str)
            exit_time = datetime.fromisoformat(exit_time_str)
            parking_seconds = int((exit_time - entry_time).total_seconds())
            
            return PaymentCalculator.calculate_from_seconds(parking_seconds)
            
        except Exception:
            return None
    
    @staticmethod
    def calculate_and_update_session(session_id: int, db_connection=None) -> Tuple[bool, Optional[float], str]:
        """Berechnet Kosten und speichert sie in der Datenbank"""
        try:
            if db_connection is None:
                from backend.database.db import db
                db_connection = db
            
            if not db_connection.connection:
                db_connection.connect()
            
            cost = DatabasePaymentCalculator.calculate_cost_for_session(session_id, db_connection)
            
            if cost is None:
                return False, None, "Kosten konnten nicht berechnet werden"
            
            cursor = db_connection.get_cursor()
            cursor.execute(
                "UPDATE parking_sessions SET cost_calculated = ? WHERE id = ?",
                (cost, session_id)
            )
            db_connection.commit()
            
            return True, cost, f"Kosten berechnet und gespeichert: {cost:.2f} EUR"
            
        except Exception as e:
            return False, None, f"Fehler: {str(e)}"
    
    @staticmethod
    def get_session_cost_info(session_id: int, db_connection=None) -> dict:
        """Gibt detaillierte Kosten-Informationen für eine Session zurück"""
        try:
            if db_connection is None:
                from backend.database.db import db
                db_connection = db
            
            if not db_connection.connection:
                db_connection.connect()
            
            cursor = db_connection.get_cursor()
            cursor.execute(
                "SELECT entry_time, exit_time, cost_calculated FROM parking_sessions WHERE id = ?",
                (session_id,)
            )
            result = cursor.fetchone()
            
            if not result:
                return {'error': f'Session {session_id} nicht gefunden'}
            
            entry_time_str, exit_time_str, stored_cost = result
            entry_time = datetime.fromisoformat(entry_time_str) if entry_time_str else None
            exit_time = datetime.fromisoformat(exit_time_str) if exit_time_str else None
            
            info = {
                'session_id': session_id,
                'entry_time': entry_time,
                'exit_time': exit_time,
                'is_active': exit_time is None,
                'stored_cost': stored_cost
            }
            
            if entry_time and exit_time:
                duration = exit_time - entry_time
                seconds = int(duration.total_seconds())
                calculated_cost = PaymentCalculator.calculate_from_seconds(seconds)
                info['calculated_cost'] = calculated_cost
                info['duration_seconds'] = seconds
                info['duration_minutes'] = seconds / 60
                info['duration_hours'] = seconds / 3600
            
            return info
            
        except Exception as e:
            return {'error': f'Fehler beim Abrufen von Session-Infos: {str(e)}'}
