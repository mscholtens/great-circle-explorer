// Explanation pop-up: formulas (KaTeX), substituted formulas, results, constants, notes.
import { buildConstants, buildNotes, buildSteps } from './explanation.js';
import { el, explanationToText } from './format.js';
import { showModal } from './modal.js';

export function createPopup(root) {
  let modal = null;

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
    const longest = Math.max(...an.rows.map((r) => r.km || 0), 1);
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
      el('div', { class: 'an-list', role: 'group', 'aria-label': 'Ways to measure the distance' }, an.rows.map(rowButton)),
      an.summary && an.summary.length
        ? el('section', { class: 'an-summary' }, el('h3', {}, 'What changes the answer'), an.summary.map((t) => el('p', {}, t)))
        : null,
      an.footnotes && an.footnotes.length ? el('p', { class: 'an-foot' }, an.footnotes.map((t) => el('span', {}, t))) : null,
      buildNotes({ ...metric.explanation, notes: metric.explanation.notes.filter((n) => !an.footnotes.includes(n) && !an.summary.includes(n)) })),
    el('footer', { class: 'dialog-foot' }, copyBtn, el('span', { class: 'muted' }, 'Esc to close')));

    modal = showModal(root, dialog, { returnFocus, initialFocus: closeBtn, onClose: () => { modal = null; } });
  }

  return { open, openAnalysis, close };
}
