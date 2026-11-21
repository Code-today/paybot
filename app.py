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
# Voice synonyms mapped to canonical menu item names (lowercase keys)
VOICE_SYNONYMS = {
    "chocolate cake": "Chocolate Cake",
    "chocolate": "Chocolate Cake",
    "vanilla cake": "Vanilla Cake",
    "vanilla": "Vanilla Cake",
    "red velvet cake": "Red Velvet Cake",
    "red velvet": "Red Velvet Cake",
    "cupcake": "Cupcake",
    "cup cakes": "Cupcake",
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


@app.route("/menu")
def menu():
    return jsonify(menu=MENU, synonyms=VOICE_SYNONYMS)


@app.route("/voice", methods=["POST"])
def voice():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip().lower()
    if not text:
        return jsonify(error="No spoken text received."), 400
    items = _parse_voice_order(text)
    if not items:
        return jsonify(error="I couldn't find any cakes in what you said. Try saying something like 'two chocolate cakes and one vanilla cupcake'."), 400
    total = sum(i["qty"] * i["price"] for i in items)
    summary = ", ".join(f"{i['qty']} x {i['name']}" for i in items)
    return jsonify(items=items, total=total, summary=summary)


def _parse_voice_order(text):
    words = re.findall(r"\w+", text)
    if not words:
        return []
    # Build candidate phrases (tuple of words) -> canonical menu name.
    # Sorted longest-first so multi-word names win over single-word ones.
    phrases = []
    for canon in MENU:
        phrases.append((tuple(canon.lower().split()), canon))
    for syn, canon in VOICE_SYNONYMS.items():
        phrases.append((tuple(syn.lower().split()), canon))
    phrases.sort(key=lambda p: -len(p[0]))

    fillers = ("and", "a", "an", "the", "please", "i", "want", "get", "order",
               "for", "me", "can", "have", "some", "of")
    num_words = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        "a": 1, "an": 1,
    }

    items = {}
    i = 0
    while i < len(words):
        w = words[i]
        if w in fillers:
            i += 1
            continue
        qty = 1
        # Consume a leading quantity word or digit.
        if w in num_words:
            qty = num_words[w]
            i += 1
            if i >= len(words):
                break
            w = words[i]
        elif w.isdigit():
            qty = int(w)
            i += 1
            if i >= len(words):
                break
            w = words[i]
        # Greedily match the longest item phrase starting at position i.
        matched = False
        for pwords, canon in phrases:
            L = len(pwords)
            if i + L <= len(words) and tuple(words[i:i + L]) == pwords:
                items[canon] = items.get(canon, 0) + qty
                i += L
                matched = True
                break
        if not matched:
            i += 1
    # Cap quantities at 50 to match the order endpoint.
    result = []
    for name, qty in items.items():
        qty = max(1, min(50, qty))
        if name in MENU:
            result.append({"name": name, "qty": qty, "price": MENU[name]["price"]})
    return result


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
#mic{width:44px;height:44px;border:none;border-radius:50%;background:#ffb36b;color:#fff;font-size:22px;cursor:pointer;box-shadow:0 2px 8px rgba(255,179,107,.35)}
#mic.listening{background:#ff4d4d;animation:pulse 1.5s infinite}
#mic:disabled{background:#ccc;color:#999;cursor:not-allowed}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.55}}
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
<button id="mic" onclick="toggleMic()" title="Order by voice" aria-label="Voice ordering">🎤</button>
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

var recognition = null;
var speaking = false;
var synth = window.speechSynthesis || null;
var voiceSession = false; // continuous session mode

function speak(text){
  if (!synth || speaking) return;
  speaking = true;
  var u = new SpeechSynthesisUtterance(text);
  u.lang = 'en-US';
  u.rate = 1.05;
  u.onend = function(){ speaking = false; };
  u.onerror = function(){ speaking = false; };
  synth.speak(u);
}

function toggleMic(){
  var btn = document.getElementById('mic');
  if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)){
    show('err', 'Voice not supported in this browser.');
    return;
  }
  // Stop if already in session
  if (voiceSession){
    stopVoiceSession();
    return;
  }

  var Rec = window.SpeechRecognition || window.webkitSpeechRecognition;
  recognition = new Rec();
  recognition.lang = 'en-US';
  recognition.interimResults = true; // get partial results
  recognition.continuous = true;     // keep listening
  recognition.maxAlternatives = 1;

  voiceSession = true;
  btn.classList.add('listening');
  speak('Voice session started. Say items to add or remove, phone number, confirm payment, or exit.');

  recognition.onresult = function(event){
    // Only process final results
    for (var i = event.resultIndex; i < event.results.length; i++){
      if (event.results[i].isFinal){
        var text = event.results[i][0].transcript.toLowerCase().trim();
        document.getElementById('msg').textContent = 'Heard: "' + text + '"';
        processVoiceCommand(text);
      }
    }
  };

  recognition.onerror = function(e){
    if (e.error === 'no-speech' || e.error === 'audio-capture'){
      // Silently ignore these common errors in continuous mode
      return;
    }
    show('err', 'Voice error: ' + e.error);
  };

  recognition.onend = function(){
    if (voiceSession){
      // Auto-restart if session still active (handles browser timeouts)
      setTimeout(function(){
        if (voiceSession && recognition){
          try { recognition.start(); } catch(e){}
        }
      }, 300);
    } else {
      btn.classList.remove('listening');
    }
  };

  try { recognition.start(); } catch(e){
    voiceSession = false;
    btn.classList.remove('listening');
    show('err', 'Could not start microphone.');
  }
}

