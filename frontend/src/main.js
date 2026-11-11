// Wires map, panel, API and pop-up together. All geodesy lives in the Python backend.
import { airports, calculate, health, nearest, terminator, units } from './api.js';
import { RECALC_DEBOUNCE_MS } from './config.js';
import { formatCoord, wrapLon } from './format.js';
import { createMap } from './map.js';
import { createPanel } from './panel.js';
import { createPopup } from './popup.js';
import { createReport } from './report.js';
import { buildHash, parseHash } from './share.js';
import { createToolbar } from './toolbar.js';
import { createWizard } from './wizard.js';
import './styles.css';

const state = { a: null, b: null };
let seq = 0;
let timer = null;
let healthTimer = null;
let nightSeq = 0;
let lastResult = null;
const nearestKey = { a: null, b: null };
const nearestSeq = { a: 0, b: 0 };
// Distance units come from the backend; the first calculation waits for them (and goes on without them if the backend is down).
const unitsReady = units().then((list) => { panel.setUnits(list); toolbar.setUnit(panel.getUnit()); }).catch(() => {});

const banner = document.getElementById('banner');
const popup = createPopup(document.getElementById('popup-root'));

const panel = createPanel(document.getElementById('panel'), {
  onCoordsEdited(which, p) {
    state[which] = p;
    globe.setPoint(which, p);
    globe.map.easeTo({ center: [p.lon, p.lat], duration: 600 });
    schedule();
  },
  onSwap() {
    if (panel.getInputMode() === 'course') return;
    [state.a, state.b] = [state.b, state.a];
    sync();
    schedule();
  },
  onReset() {
    state.a = state.b = null;
    panel.clearSearch();                 // the airport/city boxes
    panel.clearCourse();                 // course and distance of the Start + course mode
    sync();
    schedule();
  },
  onOpenWizard: (buttonEl) => wizard.open(buttonEl),
  onOptionsChanged: () => { toolbar.setDate(panel.getOptions().date); schedule(); refreshNight(); },
  onInputModeChanged(mode) {
    globe.setCourseMode(mode === 'course');
    if (mode === 'course') state.b = null;           // B is calculated from now on; going back keeps the calculated B as a normal point
    sync();
    schedule();
  },
  onUnitsChanged(unit) {
    toolbar.setUnit(unit);
    schedule();
  },
  onCopyLink: (btn) => copyLink(btn),
  onOpenExport: (btn) => report.open(btn),
  onOpenMetric: (metric, cardEl) => (metric.analysis ? popup.openAnalysis(metric, cardEl, lastResult ? lastResult.metrics : []) : popup.open(metric, cardEl)),
});

const toolbarRoot = document.createElement('div');
toolbarRoot.className = 'map-toolbar';
document.body.append(toolbarRoot);
const toolbar = createToolbar(toolbarRoot, {
  onToggle(name, on) {
    if (name === 'night') refreshNight();
    else if (name === 'airports') toggleAirports(on);
    else globe.setVisible(name, on);
  },
  onDateChanged(date) {                          // the shared date, changed in the Night picker
    panel.setDate(date);
    schedule();
    refreshNight();
  },
  onCircleChanged: () => schedule(),
  onNightChanged: () => refreshNight(),
  onProjection: (type) => globe.setProjection(type),
});

const globe = createMap(document.getElementById('map'), {
  onMapClick({ label, ...p }) {
    // an airport clicked on the map fills the search box of that point, like a search would; any other click empties it
    if (panel.getInputMode() === 'course') { state.a = p; panel.setSearchText('a', label); }      // inverse mode: a click moves the start point
    else if (!state.a) { state.a = p; panel.setSearchText('a', label); }
    else if (!state.b) { state.b = p; panel.setSearchText('b', label); }
    else { state.a = p; state.b = null; panel.setSearchText('a', label); panel.setSearchText('b'); }   // third click starts over
    sync();
    schedule();
  },
  onPointClicked(which) {                // clicking a placed point again removes it, so it can be chosen anew
    const inverse = panel.getInputMode() === 'course';
    if (inverse && which === 'b') return;          // B is calculated in this mode
    state[which] = null;
    if (inverse) state.b = null;
    panel.setSearchText(which);
    sync();
    schedule();
  },
  onPointMoved(which, p) {
    state[which] = p;
    panel.setSearchText(which);           // a dragged pin is no longer the searched place
    sync();
    schedule();
  },
});

