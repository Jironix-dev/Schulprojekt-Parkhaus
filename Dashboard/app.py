from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import sys
import os

# Pfad zum Dashboard-Verzeichnis
dashboard_dir = Path(__file__).parent
sys.path.insert(0, str(dashboard_dir))

from routes import router

app = FastAPI()

# Statische Dateien mit korrektem Pfad
app.mount("/static", StaticFiles(directory=str(dashboard_dir / "static")), name="static")

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)