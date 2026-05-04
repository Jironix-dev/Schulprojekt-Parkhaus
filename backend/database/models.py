"""
Tabellenstruktur und Datenbankmodelle für das Parkhaus-System
Kennzeichen-Format: 1 Buchstabe + Leerzeichen + 4 Ziffern (z.B. "A 1234")
"""

SCHEMA = {
    'vehicles': '''
        CREATE TABLE IF NOT EXISTS vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_plate TEXT UNIQUE NOT NULL,
            is_valid_format INTEGER DEFAULT 1,
            status TEXT DEFAULT 'pending',
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            first_seen_at TIMESTAMP,
            last_seen_at TIMESTAMP,
            notes TEXT,
            is_blocked INTEGER DEFAULT 0
        )
    ''',
    
    'parking_sessions': '''
        CREATE TABLE IF NOT EXISTS parking_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id INTEGER NOT NULL,
            entry_time TIMESTAMP NOT NULL,
            exit_time TIMESTAMP,
            entry_image_id INTEGER,
            exit_image_id INTEGER,
            status TEXT DEFAULT 'parked',
            parking_duration_minutes INTEGER,
            cost_calculated REAL DEFAULT 0.0,
            cost_paid REAL DEFAULT 0.0,
            payment_confirmed INTEGER DEFAULT 0,
            payment_confirmed_at TIMESTAMP,
            notes TEXT,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles(id),
            FOREIGN KEY (entry_image_id) REFERENCES images(id),
            FOREIGN KEY (exit_image_id) REFERENCES images(id)
        )
    ''',
    
    'images': '''
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_path TEXT NOT NULL,
            captured_at TIMESTAMP NOT NULL,
            image_type TEXT NOT NULL,
            detected_plate TEXT,
            confidence_score REAL,
            notes TEXT
        )
    ''',
    
    'plate_detections': '''
        CREATE TABLE IF NOT EXISTS plate_detections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_id INTEGER NOT NULL,
            detected_plate TEXT NOT NULL,
            raw_ocr_text TEXT,
            confidence_score REAL NOT NULL,
            is_valid INTEGER DEFAULT 1,
            detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notes TEXT,
            FOREIGN KEY (image_id) REFERENCES images(id)
        )
    ''',
    
    'parking_capacity': '''
        CREATE TABLE IF NOT EXISTS parking_capacity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            total_spaces INTEGER NOT NULL DEFAULT 50,
            occupied_spaces INTEGER DEFAULT 0,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''',
    
    'system_logs': '''
        CREATE TABLE IF NOT EXISTS system_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            vehicle_id INTEGER,
            message TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles(id)
        )
    '''
}

# Fahrzeug-Status
VEHICLE_STATUS = {
    'pending': 'Wartet auf Freigabe',
    'approved': 'Freigegeben/Bekannt',
    'blocked': 'Gesperrt',
    'unknown': 'Unbekannt'
}

# Parkplatz-Status
PARKING_STATUS = {
    'parked': 'Fahrzeug parkt',
    'payment_pending': 'Bezahlung ausstehend',
    'payment_confirmed': 'Bezahlung bestätigt',
    'exited': 'Ausgefahren'
}

# Bild-Typen
IMAGE_TYPES = {
    'entry': 'Einfahrt - Vollbild',
    'exit': 'Ausfahrt - Vollbild',
    'plate_crop': 'Kennzeichen-Ausschnitt',
    'roi': 'Region of Interest'
}