function stopVoiceSession(){
  voiceSession = false;
  var btn = document.getElementById('mic');
  btn.classList.remove('listening');
  if (recognition){
    try { recognition.stop(); } catch(e){}
    recognition = null;
  }
  speak('Voice session ended.');
  show('info-msg', 'Voice session ended. Tap mic to start again.');
}

function processVoiceCommand(text){
  // Exit commands
  if (/\b(exit|cancel|stop|quit|close)\b/.test(text)){
    stopVoiceSession();
    return;
  }

  // Confirm payment
  if (/\b(confirm|pay|checkout|place order|submit)\b/.test(text) && /\b(payment|payments|order|pay)\b/.test(text)){
    var phoneVal = document.getElementById('phone').value.trim();
    var hasItems = Object.keys(cart).some(function(k){ return cart[k] > 0; });
    if (!hasItems){
      speak('No items in cart. Add something first.');
      show('err', 'No items in cart.');
      return;
    }
    if (!phoneVal){
      speak('Please say your phone number first.');
      show('err', 'Phone number required.');
      return;
    }
    stopVoiceSession();
    // Trigger the pay button
    document.getElementById('pay').click();
    return;
  }

  // Phone number detection (9+ digits)
  var digits = text.match(/\\d/g);
  if (digits && digits.length >= 9){
    var num = digits.join('');
    if (num.startsWith('254')) num = '0' + num.substring(3);
    else if (num.startsWith('2540')) num = '0' + num.substring(4);
    else if (num.startsWith('7') || num.startsWith('1')) num = '0' + num;
    if (/^0[71]\\d{8}$/.test(num)){
      document.getElementById('phone').value = num;
      speak('Phone number set to ' + num + '.');
      show('info-msg', 'Phone set to ' + num);
      return;
    }
  }

  // Remove item commands: "remove 1 cupcake", "remove two chocolate cakes", "delete vanilla cake"
  var removeMatch = text.match(/\\b(remove|delete|take away|subtract)\\b\\s+(.+)/);
  if (removeMatch){
    var removeText = removeMatch[2];
    // Reuse the voice parser but invert quantities
    fetch('/voice', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({text: removeText})})
    .then(function(r){ return r.json(); })
    .then(function(d){
      if (!d.error && d.items && d.items.length > 0){
        d.items.forEach(function(it){
          var current = cart[it.name] || 0;
          var newQty = Math.max(0, current - it.qty);
          if (newQty === 0){
            delete cart[it.name];
          } else {
            cart[it.name] = newQty;
          }
        });
        render();
        var namesRemoved = d.items.map(function(it){ return it.qty + ' ' + it.name; }).join(', ');
        speak('Removed ' + namesRemoved + '.');
        show('info-msg', 'Removed ' + namesRemoved);
      } else {
        speak('Could not understand what to remove.');
        show('err', 'Could not understand what to remove.');
      }
    })
    .catch(function(){ speak('Remove failed.'); });
    return;
  }

  // Add item commands - use existing /voice endpoint
  fetch('/voice', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({text: text})})
  .then(function(r){ return r.json(); })
  .then(function(d){
    if (!d.error && d.items && d.items.length > 0){
      d.items.forEach(function(it){ cart[it.name] = Math.min(50, (cart[it.name] || 0) + it.qty); });
      render();
      speak('Added ' + d.summary + '. Total ' + d.total + ' KES.');
      show('info-msg', 'Added ' + d.summary + ' — ' + d.total + ' KES');
    } else {
      // Not an order, maybe just conversational - ignore silently
      // Or could be "what's my total" etc.
      if (/\b(total|how much|cost|price)\b/.test(text)){
        var t = 0;
        Object.keys(cart).forEach(function(n){ t += (cart[n] || 0) * MENU[n].price; });
        if (t > 0){
          speak('Your total is ' + t + ' KES.');
          show('info-msg', 'Total: ' + t + ' KES');
        } else {
          speak('Cart is empty.');
        }
      } else if (/\b(what|show|list)\b.*\b(cart|order|items)\b/.test(text)){
        var items = Object.keys(cart).filter(function(k){ return cart[k] > 0; });
        if (items.length > 0){
          var summary = items.map(function(n){ return cart[n] + ' ' + n; }).join(', ');
          speak('You have ' + summary + '.');
          show('info-msg', 'Cart: ' + summary);
        } else {
          speak('Cart is empty.');
        }
      } else if (/\b(clear|empty)\b.*\b(cart|order)\b/.test(text)){
        cart = {};
        render();
        speak('Cart cleared.');
        show('info-msg', 'Cart cleared.');
      }
      // Otherwise ignore unrecognized chatter
    }
  })
  .catch(function(){ /* ignore network errors in continuous mode */ });
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