"""
MQTT_Programm_ESP32.py

MicroPython-Programm fuer den ESP32.

Dieses Programm verbindet den ESP32 mit dem WLAN und dem Mosquitto-MQTT-Broker
auf dem Raspberry Pi. Danach wartet es auf Steuerbefehle vom Dashboard.

Passend zu Dashboard/mqtt_parking_control.py werden diese Nachrichten erwartet:

- "Ampel Rot"
- "Ampel Gelb"
- "Ampel Gruen"
- "Schranke Auf"
- "Schranke Zu"

Hardware:
- 3 Pins fuer die Einfahrts-Ampel
- 3 Pins fuer die Ausfahrts-Ampel
- 1 Pin fuer Servo-Signal der Einfahrts-Schranke
- 1 Pin fuer Servo-Signal der Ausfahrts-Schranke

Hinweis:
Diese Datei ist fuer MicroPython gedacht. Du kannst sie z.B. mit Thonny,
mpremote oder ampy auf den ESP32 kopieren. Wenn sie automatisch starten soll,
speichere sie auf dem ESP32 als "main.py".
"""

import machine
import network
import time

try:
    from umqtt.simple import MQTTClient
except ImportError:
    raise ImportError(
        "Das MicroPython-Modul 'umqtt.simple' fehlt. "
        "Installiere es auf dem ESP32 oder nutze eine MicroPython-Firmware mit umqtt."
    )


# =============================================================================
# WLAN-EINSTELLUNGEN - HIER ANPASSEN
# =============================================================================

WLAN_NAME = "ESP-NETZ"
WLAN_PASSWORT = ""

# Wie lange der ESP32 maximal auf die WLAN-Verbindung wartet.
WLAN_TIMEOUT_SEKUNDEN = 20

# Dauer pro LED-Schritt fuer die Verbindungs-Bestaetigung.
LED_TEST_DAUER_SEKUNDEN = 0.4


# =============================================================================
# MQTT-EINSTELLUNGEN - HIER ANPASSEN
# =============================================================================

# Wichtig:
# Hier muss die IP-Adresse des Raspberry Pi stehen, auf dem Mosquitto laeuft.
# Nicht "localhost" verwenden, weil "localhost" auf dem ESP32 der ESP32 selbst waere.
MQTT_BROKER_IP = "192.168.4.1"

MQTT_BROKER_PORT = 1883

# Diese Topics muessen exakt zum Dashboard passen.
MQTT_TOPIC_AMPEL_EINFAHRT = b"ampel/einfahrt"
MQTT_TOPIC_AMPEL_AUSFAHRT = b"ampel/ausfahrt"
MQTT_TOPIC_SCHRANKE_EINFAHRT = b"schranke/einfahrt"
MQTT_TOPIC_SCHRANKE_AUSFAHRT = b"schranke/ausfahrt"

MQTT_TOPIC_STATUS_AMPEL_EINFAHRT = b"ampel/einfahrt/status"
MQTT_TOPIC_STATUS_AMPEL_AUSFAHRT = b"ampel/ausfahrt/status"
MQTT_TOPIC_STATUS_SCHRANKE = b"schranke/status"

MQTT_TOPIC_HEARTBEAT_PING = b"esp32/heartbeat/ping"
MQTT_TOPIC_HEARTBEAT_PONG = b"esp32/heartbeat/pong"

# Frei waehlbarer Name fuer den ESP32 im MQTT-Broker.
MQTT_CLIENT_ID = b"esp32_parkhaus_schranke"

# Falls dein Mosquitto-Broker Benutzername/Passwort nutzt, hier eintragen.
# Wenn kein Login eingerichtet ist, einfach None lassen.
MQTT_USERNAME = None
MQTT_PASSWORD = None


# =============================================================================
# PINBELEGUNG - HIER KANNST DU DEINE PINS AENDERN
# =============================================================================

# LED-Pins fuer die Einfahrts-Ampel.
PIN_AMPEL_EINFAHRT_ROT = 2
PIN_AMPEL_EINFAHRT_GELB = 3
PIN_AMPEL_EINFAHRT_GRUEN = 4

# LED-Pins fuer die Ausfahrts-Ampel.
PIN_AMPEL_AUSFAHRT_ROT = 12
PIN_AMPEL_AUSFAHRT_GELB = 13
PIN_AMPEL_AUSFAHRT_GRUEN = 14

# Servo-Signalpins fuer die Schranken.
PIN_SERVO_SCHRANKE_EINFAHRT = 5
PIN_SERVO_SCHRANKE_AUSFAHRT = 15


