// Toolbar on top of the map: layer toggles plus the day/night and circle overlays with their small controls.
import { el } from './format.js';
import { formatDistance } from './search.js';
import { DATE_MAX, DATE_MIN, fromMinutes, fromUtc, nowIn, toMinutes, toUtc } from './instant.js';
import { unitField } from './unitfield.js';

const PROJECTION_KEY = 'gce.projection';
const BASIS_KEY = 'gce.timeBasis';
const MAX_RADIUS_KM = 20015;   // half the circumference; the backend enforces it too

const LAYERS = [
  ['rhumb', 'Rhumb line', true], ['midpoint', 'Midpoint', true], ['vertex', 'Vertex', true],
  ['crossings', 'Crossings', true], ['antipodes', 'Antipodes', true],
  ['airports', 'Airports', false], ['circles', 'Equal-distance circles', false], ['night', 'Night', false],
];

/**
 * handlers: { onToggle(name, on), onCircleChanged(), onNightChanged(), onDateChanged(date), onProjection('globe'|'mercator') }
 * returns:  { getOptions(), getNight(), getProjection(), setDate(date), setNightInfo(text), setCircleInfo(radiusKm), setUnit(unit) }
 */
export function createToolbar(root, handlers) {
  const checks = {};
  const chips = LAYERS.map(([name, label, on]) => {
    const input = el('input', { type: 'checkbox' });
    input.checked = on;
    checks[name] = input;
    input.addEventListener('change', () => {
      syncExtras();
      handlers.onToggle(name, input.checked);
    });
    return el('label', { class: 'chip' }, input, el('span', {}, label));
  });

  // Night: a date, a time of day and a slider, in the computer's time (default) or in UTC. The date is the shared
  // date (the same as under Options); the backend always receives UTC.
  let basis = 'local';
  try { if (localStorage.getItem(BASIS_KEY) === 'utc') basis = 'utc'; } catch (_) { /* storage unavailable */ }
  const start = nowIn(basis);
  const dateInput = el('input', {
    type: 'date', value: start.date, min: DATE_MIN, max: DATE_MAX,
    'aria-label': 'Date (also used by the sun, moon and time-zone cards)',
  });
  const timeInput = el('input', { type: 'time', value: start.time, 'aria-label': 'Time of day' });
  const slider = el('input', { type: 'range', class: 'time-slider', min: 0, max: 1439, step: 5, value: toMinutes(start.time), 'aria-label': 'Time of day slider' });
  const utcInfo = el('span', { class: 'toolbar-label night-utc' });
  const nightInfo = el('span', { class: 'toolbar-info' });
  const basisButtons = [['local', 'My time', "The date and time on this computer's clock"], ['utc', 'UTC', 'Coordinated Universal Time']].map(([id, label, title]) => {
    const b = el('button', { type: 'button', class: 'seg', role: 'radio', 'data-basis': id, title }, label);
    b.addEventListener('click', () => switchBasis(id));
    return b;
  });
  const nowBtn = el('button', { type: 'button', class: 'btn btn-small', title: "Use this computer's current date and time" }, 'Now');
  let sliderTimer = null;

  function syncBasisButtons() {
    for (const b of basisButtons) {
      const on = b.dataset.basis === basis;
      b.setAttribute('aria-checked', String(on));
      b.classList.toggle('on', on);
    }
  }
  /** The chosen instant in UTC (what the backend gets); falls back to the current UTC time if a field is empty. */
  function currentUtc() {
    return toUtc(basis, dateInput.value, timeInput.value) || nowIn('utc');
  }
  function renderUtcInfo() {
    const u = toUtc(basis, dateInput.value, timeInput.value);
    utcInfo.textContent = u ? `= ${u.date} ${u.time} UTC` : '';
  }
  function setClock(date, time) {
    dateInput.value = date;
    timeInput.value = time;
    slider.value = String(toMinutes(time));
    renderUtcInfo();
  }

  dateInput.addEventListener('change', () => { renderUtcInfo(); handlers.onDateChanged(dateInput.value || null); });
  timeInput.addEventListener('change', () => { slider.value = String(toMinutes(timeInput.value)); renderUtcInfo(); handlers.onNightChanged(); });
  slider.addEventListener('input', () => {
    timeInput.value = fromMinutes(Number(slider.value));
    renderUtcInfo();
    clearTimeout(sliderTimer);
    sliderTimer = setTimeout(() => handlers.onNightChanged(), 120);
  });
  nowBtn.addEventListener('click', () => {
    const n = nowIn(basis);
    setClock(n.date, n.time);
    handlers.onDateChanged(n.date);
  });
  function switchBasis(id) {
    if (id === basis) return;
    const instant = currentUtc();                 // keep the same moment, shown in the other clock
    basis = id;
    try { localStorage.setItem(BASIS_KEY, id); } catch (_) { /* ignore */ }
    syncBasisButtons();
    const shown = fromUtc(basis, instant.date, instant.time);
    setClock(shown.date, shown.time);
    handlers.onDateChanged(shown.date);
  }
  syncBasisButtons();
  renderUtcInfo();

  const nightRow = el('div', { class: 'toolbar-extra night-box', hidden: true },
    el('div', { class: 'night-line' },
      el('span', { class: 'toolbar-label' }, 'Night on'), dateInput, timeInput,
      el('div', { class: 'segmented', role: 'radiogroup', 'aria-label': 'Clock' }, basisButtons), nowBtn),
    el('div', { class: 'night-line night-slider' },
      el('span', { class: 'toolbar-label' }, '00:00'), slider, el('span', { class: 'toolbar-label' }, '24:00')),
    el('div', { class: 'night-line' }, utcInfo, nightInfo));

  // Circles: radius in km (empty = the route length)
  const radiusInput = el('input', { type: 'number', min: 0, step: 'any', placeholder: 'route length', 'aria-label': 'Radius of the circles in km' });
  const radius = unitField(radiusInput);          // typed in the chosen unit, kept in km
  const radiusUnitText = el('span', { class: 'toolbar-label' });
  let unit = { id: 'km', label: 'km', speed_label: 'km/h', km_per_unit: 1 };
  let routeKm = null;
  radiusInput.addEventListener('change', () => {
    const km = radius.getKm();
    radiusInput.classList.toggle('invalid', radiusInput.value !== '' && !(km != null && km >= 0 && km <= MAX_RADIUS_KM));   // ignored until fixed
    handlers.onCircleChanged();
  });
  const circleRow = el('div', { class: 'toolbar-extra', hidden: true },
    el('span', { class: 'toolbar-label' }, 'Radius'), radiusInput, radiusUnitText);
  function renderRadiusTexts() {
    radiusInput.max = String(Number((MAX_RADIUS_KM / unit.km_per_unit).toFixed(1)));
    radiusInput.setAttribute('aria-label', `Radius of the circles in ${unit.label}`);
    radiusUnitText.textContent = `${unit.label} around A and B (empty = route length)`;
    radiusInput.placeholder = routeKm == null ? 'route length' : `route length (${formatDistance(routeKm, unit)})`;
  }
  renderRadiusTexts();

  function syncExtras() {
    nightRow.hidden = !checks.night.checked;
    circleRow.hidden = !checks.circles.checked;
  }

  // Globe | Flat: the same data on a sphere or on a flat (Mercator) map
  let projection = 'globe';
  try { if (localStorage.getItem(PROJECTION_KEY) === 'mercator') projection = 'mercator'; } catch (_) { /* storage unavailable */ }
  const projButtons = [['globe', 'Globe'], ['mercator', 'Flat']].map(([id, label]) => {
    const b = el('button', { type: 'button', class: 'seg', role: 'radio', 'data-projection': id, title: id === 'globe' ? '3D globe' : 'Flat Mercator map' }, label);
    b.addEventListener('click', () => {
      if (projection === id) return;
      projection = id;
      try { localStorage.setItem(PROJECTION_KEY, id); } catch (_) { /* ignore */ }
      syncProjection();
      handlers.onProjection(id);
    });
    return b;
  });
  function syncProjection() {
    for (const b of projButtons) {
      const on = b.dataset.projection === projection;
      b.setAttribute('aria-checked', String(on));
      b.classList.toggle('on', on);
    }
  }
  syncProjection();

  root.append(el('div', { class: 'map-toolbar-row', role: 'group', 'aria-label': 'Map layers' }, chips,
    el('div', { class: 'segmented', role: 'radiogroup', 'aria-label': 'Map view' }, projButtons)), nightRow, circleRow);
  syncExtras();

  return {
    /** Option sent to the backend. */
    getOptions() {
      const km = radius.getKm();
      return km != null && km >= 0 && km <= MAX_RADIUS_KM ? { circle_km: km } : {};
    },
    getProjection: () => projection,
    /** Distance unit chosen in the panel. */
    setUnit(u) {
      unit = u;
      radius.setFactor(u.km_per_unit);
      renderRadiusTexts();
    },
    /** { on, date, time }: the chosen moment in UTC (for /api/terminator). */
    getNight: () => ({ on: checks.night.checked, ...currentUtc() }),
    getDate: () => dateInput.value,
    /** The shared date changed elsewhere (Options): show it here too. */
    setDate(date) {
      if (date && date !== dateInput.value) { dateInput.value = date; renderUtcInfo(); }
    },
    setNightInfo(text) { nightInfo.textContent = text; },
    setCircleInfo(km) {
      routeKm = km;
      renderRadiusTexts();
    },
  };
}
