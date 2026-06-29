from fastapi import APIRouter, Request, File, UploadFile, Body
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
from backend.services.exit_service import ExitService
from backend.services.plate_recognition_service import PlateRecognitionService
from livefeed import generate_stream, get_static_frame, live_feed

try:
    from .mqtt_parking_control import start_parking_sequence_async
except ImportError:
    from mqtt_parking_control import start_parking_sequence_async

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


def start_mqtt_gate_sequence(license_plate: str) -> None:
    """Startet Ampel- und Schrankenablauf nach erfolgreicher Kennzeichen-Erkennung."""
    start_parking_sequence_async()
    logs.append({
        "time": time.strftime("%H:%M:%S"),
        "event": f"MQTT-Ablauf gestartet für {license_plate}"
    })


def get_entry_request_info(request_id: int) -> dict | None:
    """Liest die wichtigsten Daten einer Entry Request fuer MQTT-Entscheidungen."""
    cursor = db.get_cursor()
    cursor.execute("""
        SELECT license_plate, approval_status, is_dauerparker
        FROM entry_requests
        WHERE id = ?
    """, (request_id,))
    row = cursor.fetchone()

    if not row:
        return None

    return {
        "license_plate": row[0],
        "approval_status": row[1],
        "is_dauerparker": bool(row[2]),
    }


def get_latest_entry_request_for_plate(license_plate: str) -> dict | None:
    """Findet die neueste Entry Request fuer ein erkanntes Kennzeichen."""
    cursor = db.get_cursor()
    cursor.execute("""
        SELECT id, approval_status, is_dauerparker
        FROM entry_requests
        WHERE license_plate = ?
        ORDER BY id DESC
        LIMIT 1
    """, (license_plate,))
    row = cursor.fetchone()

    if not row:
        return None

    return {
        "id": row[0],
        "approval_status": row[1],
        "is_dauerparker": bool(row[2]),
    }


def start_mqtt_for_auto_approved_dauerparker(license_plate: str) -> None:
    """Oeffnet Ampel/Schranke nur bei automatisch genehmigten Dauerparkern."""
    entry_request = get_latest_entry_request_for_plate(license_plate)

    if (
        entry_request
        and entry_request["approval_status"] == "approved"
        and entry_request["is_dauerparker"]
    ):
        start_mqtt_gate_sequence(license_plate)


def handle_recognized_plate(license_plate: str, ocr_confidence: float) -> dict:
    """Verarbeitet ein erkanntes Kennzeichen als Ausfahrt oder Einfahrt."""
    if ExitService.has_active_session(license_plate):
        success, message, exit_log = ExitService.process_exit_detection(license_plate)
        logs.append({
            "time": time.strftime("%H:%M:%S"),
            "event": f"Ausfahrt {'erlaubt' if success else 'verweigert'}: {license_plate} - {message}"
        })
        return {
            "flow": "exit",
            "success": success,
            "message": message,
            "exit": exit_log
        }

    success, message = DashboardService.save_entry_request(license_plate, ocr_confidence)
    if success:
        logs.append({
            "time": time.strftime("%H:%M:%S"),
            "event": f"Entry Request: {license_plate} {message}"
        })
        start_mqtt_for_auto_approved_dauerparker(license_plate)
    else:
        logs.append({
            "time": time.strftime("%H:%M:%S"),
            "event": f"Entry Request ignoriert: {license_plate} - {message}"
        })

    return {
        "flow": "entry",
        "success": success,
        "message": message
    }

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
        success, message, cost = DashboardService.confirm_session_payment(session_id)

        if not success:
            return {"message": message, "status": "error"}
        
        # Log hinzufügen
        logs.append({
            "time": time.strftime("%H:%M:%S"),
            "event": f"Zahlung bestätigt für {active_session['license_plate']} ({cost:.2f} EUR)"
        })
        
        return {"message": message, "status": "success", "cost_paid": cost}
    except Exception as e:
        return {"message": f"Fehler: {str(e)}", "status": "error"}


@router.post("/api/payment/{session_id}")
def confirm_session_payment(session_id: int):
    """Bestätigt Zahlung fuer eine bestimmte Park-Session"""
    try:
        success, message, cost = DashboardService.confirm_session_payment(session_id)

        if success:
            logs.append({
                "time": time.strftime("%H:%M:%S"),
                "event": f"{message} ({cost:.2f} EUR)"
            })

        return {
            "message": message,
            "status": "success" if success else "error",
            "cost_paid": cost
        }
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


@router.get("/api/widget/parking-occupancy")
def get_parking_occupancy_widget():
    """Widget: Aktuelle Auslastung und Fahrzeuge im Parkhaus"""
    try:
        return DashboardService.get_parking_occupancy_details()
    except Exception as e:
        return {"error": str(e), "vehicles": [], "count": 0}


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


@router.get("/api/widget/dauerparker")
def get_dauerparker_widget():
    """Widget: Dauerparker (manuell eingegebene Kennzeichen)"""
    try:
        dauerparker = DashboardService.get_dauerparker()
        return {
            "title": "Dauerparker",
            "vehicles": [
                {
                    'license_plate': v['license_plate'],
                    'registered_at': v['registered_at'],
                    'notes': v['notes']
                }
                for v in dauerparker
            ],
            "count": len(dauerparker)
        }
    except Exception as e:
        return {"error": str(e), "vehicles": []}


