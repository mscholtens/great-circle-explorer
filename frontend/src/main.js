// Wires map, panel, API and pop-up together. All geodesy lives in the Python backend.
import { calculate, health } from './api.js';
import { RECALC_DEBOUNCE_MS } from './config.js';
import { createMap } from './map.js';
import { createPanel } from './panel.js';
import { createPopup } from './popup.js';
import { createWizard } from './wizard.js';
import './styles.css';

const state = { a: null, b: null };
let seq = 0;
let timer = null;
let healthTimer = null;

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
    [state.a, state.b] = [state.b, state.a];
    sync();
    schedule();
  },
  onReset() {
    state.a = state.b = null;
    sync();
    schedule();
  },
  onOpenWizard: (buttonEl) => wizard.open(buttonEl),
  onOptionsChanged: () => schedule(),
  onToggle: (name, on) => globe.setVisible(name, on),
  onOpenMetric: (metric, cardEl) => popup.open(metric, cardEl),
});

const globe = createMap(document.getElementById('map'), {
  onMapClick(p) {
    if (!state.a) state.a = p;
    else if (!state.b) state.b = p;
    else { state.a = p; state.b = null; }   // third click starts over
    sync();
    schedule();
  },
  onPointMoved(which, p) {
    state[which] = p;
    sync();
    schedule();
  },
});

const wizard = createWizard(document.getElementById('popup-root'), {
  getMode: () => panel.getMode(),
  getPoint: (which) => state[which],
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
  clearTimeout(timer);
  if (!(state.a && state.b)) {
    seq++;                         // drop any in-flight response
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
    const result = await calculate(state.a, state.b, panel.getOptions());
    if (mine !== seq) return;      // a newer request superseded this one
    hideBanner();
    panel.setResult(result);
    globe.setResult(result);
  } catch (err) {
    if (mine !== seq) return;
    showBanner(err.message, err.unreachable);
  } finally {
    if (mine === seq) panel.setLoading(false);
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

health().catch((err) => showBanner(err.message, true));
