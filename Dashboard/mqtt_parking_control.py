"""
MQTT-Steuerung fuer Ampel und Schranke.

Dieses Script sendet einfache Textbefehle an den ESP32. Der ESP32 muss dafuer
das gleiche MQTT-Topic abonnieren und die gleichen Nachrichtentexte auswerten.

Typischer Ablauf:
1. Kennzeichen wurde erkannt.
2. Ampel schaltet von Rot auf Gelb.
3. Nach kurzer Wartezeit schaltet die Ampel auf Gruen.
4. Schranke oeffnet.
5. Auto faehrt durch.
6. Ampel schaltet wieder auf Gelb.
7. Kurz danach schliesst die Schranke.
8. Ampel schaltet wieder auf Rot.

Wichtig:
- Mosquitto laeuft auf dem Raspberry Pi als MQTT-Broker.
- Dieses Python-Script ist der MQTT-Client, der Befehle an den Broker sendet.
- Der ESP32 ist ebenfalls MQTT-Client und empfaengt diese Befehle.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

try:
    import paho.mqtt.client as mqtt
except ImportError as exc:
    raise ImportError(
        "Das Paket 'paho-mqtt' fehlt. Installiere es z.B. mit: pip install paho-mqtt"
    ) from exc


# =============================================================================
# MQTT-EINSTELLUNGEN - HIER KANNST DU BROKER UND TOPICS AENDERN
# =============================================================================

# Wenn Mosquitto auf dem gleichen Raspberry Pi laeuft, bleibt hier "localhost".
# Falls der Broker auf einem anderen Geraet laeuft, hier dessen IP-Adresse eintragen.
MQTT_BROKER_HOST = "localhost"

# Standard-Port fuer MQTT ohne Verschluesselung.
MQTT_BROKER_PORT = 1883

# Topic, auf dem der ESP32 die Steuerbefehle empfangen soll.
# Der ESP32 muss also z.B. "parkhaus/steuerung" abonnieren.
MQTT_COMMAND_TOPIC = "parkhaus/steuerung"

# Optionales Topic fuer Statusmeldungen dieses Scripts.
# Kann im ESP32 ignoriert werden, ist aber praktisch zum Testen.
MQTT_STATUS_TOPIC = "parkhaus/status"

# Frei waehlbarer Client-Name fuer die Verbindung zum Broker.
MQTT_CLIENT_ID = "parkhaus_dashboard"

# Falls dein Mosquitto-Broker Benutzername/Passwort nutzt, hier eintragen.
# Wenn kein Login eingerichtet ist, einfach None lassen.
MQTT_USERNAME: Optional[str] = None
MQTT_PASSWORD: Optional[str] = None


# =============================================================================
# NACHRICHTEN AN DEN ESP32 - HIER KANNST DU DIE TEXTBEFEHLE AENDERN
# =============================================================================

# Ampel-Befehle
NACHRICHT_AMPEL_ROT = "Ampel Rot"
NACHRICHT_AMPEL_GELB = "Ampel Gelb"
NACHRICHT_AMPEL_GRUEN = "Ampel Gruen"

# Schranken-Befehle
NACHRICHT_SCHRANKE_AUF = "Schranke Auf"
NACHRICHT_SCHRANKE_ZU = "Schranke Zu"

# Statusmeldungen, nur fuer Logs/Tests.
NACHRICHT_ABLAUF_START = "Ablauf Start"
NACHRICHT_ABLAUF_ENDE = "Ablauf Ende"


# =============================================================================
# ZEITEN - HIER KANNST DU DIE WARTEZEITEN AENDERN
# =============================================================================

# Wartezeit zwischen "Ampel Gelb" und "Ampel Gruen".
ZEIT_GELB_BIS_GRUEN_SEKUNDEN = 2.0

# Wartezeit, nachdem die Schranke geoeffnet wurde.
# Diese Zeit soll reichen, damit das Auto durchfahren kann.
ZEIT_SCHRANKE_OFFEN_SEKUNDEN = 6.0

# Wartezeit zwischen "Ampel Gelb" und "Schranke Zu".
# Dadurch wird die Ampel kurz vor dem Schliessen gelb.
ZEIT_GELB_VOR_SCHLIESSEN_SEKUNDEN = 1.5

# Kurze Wartezeit nach "Schranke Zu", bevor die Ampel wieder rot wird.
ZEIT_ROT_NACH_SCHLIESSEN_SEKUNDEN = 0.5


# =============================================================================
# LOGGING
# =============================================================================

logger = logging.getLogger(__name__)

__all__ = [
    "run_parking_sequence",
    "start_parking_sequence_async",
]

_sequence_lock = threading.Lock()


def _create_mqtt_client():
    """
    Erstellt einen MQTT-Client und verbindet ihn mit Mosquitto.

    Diese Funktion wird intern verwendet. Normalerweise musst du hier nichts
    aendern, ausser du moechtest spezielle MQTT-Optionen setzen.
    """
    try:
        # paho-mqtt ab Version 2 kennt CallbackAPIVersion.
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=MQTT_CLIENT_ID)
    except AttributeError:
        # Fallback fuer aeltere paho-mqtt-Versionen.
        client = mqtt.Client(client_id=MQTT_CLIENT_ID)

    if MQTT_USERNAME and MQTT_PASSWORD:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

    logger.info("Verbinde mit MQTT-Broker %s:%s", MQTT_BROKER_HOST, MQTT_BROKER_PORT)
    client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, keepalive=60)
    client.loop_start()
    return client


def _send_command(client, message: str) -> None:
    """
    Sendet einen einfachen Textbefehl an den ESP32.

    Alle Befehle werden auf MQTT_COMMAND_TOPIC gesendet.
    """
    logger.info("MQTT -> Topic '%s': %s", MQTT_COMMAND_TOPIC, message)
    result = client.publish(MQTT_COMMAND_TOPIC, message, qos=1)
    result.wait_for_publish()

    if not result.is_published():
        raise RuntimeError(f"MQTT-Nachricht konnte nicht gesendet werden: {message}")


def run_parking_sequence() -> None:
    """
    Fuehrt den kompletten Ablauf fuer ein erkanntes Kennzeichen aus.

    Diese Funktion blockiert, bis der Ablauf fertig ist. Wenn du sie direkt aus
    einem Web-Endpunkt aufrufst, wartet der Web-Endpunkt also solange mit der
    Antwort. Fuer FastAPI ist deshalb meistens start_parking_sequence_async()
    besser geeignet.
    """
    if not _sequence_lock.acquire(blocking=False):
        logger.warning("MQTT-Ablauf laeuft bereits, neuer Start wird uebersprungen")
        return

    client = _create_mqtt_client()

    try:
        client.publish(MQTT_STATUS_TOPIC, NACHRICHT_ABLAUF_START, qos=1)

        # 1. Ampel war vorher rot. Jetzt auf gelb schalten.
        _send_command(client, NACHRICHT_AMPEL_GELB)
        time.sleep(ZEIT_GELB_BIS_GRUEN_SEKUNDEN)

        # 2. Nach kurzer Zeit auf gruen schalten.
        _send_command(client, NACHRICHT_AMPEL_GRUEN)

        # 3. Schranke oeffnen.
        _send_command(client, NACHRICHT_SCHRANKE_AUF)

        # 4. Auto faehrt durch. Schranke bleibt fuer diese Zeit offen.
        time.sleep(ZEIT_SCHRANKE_OFFEN_SEKUNDEN)

        # 5. Kurz bevor die Schranke schliesst, Ampel auf gelb schalten.
        _send_command(client, NACHRICHT_AMPEL_GELB)
        time.sleep(ZEIT_GELB_VOR_SCHLIESSEN_SEKUNDEN)

        # 6. Schranke schliessen.
        _send_command(client, NACHRICHT_SCHRANKE_ZU)
        time.sleep(ZEIT_ROT_NACH_SCHLIESSEN_SEKUNDEN)

        # 7. Sobald die Schranke zugeht/zu ist, Ampel wieder auf rot schalten.
        _send_command(client, NACHRICHT_AMPEL_ROT)

        client.publish(MQTT_STATUS_TOPIC, NACHRICHT_ABLAUF_ENDE, qos=1)
        logger.info("Parkhaus-Ablauf erfolgreich abgeschlossen")

    finally:
        client.loop_stop()
        client.disconnect()
        _sequence_lock.release()


def start_parking_sequence_async() -> threading.Thread:
    """
    Startet den Ablauf im Hintergrund.

    Diese Funktion ist praktisch fuer das Dashboard:
    Nach erfolgreicher Kennzeichen-Erkennung kann sie aufgerufen werden, ohne
    dass der API-Endpunkt mehrere Sekunden blockiert.

    Beispiel fuer spaeter in Dashboard/routes.py:

        from Dashboard.mqtt_parking_control import start_parking_sequence_async

        start_parking_sequence_async()
    """
    thread = threading.Thread(
        target=run_parking_sequence,
        name="mqtt-parking-sequence",
        daemon=True,
    )
    thread.start()
    return thread


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("Starte Test-Ablauf fuer Ampel und Schranke per MQTT...")
    print(f"Broker: {MQTT_BROKER_HOST}:{MQTT_BROKER_PORT}")
    print(f"Topic:  {MQTT_COMMAND_TOPIC}")

    run_parking_sequence()
