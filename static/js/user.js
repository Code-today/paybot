var names = Object.keys(MENU);
var cart = {};
var $ = function(id){ return document.getElementById(id); };

function total(){
  var t = 0;
  names.forEach(function(n){ t += (cart[n] || 0) * MENU[n].price; });
  return t;
}
function render(){
  var html = '';
  names.forEach(function(n, i){
    var q = cart[n] || 0;
    html += '<div class="card' + (q ? ' active' : '') + '">' +
      '<div class="em">' + MENU[n].emoji + '</div>' +
      '<div class="body"><div class="name">' + n + '</div>' +
      '<span class="price">' + MENU[n].price + ' KES</span>' +
      '<div class="qty"><button class="minus" onclick="chg(' + i + ',-1)">-</button>' +
      '<span class="n">' + q + '</span>' +
      '<button onclick="chg(' + i + ',1)">+</button></div></div></div>';
  });
  $('list').innerHTML = html;
  var t = total();
  $('total').textContent = t + ' KES';
  $('pay').disabled = (t === 0);
}
function chg(i, d){
  var n = names[i];
  cart[n] = Math.max(0, Math.min(50, (cart[n] || 0) + d));
  render();
}
function show(cls, text){
  var m = $('msg');
  m.className = cls;
  m.textContent = text;
}
function pay(){
  var btn = $('pay');
  var items = {};
  names.forEach(function(n){ if (cart[n]) items[n] = cart[n]; });
  btn.disabled = true;
  show('info-msg', 'Sending payment request...');
  fetch('/order', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({items: items, phone: $('phone').value})})
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
        $('pay').disabled = true;
      } else if (s.status === 'FAILED'){
        clearInterval(t);
        show('err', 'Payment failed or was cancelled. Please try again.');
        $('pay').disabled = (total() === 0);
      } else if (tries > 45){
        clearInterval(t);
        show('err', 'No payment received yet. Please try again.');
        $('pay').disabled = (total() === 0);
      }
    });
  }, 2000);
}
$('pay').addEventListener('click', pay);
render();
