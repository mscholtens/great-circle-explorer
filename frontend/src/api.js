// Thin fetch wrapper for the local backend. The only network traffic of the app.
import { API_BASE } from './config.js';

export class ApiError extends Error {
  constructor(message, { unreachable = false, status = 0 } = {}) {
    super(message);
    this.unreachable = unreachable;
    this.status = status;
  }
}

async function request(path, init) {
  let res;
  try {
    res = await fetch(API_BASE + path, init);
  } catch (err) {
    throw new ApiError('Backend not running on :8000?', { unreachable: true });
  }
  if (!res.ok) {
    // A dead proxy target typically answers 5xx with an empty body.
    const unreachable = res.status >= 500;
    let detail = '';
    try {
      const body = await res.json();
      detail = Array.isArray(body.detail) ? body.detail.map((d) => d.msg).join('; ') : body.detail || '';
    } catch (_) { /* ignore */ }
    throw new ApiError(
      unreachable ? 'Backend not running on :8000? (the dev server could not reach it)' : `Request rejected: ${detail}`,
      { unreachable, status: res.status },
    );
  }
  return res.json();
}

export function health() {
  return request('/health');
}

/** a, b: {lat, lon}; options: {cruise_kmh, overhead_min, date, height_a_m, height_b_m} */
export function calculate(a, b, options) {
  return request('/calculate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ a, b, options }),
  });
}
