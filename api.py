import uuid
from datetime import datetime
from flask import Blueprint, request, jsonify
from mockdata.menu import MENU
from store import orders
from payments import clean_phone, send_payment

bp = Blueprint("api", __name__)


@bp.route("/order", methods=["POST"])
def order():
    data = request.get_json(silent=True) or {}
    phone = clean_phone(data.get("phone"))
    if not phone:
        return jsonify(error="Enter a valid M-Pesa number, e.g. 0712345678"), 400
    items = []
    for name, qty in (data.get("items") or {}).items():
        if name in MENU and isinstance(qty, int) and 0 < qty <= 50:
            items.append({"name": name, "qty": qty, "price": MENU[name]["price"]})
    if not items:
        return jsonify(error="Please add at least one item."), 400
    total = sum(i["qty"] * i["price"] for i in items)
    summary = ", ".join(f"{i['qty']} x {i['name']}" for i in items)
    ref = "ORD-" + uuid.uuid4().hex[:6].upper()
    orders[ref] = {
        "status": "PENDING", "summary": summary, "total": total,
        "phone": phone[:4] + "***" + phone[-3:],
        "time": datetime.now().strftime("%H:%M:%S"),
    }
    if not send_payment(ref, total, phone):
        return jsonify(error="Couldn't start the payment. Please try again."), 500
    return jsonify(ref=ref, total=total, summary=summary, phone=phone)


@bp.route("/callback", methods=["POST"])
def callback():
    data = request.get_json(silent=True) or {}
    print("Callback received:", data)
    info = data.get("response", data)
    ref = info.get("ExternalReference") or info.get("external_reference")
    status = str(info.get("Status") or info.get("status") or "").upper()
    if ref in orders:
        if status in ("SUCCESS", "SUCCESSFUL", "COMPLETED"):
            orders[ref]["status"] = "SUCCESS"
        elif status not in ("", "QUEUED", "PENDING"):
            orders[ref]["status"] = "FAILED"
    return jsonify(ok=True)


@bp.route("/status/<ref>")
def status(ref):
    return jsonify(orders.get(ref, {"status": "UNKNOWN"}))
