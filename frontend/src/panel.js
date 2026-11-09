// Left-hand panel: coordinate inputs, options, layer toggles, metric cards.
import { COORD_MODES, coordPlaceholder, el, formatCoord, parseCoord, todayISO } from './format.js';

const DEFAULTS = { cruise_kmh: 850, climb_descent_min: 15, taxi_min: 15, height_a_m: 1.7, height_b_m: 1.7 };
// The sun and time-zone metrics accept dates from 1 Jan 1970 to 31 Dec 2049 (the backend enforces it too).
const DATE_MIN = '1970-01-01';
const DATE_MAX = '2049-12-31';
const MODE_KEY = 'gce.coordMode';

// Shown under the format toggle: symbols are optional; spaces separate the parts, a dot marks decimals.
const TIPS = {
  dd: 'Tip: the ° symbol is not needed, just type 50.8659 N (a dot for decimals). Prefer a guided form? Use the Wizard.',
  dms: 'Tip: no ° ′ ″ symbols needed. Separate the parts with spaces and use a dot for decimals: 50 51 57.24 N. Prefer a guided form? Use the Wizard.',
  ddm: 'Tip: no ° ′ symbols needed. Separate the parts with a space and use a dot for decimals: 50 51.954 N. Prefer a guided form? Use the Wizard.',
};

// The chosen format is a per-viewer convenience; the app works without storage.
function loadMode() {
  try {
    const m = localStorage.getItem(MODE_KEY);
    if (COORD_MODES.some((x) => x.id === m)) return m;
  } catch (_) { /* storage unavailable */ }
  return 'dd';
}
function saveMode(m) {
  try { localStorage.setItem(MODE_KEY, m); } catch (_) { /* ignore */ }
}

/**
 * handlers: { onCoordsEdited(which, {lat, lon}), onSwap(), onReset(), onOpenWizard(buttonEl), onOptionsChanged(),
 *             onToggle(name, on), onOpenMetric(metric, cardEl) }
 */
