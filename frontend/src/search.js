// Airport / city search box with suggestions, and the "nearest airport / city" hint under a point.
import { places } from './api.js';
import { el } from './format.js';

/** A distance given in km, shown in the chosen unit ({ label, km_per_unit }): '3.2 km', '7 494 mi'. */
export function formatDistance(km, unit) {
  const v = km / unit.km_per_unit;
  const text = v < 10 ? v.toFixed(1) : Math.round(v).toLocaleString('en').replace(/,/g, ' ');
  return `${text} ${unit.label}`;
}

/**
 * which: 'a' | 'b'; onPick({lat, lon, label}) is called when the user chooses a result.
 * returns { root, setNearest(data|null, unit) }
 */
export function createSearch(which, onPick) {
  const id = `search-${which}`;
  const input = el('input', {
    type: 'text', class: 'search-input', placeholder: 'Airport or city, e.g. CGN', autocomplete: 'off', spellcheck: 'false',
    role: 'combobox', 'aria-autocomplete': 'list', 'aria-expanded': 'false', 'aria-controls': `${id}-list`,
    'aria-label': `Search an airport or city for point ${which.toUpperCase()}`,
  });
  const list = el('ul', { class: 'search-list', role: 'listbox', id: `${id}-list`, hidden: true });
  const hint = el('div', { class: 'nearest', 'aria-live': 'polite' });
  let results = [];
  let active = -1;
  let seq = 0;
  let timer = null;

  function close() {
    list.hidden = true;
    input.setAttribute('aria-expanded', 'false');
    input.removeAttribute('aria-activedescendant');
    active = -1;
  }

  function highlight(i) {
    active = i;
    [...list.children].forEach((li, k) => {
      li.classList.toggle('active', k === i);
      li.setAttribute('aria-selected', String(k === i));
    });
    if (i >= 0) {
      input.setAttribute('aria-activedescendant', list.children[i].id);
      list.children[i].scrollIntoView({ block: 'nearest' });
    } else input.removeAttribute('aria-activedescendant');
  }

  function choose(i) {
    const p = results[i];
    if (!p) return;
    input.value = p.label;
    close();
    onPick({ lat: p.lat, lon: p.lon, label: p.label });
  }

  function render() {
    list.replaceChildren();
    if (!results.length) {
      list.append(el('li', { class: 'search-empty', role: 'presentation' }, 'No match'));
    }
    results.forEach((p, i) => {
      const li = el('li', { class: 'search-item', role: 'option', id: `${id}-opt-${i}`, 'aria-selected': 'false' },
        el('span', { class: 'search-kind', 'aria-hidden': 'true' }, p.kind === 'airport' ? '✈' : '●'),
        el('span', { class: 'search-text' }, el('strong', {}, p.label), p.detail ? el('small', {}, p.detail) : null));
      li.addEventListener('mousedown', (e) => { e.preventDefault(); choose(i); });   // before the input loses focus
      list.append(li);
    });
    list.hidden = false;
    input.setAttribute('aria-expanded', 'true');
    highlight(results.length ? 0 : -1);
  }

  async function search() {
    const q = input.value.trim();
    const mine = ++seq;
    if (!q) { close(); return; }
    try {
      const found = await places(q, 8);
      if (mine !== seq) return;               // a newer keystroke superseded this request
      results = found;
      render();
    } catch (_) {
      if (mine === seq) close();
    }
  }

  input.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(search, 150); });
  input.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      if (list.hidden) { if (input.value.trim()) search(); return; }
      e.preventDefault();
      const n = results.length;
      if (n) highlight(e.key === 'ArrowDown' ? (active + 1) % n : (active - 1 + n) % n);
    } else if (e.key === 'Enter') {
      if (!list.hidden && active >= 0) { e.preventDefault(); choose(active); }
    } else if (e.key === 'Escape' && !list.hidden) {
      e.preventDefault();
      e.stopPropagation();
      close();
    }
  });
  input.addEventListener('blur', () => setTimeout(close, 120));

  function setNearest(data, unit) {
    hint.replaceChildren();
    if (!data) return;
    const line = (icon, text) => hint.append(el('div', {}, el('span', { 'aria-hidden': 'true' }, icon + ' '), text));
    if (data.airport) line('✈', `Nearest airport: ${data.airport.label} (${formatDistance(data.airport.km, unit)})`);
    if (data.city) line('●', `Nearest city: ${data.city.name}${data.city.country ? ', ' + data.city.country : ''} (${formatDistance(data.city.km, unit)})`);
  }

  /** Empty the box and close the list; a response that is still on its way is ignored. */
  function clear() {
    clearTimeout(timer);
    seq++;
    input.value = '';
    results = [];
    close();
  }

  return { root: el('div', { class: 'search' }, input, list, hint), setNearest, clear };
}
