// Globe + overlays (paths, markers). Draws exactly what the API returns; no geodesy.
import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { COLORS, FONT_STACK, INITIAL_VIEW } from './config.js';
import { el, wrapLon } from './format.js';
import { mapStyle } from './mapstyle.js';

const EMPTY = { type: 'FeatureCollection', features: [] };

// Fit the view to the window: the globe should fill the part of the window that is not covered by the panel,
// the toolbar on top and the pointer readout at the bottom. A MapLibre globe of zoom z has a diameter of
// 512 * 2^z / pi pixels, a flat (Mercator) world is 512 * 2^z pixels wide.
const TOOLBAR_SPACE = 64;       // px reserved at the top of the map for the toolbar
const TOOLBAR_SPACE_NARROW = 118;   // the toolbar wraps to two rows on a narrow screen
const READOUT_SPACE = 44;       // px reserved at the bottom for the pointer readout
const PANEL_SPACE = 404;        // px covered by the left-hand panel
const GLOBE_FILL = 0.97;        // share of the free area the globe diameter may use

/** Padding that keeps the view centred in the free part of a window of width x height pixels. */
function layoutPadding(collapsed, width, height) {
  const narrow = width <= 760;                                   // the panel is a bottom sheet there
  const row = document.querySelector('.map-toolbar-row');        // the toolbar wraps to two rows on narrower windows
  const top = row ? Math.round(row.getBoundingClientRect().bottom) + 8 : (narrow ? TOOLBAR_SPACE_NARROW : TOOLBAR_SPACE);
  if (narrow) return { top, right: 0, bottom: collapsed ? 0 : Math.round(height * 0.58), left: 0 };
  return { top, right: 0, bottom: READOUT_SPACE, left: collapsed ? 0 : PANEL_SPACE };
}

