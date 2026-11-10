// Explanation pop-up: formulas (KaTeX), substituted formulas, results, constants, notes.
import { buildConstants, buildNotes, buildSteps } from './explanation.js';
import { el, explanationToText } from './format.js';
import { showModal } from './modal.js';

const HIDDEN_KEY = 'gce.analysis.hidden';

export function createPopup(root) {
  let modal = null;
  // ids of the distance-analysis rows the user switched off (kept in this browser only; empty = show all)
  let hidden = new Set();
  try { hidden = new Set(JSON.parse(localStorage.getItem(HIDDEN_KEY) || '[]')); } catch (_) { /* no storage: show all */ }
  const saveHidden = () => { try { localStorage.setItem(HIDDEN_KEY, JSON.stringify([...hidden])); } catch (_) { /* ignore */ } };

  function close() {
    if (modal) modal.close();
  }

  async function copyText(text, button) {
    try {
      await navigator.clipboard.writeText(text);
    } catch (_) {
      const ta = el('textarea', { style: 'position:fixed;opacity:0' });
      ta.value = text;
      document.body.append(ta);
      ta.select();
      document.execCommand('copy');
      ta.remove();
    }
    const old = button.textContent;
    button.textContent = 'Copied ✓';
    setTimeout(() => { button.textContent = old; }, 1500);
  }

  /** back: optional function; adds a "← back" button (used to return to the distance analysis). */
  function open(metric, opener, { back = null, backLabel = '← Back' } = {}) {
    close();
    const returnFocus = opener || document.activeElement;
    const ex = metric.explanation;

    const stepList = buildSteps(ex, metric.id);
    const constants = buildConstants(ex);
    const notes = buildNotes(ex);

    const copyBtn = el('button', { class: 'btn', type: 'button' }, 'Copy as text');
    copyBtn.addEventListener('click', () => copyText(explanationToText(metric), copyBtn));
    const closeBtn = el('button', { class: 'icon-btn', type: 'button', 'aria-label': 'Close' }, '✕');
    closeBtn.addEventListener('click', close);
    const backBtn = back ? el('button', { class: 'btn', type: 'button' }, backLabel) : null;
    if (backBtn) backBtn.addEventListener('click', () => { close(); back(); });

    const dialog = el('div', {
      class: 'dialog', role: 'dialog', 'aria-modal': 'true', 'aria-labelledby': 'dialog-title', tabindex: '-1',
    },
    el('header', { class: 'dialog-head' },
      el('div', {},
        el('div', { class: 'dialog-group' }, metric.group),
        el('h2', { id: 'dialog-title' }, metric.label),
        el('div', { class: 'dialog-value' }, metric.display)),
      closeBtn),
    el('div', { class: 'dialog-body' },
      el('p', { class: 'summary' }, ex.summary),
      stepList, constants, notes),
    el('footer', { class: 'dialog-foot' }, el('span', { class: 'foot-buttons' }, backBtn, copyBtn), el('span', { class: 'muted' }, 'Esc to close')));

    modal = showModal(root, dialog, { returnFocus, initialFocus: closeBtn, onClose: () => { modal = null; } });
  }

  /**
   * The distance analysis: one row per way of measuring the distance, with a bar, the difference to the reference
   * and a click that opens the calculation (with a way back). metrics = all metrics of the current result.
   */
  function openAnalysis(metric, opener, metrics) {
    close();
    const returnFocus = opener || document.activeElement;
    const an = metric.analysis;
    const shown = an.rows.filter((r) => r.is_reference || !hidden.has(r.id));
    const longest = Math.max(...shown.map((r) => r.km || 0), 1);
    const again = () => openAnalysis(metric, opener, metrics);
    const ref = an.rows.find((r) => r.is_reference);
    const refPct = ref && ref.km ? (ref.km / longest) * 100 : null;   // a white tick on every bar marks the reference length

    const rowButton = (r) => {
      const pct = r.km == null ? 0 : (r.km / longest) * 100;
      const b = el('button', {
        type: 'button', class: `an-row${r.is_reference ? ' reference' : ''}`,
        'aria-label': `${r.label}: ${r.display}${r.diff_display ? ', ' + r.diff_display : ''}. Show calculation.`,
      },
      el('span', { class: 'an-name' }, el('strong', {}, r.label),
        el('span', { class: `an-model ${r.model}`, title: r.model === 'ellipsoid' ? 'Assumes the flattened WGS84 Earth' : 'Assumes a perfectly round Earth' }, r.model),
        (r.badges || []).map((b) => el('span', { class: `an-badge ${b}` }, b)), el('small', {}, r.what)),
      el('span', { class: 'an-bar', 'aria-hidden': 'true', style: refPct == null ? '' : `--ref:${refPct.toFixed(2)}%` }, el('i', { style: `width:${pct.toFixed(2)}%` })),
      el('span', { class: 'an-km' }, r.display),
      el('span', { class: `an-diff${r.diff_pct == null ? '' : r.diff_pct > 0.005 ? ' over' : r.diff_pct < -0.005 ? ' under' : ''}` },
        r.diff_display || '', r.vs_sphere_display ? el('small', { class: 'an-vs' }, r.vs_sphere_display) : null));
      b.addEventListener('click', () => {
        const target = r.metric_id
          ? metrics.find((m) => m.id === r.metric_id)
          : { id: r.id, group: 'Geometry', label: r.label, display: r.display, secondary: [], explanation: r.explanation };
        if (target) open(target, null, { back: again, backLabel: '← Distance analysis' });
      });
      return b;
    };

    const text = () => [metric.label, ...an.rows.map((r) => `${r.label} [${r.model}]: ${r.display}${r.diff_display ? ` (${r.diff_display})` : ''}${r.vs_sphere_display ? `, ${r.vs_sphere_display}` : ''}`), '', ...(an.summary || []), ...(an.footnotes || []), '', ...metric.explanation.notes].join('\n');
    const copyBtn = el('button', { class: 'btn', type: 'button' }, 'Copy as text');
    copyBtn.addEventListener('click', () => copyText(text(), copyBtn));
    const closeBtn = el('button', { class: 'icon-btn', type: 'button', 'aria-label': 'Close' }, '✕');
    closeBtn.addEventListener('click', close);
    const chooseBtn = el('button', { class: 'btn', type: 'button' }, 'Choose distances…');
    chooseBtn.addEventListener('click', () => { close(); openChooser(metric, again); });

    const dialog = el('div', {
      class: 'dialog analysis', role: 'dialog', 'aria-modal': 'true', 'aria-labelledby': 'dialog-title', tabindex: '-1',
    },
    el('header', { class: 'dialog-head' },
      el('div', {},
        el('div', { class: 'dialog-group' }, metric.group),
        el('h2', { id: 'dialog-title' }, metric.label),
        el('div', { class: 'dialog-value' }, `${metric.display}`)),
      closeBtn),
    el('div', { class: 'dialog-body' },
      el('p', { class: 'summary' }, `${metric.explanation.summary} Differences are relative to the ${an.reference_label}. Click a row to see how it is calculated.`),
      el('div', { class: 'an-tools' },
        el('span', { class: 'muted' }, `Showing ${shown.length} of ${an.rows.length} distances`), chooseBtn),
      el('div', { class: 'an-list', role: 'group', 'aria-label': 'Ways to measure the distance' }, shown.map(rowButton)),
      an.summary && an.summary.length
        ? el('section', { class: 'an-summary' }, el('h3', {}, 'What changes the answer'), an.summary.map((t) => el('p', {}, t)))
        : null,
      an.footnotes && an.footnotes.length ? el('p', { class: 'an-foot' }, an.footnotes.map((t) => el('span', {}, t))) : null,
      buildNotes({ ...metric.explanation, notes: metric.explanation.notes.filter((n) => !an.footnotes.includes(n) && !an.summary.includes(n)) })),
    el('footer', { class: 'dialog-foot' }, copyBtn, el('span', { class: 'muted' }, 'Esc to close')));

    modal = showModal(root, dialog, { returnFocus, initialFocus: closeBtn, onClose: () => { modal = null; } });
  }

  /** Second window: a check box for every available distance. The reference is always shown (the differences refer to it). */
  function openChooser(metric, back) {
    const an = metric.analysis;
    const boxes = an.rows.map((r) => {
      const input = el('input', { type: 'checkbox' });
      input.checked = r.is_reference || !hidden.has(r.id);
      input.disabled = !!r.is_reference;
      input.addEventListener('change', () => {
        if (input.checked) hidden.delete(r.id); else hidden.add(r.id);
        saveHidden();
        count.textContent = `${boxes.filter((b) => b.input.checked).length} of ${boxes.length} shown`;
      });
      const label = el('label', { class: 'pick-row' }, input,
        el('span', { class: 'pick-text' }, el('strong', {}, r.label),
          r.is_reference ? el('span', { class: 'an-badge' }, 'reference · always shown') : null,
          el('small', {}, `${r.display} · ${r.what}`)));
      return { input, label, r };
    });
    const count = el('span', { class: 'muted' }, `${boxes.filter((b) => b.input.checked).length} of ${boxes.length} shown`);
    const setAll = (on) => {
      boxes.forEach((b) => { if (!b.r.is_reference) { b.input.checked = on; if (on) hidden.delete(b.r.id); else hidden.add(b.r.id); } });
      saveHidden();
      count.textContent = `${boxes.filter((b) => b.input.checked).length} of ${boxes.length} shown`;
    };
    const allBtn = el('button', { class: 'btn', type: 'button' }, 'Select all');
    allBtn.addEventListener('click', () => setAll(true));
    const noneBtn = el('button', { class: 'btn', type: 'button' }, 'Select none');
    noneBtn.addEventListener('click', () => setAll(false));
    const doneBtn = el('button', { class: 'btn btn-primary', type: 'button' }, 'Done');
    doneBtn.addEventListener('click', close);
    const closeBtn = el('button', { class: 'icon-btn', type: 'button', 'aria-label': 'Close' }, '✕');
    closeBtn.addEventListener('click', close);

    const dialog = el('div', { class: 'dialog chooser', role: 'dialog', 'aria-modal': 'true', 'aria-labelledby': 'dialog-title', tabindex: '-1' },
      el('header', { class: 'dialog-head' },
        el('div', {}, el('div', { class: 'dialog-group' }, metric.label), el('h2', { id: 'dialog-title' }, 'Choose distances')), closeBtn),
      el('div', { class: 'dialog-body' },
        el('p', { class: 'summary' }, 'Tick the distances to show in the table. The choice is remembered in this browser.'),
        el('div', { class: 'pick-tools' }, allBtn, noneBtn, count),
        el('div', { class: 'pick-list' }, boxes.map((b) => b.label))),
      el('footer', { class: 'dialog-foot' }, doneBtn, el('span', { class: 'muted' }, 'Esc to go back')));
    // every way of leaving this window (Done, ✕, Esc, backdrop) returns to the table
    modal = showModal(root, dialog, { returnFocus: null, initialFocus: doneBtn, onClose: () => { modal = null; back(); } });
  }

  return { open, openAnalysis, close };
}
