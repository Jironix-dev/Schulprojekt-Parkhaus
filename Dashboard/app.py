from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import sys
import os

# Pfad zum Dashboard-Verzeichnis
dashboard_dir = Path(__file__).parent
sys.path.insert(0, str(dashboard_dir))

from routes import router
from livefeed import live_feed
from mqtt_parking_control import start_mqtt_heartbeat, stop_mqtt_heartbeat

app = FastAPI()

# Statische Dateien mit korrektem Pfad
app.mount("/static", StaticFiles(directory=str(dashboard_dir / "static")), name="static")

app.include_router(router)


@app.on_event("startup")
async def startup_mqtt_heartbeat():
    """Startet den MQTT-Heartbeat zum ESP32."""
    start_mqtt_heartbeat()


# Shutdown-Handler für Kamera
@app.on_event("shutdown")
async def shutdown_camera():
    """Beendet die Kamera beim Fahren des Dashboard herunter"""
    stop_mqtt_heartbeat()
    live_feed.shutdown()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)