# =============================================================================
# SERVO-EINSTELLUNGEN - HIER KANNST DU WINKEL UND PWM AENDERN
# =============================================================================

# Typische Servo-Werte:
# - 50 Hz fuer normale Modellbau-Servos
# - 0 Grad = Schranke geschlossen
# - 90 Grad = Schranke offen
SERVO_PWM_FREQUENZ = 50
SERVO_WINKEL_ZU = 0
SERVO_WINKEL_AUF = 90

# Pulsbreiten fuer viele Standard-Servos.
# Wenn dein Servo nicht weit genug faehrt oder brummt, diese Werte leicht anpassen.
SERVO_MIN_PULS_US = 500
SERVO_MAX_PULS_US = 2500


# =============================================================================
# MQTT-NACHRICHTEN - MUESSEN ZUM DASHBOARD PASSEN
# =============================================================================

NACHRICHT_AMPEL_ROT = b"Ampel Rot"
NACHRICHT_AMPEL_GELB = b"Ampel Gelb"
NACHRICHT_AMPEL_GRUEN = b"Ampel Gruen"
NACHRICHT_SCHRANKE_AUF = b"Schranke Auf"
NACHRICHT_SCHRANKE_ZU = b"Schranke Zu"
NACHRICHT_HEARTBEAT_PING = b"ping"


# =============================================================================
# HARDWARE INITIALISIEREN
# =============================================================================

ampel_einfahrt_rot = machine.Pin(PIN_AMPEL_EINFAHRT_ROT, machine.Pin.OUT)
ampel_einfahrt_gelb = machine.Pin(PIN_AMPEL_EINFAHRT_GELB, machine.Pin.OUT)
ampel_einfahrt_gruen = machine.Pin(PIN_AMPEL_EINFAHRT_GRUEN, machine.Pin.OUT)

ampel_ausfahrt_rot = machine.Pin(PIN_AMPEL_AUSFAHRT_ROT, machine.Pin.OUT)
ampel_ausfahrt_gelb = machine.Pin(PIN_AMPEL_AUSFAHRT_GELB, machine.Pin.OUT)
ampel_ausfahrt_gruen = machine.Pin(PIN_AMPEL_AUSFAHRT_GRUEN, machine.Pin.OUT)

servo_einfahrt = machine.PWM(
    machine.Pin(PIN_SERVO_SCHRANKE_EINFAHRT),
    freq=SERVO_PWM_FREQUENZ,
)
servo_ausfahrt = machine.PWM(
    machine.Pin(PIN_SERVO_SCHRANKE_AUSFAHRT),
    freq=SERVO_PWM_FREQUENZ,
)

mqtt_client = None


def zeitstempel_erstellen():
    """Erstellt einen einfachen Datums- und Uhrzeitstempel aus der ESP32-Uhr."""
    jetzt = time.localtime()
    return "%04d-%02d-%02d %02d:%02d:%02d" % (
        jetzt[0],
        jetzt[1],
        jetzt[2],
        jetzt[3],
        jetzt[4],
        jetzt[5],
    )


def status_senden(topic, bereich, zustand, befehl):
    """Sendet eine Rueckmeldung an den MQTT-Broker."""
    if mqtt_client is None:
        return

    nachricht = (
        "zeit=%s; bereich=%s; status=%s; befehl=%s"
        % (zeitstempel_erstellen(), bereich, zustand, befehl)
    )

    try:
        mqtt_client.publish(topic, nachricht)
        print("MQTT Status gesendet:", topic, nachricht)
    except Exception as fehler:
        print("MQTT Status konnte nicht gesendet werden:", fehler)


def heartbeat_antwort_senden(befehl):
    """Antwortet auf einen Heartbeat-Ping vom Dashboard."""
    if mqtt_client is None:
        return

    nachricht = "zeit=%s; status=online; befehl=%s" % (
        zeitstempel_erstellen(),
        befehl,
    )

    try:
        mqtt_client.publish(MQTT_TOPIC_HEARTBEAT_PONG, nachricht)
        print("Heartbeat Antwort gesendet:", nachricht)
    except Exception as fehler:
        print("Heartbeat Antwort konnte nicht gesendet werden:", fehler)


