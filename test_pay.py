import os
import requests
from dotenv import load_dotenv

load_dotenv()

response = requests.post(
    "https://backend.payhero.co.ke/api/v2/payments",
    auth=(os.getenv("PAYHERO_USERNAME"), os.getenv("PAYHERO_PASSWORD")),
    json={
        "amount": 1,
        "phone_number": "2540727640575",
        "channel_id": int(os.getenv("CHANNEL_ID")),
        "provider": "m-pesa",
        "external_reference": "test-002",
        "customer_name": "Test",
    },
)

print(response.status_code)
print(response.json())