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
- 1 Pin fuer rote Ampel-LED
- 1 Pin fuer gelbe Ampel-LED
- 1 Pin fuer gruene Ampel-LED
- 1 Pin fuer Servo-Signal der Schranke

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

# Dieses Topic muss exakt zum Dashboard passen:
# Dashboard/mqtt_parking_control.py -> MQTT_COMMAND_TOPIC = "parkhaus/steuerung"
MQTT_COMMAND_TOPIC = b"parkhaus/steuerung"

# Frei waehlbarer Name fuer den ESP32 im MQTT-Broker.
MQTT_CLIENT_ID = b"esp32_parkhaus_schranke"

# Falls dein Mosquitto-Broker Benutzername/Passwort nutzt, hier eintragen.
# Wenn kein Login eingerichtet ist, einfach None lassen.
MQTT_USERNAME = None
MQTT_PASSWORD = None


# =============================================================================
# PINBELEGUNG - HIER KANNST DU DEINE PINS AENDERN
# =============================================================================

# LED-Pins fuer die Ampel.
PIN_AMPEL_ROT = 25
PIN_AMPEL_GELB = 26
PIN_AMPEL_GRUEN = 27

# Servo-Signalpin fuer die Schranke.
PIN_SERVO_SCHRANKE = 14


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


# =============================================================================
# HARDWARE INITIALISIEREN
# =============================================================================

ampel_rot = machine.Pin(PIN_AMPEL_ROT, machine.Pin.OUT)
ampel_gelb = machine.Pin(PIN_AMPEL_GELB, machine.Pin.OUT)
ampel_gruen = machine.Pin(PIN_AMPEL_GRUEN, machine.Pin.OUT)

servo = machine.PWM(machine.Pin(PIN_SERVO_SCHRANKE), freq=SERVO_PWM_FREQUENZ)


def servo_winkel_setzen(winkel):
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
    servo.duty_u16(duty)


def ampel_aus():
    """Schaltet alle Ampel-LEDs aus."""
    ampel_rot.off()
    ampel_gelb.off()
    ampel_gruen.off()


def ampel_rot_schalten():
    """Schaltet die Ampel auf Rot."""
    ampel_aus()
    ampel_rot.on()
    print("Ampel ist jetzt ROT")


def ampel_gelb_schalten():
    """Schaltet die Ampel auf Gelb."""
    ampel_aus()
    ampel_gelb.on()
    print("Ampel ist jetzt GELB")


def ampel_gruen_schalten():
    """Schaltet die Ampel auf Gruen."""
    ampel_aus()
    ampel_gruen.on()
    print("Ampel ist jetzt GRUEN")


def schranke_oeffnen():
    """Oeffnet die Schranke."""
    servo_winkel_setzen(SERVO_WINKEL_AUF)
    print("Schranke ist jetzt OFFEN")


def schranke_schliessen():
    """Schliesst die Schranke."""
    servo_winkel_setzen(SERVO_WINKEL_ZU)
    print("Schranke ist jetzt ZU")


def grundzustand_setzen():
    """
    Setzt den Startzustand:
    - Ampel rot
    - Schranke geschlossen
    """
    ampel_rot_schalten()
    schranke_schliessen()


def verbindung_erfolgreich_anzeigen():
    """
    Zeigt ohne Serial Monitor an, dass WLAN und MQTT erfolgreich verbunden sind.

    Ablauf:
    Rot -> Gelb -> Gruen -> Gelb -> Rot
    """
    ampel_rot_schalten()
    time.sleep(LED_TEST_DAUER_SEKUNDEN)

    ampel_gelb_schalten()
    time.sleep(LED_TEST_DAUER_SEKUNDEN)

    ampel_gruen_schalten()
    time.sleep(LED_TEST_DAUER_SEKUNDEN)

    ampel_gelb_schalten()
    time.sleep(LED_TEST_DAUER_SEKUNDEN)

    ampel_rot_schalten()


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

    if msg == NACHRICHT_AMPEL_ROT:
        ampel_rot_schalten()

    elif msg == NACHRICHT_AMPEL_GELB:
        ampel_gelb_schalten()

    elif msg == NACHRICHT_AMPEL_GRUEN:
        ampel_gruen_schalten()

    elif msg == NACHRICHT_SCHRANKE_AUF:
        schranke_oeffnen()

    elif msg == NACHRICHT_SCHRANKE_ZU:
        schranke_schliessen()

    else:
        print("Unbekannter MQTT-Befehl:", msg)


def mqtt_verbinden():
    """Verbindet den ESP32 mit dem MQTT-Broker und abonniert das Steuer-Topic."""
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
    client.subscribe(MQTT_COMMAND_TOPIC)

    print("MQTT verbunden")
    print("Broker:", MQTT_BROKER_IP)
    print("Topic:", MQTT_COMMAND_TOPIC)

    return client


def hauptprogramm():
    """
    Hauptschleife:
    - WLAN verbinden
    - MQTT verbinden
    - dauerhaft auf MQTT-Befehle warten
    - bei Verbindungsfehler automatisch neu verbinden
    """
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
            time.sleep(5)


# =============================================================================
# PROGRAMMSTART
# =============================================================================

hauptprogramm()
