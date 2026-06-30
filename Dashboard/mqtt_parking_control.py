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
from collections import deque
from datetime import datetime
from itertools import count
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

# Topics, auf denen der ESP32 die Steuerbefehle empfangen soll.
MQTT_TOPIC_AMPEL_EINFAHRT = "ampel/einfahrt"
MQTT_TOPIC_AMPEL_AUSFAHRT = "ampel/ausfahrt"
MQTT_TOPIC_SCHRANKE_EINFAHRT = "schranke/einfahrt"
MQTT_TOPIC_SCHRANKE_AUSFAHRT = "schranke/ausfahrt"

# Topics, auf denen der ESP32 Statusmeldungen zuruecksendet.
MQTT_STATUS_TOPICS = (
    "ampel/einfahrt/status",
    "ampel/ausfahrt/status",
    "schranke/status",
)

MQTT_TOPIC_HEARTBEAT_PING = "esp32/heartbeat/ping"
MQTT_TOPIC_HEARTBEAT_PONG = "esp32/heartbeat/pong"
MQTT_HEARTBEAT_INTERVAL_SECONDS = 5
MQTT_HEARTBEAT_TIMEOUT_SECONDS = 8

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
    "get_mqtt_esp_status",
    "get_mqtt_monitor_entries",
    "run_parking_sequence",
    "start_parking_sequence_async",
    "run_exit_sequence",
    "start_exit_sequence_async",
    "start_mqtt_heartbeat",
    "stop_mqtt_heartbeat",
]

_sequence_lock = threading.Lock()
_mqtt_monitor_lock = threading.Lock()
_mqtt_monitor_entries = deque(maxlen=200)
_esp_connected = False
_esp_last_seen = None
_esp_last_seen_monotonic = None
_client_counter = count(1)
_heartbeat_stop_event = threading.Event()
_heartbeat_thread = None


def _timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _remember_mqtt_message(direction: str, topic: str, payload: str) -> None:
    with _mqtt_monitor_lock:
        timestamp = _timestamp()
        _mqtt_monitor_entries.appendleft({
            "timestamp": timestamp,
            "direction": direction,
            "topic": topic,
            "payload": payload,
        })


def _mark_esp_seen() -> None:
    global _esp_connected, _esp_last_seen, _esp_last_seen_monotonic

    with _mqtt_monitor_lock:
        _esp_connected = True
        _esp_last_seen = _timestamp()
        _esp_last_seen_monotonic = time.monotonic()


def _refresh_esp_connection_state() -> None:
    global _esp_connected

    with _mqtt_monitor_lock:
        if _esp_last_seen_monotonic is None:
            _esp_connected = False
            return

        _esp_connected = (
            time.monotonic() - _esp_last_seen_monotonic
            <= MQTT_HEARTBEAT_TIMEOUT_SECONDS
        )


def get_mqtt_monitor_entries(limit: int = 100) -> list[dict[str, str]]:
    with _mqtt_monitor_lock:
        return list(_mqtt_monitor_entries)[:limit]


def get_mqtt_esp_status() -> dict[str, str | bool | None]:
    _refresh_esp_connection_state()
    with _mqtt_monitor_lock:
        return {
            "connected": _esp_connected,
            "last_seen": _esp_last_seen,
        }


def _on_mqtt_message(client, userdata, message) -> None:
    payload = message.payload.decode("utf-8", errors="replace")
    logger.info("MQTT <- Topic '%s': %s", message.topic, payload)
    _mark_esp_seen()

    if message.topic != MQTT_TOPIC_HEARTBEAT_PONG:
        _remember_mqtt_message("ESP32 -> Dashboard", message.topic, payload)


def _next_client_id(purpose: str) -> str:
    return f"{MQTT_CLIENT_ID}_{purpose}_{next(_client_counter)}"


def _create_mqtt_client(
    client_id: str | None = None,
    subscribe_responses: bool = True,
):
    """
    Erstellt einen MQTT-Client und verbindet ihn mit Mosquitto.

    Diese Funktion wird intern verwendet. Normalerweise musst du hier nichts
    aendern, ausser du moechtest spezielle MQTT-Optionen setzen.
    """
    client_id = client_id or _next_client_id("sequence")

    try:
        # paho-mqtt ab Version 2 kennt CallbackAPIVersion.
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
    except AttributeError:
        # Fallback fuer aeltere paho-mqtt-Versionen.
        client = mqtt.Client(client_id=client_id)

    if MQTT_USERNAME and MQTT_PASSWORD:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

    client.on_message = _on_mqtt_message

    logger.info("Verbinde mit MQTT-Broker %s:%s", MQTT_BROKER_HOST, MQTT_BROKER_PORT)
    client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, keepalive=60)
    if subscribe_responses:
        for topic in MQTT_STATUS_TOPICS:
            client.subscribe(topic, qos=1)
        client.subscribe(MQTT_TOPIC_HEARTBEAT_PONG, qos=1)
    client.loop_start()
    return client


