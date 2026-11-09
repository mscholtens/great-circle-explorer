// Coordinate wizard: ONE scrollable form. Point and format are chosen at the top; the fields, labels and
// help texts below change with the format. Unit parsing/formatting only; all geodesy stays in the backend.
import { COORD_MODES, composeCoord, el, formatCoord, splitCoord } from './format.js';
import { showModal } from './modal.js';

const LIMIT = { lat: 90, lon: 180 };
const AXIS = {
  lat: { name: 'Latitude', blurb: 'How far north (N) or south (S) of the equator, from 0° to 90°.' },
  lon: { name: 'Longitude', blurb: 'How far east (E) or west (W) of Greenwich, from 0° to 180°.' },
};
const HEMIS = { lat: [['N', 'North'], ['S', 'South']], lon: [['E', 'East'], ['W', 'West']] };
const PART = { deg: 'Degrees', min: 'Minutes', sec: 'Seconds' };
const SUFFIX = { deg: '°', min: '′', sec: '″' };
const MODE_INFO = {
  dd: { blurb: 'One number per coordinate', example: '50.8659° N' },
  dms: { blurb: 'Degrees, minutes and seconds', example: '50° 51′ 57.24″ N' },
  ddm: { blurb: 'Degrees and decimal minutes', example: '50° 51.954′ N' },
};
const EXAMPLES = {
  lat: { dd: { deg: '50.8659' }, dms: { deg: '50', min: '51', sec: '57.24' }, ddm: { deg: '50', min: '51.954' } },
  lon: { dd: { deg: '7.1427' }, dms: { deg: '7', min: '8', sec: '33.72' }, ddm: { deg: '7', min: '8.562' } },
};

const partsFor = (mode) => (mode === 'dms' ? ['deg', 'min', 'sec'] : mode === 'ddm' ? ['deg', 'min'] : ['deg']);
const emptyAxis = () => ({ deg: '', min: '', sec: '', hemi: null });

function partSpec(axis, part, mode) {
  const max = LIMIT[axis];
  if (part === 'deg') {
    return mode === 'dd'
      ? { integer: false, help: `Decimals allowed, 0 to ${max}. Example: ${EXAMPLES[axis].dd.deg}` }
      : { integer: true, help: `Whole number, 0 to ${max}.` };
  }
  if (part === 'min') {
    return mode === 'dms'
      ? { integer: true, help: 'Whole number, 0 to 59.' }
      : { integer: false, help: 'Decimals allowed, below 60.' };
  }
  return { integer: false, help: 'Decimals allowed, below 60.' };
}