const report = createReport(document.getElementById('popup-root'), {
  getResult: () => lastResult,
  getState: () => state,
  getOptions: () => ({ ...panel.getOptions(), ...toolbar.getOptions() }),
  getMode: () => panel.getMode(),
  getUnit: () => panel.getUnit(),
  getCourse: () => (panel.getInputMode() === 'course' ? panel.getCourse() : null),
  getMapImage: () => globe.getImage(),
});

const wizard = createWizard(document.getElementById('popup-root'), {
  getMode: () => panel.getMode(),
  getInputMode: () => panel.getInputMode(),
  getCourse: () => panel.getCourse(),
  getUnit: () => panel.getUnit(),
  getPoint: (which) => state[which],
  onApplyCourse(a, bearing, km) {               // wizard, inverse mode: start point + course + distance
    panel.setInputMode('course', false);
    globe.setCourseMode(true);
    panel.setCourse(bearing, km);
    state.a = a;
    state.b = null;
    sync();
    globe.map.easeTo({ center: [a.lon, a.lat], duration: 600 });
    schedule();
  },
  onApply(which, p) {
    state[which] = p;
    sync();
    globe.map.easeTo({ center: [p.lon, p.lat], duration: 600 });
    schedule();
  },
});

function sync() {
  globe.setPoint('a', state.a);
  globe.setPoint('b', state.b);
  panel.setPoints(state.a, state.b);
}

function schedule() {
  const inverse = panel.getInputMode() === 'course';
  const course = inverse ? panel.getCourse() : null;
  if (inverse && !course && state.b) {          // incomplete course: the calculated B is no longer valid
    state.b = null;
    sync();
  }
  refreshNearest('a');
  refreshNearest('b');
  updateHash();
  clearTimeout(timer);
  if (!(state.a && (inverse ? course : state.b))) {
    seq++;                         // drop any in-flight response
    lastResult = null;
    panel.setLoading(false);
    panel.setResult(null);
    globe.setResult(null);
    return;
  }
  panel.setLoading(true);
  timer = setTimeout(run, RECALC_DEBOUNCE_MS);
}

async function run() {
  const mine = ++seq;
  try {
    await unitsReady;
    if (mine !== seq) return;
    const inverse = panel.getInputMode() === 'course';
    const course = inverse ? panel.getCourse() : null;
    if (inverse && !course) return;
    const result = await calculate(state.a, inverse ? null : state.b, { ...panel.getOptions(), ...toolbar.getOptions() }, course);
    if (mine !== seq) return;      // a newer request superseded this one
    hideBanner();
    if (inverse) {                                // the backend calculated B (the destination)
      state.b = { lat: result.b.lat, lon: result.b.lon };
      sync();
      refreshNearest('b');
      updateHash();
    }
    lastResult = result;
    panel.setResult(result);
    globe.setResult(result);
    toolbar.setCircleInfo(result.circles.length ? result.circles[0].radius_km : null);
  } catch (err) {
    if (mine !== seq) return;
    showBanner(err.message, err.unreachable);
  } finally {
    if (mine === seq) panel.setLoading(false);
  }
}

/** Nearest airport and city under each point (only asked when the point has changed). */
function refreshNearest(which) {
  const p = state[which];
  const key = p ? `${p.lat.toFixed(5)},${p.lon.toFixed(5)}` : null;
  if (key === nearestKey[which]) return;
  nearestKey[which] = key;
  const mine = ++nearestSeq[which];
  if (!p) { panel.setNearest(which, null); return; }
  nearest(p.lat, p.lon)
    .then((data) => { if (mine === nearestSeq[which]) panel.setNearest(which, data); })
    .catch(() => { if (mine === nearestSeq[which]) panel.setNearest(which, null); });
}

// Share link: the points live in the URL hash (replaceState does not add history entries or fire hashchange).
function updateHash() {
  const hash = buildHash(state.a, state.b);
  if (hash !== window.location.hash) {
    window.history.replaceState(null, '', hash || window.location.pathname + window.location.search);
  }
}

