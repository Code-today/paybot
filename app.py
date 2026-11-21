import os, re, uuid, threading, time, json
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
app = Flask(__name__)

MOCK = os.getenv("MOCK_MODE", "true").lower() == "true"
CALLBACK_URL = os.getenv("CALLBACK_URL", "")

# Edit names, prices and emojis here
MENU = {
    "Chocolate Cake": {"price": 800, "emoji": "🍫"},
    "Vanilla Cake": {"price": 700, "emoji": "🍰"},
    "Red Velvet Cake": {"price": 1000, "emoji": "❤️"},
    "Cupcake": {"price": 1, "emoji": "🧁"},
}
orders = {}  # reference -> order details


def clean_phone(p):
    p = re.sub(r"[\s\-+]", "", p or "")
    if re.fullmatch(r"254[71]\d{8}", p):
        p = "0" + p[3:]
    return p if re.fullmatch(r"0[71]\d{8}", p) else None


def send_payment(ref, amount, phone):
    if MOCK:
        def fake_pay():
            time.sleep(5)
            orders[ref]["status"] = "SUCCESS"
        threading.Thread(target=fake_pay).start()
        return True
    r = requests.post(
        "https://backend.payhero.co.ke/api/v2/payments",
        auth=(os.getenv("PAYHERO_USERNAME"), os.getenv("PAYHERO_PASSWORD")),
        json={
            "amount": amount,
            "phone_number": phone,
            "channel_id": int(os.getenv("CHANNEL_ID")),
            "provider": "m-pesa",
            "external_reference": ref,
            "customer_name": "Customer",
            "callback_url": CALLBACK_URL,
        },
    )
    print("PayHero replied:", r.status_code, r.text)
    return r.status_code in (200, 201)


@app.route("/order", methods=["POST"])
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


@app.route("/callback", methods=["POST"])
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


@app.route("/status/<ref>")
def status(ref):
    return jsonify(orders.get(ref, {"status": "UNKNOWN"}))


PAGE = """
<!doctype html><html><head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Cake Shop</title>
<style>
*{box-sizing:border-box}
body{margin:0;font-family:system-ui,sans-serif;background:#fff6f0;color:#3b2a24;padding-bottom:230px}
header{background:linear-gradient(135deg,#ff7e8b,#ffb36b);color:#fff;padding:26px 20px;text-align:center;border-radius:0 0 28px 28px}
header h1{margin:0;font-size:26px}
header p{margin:6px 0 0;opacity:.95}
.list{padding:18px 16px;max-width:520px;margin:auto}
.card{display:flex;align-items:center;gap:12px;background:#fff;border-radius:18px;padding:14px;margin-bottom:12px;box-shadow:0 3px 12px rgba(120,60,30,.08)}
.em{font-size:34px;width:54px;height:54px;border-radius:14px;background:#ffe9dc;display:flex;align-items:center;justify-content:center}
.info{flex:1}
.info b{display:block;font-size:16px}
.info span{color:#c2612f;font-weight:600}
.qty{display:flex;align-items:center;gap:10px}
.qty button{width:36px;height:36px;border:none;border-radius:50%;background:#ff7e8b;color:#fff;font-size:20px}
.qty button.minus{background:#f1d9d0;color:#8a5a48}
.qty .n{min-width:18px;text-align:center;font-weight:700}
.bar{position:fixed;left:0;right:0;bottom:0;background:#fff;padding:14px 16px 18px;border-radius:24px 24px 0 0;box-shadow:0 -6px 20px rgba(0,0,0,.12)}
.inner{max-width:520px;margin:auto}
.total{display:flex;justify-content:space-between;font-size:18px;font-weight:700;margin-bottom:10px}
input{width:100%;padding:13px;border:2px solid #f1d9d0;border-radius:12px;font-size:16px;margin-bottom:10px}
#pay{width:100%;padding:14px;border:none;border-radius:14px;background:#1fa463;color:#fff;font-size:18px;font-weight:700}
#pay:disabled{background:#b9c9c0}
#msg{margin-top:10px;padding:10px 12px;border-radius:12px;font-size:15px;display:none}
.info-msg{background:#fff3cd;display:block!important}
.ok{background:#d9f5e5;display:block!important}
.err{background:#fde0e0;display:block!important}
</style></head><body>
<header><h1>🎂 Sweet Treats Cake Shop</h1><p>Tap to order. Pay with M-Pesa.</p></header>
<div class="list" id="list"></div>
<div class="bar"><div class="inner">
<div class="total"><span>Total</span><span id="total">0 KES</span></div>
<input id="phone" type="tel" inputmode="numeric" placeholder="M-Pesa number, e.g. 0712345678">
<button id="pay" onclick="pay()" disabled>Pay with M-Pesa</button>
<div id="msg"></div>
</div></div>
<script>
var MENU = __MENU__;
var names = Object.keys(MENU);
var cart = {};
function total(){
  var t = 0;
  names.forEach(function(n){ t += (cart[n] || 0) * MENU[n].price; });
  return t;
}
function render(){
  var html = '';
  names.forEach(function(n, i){
    var q = cart[n] || 0;
    html += '<div class="card"><div class="em">' + MENU[n].emoji + '</div>' +
      '<div class="info"><b>' + n + '</b><span>' + MENU[n].price + ' KES</span></div>' +
      '<div class="qty"><button class="minus" onclick="chg(' + i + ',-1)">-</button>' +
      '<span class="n">' + q + '</span>' +
      '<button onclick="chg(' + i + ',1)">+</button></div></div>';
  });
  document.getElementById('list').innerHTML = html;
  var t = total();
  document.getElementById('total').textContent = t + ' KES';
  document.getElementById('pay').disabled = (t === 0);
}
function chg(i, d){
  var n = names[i];
  cart[n] = Math.max(0, Math.min(50, (cart[n] || 0) + d));
  render();
}
function show(cls, text){
  var m = document.getElementById('msg');
  m.className = cls;
  m.textContent = text;
}
function pay(){
  var btn = document.getElementById('pay');
  var items = {};
  names.forEach(function(n){ if (cart[n]) items[n] = cart[n]; });
  btn.disabled = true;
  show('info-msg', 'Sending payment request...');
  fetch('/order', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({items: items, phone: document.getElementById('phone').value})})
  .then(function(r){ return r.json().then(function(d){ return {ok: r.ok, d: d}; }); })
  .then(function(res){
    if (!res.ok){ show('err', res.d.error); btn.disabled = false; return; }
    show('info-msg', 'Check your phone and enter your M-Pesa PIN to pay ' + res.d.total + ' KES.');
    poll(res.d.ref);
  })
  .catch(function(){ show('err', 'Network problem. Please try again.'); btn.disabled = false; });
}
function poll(ref){
  var tries = 0;
  var t = setInterval(function(){
    tries++;
    fetch('/status/' + ref).then(function(r){ return r.json(); }).then(function(s){
      if (s.status === 'SUCCESS'){
        clearInterval(t);
        show('ok', 'Paid ✅ Receipt ' + ref + ': ' + s.summary + ' - ' + s.total + ' KES. Thank you!');
        cart = {};
        render();
        document.getElementById('pay').disabled = true;
      } else if (s.status === 'FAILED'){
        clearInterval(t);
        show('err', 'Payment failed or was cancelled. Please try again.');
        document.getElementById('pay').disabled = (total() === 0);
      } else if (tries > 45){
        clearInterval(t);
        show('err', 'No payment received yet. Please try again.');
        document.getElementById('pay').disabled = (total() === 0);
      }
    });
  }, 2000);
}
render();
</script></body></html>
"""