export function createPanel(root, handlers) {
  const inputs = { a: {}, b: {} };
  const current = { a: null, b: null };   // exact point values; the fields only show a rounded rendering
  const optionInputs = {};
  let mode = loadMode();

  /** Show the current points in the chosen format (skips a field the user is typing in). */
  function renderCoordFields() {
    for (const which of ['a', 'b']) {
      for (const axis of ['lat', 'lon']) {
        const inp = inputs[which][axis];
        inp.placeholder = coordPlaceholder(axis, mode);
        if (document.activeElement === inp) continue;
        const p = current[which];
        inp.value = p ? formatCoord(p[axis], axis, mode) : '';
        inp.classList.remove('invalid');
      }
    }
  }

  // ----- coordinate rows
  function coordRow(which) {
    const mk = (axis, label) => el('input', {
      type: 'text', 'aria-label': `${label} of ${which.toUpperCase()}`, autocomplete: 'off', spellcheck: 'false',
    });
    const lat = mk('lat', 'Latitude');
    const lon = mk('lon', 'Longitude');
    inputs[which] = { lat, lon };
    const commit = () => {
      const la = parseCoord(lat.value, 'lat');
      const lo = parseCoord(lon.value, 'lon');
      const empty = lat.value.trim() === '' || lon.value.trim() === '';
      const badLat = !empty && !(la >= -90 && la <= 90);
      const badLon = !empty && !(lo >= -180 && lo <= 180);
      lat.classList.toggle('invalid', badLat || (lat.value.trim() !== '' && Number.isNaN(la)));
      lon.classList.toggle('invalid', badLon || (lon.value.trim() !== '' && Number.isNaN(lo)));
      if (!empty && !badLat && !badLon && !Number.isNaN(la) && !Number.isNaN(lo)) {
        current[which] = { lat: la, lon: lo };
        lat.value = formatCoord(la, 'lat', mode);   // normalize whatever was typed to the chosen format
        lon.value = formatCoord(lo, 'lon', mode);
        handlers.onCoordsEdited(which, { lat: la, lon: lo });
      }
    };
    for (const inp of [lat, lon]) {
      inp.addEventListener('change', commit);
      inp.addEventListener('keydown', (e) => { if (e.key === 'Enter') commit(); });
    }
    return el('div', { class: 'coord-row' }, el('span', { class: `badge badge-${which}` }, which.toUpperCase()), lat, lon);
  }

  // ----- format toggle (DD | DMS | DDM)
  const modeButtons = COORD_MODES.map((m) => {
    const b = el('button', { type: 'button', class: 'seg', role: 'radio', title: m.title, 'aria-label': m.title, 'data-mode': m.id }, m.label);
    b.addEventListener('click', () => {
      mode = m.id;
      saveMode(mode);
      syncModeButtons();
      renderCoordFields();
    });
    return b;
  });
  const tip = el('p', { class: 'coord-tip', id: 'coord-tip' });
  function syncModeButtons() {
    for (const b of modeButtons) {
      const on = b.dataset.mode === mode;
      b.setAttribute('aria-checked', String(on));
      b.classList.toggle('on', on);
    }
    tip.textContent = TIPS[mode];
  }
  const modeToggle = el('div', {},
    el('div', { class: 'coord-mode' },
      el('span', { class: 'coord-mode-label' }, 'Coordinate format'),
      el('div', { class: 'segmented', role: 'radiogroup', 'aria-label': 'Coordinate format' }, modeButtons)),
    tip);

  const swapBtn = el('button', { class: 'btn', type: 'button', onclick: () => handlers.onSwap() }, '⇄ Swap A/B');
  const resetBtn = el('button', { class: 'btn', type: 'button', onclick: () => handlers.onReset() }, 'Reset');
  const wizardBtn = el('button', {
    class: 'btn', type: 'button', title: 'Enter coordinates step by step',
  }, '✦ Wizard');
  wizardBtn.addEventListener('click', () => handlers.onOpenWizard(wizardBtn));

  // ----- options
  function numberField(key, label, step, min) {
    const input = el('input', { type: 'number', value: DEFAULTS[key], step, min, 'aria-label': label });
    input.addEventListener('change', () => handlers.onOptionsChanged());
    optionInputs[key] = input;
    return el('label', { class: 'field' }, el('span', {}, label), input);
  }
  const dateInput = el('input', { type: 'date', value: todayISO(), min: DATE_MIN, max: DATE_MAX, 'aria-label': 'Date for sun and time-zone metrics' });
  dateInput.addEventListener('change', () => handlers.onOptionsChanged());
  optionInputs.date = dateInput;

  const options = el('details', { class: 'section' },
    el('summary', {}, 'Options'),
    el('div', { class: 'options-grid' },
      numberField('cruise_kmh', 'Cruise speed (km/h)', 10, 1),
      numberField('climb_descent_min', 'Climb & descent (min)', 5, 0),
      numberField('taxi_min', 'Taxiing, both ends (min)', 5, 0),
      el('label', { class: 'field' }, el('span', {}, 'Date (sun & time zones)'), dateInput),
      numberField('height_a_m', 'Eye height A (m)', 1, 0),
      numberField('height_b_m', 'Eye height B (m)', 1, 0)),
    el('p', { class: 'options-note' },
      'Date: 1 Jan 1970 to 31 Dec 2049. Time zones follow today\'s rules; future political decisions cannot be predicted, so later dates assume the current rules continue.'));

  // ----- layer toggles
  function toggle(name, label, checked = true) {
    const input = el('input', { type: 'checkbox', checked: checked ? '' : null });
    input.checked = checked;
    input.addEventListener('change', () => handlers.onToggle(name, input.checked));
    return el('label', { class: 'chip' }, input, el('span', {}, label));
  }
  const toggles = el('div', { class: 'chips', role: 'group', 'aria-label': 'Map layers' },
    toggle('rhumb', 'Rhumb line'), toggle('midpoint', 'Midpoint'), toggle('vertex', 'Vertex'), toggle('crossings', 'Crossings'), toggle('antipodes', 'Antipodes'));

  // ----- results
  const warningsBox = el('div', { class: 'warnings', hidden: true });
  const results = el('div', { class: 'results' });
  const status = el('div', { class: 'status', 'aria-live': 'polite' });

  const body = el('div', { class: 'panel-body' },
    el('header', { class: 'panel-head' },
      el('h1', {}, 'Great Circle Explorer'),
      el('p', {}, 'Click the globe to place A, then B — or type coordinates.')),
    el('section', { class: 'section' },
      modeToggle, coordRow('a'), coordRow('b'),
      el('div', { class: 'row-buttons' }, swapBtn, resetBtn, wizardBtn)),
    options, toggles, status, warningsBox, results,
    el('footer', { class: 'disclaimer' }, 'Spherical Earth model, R = 6371.0088 km. Click a metric to see how it is calculated.'));

  root.append(body);
  syncModeButtons();
  renderCoordFields();

  // ----- public API
  function setPoints(a, b) {
    current.a = a;
    current.b = b;
    renderCoordFields();
  }

  function getOptions() {
    const o = {};
    for (const k of ['cruise_kmh', 'climb_descent_min', 'taxi_min', 'height_a_m', 'height_b_m']) {
      const v = optionInputs[k].valueAsNumber;
      if (Number.isFinite(v) && v >= 0 && !(k === 'cruise_kmh' && v === 0)) o[k] = v;
    }
    if (optionInputs.date.value) o.date = optionInputs.date.value;
    return o;
  }

  function card(metric) {
    const node = el('div', { class: 'card', role: 'button', tabindex: '0', 'aria-label': `${metric.label}: ${metric.display}. Show calculation.` },
      el('div', { class: 'card-top' }, el('span', { class: 'card-label' }, metric.label), el('span', { class: 'fx', 'aria-hidden': 'true' }, 'ƒ(x)')),
      el('div', { class: `card-value${metric.value == null && metric.display.length < 14 ? ' undefined' : ''}` }, metric.display),
      metric.secondary.length ? el('div', { class: 'card-secondary' }, metric.secondary.map((s) => el('span', {}, s))) : null,
      metric.table ? el('table', { class: 'mini-table' }, el('tbody', {}, metric.table.map((r) =>
        el('tr', {}, el('th', { scope: 'row' }, r.label), el('td', {}, r.display))))) : null);
    const open = () => handlers.onOpenMetric(metric, node);
    node.addEventListener('click', open);
    node.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); }
    });
    return node;
  }

  function setResult(result) {
    results.replaceChildren();
    warningsBox.replaceChildren();
    warningsBox.hidden = !(result && result.warnings.length);
    if (!result) {
      results.append(el('p', { class: 'placeholder' }, 'Place two points to see distance, bearings, flight time and more.'));
      return;
    }
    result.warnings.forEach((w) => warningsBox.append(el('p', {}, '⚠ ' + w)));
    const groups = [];
    for (const m of result.metrics) {
      let g = groups.find((x) => x.name === m.group);
      if (!g) groups.push((g = { name: m.group, items: [] }));
      g.items.push(m);
    }
    for (const g of groups) {
      results.append(el('section', { class: 'group' },
        el('h2', {}, g.name),
        el('div', { class: 'cards' }, g.items.map(card))));
    }
  }

  function setLoading(on) {
    body.classList.toggle('loading', on);
    status.textContent = on ? 'Calculating…' : '';
  }

  setResult(null);
  return { setPoints, setResult, setLoading, getOptions, getMode: () => mode };
}
