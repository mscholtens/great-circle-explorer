// Explanation pop-up: formulas (KaTeX), substituted formulas, results, constants, notes.
import katex from 'katex';
import 'katex/dist/katex.min.css';
import { el, explanationToText } from './format.js';
import { showModal } from './modal.js';

function renderTex(target, tex, metricId) {
  try {
    katex.render(tex, target, { displayMode: true, throwOnError: true, output: 'htmlAndMathml' });
  } catch (err) {
    console.error(`KaTeX error in metric "${metricId}":`, err.message, '\n', tex);
    target.textContent = tex;
    target.classList.add('tex-error');
  }
}

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

  function open(metric, opener) {
    close();
    const returnFocus = opener || document.activeElement;
    const ex = metric.explanation;

    const stepList = el('ol', { class: 'steps' }, ex.steps.map((s) => {
      const li = el('li', { class: 'step' }, el('div', { class: 'step-label' }, s.label));
      if (s.tex) {
        const f = el('div', { class: 'tex tex-formula', 'aria-label': 'Formula' });
        renderTex(f, s.tex, metric.id);
        li.append(f);
      }
      if (s.substituted_tex) {
        li.append(el('div', { class: 'tex-caption' }, 'with the numbers filled in'));
        const f = el('div', { class: 'tex tex-substituted', 'aria-label': 'Formula with values' });
        renderTex(f, s.substituted_tex, metric.id);
        li.append(f);
      }
      if (s.result) li.append(el('div', { class: 'step-result' }, el('span', { class: 'arrow' }, '→'), ' ', s.result));
      return li;
    }));

    const constants = ex.constants.length
      ? el('section', {},
          el('h3', {}, 'Constants'),
          el('table', { class: 'const-table' },
            el('tbody', {}, ex.constants.map((c) => el('tr', {},
              el('th', { scope: 'row' }, c.symbol), el('td', {}, c.value), el('td', { class: 'muted' }, c.meaning))))))
      : null;
    const notes = ex.notes.length
      ? el('section', {}, el('h3', {}, 'Notes'), el('ul', { class: 'notes' }, ex.notes.map((n) => el('li', {}, n))))
      : null;

    const copyBtn = el('button', { class: 'btn', type: 'button' }, 'Copy as text');
    copyBtn.addEventListener('click', () => copyText(explanationToText(metric), copyBtn));
    const closeBtn = el('button', { class: 'icon-btn', type: 'button', 'aria-label': 'Close' }, '✕');
    closeBtn.addEventListener('click', close);

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
    el('footer', { class: 'dialog-foot' }, copyBtn, el('span', { class: 'muted' }, 'Esc to close')));

    modal = showModal(root, dialog, { returnFocus, initialFocus: closeBtn, onClose: () => { modal = null; } });
  }

  return { open, close };
}
