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

/** Night side of the Earth at a UTC date (YYYY-MM-DD) and time (HH:MM). */
export function terminator(date, time) {
  return request(`/terminator?date=${encodeURIComponent(date)}&time=${encodeURIComponent(time)}`);
}

/**
 * a, b: {lat, lon}; options (all optional): cruise_kmh, climb_descent_min, taxi_min, date, height_a_m, height_b_m,
 * project_bearing_deg + project_km (destination from A), include_return, circle_km
 */
export function calculate(a, b, options, course = null) {
  // Inverse mode: no B, but a course { bearing_deg, km } from A; the backend computes B and returns it.
  return request('/calculate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(course ? { a, course, options } : { a, b, options }),
  });
}

/** Airports and cities matching a code or name (best first). */
export function places(q, limit = 8) {
  return request(`/places?q=${encodeURIComponent(q)}&limit=${limit}`);
}

/** Nearest airport and nearest city to a point: { airport, city } with distances in km. */
export function nearest(lat, lon) {
  return request(`/nearest?lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(lon)}`);
}

/** Distance/speed units with their size in km: [{ id, label, speed_label, km_per_unit }]. */
export function units() {
  return request('/units');
}

/** Every bundled airport: [{ code, name, city, country, lat, lon }] (for the airports layer). */
export function airports() {
  return request('/airports');
}