function applyHash() {
  const { a, b } = parseHash(window.location.hash);
  if (!a && !b) return false;
  if (panel.getInputMode() === 'course') {      // a link holds two points: show it as such
    panel.setInputMode('two', false);
    globe.setCourseMode(false);
  }
  state.a = a;
  state.b = b;
  sync();
  schedule();
  const first = a || b;
  globe.map.easeTo({ center: [first.lon, first.lat], duration: 0 });
  return true;
}

async function copyLink(button) {
  if (!state.a && !state.b) { panel.flash(button, 'Set a point first'); return; }
  updateHash();
  const url = window.location.href;
  try {
    await navigator.clipboard.writeText(url);
  } catch (_) {
    const ta = document.createElement('textarea');
    ta.style.cssText = 'position:fixed;opacity:0';
    ta.value = url;
    document.body.append(ta);
    ta.select();
    document.execCommand('copy');
    ta.remove();
  }
  panel.flash(button, 'Link copied ✓');
}

/** Airports layer: the list is fetched once, the first time the layer is switched on. */
let airportList = null;
async function toggleAirports(on) {
  if (on && !airportList) {
    try {
      airportList = await airports();
      globe.setAirports(airportList);
    } catch (err) {
      showBanner(err.message, err.unreachable);
    }
  }
  globe.setVisible('airports', on);
}

/** Day/night shading: independent of A and B; needs the date (Options) and the UTC time (toolbar). */
async function refreshNight() {
  const { on, date, time } = toolbar.getNight();
  const mine = ++nightSeq;
  if (!on) {
    globe.setNight(null);
    toolbar.setNightInfo('');
    return;
  }
  try {
    const data = await terminator(date, time);
    if (mine !== nightSeq) return;
    hideBanner();
    globe.setNight(data);
    const m = panel.getMode();
    toolbar.setNightInfo(`Sun overhead at ${formatCoord(data.subsolar.lat, 'lat', m)}, ${formatCoord(data.subsolar.lon, 'lon', m)}`);
  } catch (err) {
    if (mine !== nightSeq) return;
    showBanner(err.message, err.unreachable);
  }
}

function showBanner(message, retry) {
  banner.textContent = '⚠ ' + message;
  banner.hidden = false;
  if (retry && !healthTimer) {
    healthTimer = setInterval(async () => {
      try {
        await health();
        hideBanner();
        if (state.a && state.b) schedule();
      } catch (_) { /* still down */ }
    }, 4000);
  }
}

function hideBanner() {
  banner.hidden = true;
  clearInterval(healthTimer);
  healthTimer = null;
}

// Panel collapse / bottom-sheet toggle
const toggleBtn = document.createElement('button');
toggleBtn.className = 'panel-toggle';
toggleBtn.type = 'button';
toggleBtn.setAttribute('aria-label', 'Toggle panel');
toggleBtn.addEventListener('click', () => {
  const collapsed = document.body.classList.toggle('panel-collapsed');
  globe.fitToPanel(collapsed);
});
document.body.append(toggleBtn);

panel.setDate(toolbar.getDate());                // the picker starts at the computer's current date and time
globe.setCourseMode(panel.getInputMode() === 'course');
health().catch((err) => showBanner(err.message, true));

// Live coordinates under the mouse pointer (bottom of the map), in the chosen coordinate format.
const readout = document.createElement('div');
readout.className = 'readout';
readout.setAttribute('aria-live', 'off');
document.body.append(readout);
const showPointer = (lngLat) => {
  if (!lngLat || !Number.isFinite(lngLat.lat) || !Number.isFinite(lngLat.lng)) { readout.textContent = ''; return; }
  const m = panel.getMode();
  readout.textContent = `Pointer: ${formatCoord(Math.max(-90, Math.min(90, lngLat.lat)), 'lat', m)}, ${formatCoord(wrapLon(lngLat.lng), 'lon', m)}`;
};
globe.map.on('mousemove', (e) => showPointer(e.lngLat));
globe.map.getCanvas().addEventListener('mouseleave', () => showPointer(null));

// Start from a share link (#a=lat,lon&b=lat,lon) and follow later changes of the hash.
globe.setProjection(toolbar.getProjection());
window.addEventListener('hashchange', () => {
  if (window.location.hash !== buildHash(state.a, state.b)) applyHash();
});
applyHash();
