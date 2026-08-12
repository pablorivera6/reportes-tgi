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
    var dl = $("tramos-list");
    dl.innerHTML = TRAMOS.map(function (t) {
      return "<option value=\"" + t.replace(/"/g, "&quot;") + "\">";
    }).join("");
    // tipo (segmentado)
    var seg = $("seg-tipo");
    seg.innerHTML = TIPOS.map(function (t) {
      return "<button type=\"button\" data-t=\"" + t + "\">" + t + "</button>";
    }).join("");
    Array.prototype.forEach.call(seg.querySelectorAll("button"), function (b) {
      b.onclick = function () { setTipo(b.getAttribute("data-t")); };
    });
    // fecha por defecto hoy
    $("fecha").value = new Date().toISOString().slice(0, 10);
    // listeners de validación
    ["tramo", "tecnico", "fecha"].forEach(function (id) {
      $(id).addEventListener("input", validar);
    });
    $("enviar").onclick = enviar;
    $("done-btn").onclick = function () { location.reload(); };
    setTipo(tipoSel);
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
  function validar() {
    var faltaMeta = !($("tramo").value.trim() && $("tecnico").value.trim() && $("fecha").value);
    var falta = faltantes();
    var ok = !faltaMeta && !falta.length;
    $("enviar").disabled = !ok;
    var h = $("hint");
    if (faltaMeta) { h.className = "hint"; h.textContent = "Completa tramo y tu nombre."; }
    else if (falta.length) {
      h.className = "hint err";
      h.textContent = "Faltan archivos obligatorios: " +
        falta.map(function (c) { return c.etiqueta; }).join(", ");
    } else { h.className = "hint"; h.textContent = "Listo para enviar."; }
  }

  // ── Envío ───────────────────────────────────────────────────────────────────
  function enviar() {
    var tramo = $("tramo").value.trim();
    var fecha = $("fecha").value;                 // YYYY-MM-DD
    var tecnico = $("tecnico").value.trim();
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
