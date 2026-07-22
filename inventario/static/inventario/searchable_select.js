/*
 * Mejora cualquier <select> cuyo "name" contenga "servicio" (servicio,
 * servicio_solicitante, servicio_asignado, servicios, filtros de listado,
 * etc.) para poder escribir y filtrar las opciones en vez de scrollear
 * un desplegable largo. Funciona tanto con <select> simple como
 * <select multiple> (en ese caso, con chips removibles).
 *
 * El <select> original nunca se saca del DOM: solo se oculta. Sigue
 * siendo la fuente de verdad y se sigue enviando normalmente al hacer
 * submit del formulario, así que ninguna vista necesita cambios.
 */
(function () {
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
    wrap.appendChild(panel);

    var currentOptions = [];
    var activeIndex = -1;

    function realOptions() {
      return Array.prototype.slice.call(select.options);
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
      var texto = (filterText || "").toLowerCase().trim();
      panel.innerHTML = "";
      currentOptions = [];
      activeIndex = -1;

      realOptions().forEach(function (opt) {
        if (isMulti && opt.selected) return;
        if (texto && opt.text.toLowerCase().indexOf(texto) === -1) return;

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
      panel.hidden = false;
      wrap.classList.add("is-open");
      input.setAttribute("aria-expanded", "true");
    }

    function closePanel() {
      panel.hidden = true;
      wrap.classList.remove("is-open");
      input.setAttribute("aria-expanded", "false");
      if (!isMulti) syncInputSingle();
    }

    input.addEventListener("focus", openPanel);
    input.addEventListener("input", function () {
      renderPanel(input.value);
      panel.hidden = false;
      wrap.classList.add("is-open");
    });
    input.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown") { e.preventDefault(); openPanel(); move(1); }
      else if (e.key === "ArrowUp") { e.preventDefault(); openPanel(); move(-1); }
      else if (e.key === "Enter") {
        e.preventDefault();
        var opt = currentOptions[activeIndex] || currentOptions[0];
        if (opt) choose(opt);
      } else if (e.key === "Escape") {
        closePanel();
        input.blur();
      }
    });

    document.addEventListener("click", function (e) {
      if (!wrap.contains(e.target)) closePanel();
    });

    renderChips();
    syncInputSingle();
  }

  function init() {
    document.querySelectorAll("select").forEach(function (sel) {
      if (/servicio/i.test(sel.name || "")) enhance(sel);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
