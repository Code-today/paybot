import re, threading, time
import requests
import config
from store import orders


def clean_phone(p):
    p = re.sub(r"[\s\-+]", "", p or "")
    if re.fullmatch(r"254[71]\d{8}", p):
        p = "0" + p[3:]
    return p if re.fullmatch(r"0[71]\d{8}", p) else None


def send_payment(ref, amount, phone):
    if config.MOCK:
        def fake_pay():
            time.sleep(5)
            orders[ref]["status"] = "SUCCESS"
        threading.Thread(target=fake_pay).start()
        return True
    r = requests.post(
        "https://backend.payhero.co.ke/api/v2/payments",
        auth=(config.PAYHERO_USERNAME, config.PAYHERO_PASSWORD),
        json={
            "amount": amount,
            "phone_number": phone,
            "channel_id": int(config.CHANNEL_ID),
            "provider": "m-pesa",
            "external_reference": ref,
            "customer_name": "Customer",
            "callback_url": config.CALLBACK_URL,
        },
    )
    print("PayHero replied:", r.status_code, r.text)
    return r.status_code in (200, 201)