/** Returns { value } (cleaned text) or { error }. */
function validatePart(axis, part, mode, raw) {
  const text = String(raw).replace(/[°º′″'"]/g, '').trim();
  if (text === '') return { error: 'Please enter a number.' };
  if (text.startsWith('-')) return { error: 'Use a positive number; choose N/S or E/W below.' };
  if (!/^(\d+([.,]\d*)?|[.,]\d+)$/.test(text)) return { error: 'Just a number, like 50 or 50.5. No letters or symbols.' };
  const n = Number(text.replace(',', '.'));
  if (!Number.isFinite(n)) return { error: 'That does not look like a number.' };
  if (partSpec(axis, part, mode).integer && !Number.isInteger(n)) return { error: 'A whole number is needed here (no decimals).' };
  if (part === 'deg' && n > LIMIT[axis]) return { error: `Degrees must be between 0 and ${LIMIT[axis]}.` };
  if (part !== 'deg' && n >= 60) return { error: `${PART[part]} must be below 60.` };
  return { value: text.replace(',', '.') };
}

/**
 * deps: { getMode(): 'dd'|'dms'|'ddm', getPoint('a'|'b'): {lat, lon}|null, onApply(which, {lat, lon}) }
 * returns { open(openerElement) }
 */
export function createWizard(root, { getMode, getPoint, onApply }) {
  let modal = null;

  function open(opener) {
    if (modal) return;

    const s = {
      which: !getPoint('a') ? 'a' : !getPoint('b') ? 'b' : 'a',
      mode: getMode(),
      v: { lat: emptyAxis(), lon: emptyAxis() },
      touched: new Set(),        // "lat.deg", "lon.hemi", ... fields the user has visited
      submitted: false,
    };
    const other = () => (s.which === 'a' ? 'b' : 'a');
    const up = (w) => w.toUpperCase();

    function prefill() {
      const p = getPoint(s.which);
      if (p) s.v = { lat: splitCoord(p.lat, 'lat', s.mode), lon: splitCoord(p.lon, 'lon', s.mode) };
    }
    prefill();

    // ---------- evaluation (pure: reads s, returns errors and values)
    function evaluate() {
      const out = { ok: true, values: {}, errors: { lat: {}, lon: {} }, axisError: {} };
      for (const axis of ['lat', 'lon']) {
        const parts = {};
        let partsOk = true;
        for (const part of partsFor(s.mode)) {
          const r = validatePart(axis, part, s.mode, s.v[axis][part]);
          if (r.error) { out.errors[axis][part] = r.error; partsOk = false; out.ok = false; } else parts[part] = r.value;
        }
        if (!s.v[axis].hemi) {
          out.errors[axis].hemi = `Please choose ${HEMIS[axis][0][1]} or ${HEMIS[axis][1][1]}.`;
          out.ok = false;
        }
        if (partsOk && composeCoord({ ...parts, hemi: 'N' }) > LIMIT[axis] + 1e-12) {
          out.axisError[axis] = `${AXIS[axis].name} cannot be more than ${LIMIT[axis]}°. Please check the numbers.`;
          partsOk = false;
          out.ok = false;
        }
        if (partsOk && s.v[axis].hemi) out.values[axis] = composeCoord({ ...parts, hemi: s.v[axis].hemi });
      }
      return out;
    }

    // ---------- persistent chrome
    const dialog = el('div', { class: 'dialog wizard', role: 'dialog', 'aria-modal': 'true', 'aria-labelledby': 'wiz-title', tabindex: '-1' });
    const closeBtn = el('button', { class: 'icon-btn', type: 'button', 'aria-label': 'Close wizard', onclick: () => modal.close() }, '✕');
    const axesHost = el('div', { class: 'wiz-axes' });
    const body = el('div', { class: 'dialog-body wiz-body' });
    const previewBox = el('div', { class: 'wiz-preview', 'aria-live': 'polite' });
    const setBtn = el('button', { class: 'btn btn-primary', type: 'button', onclick: () => submit(false) });
    const nextBtn = el('button', { class: 'btn', type: 'button', onclick: () => submit(true) });
    const cancelBtn = el('button', { class: 'btn', type: 'button', onclick: () => modal.close() }, 'Cancel');

    function radio(checked, onSelect, children, cls) {
      const b = el('button', { type: 'button', class: `wiz-option ${cls}${checked ? ' on' : ''}`, role: 'radio', 'aria-checked': String(checked) }, children);
      b.addEventListener('click', onSelect);
      return b;
    }

    // point + format selectors (rebuilt in place when the selection changes; their section is small)
    const pointHost = el('div', { class: 'wiz-options two', role: 'radiogroup', 'aria-label': 'Point' });
    const modeHost = el('div', { class: 'wiz-options three', role: 'radiogroup', 'aria-label': 'Format' });

    function renderSelectors() {
      pointHost.replaceChildren(...['a', 'b'].map((w) => radio(s.which === w, () => switchPoint(w),
        [el('span', { class: `badge badge-${w}` }, up(w)),
          el('span', {}, `Point ${up(w)}`, getPoint(w) ? el('small', {}, 'currently set') : null)], 'wiz-point')));
      modeHost.replaceChildren(...COORD_MODES.map((m) => radio(s.mode === m.id, () => switchMode(m.id),
        [el('strong', {}, m.label), el('small', {}, MODE_INFO[m.id].blurb), el('code', {}, MODE_INFO[m.id].example)], 'wiz-mode')));
    }

    // ---------- the dynamic part: one section per axis, fields depend on the format
    let refs = null;
    function renderAxes() {
      refs = { fields: { lat: {}, lon: {} }, hemi: { lat: {}, lon: {} }, axisErr: {} };
      const sections = ['lat', 'lon'].map((axis) => {
        const fields = partsFor(s.mode).map((part) => {
          const spec = partSpec(axis, part, s.mode);
          const id = `wiz-${axis}-${part}`;
          const input = el('input', {
            type: 'text', class: 'wiz-input', id, inputmode: 'decimal', autocomplete: 'off', spellcheck: 'false',
            placeholder: EXAMPLES[axis][s.mode][part], value: s.v[axis][part], 'aria-describedby': `${id}-help ${id}-err`,
          });
          const err = el('div', { class: 'wiz-field-error', id: `${id}-err` });
          refs.fields[axis][part] = { input, err };
          input.addEventListener('input', () => { s.v[axis][part] = input.value; refresh(); });
          input.addEventListener('blur', () => { s.touched.add(`${axis}.${part}`); refresh(); });
          input.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); advance(input); } });
          return el('div', { class: 'wiz-field' },
            el('label', { for: id }, PART[part]),
            el('div', { class: 'wiz-input-wrap' }, input, el('span', { class: 'wiz-suffix', 'aria-hidden': 'true' }, SUFFIX[part])),
            el('div', { class: 'wiz-field-help', id: `${id}-help` }, spec.help),
            err);
        });

        const hemiErr = el('div', { class: 'wiz-field-error', id: `wiz-${axis}-hemi-err` });
        const hemiBtns = HEMIS[axis].map(([l, n]) => {
          const b = radio(s.v[axis].hemi === l, () => {
            s.v[axis].hemi = l;
            s.touched.add(`${axis}.hemi`);
            syncHemi(axis);
            refresh();
          }, [el('strong', {}, l), el('small', {}, n)], 'wiz-hemi');
          b.dataset.letter = l;
          return b;
        });
        refs.hemi[axis] = { err: hemiErr, btns: hemiBtns };
        const hemiGroup = el('div', { class: 'wiz-hemi-group', role: 'radiogroup', 'aria-label': `${AXIS[axis].name} direction` }, hemiBtns);
        hemiGroup.addEventListener('keydown', (e) => {
          if (e.ctrlKey || e.metaKey || e.altKey) return;
          const hit = HEMIS[axis].find(([l]) => l.toLowerCase() === e.key.toLowerCase());
          if (hit) {
            e.preventDefault();
            s.v[axis].hemi = hit[0];
            s.touched.add(`${axis}.hemi`);
            syncHemi(axis);
            refresh();
          }
        });
        refs.axisErr[axis] = el('div', { class: 'wiz-field-error wiz-axis-error', role: 'alert' });

        return el('fieldset', { class: 'wiz-axis' },
          el('legend', {}, AXIS[axis].name),
          el('p', { class: 'wiz-help' }, AXIS[axis].blurb),
          el('div', { class: `wiz-fields n${partsFor(s.mode).length}` }, fields),
          el('div', { class: 'wiz-field' },
            el('div', { class: 'wiz-label-sm' }, 'Direction'), hemiGroup, hemiErr),
          refs.axisErr[axis]);
      });
      axesHost.replaceChildren(...sections);
    }

    function syncHemi(axis) {
      for (const b of refs.hemi[axis].btns) {
        const on = b.dataset.letter === s.v[axis].hemi;
        b.classList.toggle('on', on);
        b.setAttribute('aria-checked', String(on));
      }
    }

    // ---------- feedback (updates texts in place, so typing never loses focus)
    function refresh() {
      const r = evaluate();
      const show = (key) => s.submitted || s.touched.has(key);
      for (const axis of ['lat', 'lon']) {
        for (const part of partsFor(s.mode)) {
          const f = refs.fields[axis][part];
          const msg = show(`${axis}.${part}`) ? r.errors[axis][part] || '' : '';
          f.err.textContent = msg;
          f.input.setAttribute('aria-invalid', msg ? 'true' : 'false');
        }
        refs.hemi[axis].err.textContent = show(`${axis}.hemi`) ? r.errors[axis].hemi || '' : '';
        refs.axisErr[axis].textContent = r.axisError[axis] || '';
      }
      if (r.values.lat !== undefined && r.values.lon !== undefined) {
        const { lat, lon } = r.values;
        previewBox.replaceChildren(
          el('div', { class: 'wiz-preview-label' }, `Point ${up(s.which)} will be`),
          el('div', { class: 'wiz-preview-main' }, `${formatCoord(lat, 'lat', s.mode)},  ${formatCoord(lon, 'lon', s.mode)}`),
          el('div', { class: 'wiz-preview-alt' }, `Decimal degrees: ${lat.toFixed(6)}, ${lon.toFixed(6)}`));
        previewBox.classList.add('ready');
      } else {
        previewBox.replaceChildren(el('div', { class: 'wiz-preview-label' }, 'Fill in all fields to see a preview of the point.'));
        previewBox.classList.remove('ready');
      }
      setBtn.textContent = `Set point ${up(s.which)}`;
      nextBtn.textContent = `Set ${up(s.which)}, then enter ${up(other())}`;
      return r;
    }

    // ---------- actions
    function switchMode(newMode) {
      if (newMode === s.mode) return;
      for (const axis of ['lat', 'lon']) {
        const cur = s.v[axis];
        const num = (x) => (String(x).trim() === '' ? 0 : Number(String(x).replace(/[°º′″'"]/g, '').trim().replace(',', '.')));
        const value = composeCoord({ deg: String(cur.deg).replace(/[°º′″'"]/g, ''), min: num(cur.min), sec: num(cur.sec), hemi: 'N' });
        if (Number.isFinite(value) && value >= 0 && value <= LIMIT[axis]) {
          // convert what was typed so far into the new format (50.5 in DD becomes 50 30 0 in DMS)
          const hemi = cur.hemi;
          s.v[axis] = { ...splitCoord(value, axis, newMode), hemi };
        } else {
          s.v[axis] = { deg: cur.deg, min: '', sec: '', hemi: cur.hemi };
        }
      }
      s.mode = newMode;
      keepScroll(() => { renderSelectors(); renderAxes(); refresh(); });
      focusSelected(modeHost);
    }

    function switchPoint(w) {
      if (w === s.which) return;
      s.which = w;
      if (getPoint(w)) { s.touched.clear(); s.submitted = false; prefill(); keepScroll(() => { renderSelectors(); renderAxes(); refresh(); }); }
      else keepScroll(() => { renderSelectors(); refresh(); });   // keep what was typed for an empty point
      focusSelected(pointHost);
    }

    function keepScroll(fn) {
      const top = body.scrollTop;
      fn();
      body.scrollTop = top;
    }
    function focusSelected(host) { (host.querySelector('.wiz-option.on') || host.firstChild).focus(); }

    function firstInvalid(r) {
      for (const axis of ['lat', 'lon']) {
        for (const part of partsFor(s.mode)) if (r.errors[axis][part]) return refs.fields[axis][part].input;
        if (r.axisError[axis]) return refs.fields[axis][partsFor(s.mode)[0]].input;
        if (r.errors[axis].hemi) return refs.hemi[axis].btns[0];
      }
      return null;
    }

    function advance(fromInput) {            // Enter moves to the next field; on the last one it submits
      const inputs = [...dialog.querySelectorAll('.wiz-input')];
      const i = inputs.indexOf(fromInput);
      if (i >= 0 && i < inputs.length - 1) inputs[i + 1].focus();
      else submit(false);
    }

    function submit(thenOther) {
      s.submitted = true;
      const r = refresh();
      if (!r.ok) {
        const target = firstInvalid(r);
        if (target) { target.focus(); target.scrollIntoView({ block: 'center' }); }
        return;
      }
      onApply(s.which, { lat: r.values.lat, lon: r.values.lon });
      if (!thenOther) { modal.close(); return; }
      s.which = other();
      s.v = { lat: emptyAxis(), lon: emptyAxis() };
      s.touched.clear();
      s.submitted = false;
      prefill();
      renderSelectors(); renderAxes(); refresh();
      body.scrollTop = 0;
      refs.fields.lat.deg.input.focus();
    }

    // ---------- assemble
    body.append(
      el('p', { class: 'wiz-intro' }, 'Choose the point and the format, then fill in the fields. ',
        el('strong', {}, 'No need to type the ° ′ ″ symbols.'), ' Use a dot for decimals.'),
      el('div', { class: 'wiz-label' }, 'Point'), pointHost,
      el('div', { class: 'wiz-label' }, 'Format'), modeHost,
      axesHost);

    dialog.append(
      el('header', { class: 'dialog-head' },
        el('div', {},
          el('div', { class: 'dialog-group' }, 'Coordinate wizard'),
          el('h2', { id: 'wiz-title' }, 'Enter a point')),
        closeBtn),
      body, previewBox,
      el('footer', { class: 'dialog-foot' }, cancelBtn, el('div', { class: 'wiz-actions' }, nextBtn, setBtn)));

    renderSelectors();
    renderAxes();
    refresh();
    modal = showModal(root, dialog, { returnFocus: opener, onClose: () => { modal = null; } });
    // first empty field, or the first field when everything is prefilled
    const firstEmpty = ['lat', 'lon'].flatMap((a) => partsFor(s.mode).map((p) => refs.fields[a][p].input)).find((i) => i.value === '');
    (firstEmpty || refs.fields.lat.deg.input).focus();
  }

  return { open };
}
