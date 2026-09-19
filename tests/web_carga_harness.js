/* Arnés para probar la validación de `web_carga/app.js` sin navegador.
   Monta un DOM mínimo (lo justo que toca app.js), carga el data.js REAL —para
   que el catálogo y los 280 tramos sean los de verdad— y corre escenarios.
   Imprime un JSON que lee tests/test_web_carga_validacion.py. */
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
  this.hidden = false;
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
Elemento.prototype.disparar = function (ev, evento) {
  (this._listeners[ev] || []).forEach((fn) => fn.call(this, evento || {
    preventDefault() {}, target: this,
  }));
  if (ev === 'click' && typeof this.onclick === 'function') this.onclick();
};
Elemento.prototype.getAttribute = function (k) { return this._attrs[k]; };
Elemento.prototype.setAttribute = function (k, v) { this._attrs[k] = v; };
Elemento.prototype.querySelectorAll = function (sel) {
  if (sel === 'button') return this._hijos.filter((h) => h.tag === 'button');
  if (sel === '.op') return this._hijos.filter((h) => h.tag === 'op');
  if (sel.indexOf('input[type=file]') >= 0) {
    return this._hijos.filter((h) => h.tag === 'input');
  }
  return [];
};

const doc = { _els: {}, _listeners: {} };
function crear(id) {
  if (!doc._els[id]) doc._els[id] = new Elemento(id);
  return doc._els[id];
}
doc.getElementById = (id) => crear(id);
doc.addEventListener = function (ev, fn) {
  (doc._listeners[ev] = doc._listeners[ev] || []).push(fn);
};
doc.disparar = function (ev, evento) {
  (doc._listeners[ev] || []).forEach((fn) => fn(evento));
};

// innerHTML: se "parsea" con regex lo único que app.js genera y luego consulta
// — botones de tipo (data-t), inputs de archivo (data-clave) y opciones de
// tramo (data-i).
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
    const op = /<div class="op( sel)?"[^>]*data-i="(\d+)">([\s\S]*?)<\/div>/g;
    while ((m = op.exec(html))) {
      const o = new Elemento('op-' + m[2]);
      o.tag = 'op';
      o._attrs['data-i'] = m[2];
      o.className = 'op' + (m[1] || '');
      o.textContent = m[3];
      this._hijos.push(o);
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
  Math,
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
doc.getElementById('tramo-lista').hidden = true;   // como el atributo del HTML
vm.runInContext(fs.readFileSync(path.join(WEB, 'app.js'), 'utf8'), ctx);

// ── Utilidades del escenario ────────────────────────────────────────────────
const el = (id) => doc.getElementById(id);
const panel = () => el('tramo-lista');
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
const opciones = () => panel().querySelectorAll('.op').map((o) => o.textContent);
const abierto = () => panel().hidden === false;
function tocarOpcion(texto) {
  const op = panel().querySelectorAll('.op')
    .filter((o) => o.textContent === texto)[0];
  if (!op) throw new Error('no está la opción ' + texto);
  op.disparar('mousedown', { preventDefault() {}, target: op });
}
const estado = () => ({ disabled: el('enviar').disabled,
                        hint: el('hint').textContent });

const r = { total_tramos: ctx.TRAMOS.length };
r.catalogo = {};
Object.keys(ctx.CATALOGO).forEach((t) => {
  r.catalogo[t] = ctx.CATALOGO[t].filter((c) => c.req).map((c) => c.clave);
});

// ── Selector de tramo ───────────────────────────────────────────────────────
r.panel_inicial_cerrado = !abierto();
el('tramo').disparar('focus');
r.al_enfocar = { abierto: abierto(), n: opciones().length,
                 primero: opciones()[0] };

set('tramo', 'salento');                       // minúsculas
r.filtro_texto = { abierto: abierto(), opciones: opciones() };
set('tramo', 'chinchina');                     // sin tilde → 'Ramal Chinchiná'
r.filtro_sin_tilde = opciones();
set('tramo', 'zzz no existe');
r.filtro_sin_resultados = { opciones: opciones(), estado: estado() };

set('tramo', 'Ramal Salento Inventado');
r.tramo_inventado = estado();

set('tramo', 'sal');
tocarOpcion('Ramal Salento');
r.al_elegir = { valor: el('tramo').value, cerrado: !abierto(),
                estado: estado() };

// tocar fuera cierra el panel
el('tramo').disparar('focus');
const fuera = new Elemento('otra-cosa');
doc.disparar('mousedown', { target: fuera, preventDefault() {} });
r.click_fuera_cierra = !abierto();

// ── Formateo del PK ─────────────────────────────────────────────────────────
// La función pura, tal como la usa el campo.
r.pk_formato = {};
['125000', '126500', '9500', '850', '125+000', '', '0', '12abc34']
  .forEach((t) => { r.pk_formato[t === '' ? '(vacio)' : t] = ctx.pkFormato(t); });

// Escribiendo dígito a dígito, como en el celular (cada tecla es un 'input').
function teclear(id, texto) {
  const campo = el(id);
  campo.value = '';
  [...texto].forEach((c) => { campo.value += c; campo.disparar('input'); });
  return campo.value;
}
r.tecleando = {
  '125000': teclear('pk-inicial', '125000'),
  '850': teclear('pk-inicial', '850'),
  'pegado 125+000': (() => { set('pk-inicial', '125+000');
                             return el('pk-inicial').value; })(),
};
// borrar deja el campo vacío y sin error
set('pk-inicial', '');
r.al_borrar = { valor: el('pk-inicial').value, metros: ctx.pkMetros('') };
// lo que se guardaría: el campo muestra '125+000' y a la BD va 125000
set('pk-inicial', '125000');
set('pk-final', '129450');
r.a_la_bd = { visible_inicial: el('pk-inicial').value,
              metros_inicial: ctx.pkMetros(el('pk-inicial').value),
              visible_final: el('pk-final').value,
              metros_final: ctx.pkMetros(el('pk-final').value) };

// ── Resto de la validación (no la puede romper el selector) ─────────────────
set('fecha', '2026-09-18');
set('pk-inicial', '125+000');
set('pk-final', '129+450');
r.sin_tecnico = estado();
el('tecnico').value = 'JOSE LUIS PAEZ';
el('tecnico').disparar('change');

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
