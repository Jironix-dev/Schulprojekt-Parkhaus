"""
Initialisierungs- und Test-Skript für die Parkhaus-Datenbank
Führe dieses Skript aus um die SQLite-Datenbank zu erstellen
"""

import sys
from pathlib import Path

# Backend-Modul hinzufügen
sys.path.insert(0, str(Path(__file__).parent / 'backend'))

from database.db import db
from database.queries import VehicleQueries, ParkingQueries, SystemQueries, ImageQueries


def initialize_database():
    """Initialisiert die Datenbank"""
    print("=" * 60)
    print("PARKHAUS-SYSTEM - DATENBANKINITIALISIERUNG")
    print("=" * 60)
    
    try:
        # Verbindung herstellen
        db.connect()
        
        # Tabellen erstellen
        db.initialize()
        
        # Beispieldaten hinzufügen (optional)
        print("\n" + "=" * 60)
        print("Füge Beispieldaten hinzu...")
        print("=" * 60)
        
        # Fahrzeuge
        vehicle1_id = VehicleQueries.add_vehicle('A 1234', 'Testwagen 1')
        vehicle2_id = VehicleQueries.add_vehicle('B 5678', 'Testwagen 2')
        
        if vehicle1_id:
            print(f"[OK] Fahrzeug 1 hinzugefuegt (ID: {vehicle1_id})")
        if vehicle2_id:
            print(f"[OK] Fahrzeug 2 hinzugefuegt (ID: {vehicle2_id})")
        
        # Fahrzeug 1 freigeben
        VehicleQueries.approve_vehicle(vehicle1_id)
        print(f"[OK] Fahrzeug 1 freigegeben")
        
        # Systemevent
        SystemQueries.log_event('INIT', 'Datenbank initialisiert', None)
        print("[OK] Systemevent protokolliert")
        
        db.close()
        
        print("\n" + "=" * 60)
        print("✓ DATENBANK ERFOLGREICH INITIALISIERT")
        print("=" * 60)
        print(f"Datenbank-Pfad: {db.db_path}")
        print("=" * 60 + "\n")
        
        return True
        
    except Exception as e:
        print(f"\n✗ FEHLER: {e}")
        return False


if __name__ == '__main__':
    initialize_database()
