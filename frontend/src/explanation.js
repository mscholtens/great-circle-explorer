// Builders for the parts of an explanation (steps with KaTeX, constants, notes). Shared by the pop-up and the PDF report.
import katex from 'katex';
import 'katex/dist/katex.min.css';
import { el } from './format.js';

export function renderTex(target, tex, metricId) {
  try {
    katex.render(tex, target, { displayMode: true, throwOnError: true, output: 'htmlAndMathml' });
  } catch (err) {
    console.error(`KaTeX error in metric "${metricId}":`, err.message, '\n', tex);
    target.textContent = tex;
    target.classList.add('tex-error');
  }
}

export function buildSteps(ex, metricId) {
  return el('ol', { class: 'steps' }, ex.steps.map((s) => {
    const li = el('li', { class: 'step' }, el('div', { class: 'step-label' }, s.label));
    if (s.tex) {
      const f = el('div', { class: 'tex tex-formula', 'aria-label': 'Formula' });
      renderTex(f, s.tex, metricId);
      li.append(f);
    }
    if (s.substituted_tex) {
      li.append(el('div', { class: 'tex-caption' }, 'with the numbers filled in'));
      const f = el('div', { class: 'tex tex-substituted', 'aria-label': 'Formula with values' });
      renderTex(f, s.substituted_tex, metricId);
      li.append(f);
    }
    if (s.result) li.append(el('div', { class: 'step-result' }, el('span', { class: 'arrow' }, '→'), ' ', s.result));
    return li;
  }));
}

export function buildConstants(ex) {
  return ex.constants.length
    ? el('section', { class: 'expl-section' },
      el('h3', {}, 'Constants'),
      el('table', { class: 'const-table' },
        el('tbody', {}, ex.constants.map((c) => el('tr', {},
          el('th', { scope: 'row' }, c.symbol), el('td', {}, c.value), el('td', { class: 'muted' }, c.meaning))))))
    : null;
}

export function buildNotes(ex) {
  return ex.notes.length
    ? el('section', { class: 'expl-section' }, el('h3', {}, 'Notes'), el('ul', { class: 'notes' }, ex.notes.map((n) => el('li', {}, n))))
    : null;
}
