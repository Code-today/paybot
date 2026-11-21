import os
from dotenv import load_dotenv

load_dotenv()

for name in ["PAYHERO_USERNAME", "PAYHERO_PASSWORD", "CHANNEL_ID"]:
    value = os.getenv(name)
    print(name, "->", "MISSING" if value is None else f"found, {len(value)} characters")