/* Carga de campo TGI — web estática → Supabase (Storage + tabla `cargas`).
   Replica EXACTO lo que hace db.guardar_carga en Python para que la app de
   procesamiento lea las cargas igual. */
(function () {
  "use strict";
  var CFG = window.PCC_CONFIG || {};
  var TRAMOS = window.TRAMOS || [];
  var CATALOGO = window.CATALOGO || {};
  var TITULO_GRUPO = {
    proc: "📊 Datos para procesar el informe",
    crudo: "🗄️ Crudos para el dossier (huellas, GPS, logger)",
    rf: "📷 Registro fotográfico (mín. 5 fotos por elemento)"
  };
  var GRUPOS = ["proc", "crudo", "rf"];   // igual que intake_app.py
  var TIPOS = Object.keys(CATALOGO);       // CIPS, PAP, DCVG

  var sb = window.supabase.createClient(CFG.SUPABASE_URL, CFG.SUPABASE_ANON_KEY);

  // Estado
  var tipoSel = TIPOS[0] || "CIPS";
  var files = {};   // { clave: [File, ...] }
  var tramoSel = null;   // tramo elegido, tal cual viene en TRAMOS (o null)

  // ── Helpers ────────────────────────────────────────────────────────────────
  // slug idéntico a db._slug (Python)
  function slug(txt) {
    var s = String(txt == null ? "" : txt).trim()
      .replace(/[^0-9A-Za-z._-]+/g, "_").replace(/^_+|_+$/g, "");
    return s || "x";
  }
  function accept(tipos) {
    // tipos: ['xlsx','xls'] o ['jpg','jpeg','png','heic']
    var esImg = tipos.indexOf("jpg") >= 0 || tipos.indexOf("png") >= 0;
    var exts = tipos.map(function (t) { return "." + t; }).join(",");
    return esImg ? ("image/*," + exts) : exts;
  }
  function $(id) { return document.getElementById(id); }
  function esc(txt) {
    return String(txt).replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
  // Normaliza para comparar y filtrar: sin tildes, sin mayúsculas y con los
  // espacios colapsados (varios tramos traen dobles espacios o un salto final).
  function normTramo(txt) {
    return String(txt == null ? "" : txt).normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase().replace(/\s+/g, " ").trim();
  }
  // Un tramo solo vale si EXISTE en TRAMOS; devuelve el valor de la lista.
  function buscarTramo(txt) {
    var n = normTramo(txt);
    if (!n) return null;
    for (var i = 0; i < TRAMOS.length; i++) {
      if (normTramo(TRAMOS[i]) === n) return TRAMOS[i];
    }
    return null;
  }

  // PK escrito en campo → metros enteros. El técnico escribe '125+000' o
  // '129450' (y a veces 'K 125+000'); se quedan solo los dígitos.
  // Devuelve null si no hay ningún dígito (campo vacío o basura).
  function pkMetros(txt) {
    var d = String(txt == null ? "" : txt).replace(/[^0-9]/g, "");
    if (!d) return null;
    var n = parseInt(d, 10);
    return isNaN(n) ? null : n;
  }
  window.pkMetros = pkMetros;   // expuesto para pruebas

  // Lo que SE VE en el campo: el técnico escribe solo dígitos (en iPhone el
  // teclado numérico no trae el '+') y el campo los muestra como 'K+mmm'.
  // 125000 → '125+000' · 850 → '0+850' · vacío → vacío.
  function pkFormato(txt) {
    var m = pkMetros(txt);
    if (m === null) return "";
    var resto = String(m % 1000);
    while (resto.length < 3) resto = "0" + resto;
    return Math.floor(m / 1000) + "+" + resto;
  }
  window.pkFormato = pkFormato;   // expuesto para pruebas

  // ── Puerta de acceso opcional ──────────────────────────────────────────────
  function iniciar() {
    var code = (CFG.ACCESS_CODE || "").trim();
    if (code) {
      $("gate").style.display = "";
      $("gate-btn").onclick = function () {
        if ($("gate-code").value.trim() === code) {
          $("gate").style.display = "none";
          mostrarForm();
        } else { $("gate-err").style.display = ""; }
      };
    } else {
      mostrarForm();
    }
  }

  function mostrarForm() {
    $("form").style.display = "";
    $("barra").style.display = "";
    // tramos
    montarSelectorTramo();
    // tipo (segmentado)
    var seg = $("seg-tipo");
    seg.innerHTML = TIPOS.map(function (t) {
      return "<button type=\"button\" data-t=\"" + t + "\">" + t + "</button>";
    }).join("");
    Array.prototype.forEach.call(seg.querySelectorAll("button"), function (b) {
      b.onclick = function () { setTipo(b.getAttribute("data-t")); };
    });
    // fecha por defecto hoy — en hora LOCAL del celular, no UTC.
    // Con toISOString() a secas, en Colombia (UTC-5) toda carga hecha después
    // de las 7 p.m. quedaba fechada al día siguiente.
    var ahora = new Date();
    $("fecha").value = new Date(ahora.getTime() - ahora.getTimezoneOffset() * 60000)
      .toISOString().slice(0, 10);
    // el PK se muestra formateado a medida que escribe
    ["pk-inicial", "pk-final"].forEach(function (id) {
      $(id).addEventListener("input", function () {
        var f = pkFormato($(id).value);
        if ($(id).value !== f) $(id).value = f;
      });
    });
    // listeners de validación
    ["tramo", "tecnico", "fecha", "pk-inicial", "pk-final"].forEach(function (id) {
      $(id).addEventListener("input", validar);
    });
    $("tecnico").addEventListener("change", validar);
    $("enviar").onclick = enviar;
    $("done-btn").onclick = function () { location.reload(); };
    setTipo(tipoSel);
  }

  // ── Selector de tramo (autocompletado propio) ───────────────────────────────
  // El <datalist> nativo no despliega de forma fiable en celular (sobre todo en
  // iOS): el técnico tocaba el campo y no veía nada. Este panel se dibuja a mano.
  function montarSelectorTramo() {
    var inp = $("tramo"), panel = $("tramo-lista");

    function pintar() {
      var n = normTramo(inp.value);
      // Con el tramo ya elegido se muestran todos, para poder cambiarlo.
      var yaElegido = tramoSel && normTramo(tramoSel) === n;
      var idx = [];
      for (var i = 0; i < TRAMOS.length; i++) {
        if (!n || yaElegido || normTramo(TRAMOS[i]).indexOf(n) >= 0) idx.push(i);
      }
      panel.innerHTML = idx.length
        ? idx.map(function (i) {
            return '<div class="op' + (TRAMOS[i] === tramoSel ? " sel" : "") +
              '" role="option" data-i="' + i + '">' +
              esc(String(TRAMOS[i]).trim()) + "</div>";
          }).join("")
        : '<div class="vacio">Ningún tramo coincide con esa búsqueda.</div>';
      Array.prototype.forEach.call(panel.querySelectorAll(".op"), function (op) {
        // 'mousedown' (no 'click'): así se elige antes de que el campo pierda
        // el foco, que era lo que hacía fallar el toque en celular.
        op.addEventListener("mousedown", function (ev) {
          if (ev && ev.preventDefault) ev.preventDefault();
          elegir(TRAMOS[parseInt(op.getAttribute("data-i"), 10)]);
        });
      });
    }
    function abrir() {
      pintar();
      panel.hidden = false;
      inp.setAttribute("aria-expanded", "true");
    }
    function cerrar() {
      panel.hidden = true;
      inp.setAttribute("aria-expanded", "false");
    }
    function elegir(t) {
      tramoSel = t;
      inp.value = String(t).trim();
      cerrar();
      validar();
    }

    inp.addEventListener("focus", abrir);
    inp.addEventListener("click", abrir);
    inp.addEventListener("input", function () {
      tramoSel = buscarTramo(inp.value);   // texto libre ⇒ null ⇒ no válido
      abrir();
    });
    inp.addEventListener("keydown", function (ev) {
      if (ev && ev.key === "Escape") cerrar();
    });
    document.addEventListener("mousedown", function (ev) {
      if (panel.hidden) return;
      var n = ev && ev.target;
      while (n) { if (n === panel || n === inp) return; n = n.parentNode; }
      cerrar();
    });
  }

  // ── Render de casillas según tipo ───────────────────────────────────────────
  function setTipo(t) {
    tipoSel = t;
    files = {};
    Array.prototype.forEach.call($("seg-tipo").querySelectorAll("button"), function (b) {
      b.className = b.getAttribute("data-t") === t ? "on" : "";
    });
    $("arch-tit").textContent = "Archivos para inspección " + t;
    var casillas = CATALOGO[t] || [];
    var html = "";
    GRUPOS.forEach(function (g) {
      var delg = casillas.filter(function (c) { return c.grupo === g; });
      if (!delg.length) return;
      html += "<div class=\"grupo-tit\">" + TITULO_GRUPO[g] + "</div>";
      delg.forEach(function (c) {
        var req = c.req ? " <span class=\"req\">*</span>" : "";
        html += "" +
          "<div class=\"slot\">" +
          "<span class=\"lbl\">" + c.etiqueta + req + "</span>" +
          "<label class=\"drop\" id=\"drop-" + c.clave + "\">" +
          "<span class=\"ico\">📎</span>" +
          "<span class=\"txt\" id=\"txt-" + c.clave + "\">Toca para elegir archivo(s)</span>" +
          "<input type=\"file\" multiple accept=\"" + accept(c.tipos) + "\" " +
          "data-clave=\"" + c.clave + "\">" +
          "</label></div>";
      });
    });
    $("slots").innerHTML = html;
    Array.prototype.forEach.call($("slots").querySelectorAll("input[type=file]"), function (inp) {
      inp.addEventListener("change", function () {
        var clave = inp.getAttribute("data-clave");
        var arr = Array.prototype.slice.call(inp.files);
        files[clave] = arr;
        var drop = $("drop-" + clave), txt = $("txt-" + clave);
        if (arr.length) {
          drop.className = "drop has";
          txt.textContent = arr.length + " archivo(s): " +
            arr.map(function (f) { return f.name; }).join(", ");
        } else {
          drop.className = "drop";
          txt.textContent = "Toca para elegir archivo(s)";
        }
        validar();
      });
    });
    validar();
  }

  // ── Validación ──────────────────────────────────────────────────────────────
  function faltantes() {
    var casillas = CATALOGO[tipoSel] || [];
    return casillas.filter(function (c) {
      return c.req && !(files[c.clave] && files[c.clave].length);
    });
  }
  function adjuntos() {
    return Object.keys(files).reduce(function (n, k) {
      return n + ((files[k] || []).length);
    }, 0);
  }
  function validar() {
    // pk_final puede ser MENOR que pk_inicial: hay inspecciones en sentido
    // descendente. Solo se exige que ambos estén escritos.
    var faltaMeta = !(tramoSel && $("tecnico").value.trim() &&
      $("fecha").value &&
      pkMetros($("pk-inicial").value) !== null &&
      pkMetros($("pk-final").value) !== null);
    var falta = faltantes();
    // PAP ya no tiene ninguna casilla `req` (sus formularios se llenan en
    // FastField), así que sin este conteo el botón quedaba habilitado con cero
    // archivos y el envío moría en el alert de "No hay archivos para enviar".
    var n = adjuntos();
    var ok = !faltaMeta && !falta.length && n > 0;
    $("enviar").disabled = !ok;
    var h = $("hint");
    if (!tramoSel && $("tramo").value.trim()) {
      h.className = "hint err";
      h.textContent = "Selecciona un tramo válido de la lista.";
    }
    else if (faltaMeta) {
      h.className = "hint";
      h.textContent = "Completa tramo, fecha, nombre y PK inicial/final.";
    }
    else if (falta.length) {
      h.className = "hint err";
      h.textContent = "Faltan archivos obligatorios: " +
        falta.map(function (c) { return c.etiqueta; }).join(", ");
    } else if (!n) {
      h.className = "hint";
      h.textContent = "Adjunta al menos un archivo de evidencia.";
    } else { h.className = "hint"; h.textContent = "Listo para enviar."; }
  }

  // ── Envío ───────────────────────────────────────────────────────────────────
  function enviar() {
    var tramo = String(tramoSel || $("tramo").value).trim();
    var fecha = $("fecha").value;                 // YYYY-MM-DD
    var tecnico = $("tecnico").value.trim();
    var pkInicial = pkMetros($("pk-inicial").value);
    var pkFinal = pkMetros($("pk-final").value);
    var nota = $("nota").value.trim();
    var base = slug(tramo) + "/" + (fecha || "sin_fecha") + "/" + slug(tipoSel);

    // arma la lista de subidas (categoria = clave, igual que intake_app.py).
    // Ruta con prefijo único por archivo: evita colisiones de nombre y no
    // necesita permiso de UPDATE en el bucket (RLS = solo insertar).
    var subidas = [];
    var n = 0;
    Object.keys(files).forEach(function (clave) {
      (files[clave] || []).forEach(function (f) {
        var stamp = Date.now().toString(36) + (n++).toString(36);
        subidas.push({ categoria: clave, file: f,
          path: base + "/" + slug(clave) + "/" + stamp + "_" + slug(f.name) });
      });
    });
    if (!subidas.length) { alert("No hay archivos para enviar."); return; }

    $("enviar").disabled = true;
    var prog = $("prog"); prog.style.display = ""; $("hint").textContent = "";

    var indice = [];
    var i = 0;
    function siguiente() {
      if (i >= subidas.length) return registrar();
      var u = subidas[i];
      prog.textContent = "Subiendo " + (i + 1) + " de " + subidas.length + "…";
      sb.storage.from("cargas").upload(u.path, u.file, {
        contentType: u.file.type || "application/octet-stream", upsert: false
      }).then(function (res) {
        if (res.error) throw res.error;
        indice.push({ categoria: u.categoria, nombre: u.file.name,
          path: u.path, size: u.file.size });
        i++; siguiente();
      }).catch(function (e) { fallo(e); });
    }
    function registrar() {
      prog.textContent = "Registrando la carga…";
      sb.from("cargas").insert({
        tramo: tramo, tipo: tipoSel, fecha: fecha, tecnico: tecnico,
        pk_inicial: pkInicial, pk_final: pkFinal,
        estado: "pendiente", archivos: indice, nota: nota || null,
        sharepoint_ok: false
      }).then(function (res) {
        if (res.error) throw res.error;
        exito(tramo, indice.length);
      }).catch(function (e) { fallo(e); });
    }
    siguiente();
  }

  function exito(tramo, n) {
    $("form").style.display = "none";
    $("barra").style.display = "none";
    $("done").style.display = "";
    $("done-msg").textContent = n + " archivo(s) de " + tramo +
      " (" + tipoSel + ") quedaron organizados para la oficina.";
    window.scrollTo(0, 0);
  }
  function fallo(e) {
    $("prog").style.display = "none";
    $("enviar").disabled = false;
    var h = $("hint"); h.className = "hint err";
    h.textContent = "No se pudo enviar: " + (e && e.message ? e.message : e) +
      ". Revisa la señal e intenta de nuevo.";
  }

  iniciar();
})();
