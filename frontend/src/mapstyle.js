// Local MapLibre style: land, borders, graticule and country labels from bundled files. No remote tiles.
import { COLORS, COUNTRIES_URL, FONT_STACK, GLYPHS_URL, LABELS_URL } from './config.js';

// A lat/lon grid every `step` degrees, densified so lines curve correctly on the globe.
// (Drawing aid only; no geodesy.)
function graticule(step = 30) {
  const features = [];
  for (let lon = -180; lon <= 180; lon += step) {
    const coords = [];
    for (let lat = -90; lat <= 90; lat += 3) coords.push([lon, lat]);
    features.push({ type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: coords } });
  }
  for (let lat = -90 + step; lat < 90; lat += step) {
    const coords = [];
    for (let lon = -180; lon <= 180; lon += 3) coords.push([lon, lat]);
    features.push({ type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: coords } });
  }
  return { type: 'FeatureCollection', features };
}

export const mapStyle = {
  version: 8,
  projection: { type: 'globe' },
  glyphs: GLYPHS_URL,
  sky: {
    'sky-color': '#060c18',
    'horizon-color': '#16335e',
    'fog-color': '#0a1424',
    'sky-horizon-blend': 0.6,
    'horizon-fog-blend': 0.5,
    'fog-ground-blend': 0.5,
    'atmosphere-blend': ['interpolate', ['linear'], ['zoom'], 0, 1, 5, 1, 7, 0],
  },
  sources: {
    countries: { type: 'geojson', data: COUNTRIES_URL },
    labels: { type: 'geojson', data: LABELS_URL },
    graticule: { type: 'geojson', data: graticule() },
  },
  layers: [
    { id: 'ocean', type: 'background', paint: { 'background-color': COLORS.ocean } },
    { id: 'graticule', type: 'line', source: 'graticule',
      paint: { 'line-color': COLORS.graticule, 'line-width': 0.6 } },
    { id: 'land', type: 'fill', source: 'countries', paint: { 'fill-color': COLORS.land } },
    { id: 'borders', type: 'line', source: 'countries',
      paint: { 'line-color': COLORS.border, 'line-width': ['interpolate', ['linear'], ['zoom'], 0, 0.5, 6, 1.2] } },
    { id: 'country-labels', type: 'symbol', source: 'labels',
      layout: {
        'text-field': ['get', 'name'],
        'text-font': FONT_STACK,
        'text-size': ['interpolate', ['linear'], ['zoom'], 1, 9, 4, 12, 8, 16],
        'text-max-width': 7,
        'symbol-sort-key': ['get', 'rank'],
      },
      paint: { 'text-color': COLORS.label, 'text-halo-color': COLORS.labelHalo, 'text-halo-width': 1.2 } },
  ],
};
