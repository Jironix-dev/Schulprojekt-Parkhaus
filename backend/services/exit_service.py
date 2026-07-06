"""
Ausfahrtslogik fuer das Parkhaus.

Ein Fahrzeug darf erst ausfahren, wenn die Parkgebuehr bezahlt wurde. Nach der
Zahlung bleibt ein Zeitfenster von 3 Minuten, in dem die erneute Kennzeichen-
Erkennung die Ausfahrt abschliesst.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

from backend.database.db import db
from backend.database.validators import PlateValidator
from backend.services.payment import PaymentCalculator


class ExitService:
    EXIT_WINDOW_MINUTES = 3

    @staticmethod
    def _now_db() -> str:
        return datetime.now().replace(microsecond=0).isoformat(sep=' ')

    @staticmethod
    def _parse_db_time(value: Any) -> Optional[datetime]:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        return datetime.fromisoformat(str(value))

    @staticmethod
    def get_active_session_for_plate(license_plate: str) -> Optional[Dict[str, Any]]:
        is_valid, normalized_plate = PlateValidator.validate_and_normalize(license_plate)
        if not is_valid:
            return None

        cursor = db.get_cursor()
        cursor.execute("""
            SELECT
                ps.id,
                v.license_plate,
                ps.entry_time,
                ps.billing_started_at,
                ps.payment_confirmed,
                ps.payment_confirmed_at,
                ps.status,
                v.status
            FROM parking_sessions ps
            JOIN vehicles v ON ps.vehicle_id = v.id
            WHERE v.license_plate = ?
              AND ps.exit_time IS NULL
            ORDER BY ps.entry_time DESC
            LIMIT 1
        """, (normalized_plate,))
        row = cursor.fetchone()

        if not row:
            return None

        return {
            'session_id': row[0],
            'license_plate': row[1],
            'entry_time': row[2],
            'billing_started_at': row[3],
            'payment_confirmed': bool(row[4]),
            'payment_confirmed_at': row[5],
            'session_status': row[6],
            'vehicle_status': row[7],
        }

    @staticmethod
    def has_active_session(license_plate: str) -> bool:
        return ExitService.get_active_session_for_plate(license_plate) is not None

    @staticmethod
    def process_exit_detection(license_plate: str) -> Tuple[bool, str, Dict[str, Any]]:
        is_valid, normalized_plate = PlateValidator.validate_and_normalize(license_plate)
        if not is_valid:
            return False, "Format ungueltig", {}

        session = ExitService.get_active_session_for_plate(normalized_plate)
        now = datetime.now().replace(microsecond=0)

        if not session:
            log_data = ExitService._log_exit_attempt(
                normalized_plate,
                None,
                'not_in_parking',
                "Kennzeichen ist nicht im Parkhaus",
                False,
                None,
                None,
                None,
                now,
            )
            return False, "Kennzeichen ist nicht im Parkhaus", log_data

        payment_time = ExitService._parse_db_time(session['payment_confirmed_at'])
        deadline = payment_time + timedelta(minutes=ExitService.EXIT_WINDOW_MINUTES) if payment_time else None

        if session['vehicle_status'] == 'dauerparker':
            return ExitService._complete_exit(session, 'allowed', "Dauerparker darf ausfahren", now, None)

        if not session['payment_confirmed'] or not payment_time:
            log_data = ExitService._log_exit_attempt(
                normalized_plate,
                session['session_id'],
                'payment_required',
                "Parkgebuehr noch nicht bezahlt",
                False,
                None,
                None,
                None,
                now,
            )
            return False, "Parkgebuehr noch nicht bezahlt", log_data

        if now > deadline:
            ExitService._reset_expired_payment(session, now)
            log_data = ExitService._log_exit_attempt(
                normalized_plate,
                session['session_id'],
                'expired',
                "Ausfahrtszeit nach Zahlung abgelaufen - bitte erneut bezahlen",
                False,
                payment_time,
                deadline,
                None,
                now,
            )
            return False, "Ausfahrtszeit nach Zahlung abgelaufen - bitte erneut bezahlen", log_data

        return ExitService._complete_exit(
            session,
            'allowed',
            "Ausfahrt abgeschlossen",
            now,
            deadline,
        )

    @staticmethod
    def expire_overdue_exit_windows(now: Optional[datetime] = None) -> int:
        """Setzt bezahlte Sessions nach Ablauf des Ausfahrtsfensters automatisch zurueck."""
        now = now or datetime.now().replace(microsecond=0)
        cursor = db.get_cursor()
        cursor.execute("""
            SELECT
                ps.id,
                v.license_plate,
                ps.entry_time,
                ps.billing_started_at,
                ps.payment_confirmed,
                ps.payment_confirmed_at,
                ps.status,
                v.status
            FROM parking_sessions ps
            JOIN vehicles v ON ps.vehicle_id = v.id
            WHERE ps.exit_time IS NULL
              AND ps.payment_confirmed = 1
              AND ps.payment_confirmed_at IS NOT NULL
              AND v.status != 'dauerparker'
        """)

        expired_count = 0
        for row in cursor.fetchall():
            payment_time = ExitService._parse_db_time(row[5])
            if not payment_time:
                continue

            deadline = payment_time + timedelta(minutes=ExitService.EXIT_WINDOW_MINUTES)
            if now <= deadline:
                continue

            ExitService._reset_expired_payment({
                'session_id': row[0],
                'license_plate': row[1],
                'entry_time': row[2],
                'billing_started_at': row[3],
                'payment_confirmed': bool(row[4]),
                'payment_confirmed_at': row[5],
                'session_status': row[6],
                'vehicle_status': row[7],
            }, now, billing_start=deadline)
            expired_count += 1

        return expired_count

    @staticmethod
    def _reset_expired_payment(
        session: Dict[str, Any],
        now: datetime,
        billing_start: Optional[datetime] = None,
    ) -> None:
        """Macht eine abgelaufene Zahlung wieder zahlungspflichtig."""
        payment_time = ExitService._parse_db_time(session['payment_confirmed_at'])
        if billing_start is None and payment_time:
            billing_start = payment_time + timedelta(minutes=ExitService.EXIT_WINDOW_MINUTES)
        billing_start = billing_start or now

        parking_seconds = max(0, int((now - billing_start).total_seconds()))
        parking_minutes = int(parking_seconds / 60)
        current_cost = PaymentCalculator.calculate_from_seconds(parking_seconds)

        cursor = db.get_cursor()
        cursor.execute("""
            UPDATE parking_sessions
            SET status = 'parked',
                billing_started_at = ?,
                parking_duration_minutes = ?,
                cost_calculated = ?,
                cost_paid = 0,
                payment_confirmed = 0,
                payment_confirmed_at = NULL
            WHERE id = ?
        """, (
            billing_start,
            parking_minutes,
            current_cost,
            session['session_id'],
        ))
        db.commit()

    @staticmethod
    def get_exit_protocol(limit: int = 100) -> list:
        cursor = db.get_cursor()
        cursor.execute("""
            SELECT
                id,
                license_plate,
                detected_at,
                exit_status,
                message,
                payment_confirmed,
                payment_confirmed_at,
                exit_deadline,
                completed_at
            FROM exit_requests
            ORDER BY detected_at DESC
            LIMIT ?
        """, (limit,))

        return [
            {
                'id': row[0],
                'license_plate': row[1],
                'detected_at': row[2],
                'exit_status': row[3],
                'message': row[4],
                'payment_confirmed': bool(row[5]),
                'payment_confirmed_at': row[6],
                'exit_deadline': row[7],
                'completed_at': row[8],
            }
            for row in cursor.fetchall()
        ]

    @staticmethod
    def _complete_exit(
        session: Dict[str, Any],
        status: str,
        message: str,
        completed_at: datetime,
        deadline: Optional[datetime],
    ) -> Tuple[bool, str, Dict[str, Any]]:
        cursor = db.get_cursor()
        cursor.execute("""
            UPDATE parking_sessions
            SET exit_time = ?,
                status = 'exited'
            WHERE id = ?
        """, (completed_at, session['session_id']))

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

        log_data = ExitService._log_exit_attempt(
            session['license_plate'],
            session['session_id'],
            status,
            message,
            True,
            ExitService._parse_db_time(session['payment_confirmed_at']),
            deadline,
            completed_at,
            completed_at,
        )
        return True, message, log_data

    @staticmethod
    def _log_exit_attempt(
        license_plate: str,
        session_id: Optional[int],
        status: str,
        message: str,
        payment_confirmed: bool,
        payment_confirmed_at: Optional[datetime],
        exit_deadline: Optional[datetime],
        completed_at: Optional[datetime],
        detected_at: datetime,
    ) -> Dict[str, Any]:
        cursor = db.get_cursor()
        cursor.execute("""
            INSERT INTO exit_requests (
                license_plate,
                detected_at,
                session_id,
                exit_status,
                message,
                payment_confirmed,
                payment_confirmed_at,
                exit_deadline,
                completed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            license_plate,
            detected_at,
            session_id,
            status,
            message,
            1 if payment_confirmed else 0,
            payment_confirmed_at,
            exit_deadline,
            completed_at,
        ))
        db.commit()

        return {
            'id': cursor.lastrowid,
            'license_plate': license_plate,
            'detected_at': detected_at.isoformat(sep=' '),
            'session_id': session_id,
            'exit_status': status,
            'message': message,
            'payment_confirmed': payment_confirmed,
            'payment_confirmed_at': payment_confirmed_at.isoformat(sep=' ') if payment_confirmed_at else None,
            'exit_deadline': exit_deadline.isoformat(sep=' ') if exit_deadline else None,
            'completed_at': completed_at.isoformat(sep=' ') if completed_at else None,
        }