@router.post("/api/widget/add-dauerparker")
def add_dauerparker(request_body: dict = Body(...)):
    """Endpunkt: Neuen Dauerparker hinzufügen"""
    try:
        license_plate = request_body.get('license_plate', '').strip().upper()
        
        success, message = DashboardService.add_dauerparker(license_plate)
        
        return {
            "success": success,
            "message": message,
            "license_plate": license_plate if success else None
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Fehler: {str(e)}"
        }


@router.post("/api/widget/delete-dauerparker")
def delete_dauerparker(request_body: dict = Body(...)):
    """Endpunkt: Dauerparker löschen"""
    try:
        license_plate = request_body.get('license_plate', '').strip().upper()
        
        success, message = DashboardService.delete_dauerparker(license_plate)
        
        return {
            "success": success,
            "message": message,
            "license_plate": license_plate if success else None
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Fehler: {str(e)}"
        }


@router.get("/api/widget/detection-protocol")
def get_detection_protocol():
    """Widget: Erkennungsprotokoll - alle erkannten Kennzeichen"""
    try:
        detections = DashboardService.get_detection_protocol(limit=100)
        return {
            "title": "Erkennungsprotokoll",
            "detections": detections,
            "count": len(detections)
        }
    except Exception as e:
        return {"error": str(e), "detections": [], "count": 0}


@router.get("/api/widget/protocol-preview")
def get_protocol_preview():
    """Widget-Vorschau: letzte Protokollaktion aus Einfahrt oder Ausfahrt."""
    try:
        return {
            "status": "success",
            "latest": DashboardService.get_latest_protocol_action()
        }
    except Exception as e:
        return {"status": "error", "message": str(e), "latest": None}


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
        
        # Speichere Entry Request wenn gültiges Kennzeichen erkannt wurde
        if result.get("success") and result.get("detected_plate"):
            license_plate = result["detected_plate"].strip()
            ocr_confidence = result.get("ocr_confidence", 0.0)
            result["parking_flow"] = handle_recognized_plate(license_plate, ocr_confidence)
        
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
        
        # Speichere Entry Request wenn gültiges Kennzeichen erkannt wurde
        if result.get("success") and result.get("detected_plate"):
            license_plate = result["detected_plate"].strip()
            ocr_confidence = result.get("ocr_confidence", 0.0)
            result["parking_flow"] = handle_recognized_plate(license_plate, ocr_confidence)
        elif result.get("detected_plate"):
            # Ungültiges Kennzeichen erkannt
            logs.append({
                "time": time.strftime("%H:%M:%S"),
                "event": f"⚠️ UNGÜLTIGES FORMAT: {result.get('detected_plate')} (Conf: {result.get('combined_confidence', 0):.2%})"
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
        return {"status": "error", "message": str(e)}


@router.post("/api/entry/save-request")
def save_entry_request(data: dict = Body(...)):
    """
    Speichert einen Entry Request wenn OCR ein gültiges Kennzeichen erkennt.
    
    Body:
        {
            "license_plate": "A 1234",
            "ocr_confidence": 0.95
        }
    """
    try:
        license_plate = data.get("license_plate", "").strip()
        ocr_confidence = data.get("ocr_confidence", 0.0)
        
        success, message = DashboardService.save_entry_request(license_plate, ocr_confidence)
        
        logs.append({
            "time": time.strftime("%H:%M:%S"),
            "event": f"Entry Request: {license_plate} - {message}"
        })
        if success:
            start_mqtt_for_auto_approved_dauerparker(license_plate)
        
        return {
            "status": "success" if success else "error",
            "message": message
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/api/entry/requests")
def get_entry_requests(limit: int = 50):
    """
    Ruft alle Entry Requests ab (erkannte Kennzeichen für Genehmigung).
    """
    try:
        requests = DashboardService.get_entry_requests(limit)
        return {
            "status": "success",
            "data": requests,
            "count": len(requests)
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/api/exit/requests")
def get_exit_requests(limit: int = 100):
    """
    Ruft alle Ausfahrtsversuche ab.
    """
    try:
        requests = ExitService.get_exit_protocol(limit)
        return {
            "status": "success",
            "data": requests,
            "count": len(requests)
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/api/entry/approve/{request_id}")
def approve_entry(request_id: int):
    """
    Genehmigt einen Entry Request (Auto darf einfahren).
    """
    try:
        entry_before_approval = get_entry_request_info(request_id)
        success, message = DashboardService.approve_entry_request(request_id)
        
        logs.append({
            "time": time.strftime("%H:%M:%S"),
            "event": f"Entry #{request_id} genehmigt"
        })

        if (
            success
            and entry_before_approval
            and entry_before_approval["approval_status"] == "pending"
        ):
            start_mqtt_gate_sequence(entry_before_approval["license_plate"])
        
        return {
            "status": "success" if success else "error",
            "message": message
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/api/entry/reject/{request_id}")
def reject_entry(request_id: int):
    """
    Lehnt einen Entry Request ab (Auto darf NICHT einfahren).
    """
    try:
        success, message = DashboardService.reject_entry_request(request_id)
        
        logs.append({
            "time": time.strftime("%H:%M:%S"),
            "event": f"Entry #{request_id} abgelehnt"
        })
        
        return {
            "status": "success" if success else "error",
            "message": message
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
        return {"status": "error", "error": str(e)}
