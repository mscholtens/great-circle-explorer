// Globe + overlays (paths, markers). Draws exactly what the API returns; no geodesy.
import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { COLORS, FONT_STACK, INITIAL_VIEW } from './config.js';
import { el, wrapLon } from './format.js';
import { mapStyle } from './mapstyle.js';

const EMPTY = { type: 'FeatureCollection', features: [] };

function lineFeature(coords) {
  return coords && coords.length > 1
    ? { type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: coords } }
    : null;
}

/**
 * handlers: { onMapClick({lat, lon}), onPointMoved('a'|'b', {lat, lon}) }
 * returns:  { setPoint, setResult, setVisible, resize }
 */
export function createMap(container, handlers) {
  const map = new maplibregl.Map({
    container,
    style: mapStyle,
    center: INITIAL_VIEW.center,
    zoom: INITIAL_VIEW.zoom,
    attributionControl: false,
    maxPitch: 60,
    renderWorldCopies: true,
  });
  map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-right');
  map.addControl(new maplibregl.AttributionControl({ compact: true, customAttribution: 'Natural Earth · Noto Sans' }), 'bottom-right');

  const markers = { a: null, b: null };
  let pending = null;       // last result, applied once the style has loaded
  let ready = false;
  const visible = { rhumb: true, midpoint: true, vertex: true, antipodes: true, crossings: true };

  function makeMarker(which, p) {
    const node = el('div', { class: `pin pin-${which}`, title: `Point ${which.toUpperCase()} (drag to move)` },
      el('span', { text: which.toUpperCase() }));
    node.addEventListener('click', (e) => e.stopPropagation());
    const m = new maplibregl.Marker({ element: node, draggable: true, anchor: 'center' })
      .setLngLat([p.lon, p.lat])
      .addTo(map);
    m.on('dragend', () => {
      const ll = m.getLngLat();
      const lat = Math.max(-90, Math.min(90, ll.lat));
      const lon = wrapLon(ll.lng);
      m.setLngLat([lon, lat]);
      handlers.onPointMoved(which, { lat, lon });
    });
    return m;
  }

  /** p = {lat, lon} or null (remove) */
  function setPoint(which, p) {
    if (!p) {
      markers[which]?.remove();
      markers[which] = null;
    } else if (markers[which]) {
      markers[which].setLngLat([p.lon, p.lat]);
    } else {
      markers[which] = makeMarker(which, p);
    }
  }

  function applyVisibility() {
    if (!ready) return;
    const vis = (on) => (on ? 'visible' : 'none');
    map.setLayoutProperty('path-rhumb', 'visibility', vis(visible.rhumb));
    for (const kind of ['midpoint', 'vertex', 'antipodes']) {
      map.setLayoutProperty(`extra-${kind}`, 'visibility', vis(visible[kind]));
      map.setLayoutProperty(`extra-${kind}-halo`, 'visibility', vis(visible[kind]));
    }
    map.setLayoutProperty('crossings-marker', 'visibility', vis(visible.crossings));
    map.setLayoutProperty('crossings-label', 'visibility', vis(visible.crossings));
  }

  function applyResult() {
    if (!ready) return;
    const r = pending;
    const gc = r && lineFeature(r.paths.great_circle);
    const rh = r && lineFeature(r.paths.rhumb);
    map.getSource('path-gc').setData(gc ? { type: 'FeatureCollection', features: [gc] } : EMPTY);
    map.getSource('path-rhumb').setData(rh ? { type: 'FeatureCollection', features: [rh] } : EMPTY);
    const pts = [];
    if (r) {
      const add = (kind, p) => p && pts.push({
        type: 'Feature', properties: { kind }, geometry: { type: 'Point', coordinates: [p.lon, p.lat] },
      });
      add('midpoint', r.markers.midpoint);
      add('vertex', r.markers.vertex);
      add('antipodes', r.markers.antipode_a);
      add('antipodes', r.markers.antipode_b);
    }
    map.getSource('extras').setData({ type: 'FeatureCollection', features: pts });
    const cross = (r ? r.markers.crossings : []).map((c) => ({
      type: 'Feature',
      properties: { label: c.label, km: Math.round(c.km_from_a) },
      geometry: { type: 'Point', coordinates: [c.lon, c.lat] },
    }));
    map.getSource('crossings').setData({ type: 'FeatureCollection', features: cross });
  }

  map.on('load', () => {
    map.addSource('path-rhumb', { type: 'geojson', data: EMPTY });
    map.addSource('path-gc', { type: 'geojson', data: EMPTY });
    map.addSource('extras', { type: 'geojson', data: EMPTY });
    map.addSource('crossings', { type: 'geojson', data: EMPTY });
    map.addLayer({ id: 'path-rhumb', type: 'line', source: 'path-rhumb',
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': COLORS.rhumb, 'line-width': 2, 'line-dasharray': [2, 2], 'line-opacity': 0.8 } });
    map.addLayer({ id: 'path-gc-glow', type: 'line', source: 'path-gc',
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': COLORS.greatCircle, 'line-width': 8, 'line-opacity': 0.18, 'line-blur': 4 } });
    map.addLayer({ id: 'path-gc', type: 'line', source: 'path-gc',
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': COLORS.greatCircle, 'line-width': 3 } });
    const kinds = { midpoint: COLORS.midpoint, vertex: COLORS.vertex, antipodes: COLORS.antipode };
    for (const [kind, color] of Object.entries(kinds)) {
      map.addLayer({ id: `extra-${kind}-halo`, type: 'circle', source: 'extras', filter: ['==', ['get', 'kind'], kind],
        paint: { 'circle-radius': 9, 'circle-color': color, 'circle-opacity': 0.18 } });
      map.addLayer({ id: `extra-${kind}`, type: 'circle', source: 'extras', filter: ['==', ['get', 'kind'], kind],
        paint: { 'circle-radius': 4.5, 'circle-color': color, 'circle-stroke-color': '#0a1424', 'circle-stroke-width': 1.5 } });
    }
    // Crossings: a small diamond-like marker (rotated square via a square circle-ish symbol) with its name.
    map.addLayer({ id: 'crossings-marker', type: 'circle', source: 'crossings',
      paint: { 'circle-radius': 5, 'circle-color': COLORS.crossing, 'circle-stroke-color': '#0a1424', 'circle-stroke-width': 2 } });
    map.addLayer({ id: 'crossings-label', type: 'symbol', source: 'crossings',
      layout: {
        'text-field': ['get', 'label'], 'text-font': FONT_STACK, 'text-size': 12, 'text-offset': [0, 1.1], 'text-anchor': 'top',
        'text-allow-overlap': true, 'text-max-width': 12,
      },
      paint: { 'text-color': COLORS.crossing, 'text-halo-color': COLORS.labelHalo, 'text-halo-width': 1.5 } });
    ready = true;
    applyResult();
    applyVisibility();
  });

  map.on('click', (e) => {
    const { lat, lng } = e.lngLat || {};
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) return; // clicked in space, beside the globe
    handlers.onMapClick({ lat, lon: wrapLon(lng) });
  });

  /** Keep the globe centered in the part of the screen the panel does not cover. */
  function fitToPanel(collapsed, animate = true) {
    const narrow = window.matchMedia('(max-width: 760px)').matches;
    const padding = collapsed
      ? { top: 0, right: 0, bottom: 0, left: 0 }
      : narrow
        ? { top: 0, right: 0, bottom: Math.round(window.innerHeight * 0.58), left: 0 }
        : { top: 0, right: 0, bottom: 0, left: 404 };
    map.easeTo({ padding, duration: animate ? 300 : 0 });
  }
  map.on('load', () => fitToPanel(false, false));
  window.addEventListener('resize', () => fitToPanel(document.body.classList.contains('panel-collapsed'), false));

  return {
    map,
    setPoint,
    setResult(result) { pending = result; applyResult(); },
    setVisible(name, on) { visible[name] = on; applyVisibility(); },
    fitToPanel,
  };
}
