/*
 * Helper único para "agregar fila a un formset dinámico clonando la
 * primera fila" — unifica las implementaciones gemelas de
 * pedidos/form.html (addDetallePedido) y pedidos/detail.html (addDetalle)
 * (DUP-01 de la auditoría de 2026-10-23).
 *
 * Las otras 2 implementaciones existentes en el repo (movimientos/notas)
 * usan una estrategia distinta — template con placeholders + data-attrs
 * del empty_form, con hasta 2 formsets por tipo de ítem — y quedan fuera
 * de esta unificación: migrarlas significaría reescribir su markup, no
 * solo extraer una función, para un patrón que hoy no tiene ningún bug
 * activo (ver sección 5/7 del informe).
 */
window.HeepFormsetRows = (function () {
  function agregarFilaClonando(tbodySelector, filaSelector, totalFormsId) {
    var tbody = document.querySelector(tbodySelector);
    var total = document.getElementById(totalFormsId);
    if (!tbody || !total) return null;

    var idx = parseInt(total.value, 10);
    var primera = tbody.querySelector(filaSelector);
    if (!primera) return null;
    var nueva = primera.cloneNode(true);

    // Si el <select> de ítem ya está mejorado con buscador (ssel-wrap), el
    // clon trae ese wrapper sin sus listeners (cloneNode no los copia): se
    // desarma a un <select> limpio para volver a mejorarlo en la fila nueva.
    var wrapClon = nueva.querySelector('.ssel-wrap');
    if (wrapClon) {
      var selClon = wrapClon.querySelector('select');
      selClon.classList.remove('ssel-native');
      delete selClon.dataset.sselDone;
      wrapClon.parentNode.replaceChild(selClon, wrapClon);
    }

    nueva.querySelectorAll('input, select, textarea').forEach(function (el) {
      el.name = el.name.replace(/-\d+-/, '-' + idx + '-');
      el.id   = el.id.replace(/-\d+-/, '-' + idx + '-');
      if (el.type === 'checkbox') {
        el.checked = false;
      } else {
        el.value = '';
      }
    });
    nueva.querySelectorAll('label[for]').forEach(function (lbl) {
      lbl.setAttribute('for', lbl.getAttribute('for').replace(/-\d+-/, '-' + idx + '-'));
    });

    tbody.appendChild(nueva);
    total.value = idx + 1;
    window.HeepSearchableSelect && window.HeepSearchableSelect.enhanceAll(nueva);
    return nueva;
  }

  return { agregarFilaClonando: agregarFilaClonando };
})();
