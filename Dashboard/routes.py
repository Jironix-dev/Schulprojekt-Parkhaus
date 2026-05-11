from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
import time
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
import sys

# Füge backend zum Pfad hinzu
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.database.db import db
from backend.services.dashboard_service import DashboardService

router = APIRouter()
# Pfad zum templates-Verzeichnis
templates_dir = Path(__file__).parent / "templates"
env = Environment(loader=FileSystemLoader(str(templates_dir)))

# Datenbank initialisieren
try:
    db.connect()
    db.initialize()
except Exception as e:
    print(f"[WARNUNG] Datenbank konnte nicht initialisiert werden: {e}")

# Logs speichern
logs = []

@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    # Hole alle Dashboard-Daten von der Datenbank
    dashboard_data = DashboardService.get_dashboard_summary()
    
    template = env.get_template("index.html")
    html = template.render(request=request, data=dashboard_data)
    return html

@router.get("/logs", response_class=HTMLResponse)
def log_page(request: Request):
    template = env.get_template("logs.html")
    html = template.render(request=request, logs=logs)
    return html

@router.get("/api/status")
def get_status():
    """Gibt aktuelle Dashboard-Daten zurück"""
    return DashboardService.get_dashboard_summary()

@router.post("/api/payment")
def confirm_payment():
    """Bestätigt Zahlung für aktuelle Session"""
    try:
        active_session = DashboardService.get_active_session()
        
        if not active_session:
            return {"message": "Keine aktive Session", "status": "error"}
        
        session_id = active_session['session_id']
        
        # Update in Datenbank
        cursor = db.get_cursor()
        cursor.execute("""
            UPDATE parking_sessions 
            SET payment_confirmed = 1, 
                payment_confirmed_at = datetime('now'),
                cost_paid = cost_calculated,
                status = 'paid'
            WHERE id = ?
        """, (session_id,))
        db.commit()
        
        # Log hinzufügen
        logs.append({
            "time": time.strftime("%H:%M:%S"),
            "event": f"Zahlung bestätigt für {active_session['license_plate']}"
        })
        
        return {"message": "OK", "status": "success"}
    except Exception as e:
        return {"message": f"Fehler: {str(e)}", "status": "error"}


# ==================== Widget Endpoints ====================

@router.get("/api/widget/costs")
def get_costs_widget():
    """Widget: Kostendetails für alle parkenden Fahrzeuge"""
    try:
        costs = DashboardService.get_cost_details()
        total_cost = sum(v['cost_calculated'] for v in costs)
        return {
            "title": "Kosten",
            "vehicles": costs,
            "total": round(total_cost, 2),
            "count": len(costs)
        }
    except Exception as e:
        return {"error": str(e), "vehicles": []}


@router.get("/api/widget/durations")
def get_durations_widget():
    """Widget: Parkdauer-Details für alle parkenden Fahrzeuge"""
    try:
        durations = DashboardService.get_duration_details()
        avg_duration = sum(v['parking_duration_minutes'] for v in durations) / len(durations) if durations else 0
        return {
            "title": "Parkdauer",
            "vehicles": durations,
            "average_duration_minutes": round(avg_duration, 1),
            "count": len(durations)
        }
    except Exception as e:
        return {"error": str(e), "vehicles": []}


@router.get("/api/widget/plate-recognition")
def get_plate_recognition_widget():
    """Widget: Kennzeichen-Erkennungs-Details"""
    try:
        plates = DashboardService.get_plate_recognition_details()
        avg_confidence = sum(v['confidence_score'] for v in plates) / len(plates) if plates else 0
        return {
            "title": "Kennzeichen-Erkennung",
            "vehicles": plates,
            "average_confidence": round(avg_confidence, 1),
            "count": len(plates)
        }
    except Exception as e:
        return {"error": str(e), "vehicles": []}


@router.get("/api/widget/status")
def get_status_widget():
    """Widget: Fahrzeug-Status-Details"""
    try:
        statuses = DashboardService.get_vehicle_status_details()
        return {
            "title": "Fahrzeug-Status",
            "vehicles": statuses,
            "count": len(statuses)
        }
    except Exception as e:
        return {"error": str(e), "vehicles": []}