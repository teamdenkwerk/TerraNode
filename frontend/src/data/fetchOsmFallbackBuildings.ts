/**
 * src/data/fetchOsmFallbackBuildings.ts
 *
 * Real building footprints, fetched directly from OpenStreetMap's Overpass
 * API in the browser, for the same district bbox as config.DISTRICT_BBOX /
 * ingestion/fetch_osm_buildings.py — just requested client-side instead of
 * server-side via osmnx, so the map shows real building positions even when
 * the Geo-Reconciliation backend/Postgres isn't running.
 *
 * IMPORTANT — what this is NOT: these are raw, single-source OSM footprints
 * that have never been through matching/reconciliation.py. They are real
 * geometry in the real place, but every building here is marked
 * status: 'review', sourcesCount: 1, confidence: 0, and every field the
 * actual reconciliation pipeline would produce (agreementScore, cadastral/
 * municipal/AI sources, verificationChecks, conflictDetails, history) is
 * left honestly empty/false rather than invented. Once the real backend is
 * reachable, useLiveBuildings.ts prefers it over this every time.
 */

import { BuildingEntity } from '../types';
import { BBox } from '../api/geoReconciliationClient';

const OVERPASS_ENDPOINT = 'https://overpass-api.de/api/interpreter';
// Hard cap so a large district bbox doesn't try to render thousands of
// polygons in a demo browser tab — real behavior, just bounded.
const MAX_BUILDINGS = 400;

interface OverpassGeomPoint {
  lat: number;
  lon: number;
}

interface OverpassElement {
  type: 'way' | 'relation' | 'node';
  id: number;
  tags?: Record<string, string>;
  geometry?: OverpassGeomPoint[];
}

interface OverpassResponse {
  elements: OverpassElement[];
}

/** Shoelace formula on an equirectangular projection local to the footprint's
 *  own latitude — accurate enough for building-scale areas (tens to low
 *  thousands of m²), not meant for anything continental. */
function polygonAreaM2(coords: [number, number][]): number {
  if (coords.length < 3) return 0;
  const latRad = (coords[0][0] * Math.PI) / 180;
  const mPerDegLat = 111_320;
  const mPerDegLon = 111_320 * Math.cos(latRad);

  let area = 0;
  for (let i = 0; i < coords.length; i++) {
    const [lat1, lon1] = coords[i];
    const [lat2, lon2] = coords[(i + 1) % coords.length];
    const x1 = lon1 * mPerDegLon;
    const y1 = lat1 * mPerDegLat;
    const x2 = lon2 * mPerDegLon;
    const y2 = lat2 * mPerDegLat;
    area += x1 * y2 - x2 * y1;
  }
  return Math.abs(area / 2);
}

function computeCentroid(coords: [number, number][]): [number, number] {
  const [sumLat, sumLon] = coords.reduce(
    ([accLat, accLon], [lat, lon]) => [accLat + lat, accLon + lon],
    [0, 0]
  );
  return [sumLat / coords.length, sumLon / coords.length];
}

/** OSM's `building` tag is free-text-ish; map the common values onto the
 *  app's fixed land-use set. Anything unrecognized stays honestly
 *  'Not classified' rather than defaulting to 'Residential'. */
function mapOsmBuildingTagToLandUse(tag: string | undefined): BuildingEntity['landUse'] {
  const v = (tag || '').toLowerCase();
  if (['house', 'residential', 'apartments', 'terrace', 'detached', 'semidetached_house', 'bungalow', 'dormitory'].includes(v)) {
    return 'Residential';
  }
  if (['commercial', 'retail', 'office', 'supermarket', 'kiosk'].includes(v)) {
    return 'Commercial';
  }
  if (['school', 'university', 'college', 'hospital', 'government', 'civic', 'public'].includes(v)) {
    return 'Institutional';
  }
  if (['industrial', 'warehouse', 'factory'].includes(v)) {
    return 'Industrial';
  }
  if (v === 'mixed' || v === 'mixed_use') return 'Mixed Use';
  return 'Not classified';
}

function elementToBuildingEntity(el: OverpassElement, index: number): BuildingEntity | null {
  if (!el.geometry || el.geometry.length < 3) return null;

  // Overpass `out geom` gives ring points in {lat, lon}; the app's
  // coordinates are [lat, lon] tuples — same axis order, no flip needed.
  const coords: [number, number][] = el.geometry.map((p) => [p.lat, p.lon]);
  const centroid = computeCentroid(coords);
  const area = Math.round(polygonAreaM2(coords));
  const landUse = mapOsmBuildingTagToLandUse(el.tags?.building);

  const notCaptured = {
    sourceName: 'not captured',
    sourceType: 'municipal' as const,
    area: 0,
    coordinates: [] as [number, number][],
    confidence: 0,
    captureDate: '',
    resolutionOrScale: '',
    color: '#999999',
  };

  return {
    id: `OSM-${el.id}`,
    surveyNumber: 'N/A',
    wardNo: 'N/A',
    zone: 'N/A',
    // Honest status: this is a single unreconciled source, not a verified
    // match — 'review' fits better than pretending it's 'reconciled'.
    status: 'review',
    confidence: 0,
    area,
    landUse,
    height: 0,
    floors: 0,
    sourcesCount: 1,
    agreementScore: 0,
    lastUpdated: new Date().toISOString().slice(0, 10),
    coordinates: coords,
    centroid,
    sources: {
      ori: { ...notCaptured, sourceType: 'ori' },
      municipal: { ...notCaptured, sourceType: 'municipal' },
      cadastral: { ...notCaptured, sourceType: 'cadastral' },
      ai: { ...notCaptured, sourceType: 'ai' },
    },
    verificationChecks: {
      geometryAgreement: false,
      sourceAgreement: false,
      attributeAgreement: false,
      spatialProximity: false,
    },
    conflictDetails: undefined,
    history: [
      {
        date: new Date().toISOString().slice(0, 10),
        action: 'Ingested from OpenStreetMap (client-side reference fetch)',
        actor: 'system',
        note: 'Single-source footprint — not yet run through the reconciliation pipeline.',
      },
    ],
  };
}

/**
 * Fetches real building footprints from OpenStreetMap for the given bbox.
 * Throws on network failure or an empty result — callers should catch and
 * fall back further (see useLiveBuildings.ts's three-tier fallback).
 */
export async function fetchOsmFallbackBuildings(bbox: BBox): Promise<BuildingEntity[]> {
  const query = `[out:json][timeout:25][bbox:${bbox.minLat},${bbox.minLon},${bbox.maxLat},${bbox.maxLon}];
way["building"];
out geom;`;

  const res = await fetch(OVERPASS_ENDPOINT, {
    method: 'POST',
    headers: { 'Content-Type': 'text/plain' },
    body: query,
  });

  if (!res.ok) {
    throw new Error(`Overpass API returned ${res.status}`);
  }

  const data: OverpassResponse = await res.json();
  const buildings = data.elements
    .slice(0, MAX_BUILDINGS)
    .map((el, i) => elementToBuildingEntity(el, i))
    .filter((b): b is BuildingEntity => b !== null);

  if (buildings.length === 0) {
    throw new Error('OSM returned no building footprints for this bbox');
  }

  return buildings;
}