def _run_mqtt_heartbeat() -> None:
    client = None

    while not _heartbeat_stop_event.is_set():
        try:
            if client is None:
                client = _create_mqtt_client(_next_client_id("heartbeat"))

            result = client.publish(MQTT_TOPIC_HEARTBEAT_PING, "ping", qos=1)
            result.wait_for_publish()

            if not result.is_published():
                logger.warning("MQTT-Heartbeat konnte nicht gesendet werden")

            _refresh_esp_connection_state()

            if _heartbeat_stop_event.wait(MQTT_HEARTBEAT_INTERVAL_SECONDS):
                break

        except Exception as fehler:
            logger.warning("MQTT-Heartbeat Fehler: %s", fehler)
            _refresh_esp_connection_state()

            try:
                if client:
                    client.loop_stop()
                    client.disconnect()
            except Exception:
                pass

            client = None
            _heartbeat_stop_event.wait(MQTT_HEARTBEAT_INTERVAL_SECONDS)

    try:
        if client:
            client.loop_stop()
            client.disconnect()
    except Exception:
        pass


def start_mqtt_heartbeat() -> None:
    """Startet den Hintergrund-Heartbeat zum ESP32."""
    global _heartbeat_thread

    if _heartbeat_thread and _heartbeat_thread.is_alive():
        return

    _heartbeat_stop_event.clear()
    _heartbeat_thread = threading.Thread(
        target=_run_mqtt_heartbeat,
        name="mqtt-esp-heartbeat",
        daemon=True,
    )
    _heartbeat_thread.start()


def stop_mqtt_heartbeat() -> None:
    """Stoppt den Hintergrund-Heartbeat."""
    _heartbeat_stop_event.set()


def _send_command(client, topic: str, message: str) -> None:
    """
    Sendet einen einfachen Textbefehl an den ESP32.
    """
    logger.info("MQTT -> Topic '%s': %s", topic, message)
    _remember_mqtt_message("Dashboard -> ESP32", topic, message)
    result = client.publish(topic, message, qos=1)
    result.wait_for_publish()

    if not result.is_published():
        raise RuntimeError(f"MQTT-Nachricht konnte nicht gesendet werden: {message}")


def _run_gate_sequence(traffic_light_topic: str, barrier_topic: str, flow_name: str) -> None:
    """
    Fuehrt den kompletten Ampel- und Schrankenablauf fuer Einfahrt oder Ausfahrt aus.
    """
    if not _sequence_lock.acquire(blocking=False):
        logger.warning("MQTT-Ablauf laeuft bereits, neuer Start fuer %s wird uebersprungen", flow_name)
        return

    client = _create_mqtt_client(subscribe_responses=False)

    try:
        # 1. Ampel war vorher rot. Jetzt auf gelb schalten.
        _send_command(client, traffic_light_topic, NACHRICHT_AMPEL_GELB)
        time.sleep(ZEIT_GELB_BIS_GRUEN_SEKUNDEN)

        # 2. Nach kurzer Zeit auf gruen schalten.
        _send_command(client, traffic_light_topic, NACHRICHT_AMPEL_GRUEN)

        # 3. Schranke oeffnen.
        _send_command(client, barrier_topic, NACHRICHT_SCHRANKE_AUF)

        # 4. Auto faehrt durch. Schranke bleibt fuer diese Zeit offen.
        time.sleep(ZEIT_SCHRANKE_OFFEN_SEKUNDEN)

        # 5. Kurz bevor die Schranke schliesst, Ampel auf gelb schalten.
        _send_command(client, traffic_light_topic, NACHRICHT_AMPEL_GELB)
        time.sleep(ZEIT_GELB_VOR_SCHLIESSEN_SEKUNDEN)

        # 6. Schranke schliessen.
        _send_command(client, barrier_topic, NACHRICHT_SCHRANKE_ZU)
        time.sleep(ZEIT_ROT_NACH_SCHLIESSEN_SEKUNDEN)

        # 7. Sobald die Schranke zugeht/zu ist, Ampel wieder auf rot schalten.
        _send_command(client, traffic_light_topic, NACHRICHT_AMPEL_ROT)
        time.sleep(0.3)

        logger.info("Parkhaus-%s-Ablauf erfolgreich abgeschlossen", flow_name)

    finally:
        client.loop_stop()
        client.disconnect()
        _sequence_lock.release()


def run_parking_sequence() -> None:
    """
    Fuehrt den kompletten Ablauf fuer die Einfahrt aus.
    """
    _run_gate_sequence(
        MQTT_TOPIC_AMPEL_EINFAHRT,
        MQTT_TOPIC_SCHRANKE_EINFAHRT,
        "Einfahrt",
    )


def run_exit_sequence() -> None:
    """
    Fuehrt den kompletten Ablauf fuer die Ausfahrt aus.
    """
    _run_gate_sequence(
        MQTT_TOPIC_AMPEL_AUSFAHRT,
        MQTT_TOPIC_SCHRANKE_AUSFAHRT,
        "Ausfahrt",
    )


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


def start_exit_sequence_async() -> threading.Thread:
    """Startet den Ausfahrts-Ablauf im Hintergrund."""
    thread = threading.Thread(
        target=run_exit_sequence,
        name="mqtt-exit-sequence",
        daemon=True,
    )
    thread.start()
    return thread


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("Starte Test-Ablauf fuer Ampel und Schranke per MQTT...")
    print(f"Broker: {MQTT_BROKER_HOST}:{MQTT_BROKER_PORT}")
    print(f"Topics: {MQTT_TOPIC_AMPEL_EINFAHRT}, {MQTT_TOPIC_SCHRANKE_EINFAHRT}")

    run_parking_sequence()
