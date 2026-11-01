
import os
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client

# Load environment variables
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(env_path, override=True)

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

print("\nConnecting to Supabase...")

try:
    # Initialize Supabase
    supabase = create_client(url, key)

    print("Supabase client initialized!")

    # Test actual database access
    response = (
        supabase
        .table("sensor_readings")
        .select("*")
        .limit(5)
        .execute()
    )

    print("\nSUCCESS!")
    print("Database connection established.")
    print("Table sensor_readings is accessible.")

    print("\nExisting records:")
    print(response.data)

except Exception as e:
    print("\nCONNECTION FAILED!")
    print("Error:", e)