/** The zoom at which the globe (or the flat world) fills the free area. */
function fitZoom(type, width, height, padding) {
  const w = Math.max(100, width - padding.left - padding.right);
  const h = Math.max(100, height - padding.top - padding.bottom);
  const z = type === 'mercator' ? Math.log2(w / 512) : Math.log2((Math.min(w, h) * GLOBE_FILL * Math.PI) / 512);
  return Math.min(6, Math.max(0.3, z));
}

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
  const startPadding = layoutPadding(false, window.innerWidth, window.innerHeight);
  const startZoom = fitZoom('globe', window.innerWidth, window.innerHeight, startPadding);   // already right in the first frame
  const map = new maplibregl.Map({
    container,
    style: mapStyle,
    center: INITIAL_VIEW.center,
    zoom: startZoom,
    attributionControl: false,
    maxPitch: 60,
    renderWorldCopies: true,
    canvasContextAttributes: { preserveDrawingBuffer: true },   // lets the PDF report take a picture of the map
  });
  map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-right');
  map.addControl(new maplibregl.AttributionControl({ compact: true, customAttribution: 'Natural Earth · Noto Sans' }), 'bottom-right');

  const markers = { a: null, b: null };
  let pending = null;       // last result, applied once the style has loaded
  let ready = false;
  const visible = { rhumb: true, midpoint: true, vertex: true, antipodes: true, crossings: true, circles: false, airports: false };
  let night = null;         // last day/night response (or null)
  let projection = 'globe'; // 'globe' | 'mercator'
  let airportList = null;   // airports for the optional layer (from /api/airports)
  let airportTip = null;    // hover tooltip
  let courseMode = false;   // inverse mode: B is computed, so its pin cannot be dragged

  function makeMarker(which, p) {
    const node = el('div', { class: `pin pin-${which}`, title: `Point ${which.toUpperCase()} (drag to move)` },
      el('span', { text: which.toUpperCase() }));
    node.addEventListener('click', (e) => e.stopPropagation());
    const m = new maplibregl.Marker({ element: node, draggable: !(which === 'b' && courseMode), anchor: 'center' })
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
    map.setLayoutProperty('airports-dot', 'visibility', vis(visible.airports));
    map.setLayoutProperty('airports-label', 'visibility', vis(visible.airports));
    map.setLayoutProperty('circle-a', 'visibility', vis(visible.circles));
    map.setLayoutProperty('circle-b', 'visibility', vis(visible.circles));
  }

  /** Airports layer: one point per airport; the code, name and place are kept as properties for labels and tooltips. */
  function applyAirports() {
    if (!ready) return;
    map.getSource('airports').setData(airportList
      ? {
        type: 'FeatureCollection',
        features: airportList.map((a) => ({
          type: 'Feature', properties: { ...a }, geometry: { type: 'Point', coordinates: [a.lon, a.lat] },
        })),
      }
      : EMPTY);
  }

  function applyProjection() {
    if (!ready) return;
    map.setProjection({ type: projection });
    fitToPanel(document.body.classList.contains('panel-collapsed'), false, true);     // another projection, another size
  }

  /** Day/night shading and the sub-solar point (data from /api/terminator, or null to clear). */
  function applyNight() {
    if (!ready) return;
    map.getSource('night').setData(night
      ? { type: 'Feature', properties: {}, geometry: { type: 'Polygon', coordinates: [night.polygon] } }
      : EMPTY);
    map.getSource('subsolar').setData(night
      ? { type: 'Feature', properties: {}, geometry: { type: 'Point', coordinates: [night.subsolar.lon, night.subsolar.lat] } }
      : EMPTY);
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
    // Circles of equal distance (one polyline per piece, cut at the date line by the backend)
    const circleFeatures = (r ? r.circles : []).flatMap((c) => c.segments.map((seg) => ({
      type: 'Feature', properties: { center: c.center }, geometry: { type: 'LineString', coordinates: seg },
    })));
    map.getSource('circles').setData({ type: 'FeatureCollection', features: circleFeatures });
    // Projection: path from A and the destination point
    const proj = r && r.markers.projected;
    const projLine = r && lineFeature(r.paths.projection);
    map.getSource('projection').setData({
      type: 'FeatureCollection',
      features: [projLine, proj && { type: 'Feature', properties: { label: 'Destination' }, geometry: { type: 'Point', coordinates: [proj.lon, proj.lat] } }].filter(Boolean),
    });
  }

  map.on('load', () => {
    map.addSource('airports', { type: 'geojson', data: EMPTY });
    map.addSource('night', { type: 'geojson', data: EMPTY });
    map.addSource('subsolar', { type: 'geojson', data: EMPTY });
    map.addSource('circles', { type: 'geojson', data: EMPTY });
    map.addSource('projection', { type: 'geojson', data: EMPTY });
    map.addSource('path-rhumb', { type: 'geojson', data: EMPTY });
    map.addSource('path-gc', { type: 'geojson', data: EMPTY });
    map.addSource('extras', { type: 'geojson', data: EMPTY });
    map.addSource('crossings', { type: 'geojson', data: EMPTY });
    map.addLayer({ id: 'night-fill', type: 'fill', source: 'night', paint: { 'fill-color': COLORS.night, 'fill-opacity': 0.55 } });
    map.addLayer({ id: 'airports-dot', type: 'circle', source: 'airports',
      layout: { visibility: 'none' },
      paint: {
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 1, 1.8, 5, 3.6], 'circle-color': COLORS.airport,
        'circle-opacity': 0.9, 'circle-stroke-color': '#0a1424', 'circle-stroke-width': 0.8,
      } });
    map.addLayer({ id: 'airports-label', type: 'symbol', source: 'airports', minzoom: 4,
      layout: {
        visibility: 'none', 'text-field': ['get', 'code'], 'text-font': FONT_STACK, 'text-size': 10.5,
        'text-offset': [0, 0.8], 'text-anchor': 'top', 'text-optional': true,
      },
      paint: { 'text-color': COLORS.airport, 'text-halo-color': COLORS.labelHalo, 'text-halo-width': 1.4 } });
    airportTip = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 10, maxWidth: '280px', className: 'airport-tip' });
    map.on('mousemove', 'airports-dot', (e) => {
      const f = e.features && e.features[0];
      if (!f) return;
      map.getCanvas().style.cursor = 'pointer';
      const p = f.properties;
      const place = [p.city, p.country].filter(Boolean).join(', ');
      airportTip.setLngLat([Number(p.lon), Number(p.lat)])
        .setDOMContent(el('div', {}, el('strong', {}, `${p.code} · ${p.name}`), place ? el('div', { class: 'tip-sub' }, place) : null))
        .addTo(map);
    });
    map.on('mouseleave', 'airports-dot', () => {
      map.getCanvas().style.cursor = '';
      airportTip.remove();
    });
    for (const [which, color] of [['a', COLORS.pointA], ['b', COLORS.pointB]]) {
      map.addLayer({ id: `circle-${which}`, type: 'line', source: 'circles', filter: ['==', ['get', 'center'], which],
        layout: { 'line-cap': 'round', 'line-join': 'round', visibility: 'none' },
        paint: { 'line-color': color, 'line-width': 2, 'line-dasharray': [3, 2], 'line-opacity': 0.9 } });
    }
    map.addLayer({ id: 'projection-line', type: 'line', source: 'projection', filter: ['==', ['geometry-type'], 'LineString'],
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': COLORS.projection, 'line-width': 2.5, 'line-dasharray': [1, 2] } });
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
    map.addLayer({ id: 'projection-point', type: 'circle', source: 'projection', filter: ['==', ['geometry-type'], 'Point'],
      paint: { 'circle-radius': 6, 'circle-color': COLORS.projection, 'circle-stroke-color': '#0a1424', 'circle-stroke-width': 2 } });
    map.addLayer({ id: 'projection-label', type: 'symbol', source: 'projection', filter: ['==', ['geometry-type'], 'Point'],
      layout: { 'text-field': ['get', 'label'], 'text-font': FONT_STACK, 'text-size': 12, 'text-offset': [0, 1.1], 'text-anchor': 'top', 'text-allow-overlap': true },
      paint: { 'text-color': COLORS.projection, 'text-halo-color': COLORS.labelHalo, 'text-halo-width': 1.5 } });
    map.addLayer({ id: 'subsolar-halo', type: 'circle', source: 'subsolar', paint: { 'circle-radius': 14, 'circle-color': COLORS.sun, 'circle-opacity': 0.2 } });
    map.addLayer({ id: 'subsolar-point', type: 'circle', source: 'subsolar',
      paint: { 'circle-radius': 5.5, 'circle-color': COLORS.sun, 'circle-stroke-color': '#0a1424', 'circle-stroke-width': 1.5 } });
    ready = true;
    applyProjection();
    applyAirports();
    applyResult();
    applyNight();
    applyVisibility();
  });

  map.on('click', (e) => {
    if (visible.airports && ready) {              // a click on an airport dot snaps to that airport
      const box = [[e.point.x - 6, e.point.y - 6], [e.point.x + 6, e.point.y + 6]];
      const hit = map.queryRenderedFeatures(box, { layers: ['airports-dot'] })[0];
      if (hit) {
        handlers.onMapClick({ lat: Number(hit.properties.lat), lon: Number(hit.properties.lon) });
        return;
      }
    }
    const { lat, lng } = e.lngLat || {};
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) return; // clicked in space, beside the globe
    handlers.onMapClick({ lat, lon: wrapLon(lng) });
  });

  let userZoomed = false;      // once the user zooms by hand, a resize no longer changes the zoom
  map.on('zoomstart', (e) => { if (e.originalEvent) userZoomed = true; });

  /**
   * Centre the view in the part of the window the panel does not cover and, unless the user zoomed by hand
   * (or `refit` forces it), zoom so that the globe fills that area.
   */
  function fitToPanel(collapsed, animate = true, refit = true) {
    const width = map.getContainer().clientWidth;
    const height = map.getContainer().clientHeight;
    const padding = layoutPadding(collapsed, width, height);
    if (refit) userZoomed = false;
    const options = { padding, duration: animate ? 300 : 0 };
    if (!userZoomed) options.zoom = fitZoom(projection, width, height, padding);
    map.easeTo(options);
  }
  map.on('load', () => fitToPanel(false, false));
  window.addEventListener('resize', () => fitToPanel(document.body.classList.contains('panel-collapsed'), false, false));

  return {
    map,
    setPoint,
    setResult(result) { pending = result; applyResult(); },
    setVisible(name, on) { visible[name] = on; applyVisibility(); },
    setNight(data) { night = data; applyNight(); },
    /** Airports for the optional layer ([{ code, name, city, country, lat, lon }]). */
    setAirports(list) { airportList = list; applyAirports(); },
    setProjection(type) { projection = type; applyProjection(); },
    /** Inverse mode (B is calculated): B's pin is shown but not draggable. */
    setCourseMode(on) {
      courseMode = on;
      markers.b?.setDraggable(!on);
    },
    /** PNG data URL of the visible map area (without the panel padding), including the A and B pins; null if refused. */
    getImage() {
      try {
        map.triggerRepaint();
        const src = map.getCanvas();
        const pad = map.getPadding();
        const dpr = src.width / src.clientWidth;
        const sx = Math.round(pad.left * dpr);
        const sy = Math.round(pad.top * dpr);
        const sw = src.width - sx - Math.round(pad.right * dpr);
        const sh = src.height - sy - Math.round(pad.bottom * dpr);
        const out = document.createElement('canvas');
        out.width = sw;
        out.height = sh;
        const ctx = out.getContext('2d');
        ctx.fillStyle = COLORS.ocean;
        ctx.fillRect(0, 0, sw, sh);
        ctx.drawImage(src, sx, sy, sw, sh, 0, 0, sw, sh);
        for (const [which, color] of [['a', COLORS.pointA], ['b', COLORS.pointB]]) {   // the pins are HTML, not part of the canvas
          if (!markers[which]) continue;
          const pt = map.project(markers[which].getLngLat());
          const x = pt.x * dpr - sx;
          const y = pt.y * dpr - sy;
          if (!(x >= 0 && y >= 0 && x <= sw && y <= sh)) continue;
          ctx.beginPath();
          ctx.arc(x, y, 13 * dpr, 0, 2 * Math.PI);
          ctx.fillStyle = color;
          ctx.fill();
          ctx.lineWidth = 2 * dpr;
          ctx.strokeStyle = '#ffffff';
          ctx.stroke();
          ctx.fillStyle = '#0a1424';
          ctx.font = `700 ${13 * dpr}px system-ui, sans-serif`;
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillText(which.toUpperCase(), x, y + dpr);
        }
        return out.toDataURL('image/png');
      } catch (_) { return null; }
    },
    fitToPanel,
  };
}
