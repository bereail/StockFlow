/*
 * Helpers únicos para "agregar fila a un formset dinámico" — unifica las 4
 * implementaciones independientes detectadas en la auditoría de
 * 2026-10-23 (DUP-01). Hay 2 estrategias reales en el repo, no 1 — forzar
 * las 4 a una sola hubiera significado reescribir el markup de
 * movimientos/notas (el campo "id" de ModelForm vive fuera de la fila en
 * notas/form.html, no adentro como en pedidos) para un patrón que hoy no
 * tiene ningún bug activo. Cada estrategia quedó con un único helper:
 *
 * - agregarFilaClonando: clona la primera fila ya renderizada y reindexa
 *   sus inputs. La usan pedidos/form.html y pedidos/detail.html.
 * - agregarFilaDesdeTemplate: arma la fila desde el empty_form del
 *   formset (HTML guardado en data-attrs, con "__prefix__" a reemplazar
 *   por el índice) sobre un <template> con placeholders. La usan
 *   movimientos/movimiento_form.html y notas/form.html — clonar su
 *   primera fila no alcanzaba: en notas/form.html el campo oculto "id"
 *   de ModelForm se renderiza FUERA del <tr> (no adentro, como en
 *   pedidos), y en movimientos el campo variable (tóner/artículo) no
 *   tiene un nombre de placeholder fijo entre los dos formsets.
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

  /*
   * opts: {
   *   tbodyId, totalFormsId, emptyDataDivId, templateId,
   *   placeholders: { "__PLACEHOLDER__": "datasetKey", ... },
   *   onRowAdded: function(fila) {},  // opcional
   * }
   * "datasetKey" es la clave en emptyDiv.dataset (ej. "toner" para
   * data-toner) cuyo HTML reemplaza a "__PLACEHOLDER__" en el <template>,
   * con "__prefix__" ya cambiado por el índice de la fila nueva.
   */
  function agregarFilaDesdeTemplate(opts) {
    var tbody = document.getElementById(opts.tbodyId);
    var totalForms = document.getElementById(opts.totalFormsId);
    var emptyDiv = document.getElementById(opts.emptyDataDivId);
    var tpl = document.getElementById(opts.templateId);
    if (!tbody || !totalForms || !emptyDiv || !tpl) return null;

    var index = parseInt(totalForms.value, 10);
    var rowHtml = tpl.innerHTML;
    Object.keys(opts.placeholders).forEach(function (placeholder) {
      var datasetKey = opts.placeholders[placeholder];
      var html = (emptyDiv.dataset[datasetKey] || "").replaceAll("__prefix__", index);
      rowHtml = rowHtml.split(placeholder).join(html);
    });

    tbody.insertAdjacentHTML("beforeend", rowHtml);
    var fila = tbody.lastElementChild;
    totalForms.value = index + 1;
    if (opts.onRowAdded) opts.onRowAdded(fila);
    return fila;
  }

  return {
    agregarFilaClonando: agregarFilaClonando,
    agregarFilaDesdeTemplate: agregarFilaDesdeTemplate,
  };
})();
