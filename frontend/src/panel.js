// Left-hand panel: coordinate inputs, options, layer toggles, metric cards.
import { COORD_MODES, coordPlaceholder, el, formatCoord, parseCoord, todayISO } from './format.js';
import { createSearch } from './search.js';
import { unitField } from './unitfield.js';

const DEFAULTS = { cruise_kmh: 850, climb_descent_min: 15, taxi_min: 15, height_a_m: 1.7, height_b_m: 1.7 };
// The sun and time-zone metrics accept dates from 1 Jan 1970 to 31 Dec 2049 (the backend enforces it too).
const DATE_MIN = '1970-01-01';
const DATE_MAX = '2049-12-31';
const MODE_KEY = 'gce.coordMode';
const UNIT_KEY = 'gce.units';
const INPUT_KEY = 'gce.inputMode';

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
function loadUnitId() {
  try { return localStorage.getItem(UNIT_KEY) || 'km'; } catch (_) { return 'km'; }
}
function saveUnitId(id) {
  try { localStorage.setItem(UNIT_KEY, id); } catch (_) { /* ignore */ }
}
function loadInputMode() {
  try { return localStorage.getItem(INPUT_KEY) === 'course' ? 'course' : 'two'; } catch (_) { return 'two'; }
}
function saveInputMode(m) {
  try { localStorage.setItem(INPUT_KEY, m); } catch (_) { /* ignore */ }
}
function saveMode(m) {
  try { localStorage.setItem(MODE_KEY, m); } catch (_) { /* ignore */ }
}

/**
 * handlers: { onCoordsEdited(which, {lat, lon}), onSwap(), onReset(), onOpenWizard(buttonEl), onOptionsChanged(),
 *             onInputModeChanged('two'|'course'), onUnitsChanged(unit), onCopyLink(buttonEl), onOpenExport(buttonEl), onOpenMetric(metric, cardEl) }
 * (the map-layer toggles live in the toolbar on top of the map, see toolbar.js)
 */
