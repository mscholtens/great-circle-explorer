// PDF export: a form to choose what goes into the report, then a clean printable page and the browser's print dialog
// ("Save as PDF" as the destination). Vector output, so the KaTeX formulas stay sharp. Fully offline.
import { buildConstants, buildNotes, buildSteps } from './explanation.js';
import { el, formatCoord } from './format.js';
import { showModal } from './modal.js';

const STORE_KEY = 'gce.export';

function loadPrefs() {
  try { return JSON.parse(localStorage.getItem(STORE_KEY)) || {}; } catch (_) { return {}; }
}
function savePrefs(p) {
  try { localStorage.setItem(STORE_KEY, JSON.stringify(p)); } catch (_) { /* storage unavailable */ }
}

/**
 * ctx: { getResult(), getState() -> {a, b}, getOptions(), getMode(), getUnit(), getCourse() -> {bearing_deg, km}|null, getMapImage() }
 * returns { open(openerButton) }
 */
export function createReport(root, ctx) {
  let modal = null;

  function message(text, opener) {
    const okBtn = el('button', { class: 'btn btn-primary', type: 'button' }, 'OK');
    const dialog = el('div', { class: 'dialog export', role: 'dialog', 'aria-modal': 'true', 'aria-labelledby': 'export-title', tabindex: '-1' },
      el('header', { class: 'dialog-head' }, el('h2', { id: 'export-title' }, 'Export PDF')),
      el('div', { class: 'dialog-body' }, el('p', {}, text)),
      el('footer', { class: 'dialog-foot' }, okBtn));
    modal = showModal(root, dialog, { returnFocus: opener, initialFocus: okBtn, onClose: () => { modal = null; } });
    okBtn.addEventListener('click', () => modal.close());
  }

  function open(opener) {
    if (modal) modal.close();
    const result = ctx.getResult();
    if (!result) { message('Place both points A and B first, then export the results.', opener); return; }

    const prefs = loadPrefs();
    const hidden = new Set(prefs.hidden || []);
    const titleInput = el('input', { type: 'text', value: prefs.title || 'Great Circle Explorer', 'aria-label': 'Report title', maxlength: '100' });
    const fullBox = el('input', { type: 'checkbox', id: 'exp-full' });
    fullBox.checked = !!prefs.full;
    const mapBox = el('input', { type: 'checkbox', id: 'exp-map' });
    mapBox.checked = prefs.map !== false;

    const metricBoxes = [];
    const groups = [];
    for (const m of result.metrics) {
      let g = groups.find((x) => x.name === m.group);
      if (!g) groups.push((g = { name: m.group, items: [] }));
      g.items.push(m);
    }
    const createBtn = el('button', { class: 'btn btn-primary', type: 'button' }, 'Create PDF…');
    const count = el('span', { class: 'muted', 'aria-live': 'polite' });
    const sync = () => {
      const n = metricBoxes.filter((b) => b.input.checked).length;
      createBtn.disabled = n === 0;
      count.textContent = `${n} of ${metricBoxes.length} selected`;
    };
    const groupNodes = groups.map((g) => el('fieldset', { class: 'exp-group' },
      el('legend', {}, g.name),
      g.items.map((m) => {
        const input = el('input', { type: 'checkbox' });
        input.checked = !hidden.has(m.id);
        input.addEventListener('change', sync);
        metricBoxes.push({ id: m.id, input });
        return el('label', { class: 'exp-check' }, input, el('span', {}, m.label));
      })));
    const setAll = (on) => { metricBoxes.forEach((b) => { b.input.checked = on; }); sync(); };
    const allBtn = el('button', { class: 'btn btn-small', type: 'button' }, 'All');
    const noneBtn = el('button', { class: 'btn btn-small', type: 'button' }, 'None');
    allBtn.addEventListener('click', () => setAll(true));
    noneBtn.addEventListener('click', () => setAll(false));
    sync();

    const cancelBtn = el('button', { class: 'btn', type: 'button' }, 'Cancel');
    const closeBtn = el('button', { class: 'icon-btn', type: 'button', 'aria-label': 'Close' }, '✕');
    const dialog = el('div', { class: 'dialog export', role: 'dialog', 'aria-modal': 'true', 'aria-labelledby': 'export-title', tabindex: '-1' },
      el('header', { class: 'dialog-head' },
        el('div', {}, el('div', { class: 'dialog-group' }, 'Report'), el('h2', { id: 'export-title' }, 'Export PDF')), closeBtn),
      el('div', { class: 'dialog-body' },
        el('label', { class: 'field exp-title' }, el('span', {}, 'Title'), titleInput),
        el('div', { class: 'exp-options' },
          el('label', { class: 'exp-check' }, fullBox, el('span', {}, 'Include the full calculation (steps, formulas, constants and notes)')),
          el('label', { class: 'exp-check' }, mapBox, el('span', {}, 'Include a picture of the map'))),
        el('div', { class: 'exp-bar' }, el('h3', {}, 'Metrics to include'), el('div', { class: 'exp-bar-buttons' }, allBtn, noneBtn)),
        el('div', { class: 'exp-groups' }, groupNodes),
        el('p', { class: 'wiz-help' }, 'A print dialog opens next. Choose "Save as PDF" as the destination.')),
      el('footer', { class: 'dialog-foot' }, count, el('span', { class: 'exp-foot-buttons' }, cancelBtn, createBtn)));

    modal = showModal(root, dialog, { returnFocus: opener, initialFocus: titleInput, onClose: () => { modal = null; } });
    closeBtn.addEventListener('click', () => modal.close());
    cancelBtn.addEventListener('click', () => modal.close());
    createBtn.addEventListener('click', async () => {
      const choice = {
        title: titleInput.value.trim() || 'Great Circle Explorer',
        ids: new Set(metricBoxes.filter((b) => b.input.checked).map((b) => b.id)),
        full: fullBox.checked,
        withMap: mapBox.checked,
      };
      savePrefs({ title: choice.title, full: choice.full, map: choice.withMap, hidden: metricBoxes.filter((b) => !b.input.checked).map((b) => b.id) });
      modal.close();
      await printReport(buildReport(result, choice));
    });
  }

  /** The report as a DOM tree (id "print-root"); only visible when printing. */
  function buildReport(result, choice) {
    const mode = ctx.getMode();
    const unit = ctx.getUnit();
    const opts = ctx.getOptions();
    const coord = (p) => `${formatCoord(p.lat, 'lat', mode)}, ${formatCoord(p.lon, 'lon', mode)}`;
    const decimal = (p) => `${p.lat.toFixed(5)}°, ${p.lon.toFixed(5)}°`;
    const speed = opts.cruise_kmh != null ? `${Number((opts.cruise_kmh / unit.km_per_unit).toPrecision(5))} ${unit.speed_label}` : null;
    const optionLines = [
      speed && `Cruise speed ${speed}`,
      opts.climb_descent_min != null && `climb & descent ${opts.climb_descent_min} min`,
      opts.taxi_min != null && `taxiing ${opts.taxi_min} min`,
      opts.date && `date ${opts.date}`,
      opts.height_a_m != null && `eye heights ${opts.height_a_m} m (A), ${opts.height_b_m} m (B)`,
      opts.project_km != null && `projection from A: bearing ${opts.project_bearing_deg}°, ${Number((opts.project_km / unit.km_per_unit).toPrecision(5))} ${unit.label}`,
      `distances in ${unit.label}`,
    ].filter(Boolean).join(' · ');

    const course = ctx.getCourse();
    const image = choice.withMap ? ctx.getMapImage() : null;
    const groups = [];
    for (const m of result.metrics) {
      if (!choice.ids.has(m.id)) continue;
      let g = groups.find((x) => x.name === m.group);
      if (!g) groups.push((g = { name: m.group, items: [] }));
      g.items.push(m);
    }

    const metricNode = (m) => {
      const node = el('article', { class: `rep-metric${choice.full ? ' rep-full' : ''}` },
        el('h3', {}, m.label),
        el('div', { class: 'rep-value' }, m.display),
        m.secondary.length ? el('div', { class: 'rep-secondary' }, m.secondary.map((s) => el('span', {}, s))) : null,
        m.table ? el('table', { class: 'rep-table' }, el('tbody', {}, m.table.map((r) => el('tr', {}, el('th', { scope: 'row' }, r.label), el('td', {}, r.display))))) : null);
      if (choice.full) {
        const ex = m.explanation;
        node.append(el('div', { class: 'rep-expl' },
          el('p', { class: 'summary' }, ex.summary), buildSteps(ex, m.id), buildConstants(ex), buildNotes(ex)));
      }
      return node;
    };

    return el('div', { id: 'print-root' },
      el('header', { class: 'rep-head' },
        el('h1', {}, choice.title),
        el('p', { class: 'rep-meta' }, `Created ${new Date().toLocaleString()}`)),
      el('section', { class: 'rep-points' },
        el('table', { class: 'rep-table' }, el('tbody', {},
          el('tr', {}, el('th', { scope: 'row' }, 'Point A'), el('td', {}, coord(result.a), el('span', { class: 'muted' }, `  (${decimal(result.a)})`))),
          el('tr', {}, el('th', { scope: 'row' }, course ? 'Point B (calculated)' : 'Point B'), el('td', {}, coord(result.b), el('span', { class: 'muted' }, `  (${decimal(result.b)})`))))),
        course ? el('p', { class: 'rep-options' }, `B is the destination from A on course ${course.bearing_deg}° (true north = 0°) after ${Number((course.km / unit.km_per_unit).toPrecision(5))} ${unit.label}.`) : null,
        el('p', { class: 'rep-options' }, optionLines)),
      image ? el('figure', { class: 'rep-map' }, el('img', { src: image, alt: 'Map with the route between A and B' })) : null,
      result.warnings.length ? el('section', { class: 'rep-warnings' }, result.warnings.map((w) => el('p', {}, '⚠ ' + w))) : null,
      groups.map((g) => el('section', { class: 'rep-group' }, el('h2', {}, g.name), g.items.map(metricNode))),
      el('footer', { class: 'rep-foot' }, 'Spherical Earth model, R = 6371.0088 km. Calculated offline by Great Circle Explorer, a project for learning and exploration only: not for navigation or any real-life decision. See docs/ACCURACY.md for the accuracy and assumptions.'));
  }

  /** Put the report in the page, wait for fonts and images, open the print dialog, remove the report afterwards. */
  async function printReport(node) {
    document.getElementById('print-root')?.remove();
    // Lay the report out off-screen first: the browser only loads the KaTeX fonts once text that uses them is laid out,
    // and the print dialog must not open before they are there (formulas would print without symbols).
    node.classList.add('measuring');
    document.body.append(node);
    await Promise.all([...node.querySelectorAll('img')].map((img) => img.decode().catch(() => {})));
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    if (document.fonts && document.fonts.ready) await document.fonts.ready;
    node.classList.remove('measuring');
    const cleanup = () => {
      node.remove();
      window.removeEventListener('afterprint', cleanup);
    };
    window.addEventListener('afterprint', cleanup);
    window.print();
  }

  return { open };
}