def servo_winkel_setzen(servo_objekt, winkel):
    """
    Stellt den Servo auf einen Winkel zwischen 0 und 180 Grad.

    Wenn die Schranke falsch herum arbeitet, kannst du entweder
    SERVO_WINKEL_ZU und SERVO_WINKEL_AUF tauschen oder hier die Rechnung
    anpassen.
    """
    if winkel < 0:
        winkel = 0
    if winkel > 180:
        winkel = 180

    puls_us = SERVO_MIN_PULS_US + (
        (SERVO_MAX_PULS_US - SERVO_MIN_PULS_US) * winkel // 180
    )

    # MicroPython auf ESP32 nutzt duty_u16 mit 0..65535.
    periode_us = 1000000 // SERVO_PWM_FREQUENZ
    duty = int(puls_us * 65535 // periode_us)
    servo_objekt.duty_u16(duty)


def ampel_aus(rot_pin, gelb_pin, gruen_pin):
    """Schaltet alle Ampel-LEDs aus."""
    rot_pin.off()
    gelb_pin.off()
    gruen_pin.off()


def ampel_rot_schalten(name, status_topic, rot_pin, gelb_pin, gruen_pin, befehl):
    """Schaltet die Ampel auf Rot."""
    ampel_aus(rot_pin, gelb_pin, gruen_pin)
    rot_pin.on()
    print("Ampel", name, "ist jetzt ROT")
    status_senden(status_topic, "ampel/" + name, "Rot", befehl)


def ampel_gelb_schalten(name, status_topic, rot_pin, gelb_pin, gruen_pin, befehl):
    """Schaltet die Ampel auf Gelb."""
    ampel_aus(rot_pin, gelb_pin, gruen_pin)
    gelb_pin.on()
    print("Ampel", name, "ist jetzt GELB")
    status_senden(status_topic, "ampel/" + name, "Gelb", befehl)


def ampel_gruen_schalten(name, status_topic, rot_pin, gelb_pin, gruen_pin, befehl):
    """Schaltet die Ampel auf Gruen."""
    ampel_aus(rot_pin, gelb_pin, gruen_pin)
    gruen_pin.on()
    print("Ampel", name, "ist jetzt GRUEN")
    status_senden(status_topic, "ampel/" + name, "Gruen", befehl)


def schranke_oeffnen(name, servo_objekt, befehl):
    """Oeffnet die Schranke."""
    servo_winkel_setzen(servo_objekt, SERVO_WINKEL_AUF)
    print("Schranke", name, "ist jetzt OFFEN")
    status_senden(MQTT_TOPIC_STATUS_SCHRANKE, "schranke/" + name, "Offen", befehl)


def schranke_schliessen(name, servo_objekt, befehl):
    """Schliesst die Schranke."""
    servo_winkel_setzen(servo_objekt, SERVO_WINKEL_ZU)
    print("Schranke", name, "ist jetzt ZU")
    status_senden(MQTT_TOPIC_STATUS_SCHRANKE, "schranke/" + name, "Zu", befehl)


def ampel_einfahrt_rot_schalten(befehl="Startzustand"):
    ampel_rot_schalten(
        "einfahrt",
        MQTT_TOPIC_STATUS_AMPEL_EINFAHRT,
        ampel_einfahrt_rot,
        ampel_einfahrt_gelb,
        ampel_einfahrt_gruen,
        befehl,
    )


def ampel_einfahrt_gelb_schalten(befehl):
    ampel_gelb_schalten(
        "einfahrt",
        MQTT_TOPIC_STATUS_AMPEL_EINFAHRT,
        ampel_einfahrt_rot,
        ampel_einfahrt_gelb,
        ampel_einfahrt_gruen,
        befehl,
    )


def ampel_einfahrt_gruen_schalten(befehl):
    ampel_gruen_schalten(
        "einfahrt",
        MQTT_TOPIC_STATUS_AMPEL_EINFAHRT,
        ampel_einfahrt_rot,
        ampel_einfahrt_gelb,
        ampel_einfahrt_gruen,
        befehl,
    )


def ampel_ausfahrt_rot_schalten(befehl="Startzustand"):
    ampel_rot_schalten(
        "ausfahrt",
        MQTT_TOPIC_STATUS_AMPEL_AUSFAHRT,
        ampel_ausfahrt_rot,
        ampel_ausfahrt_gelb,
        ampel_ausfahrt_gruen,
        befehl,
    )


def ampel_ausfahrt_gelb_schalten(befehl):
    ampel_gelb_schalten(
        "ausfahrt",
        MQTT_TOPIC_STATUS_AMPEL_AUSFAHRT,
        ampel_ausfahrt_rot,
        ampel_ausfahrt_gelb,
        ampel_ausfahrt_gruen,
        befehl,
    )


def ampel_ausfahrt_gruen_schalten(befehl):
    ampel_gruen_schalten(
        "ausfahrt",
        MQTT_TOPIC_STATUS_AMPEL_AUSFAHRT,
        ampel_ausfahrt_rot,
        ampel_ausfahrt_gelb,
        ampel_ausfahrt_gruen,
        befehl,
    )


def grundzustand_setzen():
    """
    Setzt den Startzustand:
    - beide Ampeln rot
    - beide Schranken geschlossen
    """
    ampel_einfahrt_rot_schalten()
    ampel_ausfahrt_rot_schalten()
    schranke_schliessen("einfahrt", servo_einfahrt, "Startzustand")
    schranke_schliessen("ausfahrt", servo_ausfahrt, "Startzustand")


def verbindung_erfolgreich_anzeigen():
    """
    Zeigt ohne Serial Monitor an, dass WLAN und MQTT erfolgreich verbunden sind.

    Ablauf:
    Rot -> Gelb -> Gruen -> Gelb -> Rot
    """
    ampel_einfahrt_rot_schalten("Verbindungstest")
    ampel_ausfahrt_rot_schalten("Verbindungstest")
    time.sleep(LED_TEST_DAUER_SEKUNDEN)

    ampel_einfahrt_gelb_schalten("Verbindungstest")
    ampel_ausfahrt_gelb_schalten("Verbindungstest")
    time.sleep(LED_TEST_DAUER_SEKUNDEN)

    ampel_einfahrt_gruen_schalten("Verbindungstest")
    ampel_ausfahrt_gruen_schalten("Verbindungstest")
    time.sleep(LED_TEST_DAUER_SEKUNDEN)

    ampel_einfahrt_gelb_schalten("Verbindungstest")
    ampel_ausfahrt_gelb_schalten("Verbindungstest")
    time.sleep(LED_TEST_DAUER_SEKUNDEN)

    ampel_einfahrt_rot_schalten("Verbindungstest")
    ampel_ausfahrt_rot_schalten("Verbindungstest")


# =============================================================================
# WLAN UND MQTT
# =============================================================================

def wlan_verbinden():
    """Verbindet den ESP32 mit dem WLAN."""
    wlan = network.WLAN(network.STA_IF)

    # ESP32-WLAN manchmal erst sauber zuruecksetzen, sonst kann
    # "Wifi internal state error" auftreten.
    wlan.active(False)
    time.sleep(1)
    wlan.active(True)
    time.sleep(1)

    try:
        # Verhindert auf manchen ESP32-Boards Probleme durch WLAN-Stromsparmodus.
        wlan.config(pm=0xa11140)
    except Exception:
        pass

    if not wlan.isconnected():
        print("Verbinde mit WLAN:", WLAN_NAME)

        try:
            wlan.disconnect()
        except Exception:
            pass

        time.sleep(1)

        try:
            wlan.connect(WLAN_NAME, WLAN_PASSWORT)
        except OSError as fehler:
            print("WLAN-Startfehler:", fehler)
            print("ESP32 wird in 5 Sekunden neu gestartet...")
            time.sleep(5)
            machine.reset()

        startzeit = time.time()
        while not wlan.isconnected():
            if time.time() - startzeit > WLAN_TIMEOUT_SEKUNDEN:
                print("WLAN-Timeout nach", WLAN_TIMEOUT_SEKUNDEN, "Sekunden")
                print("ESP32 wird in 5 Sekunden neu gestartet...")
                time.sleep(5)
                machine.reset()

            print("Warte auf WLAN...")
            time.sleep(1)

    print("WLAN verbunden")
    print("IP-Adresse:", wlan.ifconfig()[0])
    return wlan


def mqtt_nachricht_empfangen(topic, msg):
    """
    Wird automatisch aufgerufen, wenn eine MQTT-Nachricht empfangen wird.

    Hier werden die einfachen Textbefehle vom Raspberry Pi ausgewertet.
    """
    print("MQTT empfangen:", topic, msg)

    befehl = msg.decode() if isinstance(msg, bytes) else str(msg)

    if topic == MQTT_TOPIC_AMPEL_EINFAHRT:
        if msg == NACHRICHT_AMPEL_ROT:
            ampel_einfahrt_rot_schalten(befehl)
        elif msg == NACHRICHT_AMPEL_GELB:
            ampel_einfahrt_gelb_schalten(befehl)
        elif msg == NACHRICHT_AMPEL_GRUEN:
            ampel_einfahrt_gruen_schalten(befehl)
        else:
            print("Unbekannter Ampel-Befehl Einfahrt:", msg)

    elif topic == MQTT_TOPIC_AMPEL_AUSFAHRT:
        if msg == NACHRICHT_AMPEL_ROT:
            ampel_ausfahrt_rot_schalten(befehl)
        elif msg == NACHRICHT_AMPEL_GELB:
            ampel_ausfahrt_gelb_schalten(befehl)
        elif msg == NACHRICHT_AMPEL_GRUEN:
            ampel_ausfahrt_gruen_schalten(befehl)
        else:
            print("Unbekannter Ampel-Befehl Ausfahrt:", msg)

    elif topic == MQTT_TOPIC_SCHRANKE_EINFAHRT:
        if msg == NACHRICHT_SCHRANKE_AUF:
            schranke_oeffnen("einfahrt", servo_einfahrt, befehl)
        elif msg == NACHRICHT_SCHRANKE_ZU:
            schranke_schliessen("einfahrt", servo_einfahrt, befehl)
        else:
            print("Unbekannter Schranken-Befehl Einfahrt:", msg)

    elif topic == MQTT_TOPIC_SCHRANKE_AUSFAHRT:
        if msg == NACHRICHT_SCHRANKE_AUF:
            schranke_oeffnen("ausfahrt", servo_ausfahrt, befehl)
        elif msg == NACHRICHT_SCHRANKE_ZU:
            schranke_schliessen("ausfahrt", servo_ausfahrt, befehl)
        else:
            print("Unbekannter Schranken-Befehl Ausfahrt:", msg)

    elif topic == MQTT_TOPIC_HEARTBEAT_PING:
        heartbeat_antwort_senden(befehl)

    else:
        print("Unbekanntes MQTT-Topic:", topic)


def mqtt_verbinden():
    """Verbindet den ESP32 mit dem MQTT-Broker und abonniert das Steuer-Topic."""
    global mqtt_client

    if MQTT_USERNAME and MQTT_PASSWORD:
        client = MQTTClient(
            MQTT_CLIENT_ID,
            MQTT_BROKER_IP,
            port=MQTT_BROKER_PORT,
            user=MQTT_USERNAME,
            password=MQTT_PASSWORD,
        )
    else:
        client = MQTTClient(
            MQTT_CLIENT_ID,
            MQTT_BROKER_IP,
            port=MQTT_BROKER_PORT,
        )

    client.set_callback(mqtt_nachricht_empfangen)
    client.connect()
    client.subscribe(MQTT_TOPIC_AMPEL_EINFAHRT)
    client.subscribe(MQTT_TOPIC_AMPEL_AUSFAHRT)
    client.subscribe(MQTT_TOPIC_SCHRANKE_EINFAHRT)
    client.subscribe(MQTT_TOPIC_SCHRANKE_AUSFAHRT)
    client.subscribe(MQTT_TOPIC_HEARTBEAT_PING)
    mqtt_client = client

    print("MQTT verbunden")
    print("Broker:", MQTT_BROKER_IP)
    print("Topics:")
    print("-", MQTT_TOPIC_AMPEL_EINFAHRT)
    print("-", MQTT_TOPIC_AMPEL_AUSFAHRT)
    print("-", MQTT_TOPIC_SCHRANKE_EINFAHRT)
    print("-", MQTT_TOPIC_SCHRANKE_AUSFAHRT)
    print("-", MQTT_TOPIC_HEARTBEAT_PING)

    return client


def hauptprogramm():
    """
    Hauptschleife:
    - WLAN verbinden
    - MQTT verbinden
    - dauerhaft auf MQTT-Befehle warten
    - bei Verbindungsfehler automatisch neu verbinden
    """
    global mqtt_client

    grundzustand_setzen()
    wlan_verbinden()

    client = None

    while True:
        try:
            if client is None:
                client = mqtt_verbinden()
                verbindung_erfolgreich_anzeigen()

            # Wartet blockierend auf die naechste MQTT-Nachricht.
            client.wait_msg()

        except OSError as fehler:
            print("Verbindungsfehler:", fehler)
            print("Versuche in 5 Sekunden neu zu verbinden...")

            try:
                if client:
                    client.disconnect()
            except Exception:
                pass

            client = None
            mqtt_client = None
            time.sleep(5)


# =============================================================================
# PROGRAMMSTART
# =============================================================================

hauptprogramm()