export function createPanel(root, handlers) {
  const inputs = { a: {}, b: {} };
  const current = { a: null, b: null };   // exact point values; the fields only show a rounded rendering
  const optionInputs = {};
  const unitFields = {};      // options typed in the chosen unit but kept in km
  const unitLabels = {};      // { key: { span, input, base, kind } }
  const searches = {};
  const nearestData = { a: null, b: null };
  let unitList = [{ id: 'km', label: 'km', speed_label: 'km/h', km_per_unit: 1 }];
  let unit = unitList[0];
  let mode = loadMode();
  let inputMode = loadInputMode();   // 'two' = two points, 'course' = start point + course + distance (B is calculated)

  /** Show the current points in the chosen format (skips a field the user is typing in). */
  function renderCoordFields() {
    for (const which of ['a', 'b']) {
      for (const axis of ['lat', 'lon']) {
        const inp = inputs[which][axis];
        inp.placeholder = which === 'b' && inputMode === 'course' ? 'calculated' : coordPlaceholder(axis, mode);
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
  const copyBtn = el('button', { class: 'btn', type: 'button', title: 'Copy a link that restores A and B' }, '🔗 Copy link');
  copyBtn.addEventListener('click', () => handlers.onCopyLink(copyBtn));
  const exportBtn = el('button', { class: 'btn', type: 'button', title: 'Create a PDF report of the results' }, '⤓ Export PDF');
  exportBtn.addEventListener('click', () => handlers.onOpenExport(exportBtn));

  // ----- input mode: two points | start + course (B is calculated from A, a course and a distance)
  const inputModeBox = el('div', { class: 'coord-mode' },
    el('span', { class: 'coord-mode-label' }, 'Enter'),
    el('div', { class: 'segmented', role: 'radiogroup', 'aria-label': 'What to enter' },
      [['two', 'Two points', 'Enter A and B; the app measures the route'], ['course', 'Start + course', 'Enter A, a course and a distance; the app calculates B']]
        .map(([id, label, title]) => {
          const b = el('button', { type: 'button', class: 'seg', role: 'radio', 'data-input': id, title }, label);
          b.addEventListener('click', () => setInputMode(id, true));
          return b;
        })));
  const bearingInput = el('input', { type: 'number', min: 0, max: 360, step: 1, placeholder: '0–360', 'aria-label': 'Course in degrees' });
  bearingInput.addEventListener('change', () => handlers.onOptionsChanged());
  const bearingField = el('label', { class: 'field' }, el('span', {}, 'Course (°, 0 = north)'), bearingInput);
  const courseDistanceField = numberField('course_km', 'Distance', 100, 0, { empty: true, placeholder: 'e.g. 1000', kind: 'dist' });
  const courseBox = el('div', { class: 'course-box', hidden: true },
    el('div', { class: 'options-grid' }, bearingField, courseDistanceField),
    el('p', { class: 'options-hint' }, 'The course is the true bearing measured clockwise from north (90° = east). B, the destination, is calculated and shown below.'));
  function syncInputMode() {
    for (const b of inputModeBox.querySelectorAll('.seg')) {
      const on = b.dataset.input === inputMode;
      b.setAttribute('aria-checked', String(on));
      b.classList.toggle('on', on);
    }
    const course = inputMode === 'course';
    courseBox.hidden = !course;
    searches.b.root.hidden = course;
    swapBtn.disabled = course;
    for (const axis of ['lat', 'lon']) inputs.b[axis].readOnly = course;
    section.classList.toggle('course-mode', course);
    renderCoordFields();
  }
  function setInputMode(id, notify) {
    if (id === inputMode) return;
    inputMode = id;
    saveInputMode(id);
    syncInputMode();
    if (notify) handlers.onInputModeChanged(id);
  }

  // ----- units toggle (km | nm | mi); the list comes from the backend (setUnits)
  const unitsBox = el('div', { class: 'coord-mode', hidden: true });
  function syncUnitButtons() {
    for (const b of unitsBox.querySelectorAll('.seg')) {
      const on = b.dataset.unit === unit.id;
      b.setAttribute('aria-checked', String(on));
      b.classList.toggle('on', on);
    }
  }
  function applyUnit(id, notify) {
    unit = unitList.find((u) => u.id === id) || unitList[0];
    saveUnitId(unit.id);
    for (const f of Object.values(unitFields)) f.setFactor(unit.km_per_unit);
    renderUnitLabels();
    syncUnitButtons();
    for (const w of ['a', 'b']) searches[w].setNearest(nearestData[w], unit);
    if (notify) handlers.onUnitsChanged(unit);
  }

  // ----- options
  function numberField(key, label, step, min, { max = null, empty = false, placeholder = null, kind = null } = {}) {
    const input = el('input', { type: 'number', value: empty ? '' : DEFAULTS[key], step, min, max, placeholder, 'aria-label': label });
    if (kind) unitFields[key] = unitField(input, empty ? null : DEFAULTS[key]);   // before the change listener below
    input.addEventListener('change', () => handlers.onOptionsChanged());
    optionInputs[key] = input;
    const span = el('span', {}, label);
    if (kind) unitLabels[key] = { span, input, base: label, kind };
    return el('label', { class: 'field' }, span, input);
  }
  /** Labels of the unit-aware fields: 'Cruise speed (mph)'. */
  function renderUnitLabels() {
    for (const { span, input, base, kind } of Object.values(unitLabels)) {
      const text = `${base} (${kind === 'speed' ? unit.speed_label : unit.label})`;
      span.textContent = text;
      input.setAttribute('aria-label', text);
    }
  }
  const dateInput = el('input', { type: 'date', value: todayISO(), min: DATE_MIN, max: DATE_MAX, 'aria-label': 'Date for sun and time-zone metrics' });
  dateInput.addEventListener('change', () => handlers.onOptionsChanged());
  optionInputs.date = dateInput;

  const returnBox = el('input', { type: 'checkbox', 'aria-label': 'Include return trip' });
  returnBox.addEventListener('change', () => handlers.onOptionsChanged());

  const options = el('details', { class: 'section' },
    el('summary', {}, 'Options'),
    el('div', { class: 'options-grid' },
      numberField('cruise_kmh', 'Cruise speed', 10, 1, { kind: 'speed' }),
      numberField('climb_descent_min', 'Climb & descent (min)', 5, 0),
      numberField('taxi_min', 'Taxiing, both ends (min)', 5, 0),
      el('label', { class: 'field' }, el('span', {}, 'Date (sun & time zones)'), dateInput),
      numberField('height_a_m', 'Eye height A (m)', 1, 0),
      numberField('height_b_m', 'Eye height B (m)', 1, 0),
      numberField('project_bearing_deg', 'Project from A: bearing (°)', 1, 0, { max: 360, empty: true, placeholder: '0–360' }),
      numberField('project_km', 'Project from A: distance', 100, 0, { empty: true, placeholder: 'e.g. 1000', kind: 'dist' }),
      el('label', { class: 'field field-check' }, returnBox, el('span', {}, 'Include return trip (B → A)'))),
    el('p', { class: 'options-hint' },
      'Fill both "Project from A" fields to see where you end up from A on a bearing after a distance (card "Destination from A", drawn on the globe).'),
    el('p', { class: 'options-note' },
      'Date: 1 Jan 1970 to 31 Dec 2049. Time zones follow today\'s rules; future political decisions cannot be predicted, so later dates assume the current rules continue.'));

  // ----- search boxes (airport / city) under each coordinate row
  for (const w of ['a', 'b']) {
    searches[w] = createSearch(w, (p) => {
      current[w] = { lat: p.lat, lon: p.lon };
      renderCoordFields();
      handlers.onCoordsEdited(w, { lat: p.lat, lon: p.lon });
    });
  }

  // ----- results
  const warningsBox = el('div', { class: 'warnings', hidden: true });
  const results = el('div', { class: 'results' });
  const status = el('div', { class: 'status', 'aria-live': 'polite' });

  let section = null;
  const body = el('div', { class: 'panel-body' },
    el('header', { class: 'panel-head' },
      el('h1', {}, 'Great Circle Explorer'),
      el('p', {}, 'Click the globe to place A, then B — or type coordinates.')),
    section = el('section', { class: 'section' },
      inputModeBox, modeToggle, unitsBox, coordRow('a'), searches.a.root, courseBox, coordRow('b'), searches.b.root,
      el('div', { class: 'row-buttons' }, swapBtn, resetBtn, wizardBtn),
      el('div', { class: 'row-buttons' }, copyBtn, exportBtn)),
    options, status, warningsBox, results,
    el('footer', { class: 'disclaimer' }, 'Spherical Earth model, R = 6371.0088 km. Click a metric to see how it is calculated. For learning and exploration only: not for navigation or any real-life decision.'));

  root.append(body);
  syncModeButtons();
  renderCoordFields();
  renderUnitLabels();
  syncInputMode();

  // ----- public API
  function setPoints(a, b) {
    current.a = a;
    current.b = b;
    renderCoordFields();
  }

  function getOptions() {
    const o = {};
    for (const k of ['climb_descent_min', 'taxi_min', 'height_a_m', 'height_b_m']) {
      const v = optionInputs[k].valueAsNumber;
      if (Number.isFinite(v) && v >= 0) o[k] = v;
    }
    const speedKmh = unitFields.cruise_kmh.getKm();
    if (speedKmh != null && speedKmh > 0) o.cruise_kmh = speedKmh;
    o.units = unit.id;
    if (optionInputs.date.value) o.date = optionInputs.date.value;
    const bearing = optionInputs.project_bearing_deg.valueAsNumber;
    const distance = unitFields.project_km.getKm() ?? NaN;
    if (Number.isFinite(bearing) && Number.isFinite(distance) && bearing >= 0 && bearing <= 360 && distance >= 0) {
      o.project_bearing_deg = bearing;
      o.project_km = distance;
    }
    if (returnBox.checked) o.include_return = true;
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
  /** Units from the backend: builds the toggle and restores the remembered choice (no recalculation). */
  function setUnits(list) {
    unitList = list;
    unitsBox.replaceChildren(
      el('span', { class: 'coord-mode-label' }, 'Distance units'),
      el('div', { class: 'segmented', role: 'radiogroup', 'aria-label': 'Distance units' }, list.map((u) => {
        const b = el('button', { type: 'button', class: 'seg', role: 'radio', 'data-unit': u.id, title: `${u.label}, speeds in ${u.speed_label}` }, u.label);
        b.addEventListener('click', () => { if (u.id !== unit.id) applyUnit(u.id, true); });
        return b;
      })));
    unitsBox.hidden = false;
    applyUnit(loadUnitId(), false);
  }

  /** Nearest airport / city hint under point `which` (data from /api/nearest, or null). */
  function setNearest(which, data) {
    nearestData[which] = data;
    searches[which].setNearest(data, unit);
  }

  /** Show the place of a point that was set on the map (an airport dot), or empty the box when it was not a place. */
  function setSearchText(which, text) {
    searches[which].clear(text || '');
  }

  /** Reset: empty both airport/city search boxes. */
  function clearSearch() {
    for (const w of ['a', 'b']) searches[w].clear();
  }

  /** Reset: empty the course and distance of the Start + course mode. */
  function clearCourse() {
    bearingInput.value = '';
    optionInputs.course_km.value = '';
    optionInputs.course_km.dispatchEvent(new Event('change'));      // lets the unit field forget its value
  }

  /** The shared date changed elsewhere (the Night picker). */
  function setDate(date) {
    if (date) optionInputs.date.value = date;
  }

  /** Short confirmation on a button ("Link copied ✓"). */
  function flash(button, text) {
    const old = button.textContent;
    button.textContent = text;
    setTimeout(() => { button.textContent = old; }, 1600);
  }

  /** Inverse mode input: { bearing_deg, km } or null while a field is empty or invalid. */
  function getCourse() {
    const bearing = bearingInput.valueAsNumber;
    const km = unitFields.course_km.getKm();
    return Number.isFinite(bearing) && bearing >= 0 && bearing <= 360 && km != null && km >= 0 ? { bearing_deg: bearing, km } : null;
  }
  function setCourse(bearing, km) {
    bearingInput.value = String(bearing);
    optionInputs.course_km.value = String(Number((km / unit.km_per_unit).toFixed(6)));      // exact enough: nothing is rounded away
    optionInputs.course_km.dispatchEvent(new Event('change'));       // lets the unit field take the value
  }

  return { setSearchText, setPoints, setResult, setLoading, getOptions, setUnits, setNearest, flash, getCourse, setCourse, setInputMode,
    clearSearch, clearCourse, setDate,
    getInputMode: () => inputMode, getUnit: () => unit, getMode: () => mode };
}
