// Auto-dismiss messages after 5s
document.addEventListener('DOMContentLoaded', function() {
  setTimeout(function() {
    document.querySelectorAll('.msg').forEach(function(el) {
      el.style.transition = 'opacity 1s';
      el.style.opacity = '0';
      setTimeout(function() { el.remove(); }, 1000);
    });
  }, 5000);
});

// Confirm delete
function confirmDelete(msg) {
  return confirm(msg || 'Confirmar exclusão?');
}

// Buscar máquina por tombo
function buscarMaquina() {
  var tombo = document.getElementById('tombo').value.trim();
  if (!tombo) return;
  var info = document.getElementById('maquina-info');
  fetch('/api/maquina_por_tombo?tombo=' + encodeURIComponent(tombo))
    .then(function(r) { return r.json(); })
    .then(function(d) {
      if (d.erro) {
        if (info) info.textContent = '⚠ Máquina não encontrada para este tombo.';
        if (info) info.style.color = 'red';
      } else {
        if (info) {
          info.textContent = '✔ ' + d.marca + ' ' + d.modelo + ' — Setor: ' + d.setor;
          info.style.color = 'green';
        }
        var sid = document.getElementById('maquina_id');
        if (sid) sid.value = d.id;
      }
    })
    .catch(function() {
      if (info) info.textContent = 'Erro ao buscar máquina.';
    });
}
