"""
SQLite Datenbankverbindung und Verwaltung
"""

import sqlite3
from pathlib import Path
from typing import Optional
from .models import SCHEMA

# Datenbankpfad
DB_PATH = Path(__file__).parent.parent.parent / 'data' / 'parkhaus.db'


class Database:
    """Verwaltet SQLite-Verbindung und Tabelleninitialisierung"""
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = None
        
    def connect(self):
        """Stellt Verbindung zur Datenbank her"""
        try:
            self.connection = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self.connection.row_factory = sqlite3.Row
            print(f"[OK] Datenbankverbindung hergestellt: {self.db_path}")
        except sqlite3.Error as e:
            print(f"[FEHLER] Fehler bei Datenbankverbindung: {e}")
            raise
            
    def close(self):
        """Schließt Datenbankverbindung"""
        if self.connection:
            self.connection.close()
            print("[OK] Datenbankverbindung geschlossen")
            
    def initialize(self):
        """Erstellt alle notwendigen Tabellen"""
        if not self.connection:
            self.connect()
            
        cursor = self.connection.cursor()
        
        try:
            for table_name, create_sql in SCHEMA.items():
                cursor.execute(create_sql)
                print(f"[OK] Tabelle '{table_name}' initialisiert")
            
            # Kapazität initialisieren, falls leer
            cursor.execute("SELECT COUNT(*) FROM parking_capacity")
            if cursor.fetchone()[0] == 0:
                cursor.execute(
                    "INSERT INTO parking_capacity (total_spaces, occupied_spaces) VALUES (50, 0)"
                )
                print("[OK] Parkplatz-Kapazitaet initialisiert (50 Plaetze)")
            
            self.connection.commit()
            print("[OK] Datenbank erfolgreich initialisiert")
            
        except sqlite3.Error as e:
            print(f"[FEHLER] Fehler beim Initialisieren: {e}")
            self.connection.rollback()
            raise
            
    def get_cursor(self):
        """Gibt einen Datenbank-Cursor zurück"""
        if not self.connection:
            self.connect()
        return self.connection.cursor()
    
    def commit(self):
        """Speichert Änderungen"""
        if self.connection:
            self.connection.commit()
            
    def rollback(self):
        """Macht letzte Änderungen rückgängig"""
        if self.connection:
            self.connection.rollback()


# Globale Datenbankinstanz
db = Database()


if __name__ == '__main__':
    # Test: Datenbank initialisieren
    db.connect()
    db.initialize()
    db.close()
