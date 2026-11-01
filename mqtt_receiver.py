
import os
import json
import math
import uuid

import paho.mqtt.client as mqtt
from supabase import create_client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

MQTT_BROKER = os.getenv("MQTT_BROKER", "broker.hivemq.com")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv(
    "MQTT_TOPIC",
    "smartwater/demo/asmi001/sensors"
)

DEVICE_ID = "ESP32-001"

# Check credentials
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Supabase credentials missing!")

# Initialize database
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

print("Supabase initialized successfully!")


# Validate incoming readings
def validate_data(data):

    fields = ["ph", "tds", "turbidity", "temperature"]

    for field in fields:

        if field not in data:
            raise ValueError(f"Missing field: {field}")

        value = float(data[field])

        if not math.isfinite(value):
            raise ValueError(f"Invalid value: {field}")

        data[field] = value

    if not 0 <= data["ph"] <= 14:
        raise ValueError("Invalid pH value")

    if data["tds"] < 0:
        raise ValueError("Invalid TDS value")

    if data["turbidity"] < 0:
        raise ValueError("Invalid turbidity value")

    if not -20 <= data["temperature"] <= 80:
        raise ValueError("Invalid temperature")

    return data


# MQTT connection callback
def on_connect(client, userdata, flags, reason_code, properties):

    if reason_code.is_failure:
        print("MQTT connection failed:", reason_code)
        return

    print("Connected to HiveMQ successfully!")

    client.subscribe(MQTT_TOPIC)

    print("Subscribed to topic:", MQTT_TOPIC)


# Receive MQTT messages
def on_message(client, userdata, message):

    try:

        # Decode incoming JSON
        payload = message.payload.decode("utf-8")
        data = json.loads(payload)

        # Validate sensor readings
        data = validate_data(data)

        print("\nNew Sensor Data Received")
        print("------------------------")

        print("pH:", data["ph"])
        print("TDS:", data["tds"], "ppm")
        print("Turbidity:", data["turbidity"], "NTU")
        print("Temperature:", data["temperature"], "C")

        # Prepare database record
        record = {
            "device_id": DEVICE_ID,
            "ph": data["ph"],
            "tds": data["tds"],
            "turbidity": data["turbidity"],
            "temperature": data["temperature"]
        }

        # Insert into Supabase
        response = (
            supabase
            .table("sensor_readings")
            .insert(record)
            .execute()
        )

        print("Supabase: Reading saved successfully!")

    except Exception as error:

        print("Error:", error)


# Create MQTT client
client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2,
    client_id="water-python-" + uuid.uuid4().hex[:8]
)

client.on_connect = on_connect
client.on_message = on_message

print("\nConnecting to MQTT broker...")

try:

    client.connect(MQTT_BROKER, MQTT_PORT, 60)

    print("Waiting for Wokwi sensor readings...")

    client.loop_forever()

except KeyboardInterrupt:

    print("\nStopping receiver...")
    client.disconnect()

except Exception as error:

    print("MQTT error:", error)
