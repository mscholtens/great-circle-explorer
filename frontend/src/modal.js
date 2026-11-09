// Shared modal behavior: overlay, Esc / backdrop close, focus trap, focus return.
import { el } from './format.js';

const FOCUSABLE = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';

/**
 * Show `dialog` (an element with role="dialog") in a full-screen overlay appended to `root`.
 * Returns { close, overlay }. Focus moves to `initialFocus` (or the dialog) and returns to
 * `returnFocus` on close.
 */
export function showModal(root, dialog, { returnFocus = null, initialFocus = null, onClose = null } = {}) {
  const overlay = el('div', { class: 'overlay' }, dialog);
  let open = true;

  function close() {
    if (!open) return;
    open = false;
    document.removeEventListener('keydown', onKey, true);
    overlay.remove();
    if (returnFocus && document.contains(returnFocus)) returnFocus.focus();
    if (onClose) onClose();
  }

  function onKey(e) {
    if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();
      close();
      return;
    }
    if (e.key !== 'Tab') return;
    const items = [...overlay.querySelectorAll(FOCUSABLE)].filter((n) => !n.disabled && n.offsetParent !== null);
    if (!items.length) return;
    const first = items[0];
    const last = items[items.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    else if (!overlay.contains(document.activeElement)) { e.preventDefault(); first.focus(); }
  }

  overlay.addEventListener('mousedown', (e) => { if (e.target === overlay) close(); });
  root.append(overlay);
  document.addEventListener('keydown', onKey, true);
  (initialFocus || dialog).focus();
  return { close, overlay };
}
