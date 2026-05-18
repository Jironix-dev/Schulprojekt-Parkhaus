from fastapi import APIRouter, Request, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
import time
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
import sys
import cv2
import numpy as np
from io import BytesIO

# Füge backend zum Pfad hinzu
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.database.db import db
from backend.services.dashboard_service import DashboardService
from backend.services.plate_recognition_service import PlateRecognitionService
from livefeed import generate_stream, get_static_frame, live_feed

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

@router.get("/api/health")
def health_check():
    """Health-Check: Überprüft ob alle Services verfügbar sind"""
    plate_service = PlateRecognitionService.get_instance()
    
    return {
        "status": "ok",
        "services": {
            "database": "✓ OK",
            "plate_recognition": "✓ OK" if plate_service.is_ready() else "❌ FEHLER",
            "tesseract_ocr": "✓ OK" if plate_service._recognizer and hasattr(plate_service._recognizer, 'ocr_handler') else "❌ NICHT VERFÜGBAR",
            "yolo_model": "✓ OK" if plate_service.is_ready() else "❌ MODELL NICHT GELADEN"
        }
    }

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


@router.get("/api/widget/known-vehicles")
def get_known_vehicles_widget():
    """Widget: Alle bekannten Kennzeichen"""
    try:
        vehicles = DashboardService.get_known_vehicles()
        return {
            "title": "Bekannte Kennzeichen",
            "vehicles": [
                {
                    'license_plate': v['license_plate'],
                    'status': v['status'],
                    'first_seen_at': v['first_seen_at'],
                    'last_seen_at': v['last_seen_at'],
                    'total_sessions': v['total_sessions']
                }
                for v in vehicles
            ],
            "count": len(vehicles)
        }
    except Exception as e:
        return {"error": str(e), "vehicles": []}


# ==================== Live-Feed Endpoints ====================

@router.get("/api/stream")
def video_stream():
    """Motion JPEG Stream für Live-Feed"""
    return StreamingResponse(
        generate_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@router.get("/api/camera/frame")
def get_camera_frame():
    """Statischer Frame vom Live-Feed"""
    frame = get_static_frame()
    return StreamingResponse(
        iter([frame]),
        media_type="image/jpeg"
    )


@router.get("/api/camera/status")
def get_camera_status():
    """Gibt Status der Kamera zurück"""
    return {
        "active": live_feed.is_active(),
        "status": "aktiv" if live_feed.is_active() else "inaktiv"
    }


@router.get("/api/debug/camera")
def debug_camera():
    """Debug-Endpoint: Zeigt Kamera-Status und Fallback-Bild-Größe"""
    frame = get_static_frame()
    return {
        "camera_active": live_feed.is_active(),
        "frame_size_bytes": len(frame),
        "fallback_frame_size_bytes": len(live_feed.fallback_frame),
        "frame_is_empty": len(frame) == 0,
        "has_camera_object": live_feed.camera is not None,
        "capture_thread_alive": live_feed.capture_thread is not None and live_feed.capture_thread.is_alive() if live_feed.capture_thread else False
    }


# ==================== Plate Recognition Endpoints ====================

@router.post("/api/recognition/detect-plate")
async def detect_plate_from_camera():
    """
    Erkennt Kennzeichen im aktuellen Live-Feed
    
    Returns:
        - detected_plate: Erkanntes Kennzeichen
        - plate_confidence: YOLO Konfidenz
        - ocr_confidence: OCR Konfidenz
        - combined_confidence: Kombinierte Konfidenz
        - vehicle_snapshot: Base64 des ganzen Fahrzeugs
        - plate_image: Base64 des Kennzeichens
        - annotated_frame: Base64 mit Bounding Box
    """
    try:
        # Hole aktuellen Frame
        frame_bytes = get_static_frame()
        if not frame_bytes:
            return JSONResponse(
                {"success": False, "error": "Kein Frame verfügbar"},
                status_code=503
            )
        
        # Dekodiere Frame
        nparr = np.frombuffer(frame_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is None or frame.size == 0:
            return JSONResponse(
                {"success": False, "error": "Frame konnte nicht dekodiert werden"},
                status_code=400
            )
        
        # Erkenne Kennzeichen
        plate_service = PlateRecognitionService.get_instance()
        result = plate_service.recognize_frame(frame)
        
        return JSONResponse(result)
        
    except Exception as e:
        return JSONResponse(
            {"success": False, "error": str(e)},
            status_code=500
        )


@router.post("/api/recognition/upload-image")
async def detect_plate_from_upload(file: UploadFile = File(...)):
    """
    Erkennt Kennzeichen in hochgeladenem Bild
    
    Returns:
        - detected_plate: Erkanntes Kennzeichen
        - plate_confidence: YOLO Konfidenz
        - ocr_confidence: OCR Konfidenz
        - combined_confidence: Kombinierte Konfidenz
        - vehicle_snapshot: Base64 des Bildes
        - plate_image: Base64 des Kennzeichens
        - annotated_frame: Base64 mit Bounding Box
    """
    try:
        # Lese Datei
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is None or frame.size == 0:
            return JSONResponse(
                {"success": False, "error": "Bild konnte nicht gelesen werden"},
                status_code=400
            )
        
        # Erkenne Kennzeichen
        plate_service = PlateRecognitionService.get_instance()
        result = plate_service.recognize_frame(frame)
        
        # Speichere Erkennung falls erfolgreich
        if result["success"]:
            logs.append({
                "time": time.strftime("%H:%M:%S"),
                "event": f"Kennzeichen erkannt: {result['detected_plate']} (Conf: {result['combined_confidence']:.2%})"
            })
        
        return JSONResponse(result)
        
    except Exception as e:
        return JSONResponse(
            {"success": False, "error": str(e)},
            status_code=500
        )


@router.get("/api/recognition/statistics")
def get_recognition_statistics():
    """Gibt Statistiken über Kennzeichen-Erkennungen zurück"""
    try:
        plate_service = PlateRecognitionService.get_instance()
        stats = plate_service.get_statistics()
        return {
            "status": "success",
            "statistics": stats,
            "service_ready": plate_service.is_ready()
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "service_ready": False
        }


@router.get("/api/recognition/status")
def get_recognition_status():
    """Gibt Status des Plate Recognition Service zurück"""
    try:
        plate_service = PlateRecognitionService.get_instance()
        return {
            "service_ready": plate_service.is_ready(),
            "status": "ready" if plate_service.is_ready() else "not_ready",
            "message": "Plate Recognition Service läuft" if plate_service.is_ready() else "Service nicht verfügbar"
        }
    except Exception as e:
        return {
            "service_ready": False,
            "status": "error",
            "error": str(e)
        }


@router.post("/api/recognition/reset-statistics")
def reset_recognition_statistics():
    """Setzt Erkennungs-Statistiken zurück"""
    try:
        plate_service = PlateRecognitionService.get_instance()
        plate_service.reset_statistics()
        
        logs.append({
            "time": time.strftime("%H:%M:%S"),
            "event": "Erkennungs-Statistiken zurückgesetzt"
        })
        
        return {"status": "success", "message": "Statistiken zurückgesetzt"}
    except Exception as e:
        return {"status": "error", "error": str(e)}