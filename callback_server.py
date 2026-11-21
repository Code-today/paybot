from flask import Flask, request, jsonify

app = Flask(__name__)
payments = {}  # remembers each payment: reference -> status


@app.route("/callback", methods=["POST"])
def callback():
    data = request.get_json(silent=True) or {}
    print("Callback received:", data)

    info = data.get("response", data)
    ref = info.get("ExternalReference") or info.get("external_reference")
    status = str(info.get("Status") or info.get("status") or "").upper()

    if ref:
        payments[ref] = status
    return jsonify({"ok": True})


@app.route("/status/<ref>")
def status(ref):
    return jsonify({"reference": ref, "status": payments.get(ref, "PENDING")})


if __name__ == "__main__":
    app.run(port=5000)