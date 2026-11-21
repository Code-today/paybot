// var names = Object.keys(MENU);
// var cart = {};
// var $ = function(id){ return document.getElementById(id); };

// function total(){
//   var t = 0;
//   names.forEach(function(n){ t += (cart[n] || 0) * MENU[n].price; });
//   return t;
// }
// function render(){
//   var html = '';
//   names.forEach(function(n, i){
//     var q = cart[n] || 0;
//     html += '<div class="card' + (q ? ' active' : '') + '">' +
//       '<div class="em">' + MENU[n].emoji + '</div>' +
//       '<div class="body"><div class="name">' + n + '</div>' +
//       '<span class="price">' + MENU[n].price + ' KES</span>' +
//       '<div class="qty"><button class="minus" onclick="chg(' + i + ',-1)">-</button>' +
//       '<span class="n">' + q + '</span>' +
//       '<button onclick="chg(' + i + ',1)">+</button></div></div></div>';
//   });
//   $('list').innerHTML = html;
//   var t = total();
//   $('total').textContent = t + ' KES';
//   $('pay').disabled = (t === 0);
// }
// function chg(i, d){
//   var n = names[i];
//   cart[n] = Math.max(0, Math.min(50, (cart[n] || 0) + d));
//   render();
// }
// function show(cls, text){
//   var m = $('msg');
//   m.className = cls;
//   m.textContent = text;
// }
// function pay(){
//   var btn = $('pay');
//   var items = {};
//   names.forEach(function(n){ if (cart[n]) items[n] = cart[n]; });
//   btn.disabled = true;
//   show('info-msg', 'Sending payment request...');
//   fetch('/order', {method:'POST', headers:{'Content-Type':'application/json'},
//     body: JSON.stringify({items: items, phone: $('phone').value})})
//   .then(function(r){ return r.json().then(function(d){ return {ok: r.ok, d: d}; }); })
//   .then(function(res){
//     if (!res.ok){ show('err', res.d.error); btn.disabled = false; return; }
//     show('info-msg', 'Check your phone and enter your M-Pesa PIN to pay ' + res.d.total + ' KES.');
//     poll(res.d.ref);
//   })
//   .catch(function(){ show('err', 'Network problem. Please try again.'); btn.disabled = false; });
// }
// function poll(ref){
//   var tries = 0;
//   var t = setInterval(function(){
//     tries++;
//     fetch('/status/' + ref).then(function(r){ return r.json(); }).then(function(s){
//       if (s.status === 'SUCCESS'){
//         clearInterval(t);
//         show('ok', 'Paid ✅ Receipt ' + ref + ': ' + s.summary + ' - ' + s.total + ' KES. Thank you!');
//         cart = {};
//         render();
//         $('pay').disabled = true;
//       } else if (s.status === 'FAILED'){
//         clearInterval(t);
//         show('err', 'Payment failed or was cancelled. Please try again.');
//         $('pay').disabled = (total() === 0);
//       } else if (tries > 45){
//         clearInterval(t);
//         show('err', 'No payment received yet. Please try again.');
//         $('pay').disabled = (total() === 0);
//       }
//     });
//   }, 2000);
// }
// $('pay').addEventListener('click', pay);
// render();



const cart = Object.create(null);
const list = document.getElementById('list');
const payBtn = document.getElementById('pay');
const phoneInput = document.getElementById('phone');
const msg = document.getElementById('msg');

const fmt = n => n.toLocaleString('en-KE');
const esc = s => String(s).replace(/"/g, '&quot;');

function cardHTML(name, item) {
  const tags = (item.tags || []).map(t => `<li class="_tag -trim-both">${t}</li>`).join('');
  return `<section class="_card" data-name="${esc(name)}" style="--product-card--accent:${item.accent || '#8b5e3c'}">
    <h2 class="_heading -fluid-text -trim-both" style="--fluid-text--min-font-size:18;--fluid-text--max-font-size:24;">${name}</h2>
    <div class="_thumbnail-stack">
      <div class="_thumb">${item.emoji}</div>
      <div class="_thumb">${item.emoji}</div>
    </div>
    <p class="_category -trim-both">${item.category || 'Cake'}</p>
    <p class="_price -trim-both">${fmt(item.price)} KES</p>
    <p class="_description -line-clamp">${item.desc || 'Freshly baked every morning.'}</p>
    <ul class="_tag-list cluster" style="--cluster--gap:.5rem;">${tags}</ul>
    <div class="_button" style="--purchase-button--background:var(--_accent);--purchase-button--foreground:var(--_contrast);">
      <button type="button" class="scope purchase-button" data-add="${esc(name)}">Add To Cart</button>
    </div>
  </section>`;
}

list.innerHTML = Object.entries(MENU).map(([n, i]) => cardHTML(n, i)).join('');

function setQty(name, q) {
  const item = MENU[name]; if (!item) return;
  q = Math.max(0, Math.min(99, q));
  if (q === 0) delete cart[name]; else cart[name] = q;
  syncCard(name); updateBar();
}

function syncCard(name) {
  const card = list.querySelector(`[data-name="${CSS.escape(name)}"]`); if (!card) return;
  const btn = card.querySelector('.purchase-button');
  const q = cart[name] || 0;
  card.classList.toggle('in-cart', q > 0);
  btn.classList.toggle('is-stepper', q > 0);
  btn.innerHTML = q > 0
    ? `<button class="step" data-minus="${esc(name)}" aria-label="Remove one">−</button>
       <span class="n">${q}</span>
       <button class="step" data-plus="${esc(name)}" aria-label="Add one">+</button>`
    : 'Add To Cart';
}

list.addEventListener('click', e => {
  const add = e.target.closest('[data-add]');
  const plus = e.target.closest('[data-plus]');
  const minus = e.target.closest('[data-minus]');
  if (add) setQty(add.dataset.add, (cart[add.dataset.add] || 0) + 1);
  if (plus) setQty(plus.dataset.plus, (cart[plus.dataset.plus] || 0) + 1);
  if (minus) setQty(minus.dataset.minus, (cart[minus.dataset.minus] || 0) - 1);
});

function totals() {
  let total = 0, count = 0;
  for (const [name, q] of Object.entries(cart)) { total += MENU[name].price * q; count += q; }
  return { total, count };
}

const phoneOK = () => /^(?:\+?254|0)(1|7)\d{8}$/.test(phoneInput.value.replace(/\s/g, ''));

function updateBar() {
  const { total, count } = totals();
  document.getElementById('total').textContent = `${fmt(total)} KES`;
  document.getElementById('item-count').textContent = `${count} item${count !== 1 ? 's' : ''}`;
  payBtn.disabled = total === 0 || !phoneOK();
}
phoneInput.addEventListener('input', () => { updateBar(); msg.className = ''; });
updateBar();

payBtn.addEventListener('click', async () => {
  const items = Object.entries(cart).map(([name, qty]) => ({ name, qty, price: MENU[name].price }));
  payBtn.classList.add('loading'); msg.className = 'info-msg'; msg.textContent = 'Sending STK Push…';
  try {
    const res = await fetch('/pay', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phone: phoneInput.value, items, total: totals().total })
    });
    const data = await res.json();
    if (data.ok) {
      msg.className = 'ok'; msg.textContent = '✅ Check your phone and enter your M-Pesa PIN!';
      Object.keys(cart).forEach(syncCard);
    } else {
      msg.className = 'err'; msg.textContent = '❌ ' + (data.error || 'Payment failed.');
    }
  } catch {
    msg.className = 'err'; msg.textContent = '❌ Network error. Try again.';
  } finally {
    payBtn.classList.remove('loading');
  }
});