@app.route("/")
def home():
    return PAGE.replace("__MENU__", json.dumps(MENU))

ADMIN_KEY = os.getenv("ADMIN_KEY", "")


def admin_ok():
    return bool(ADMIN_KEY) and request.args.get("key") == ADMIN_KEY


@app.route("/admin/data")
def admin_data():
    if not admin_ok():
        return jsonify(error="Not allowed"), 403
    rows = [dict(ref=ref, **o) for ref, o in orders.items()]
    rows.reverse()
    paid = [o for o in rows if o["status"] == "SUCCESS"]
    return jsonify(
        orders=rows,
        total_count=len(rows),
        paid_count=len(paid),
        revenue=sum(o["total"] for o in paid),
    )


ADMIN_PAGE = """
<!doctype html><html><head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Shop Dashboard</title>
<style>
*{box-sizing:border-box}
body{margin:0;font-family:system-ui,sans-serif;background:#f4f1ee;color:#2d2420;padding:16px}
h1{font-size:22px;margin:4px 0 14px}
.stats{display:flex;gap:10px;margin-bottom:16px}
.stat{flex:1;background:#fff;border-radius:16px;padding:14px;box-shadow:0 2px 10px rgba(0,0,0,.06)}
.stat span{display:block;font-size:12px;color:#8a7a72}
.stat b{font-size:22px}
.order{background:#fff;border-radius:14px;padding:12px 14px;margin-bottom:10px;box-shadow:0 2px 8px rgba(0,0,0,.05)}
.top{display:flex;justify-content:space-between;font-weight:700}
.sub{color:#8a7a72;font-size:13px;margin-top:4px}
.badge{padding:2px 10px;border-radius:20px;font-size:12px;font-weight:700}
.SUCCESS{background:#d9f5e5;color:#177a46}
.PENDING{background:#fff3cd;color:#8a6d00}
.FAILED{background:#fde0e0;color:#b02a2a}
</style></head><body>
<h1>📊 Shop Dashboard</h1>
<div class="stats">
<div class="stat"><span>Revenue (paid)</span><b id="rev">0</b></div>
<div class="stat"><span>Paid orders</span><b id="paid">0</b></div>
<div class="stat"><span>All orders</span><b id="all">0</b></div>
</div>
<div id="list"></div>
<script>
function load(){
  fetch('/admin/data' + location.search).then(function(r){ return r.json(); }).then(function(d){
    if (d.error) { document.body.textContent = 'Not allowed'; return; }
    document.getElementById('rev').textContent = d.revenue + ' KES';
    document.getElementById('paid').textContent = d.paid_count;
    document.getElementById('all').textContent = d.total_count;
    var html = '';
    d.orders.forEach(function(o){
      html += '<div class="order"><div class="top"><span>' + o.ref + '</span>' +
        '<span class="badge ' + o.status + '">' + o.status + '</span></div>' +
        '<div>' + o.summary + '</div>' +
        '<div class="sub">' + o.total + ' KES &middot; ' + o.phone + ' &middot; ' + o.time + '</div></div>';
    });
    document.getElementById('list').innerHTML = html || '<p>No orders yet.</p>';
  });
}
load();
setInterval(load, 3000);
</script></body></html>
"""


@app.route("/admin")
def admin():
    if not admin_ok():
        return "Not allowed", 403
    return ADMIN_PAGE
if __name__ == "__main__":
    app.run(port=5000)