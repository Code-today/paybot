import os
from dotenv import load_dotenv

load_dotenv()

MOCK = os.getenv("MOCK_MODE", "true").lower() == "true"
CALLBACK_URL = os.getenv("CALLBACK_URL", "")
ADMIN_KEY = os.getenv("ADMIN_KEY", "")
PAYHERO_USERNAME = os.getenv("PAYHERO_USERNAME")
PAYHERO_PASSWORD = os.getenv("PAYHERO_PASSWORD")
CHANNEL_ID = os.getenv("CHANNEL_ID")
