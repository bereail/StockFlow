/*
 * Mejora cualquier <select> cuyo "name" contenga "servicio", "patrimonio" o
 * "item" (servicio, servicio_solicitante, patrimonio_saliente,
 * detalles-0-item, etc.) para poder escribir y filtrar las opciones en vez
 * de scrollear un desplegable largo. Funciona tanto con <select> simple
 * como <select multiple> (en ese caso, con chips removibles).
 *
 * El <select> original nunca se saca del DOM: solo se oculta. Sigue
 * siendo la fuente de verdad y se sigue enviando normalmente al hacer
 * submit del formulario, así que ninguna vista necesita cambios.
 *
 * Para contenido agregado dinámicamente (filas de formset agregadas por
 * JS después de la carga de la página), llamar a
 * window.HeepSearchableSelect.enhanceAll(elementoRaiz) una vez insertado
 * en el DOM.
 */
(function () {
  // Normaliza para comparar sin importar mayúsculas/minúsculas ni acentos
  // (ej: "clinica" debe encontrar "Clínica").
  function normalizar(s) {
    return (s || "")
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "");
  }

  function enhance(select) {
    if (select.dataset.sselDone) return;
    select.dataset.sselDone = "1";

    var isMulti = select.multiple;

    var wrap = document.createElement("div");
    wrap.className = "ssel-wrap";
    select.parentNode.insertBefore(wrap, select);

    var box = document.createElement("div");
    box.className = "ssel-box";
    wrap.appendChild(select);
    wrap.appendChild(box);
    select.classList.add("ssel-native");

    var chipsRow = null;
    if (isMulti) {
      chipsRow = document.createElement("div");
      chipsRow.className = "ssel-chips";
      box.appendChild(chipsRow);
    }

    var input = document.createElement("input");
    input.type = "text";
    input.className = "ssel-input";
    input.autocomplete = "off";
    input.setAttribute("role", "combobox");
    input.setAttribute("aria-expanded", "false");
    input.setAttribute("aria-autocomplete", "list");
    input.placeholder = isMulti ? "Agregar…" : "Buscar…";
    box.appendChild(input);

    var panel = document.createElement("div");
    panel.className = "ssel-panel";
    panel.setAttribute("role", "listbox");
    panel.hidden = true;

    // Nombre accesible del listbox: el <label> del select original si existe,
    // si no el placeholder ("Buscar…"/"Agregar…"). También se conecta el
    // combobox con su listbox vía aria-controls (requerido por el role).
    var panelId = "ssel-panel-" + Math.random().toString(36).slice(2, 9);
    panel.id = panelId;
    input.setAttribute("aria-controls", panelId);
    var labelEl = select.id && document.querySelector('label[for="' + select.id + '"]');
    panel.setAttribute("aria-label", (labelEl ? labelEl.textContent.trim() : input.placeholder));

    /* Se cuelga directo del <body> (no de wrap) para que un position:fixed
       escape de cualquier ancestro con backdrop-filter/transform (ej. .card),
       que si no atrapa al panel y hace que otros campos de la página le
       tapen el click a las opciones. */
    document.body.appendChild(panel);

    function positionPanel() {
      var rect = box.getBoundingClientRect();
      panel.style.position = "fixed";
      panel.style.left = rect.left + "px";
      panel.style.top = (rect.bottom + 4) + "px";
      panel.style.width = rect.width + "px";
    }

    var currentOptions = [];
    var activeIndex = -1;

    function realOptions() {
      return Array.prototype.slice.call(select.options);
    }

    function findExactMatch(text) {
      var t = normalizar(text).trim();
      if (!t) return null;
      var opts = realOptions();
      for (var i = 0; i < opts.length; i++) {
        if (normalizar(opts[i].text).trim() === t) return opts[i];
      }
      return null;
    }

    function renderChips() {
      if (!isMulti) return;
      chipsRow.innerHTML = "";
      Array.prototype.slice.call(select.selectedOptions).forEach(function (opt) {
        var chip = document.createElement("span");
        chip.className = "ssel-chip";
        chip.textContent = opt.text;

        var x = document.createElement("button");
        x.type = "button";
        x.className = "ssel-chip-x";
        x.setAttribute("aria-label", "Quitar " + opt.text);
        x.textContent = "✕";
        x.addEventListener("click", function (e) {
          e.stopPropagation();
          opt.selected = false;
          select.dispatchEvent(new Event("change", { bubbles: true }));
          renderChips();
        });

        chip.appendChild(x);
        chipsRow.appendChild(chip);
      });
    }

    function syncInputSingle() {
      if (isMulti) return;
      var opt = select.options[select.selectedIndex];
      input.value = opt ? opt.text : "";
    }

    function renderPanel(filterText) {
      var texto = normalizar(filterText).trim();
      panel.innerHTML = "";
      currentOptions = [];
      activeIndex = -1;

      realOptions().forEach(function (opt) {
        if (isMulti && opt.selected) return;
        if (texto && normalizar(opt.text).indexOf(texto) === -1) return;

        currentOptions.push(opt);
        var item = document.createElement("div");
        item.className = "ssel-opt";
        item.setAttribute("role", "option");
        item.textContent = opt.text || "—";
        item.addEventListener("mousedown", function (e) {
          e.preventDefault();
          choose(opt);
        });
        panel.appendChild(item);
      });

      if (!currentOptions.length) {
        var empty = document.createElement("div");
        empty.className = "ssel-empty";
        empty.textContent = "Sin resultados";
        panel.appendChild(empty);
      }
    }

    function setActive(idx) {
      var items = panel.querySelectorAll(".ssel-opt");
      for (var i = 0; i < items.length; i++) items[i].classList.remove("is-active");
      if (idx >= 0 && idx < items.length) {
        items[idx].classList.add("is-active");
        items[idx].scrollIntoView({ block: "nearest" });
      }
      activeIndex = idx;
    }

    function move(delta) {
      var count = currentOptions.length;
      if (!count) return;
      setActive((activeIndex + delta + count) % count);
    }

    function choose(opt) {
      if (isMulti) {
        opt.selected = true;
        select.dispatchEvent(new Event("change", { bubbles: true }));
        input.value = "";
        renderChips();
        renderPanel("");
        input.focus();
      } else {
        select.value = opt.value;
        select.dispatchEvent(new Event("change", { bubbles: true }));
        syncInputSingle();
        closePanel();
      }
    }

    function openPanel() {
      renderPanel("");
      if (!isMulti) input.select();
      positionPanel();
      panel.hidden = false;
      wrap.classList.add("is-open");
      input.setAttribute("aria-expanded", "true");
    }

    function closePanel() {
      panel.hidden = true;
      wrap.classList.remove("is-open");
      input.setAttribute("aria-expanded", "false");
      if (!isMulti) {
        var exacto = findExactMatch(input.value);
        if (exacto && exacto.value !== select.value) {
          select.value = exacto.value;
          select.dispatchEvent(new Event("change", { bubbles: true }));
        }
        syncInputSingle();
      }
    }

    input.addEventListener("focus", openPanel);
    input.addEventListener("blur", closePanel);
    input.addEventListener("input", function () {
      renderPanel(input.value);
      positionPanel();
      panel.hidden = false;
      wrap.classList.add("is-open");
    });
    input.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        if (panel.hidden) openPanel(); else move(1);
      }
      else if (e.key === "ArrowUp") {
        e.preventDefault();
        if (panel.hidden) openPanel(); else move(-1);
      }
      else if (e.key === "Enter") {
        e.preventDefault();
        var opt = findExactMatch(input.value) || currentOptions[activeIndex] || currentOptions[0];
        if (opt) choose(opt);
      } else if (e.key === "Escape") {
        closePanel();
        input.blur();
      }
    });

    document.addEventListener("click", function (e) {
      if (!wrap.contains(e.target) && !panel.contains(e.target)) closePanel();
    });

    window.addEventListener("resize", function () {
      if (!panel.hidden) positionPanel();
    });
    window.addEventListener("scroll", function () {
      if (!panel.hidden) positionPanel();
    }, true);

    renderChips();
    syncInputSingle();
  }

  function enhanceAll(root) {
    (root || document).querySelectorAll("select").forEach(function (sel) {
      if (/servicio|patrimonio|item/i.test(sel.name || "")) enhance(sel);
    });
  }

  window.HeepSearchableSelect = { enhanceAll: enhanceAll };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { enhanceAll(document); });
  } else {
    enhanceAll(document);
  }
})();
