var filter = 'ALL', last = null;
var $ = function(id){ return document.getElementById(id); };
function esc(s){ var d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

function draw(){
  if (!last) return;
  var rows = last.orders.filter(function(o){ return filter === 'ALL' || o.status === filter; });
  $('list').innerHTML = rows.map(function(o){
    return '<div class="order ' + o.status + '"><div class="row"><span>' + esc(o.ref) + '</span>' +
      '<span class="badge ' + o.status + '">' + o.status + '</span></div>' +
      '<div class="items">' + esc(o.summary) + '</div>' +
      '<div class="sub"><b>' + o.total + ' KES</b> &middot; ' + esc(o.phone) + ' &middot; ' + esc(o.time) + '</div></div>';
  }).join('') || '<div class="empty">No orders here yet.</div>';
}
function load(){
  fetch('/admin/data' + location.search).then(function(r){ return r.json(); }).then(function(d){
    if (d.error){ document.body.textContent = 'Not allowed'; return; }
    last = d;
    $('rev').textContent = d.revenue + ' KES';
    $('paid').textContent = d.paid_count;
    $('all').textContent = d.total_count;
    $('pend').textContent = d.orders.filter(function(o){ return o.status === 'PENDING'; }).length;
    draw();
  });
}
$('filters').addEventListener('click', function(e){
  if (!e.target.dataset.f) return;
  filter = e.target.dataset.f;
  [].forEach.call(this.children, function(b){ b.classList.toggle('on', b.dataset.f === filter); });
  draw();
});
load();
setInterval(load, 3000);
