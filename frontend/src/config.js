// Central configuration. Nothing here points to an external server: the app is fully offline.

export const API_BASE = '/api';

// Local map data (created once by tools/fetch_data.py; served from frontend/public/).
export const COUNTRIES_URL = '/data/countries.json';
export const LABELS_URL = '/data/labels.json';
export const GLYPHS_URL = '/fonts/{fontstack}/{range}.pbf';
export const FONT_STACK = ['Noto Sans Regular'];

export const INITIAL_VIEW = { center: [10, 30], zoom: 1.5 };
export const RECALC_DEBOUNCE_MS = 150;

export const COLORS = {
  ocean: '#0a1424',
  land: '#16263f',
  border: '#2d4a73',
  graticule: '#1c2f4d',
  label: '#9fb6d8',
  labelHalo: '#0a1424',
  greatCircle: '#ffb84d',
  rhumb: '#8aa4c8',
  pointA: '#4dd2ff',
  pointB: '#ff6b9a',
  midpoint: '#ffffff',
  vertex: '#ffb84d',
  antipode: '#8aa4c8',
  crossing: '#7be0a8',
};
