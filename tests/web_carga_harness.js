/* Arnés para probar la validación de `web_carga/app.js` sin navegador.
   Monta un DOM mínimo (lo justo que toca app.js), carga el data.js REAL —para
   que el catálogo sea el de verdad, PAP incluido, que ya no tiene ninguna
   casilla obligatoria— y corre escenarios. Imprime un JSON que lee
   tests/test_web_carga_validacion.py. */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const WEB = path.join(__dirname, '..', 'web_carga');

// ── DOM mínimo ──────────────────────────────────────────────────────────────
function Elemento(id) {
  this.id = id;
  this.value = '';
  this.textContent = '';
  this.className = '';
  this.disabled = false;
  this.style = {};
  this.files = [];
  this._hijos = [];
  this._attrs = {};
  this._listeners = {};
  this._innerHTML = '';
}
Elemento.prototype.addEventListener = function (ev, fn) {
  (this._listeners[ev] = this._listeners[ev] || []).push(fn);
};
Elemento.prototype.disparar = function (ev) {
  (this._listeners[ev] || []).forEach((fn) => fn.call(this));
  if (ev === 'click' && typeof this.onclick === 'function') this.onclick();
};
Elemento.prototype.getAttribute = function (k) { return this._attrs[k]; };
Elemento.prototype.querySelectorAll = function (sel) {
  if (sel === 'button') return this._hijos.filter((h) => h.tag === 'button');
  if (sel.indexOf('input[type=file]') >= 0) {
    return this._hijos.filter((h) => h.tag === 'input');
  }
  return [];
};

const doc = { _els: {} };
function crear(id) {
  if (!doc._els[id]) doc._els[id] = new Elemento(id);
  return doc._els[id];
}
doc.getElementById = (id) => crear(id);

// innerHTML: se "parsea" con regex lo único que app.js genera y luego consulta,
// los botones de tipo (data-t) y los inputs de archivo (data-clave).
Object.defineProperty(Elemento.prototype, 'innerHTML', {
  get() { return this._innerHTML; },
  set(html) {
    this._innerHTML = html;
    this._hijos = [];
    let m;
    const btn = /<button[^>]*data-t="([^"]+)"[^>]*>/g;
    while ((m = btn.exec(html))) {
      const b = new Elemento('btn-' + m[1]);
      b.tag = 'button';
      b._attrs['data-t'] = m[1];
      this._hijos.push(b);
    }
    const inp = /<input type="file"[^>]*data-clave="([^"]+)"/g;
    while ((m = inp.exec(html))) {
      const i = new Elemento('file-' + m[1]);
      i.tag = 'input';
      i._attrs['data-clave'] = m[1];
      this._hijos.push(i);
    }
  },
});

// ── Contexto global ─────────────────────────────────────────────────────────
const ctx = {
  document: doc,
  console,
  Date,
  Object,
  Array,
  String,
  isNaN,
  parseInt,
  Intl,
  setTimeout,
};
ctx.window = ctx;
ctx.PCC_CONFIG = { SUPABASE_URL: 'http://stub', SUPABASE_ANON_KEY: 'stub',
                   ACCESS_CODE: '' };
ctx.supabase = { createClient: () => ({ storage: { from: () => ({}) },
                                        from: () => ({}) }) };
vm.createContext(ctx);

vm.runInContext(fs.readFileSync(path.join(WEB, 'data.js'), 'utf8'), ctx);
vm.runInContext(fs.readFileSync(path.join(WEB, 'app.js'), 'utf8'), ctx);

// ── Utilidades del escenario ────────────────────────────────────────────────
const el = (id) => doc.getElementById(id);
function set(id, v) { el(id).value = v; el(id).disparar('input'); }
function tipo(t) {
  el('seg-tipo').querySelectorAll('button')
    .filter((b) => b.getAttribute('data-t') === t)
    .forEach((b) => b.disparar('click'));
}
function adjuntar(clave, nombre) {
  const inp = el('slots').querySelectorAll('input[type=file]')
    .filter((i) => i.getAttribute('data-clave') === clave)[0];
  if (!inp) throw new Error('no existe la casilla ' + clave);
  inp.files = [{ name: nombre, size: 10, type: '' }];
  inp.disparar('change');
}
const estado = () => ({ disabled: el('enviar').disabled,
                        hint: el('hint').textContent });

const r = {};
r.catalogo = {};
Object.keys(ctx.CATALOGO).forEach((t) => {
  r.catalogo[t] = ctx.CATALOGO[t].filter((c) => c.req).map((c) => c.clave);
});

// meta completa (tramo, técnico, fecha, PK) para aislar la regla de archivos
set('tramo', 'Ramal Salento ');
set('tecnico', 'Juan Perez');
set('fecha', '2026-09-18');
set('pk-inicial', '125+000');
set('pk-final', '129+450');

tipo('PAP');
r.pap_sin_archivos = estado();
adjuntar('equipos', 'Listado equipos.xlsx');
r.pap_con_equipos = estado();

tipo('PAP');                       // reinicia los archivos del tipo
adjuntar('foto_postes', 'poste_1.jpg');
r.pap_con_foto = estado();

tipo('CIPS');
r.cips_sin_archivos = estado();
adjuntar('huellas_osc', 'huella.xlsx');
r.cips_solo_opcional = estado();
adjuntar('cips', 'CIPS.xlsx');
r.cips_completo = estado();

tipo('DCVG');
r.dcvg_sin_archivos = estado();

tipo('PAP');
adjuntar('equipos', 'Listado equipos.xlsx');
set('pk-final', '');
r.pap_con_archivo_sin_pk = estado();

console.log(JSON.stringify(r, null, 2));
