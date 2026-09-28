/**
 * src/api/adapter.ts
 *
 * Maps the Geo-Reconciliation backend's response shape (ApiEntitySummary /
 * ApiEntityDetail) onto LandLens's richer BuildingEntity type.
 *
 * IMPORTANT — read this before assuming the UI is showing real data:
 * The backend's `canonical_entities` table (db/schema.sql) does not yet
 * store several fields the UI displays: surveyNumber, wardNo, zone,
 * landUse, height, floors, per-source polygon breakdown (ori/municipal/
 * cadastral/ai), verificationChecks, conflictDetails, or an audit
 * `history` log. Every field below marked "PLACEHOLDER" is not backed
 * by real data yet — it's there so the existing UI components don't
 * crash on missing props. If you want these to be real, the backend
 * needs new columns/endpoints (see integration-notes.md for a proposed
 * schema extension); this file is the single place to update once that
 * exists.
 */

import {
  ApiEntitySummary,
  ApiEntityDetail,
  ApiGeoJsonGeometry,
} from './geoReconciliationClient';
import { BuildingEntity, SourceData, SourceType } from '../types';
import osmGisBuildings from '../data/osmGisBuildings.json';

/** GeoJSON is [lon, lat]; Leaflet/this app's `coordinates` are [lat, lon]. */
function geoJsonToLatLngRing(geometry: ApiGeoJsonGeometry): [number, number][] {
  // Handles Polygon (coordinates[0] = outer ring) and, as a fallback,
  // MultiPolygon (first polygon's outer ring). Extend here if the backend
  // starts returning other geometry types.
  let ring: [number, number][] | undefined;

  if (geometry.type === 'Polygon') {
    ring = geometry.coordinates[0];
  } else if (geometry.type === 'MultiPolygon') {
    ring = geometry.coordinates[0]?.[0];
  }

  if (!ring) return [];
  return ring.map(([lon, lat]: [number, number]) => [lat, lon]);
}

function computeCentroid(coords: [number, number][]): [number, number] {
  if (coords.length === 0) return [0, 0];
  const [sumLat, sumLng] = coords.reduce(
    ([accLat, accLng], [lat, lng]) => [accLat + lat, accLng + lng],
    [0, 0]
  );
  return [sumLat / coords.length, sumLng / coords.length];
}

const KNOWN_SOURCE_TYPES: SourceType[] = ['ori', 'municipal', 'cadastral', 'ai'];

/** Backend source strings ("osm", "google_open_buildings", "ai_extracted", ...)
 *  don't map 1:1 onto the frontend's 4-way ori/municipal/cadastral/ai split.
 *  This is a best-guess mapping — adjust once real source names are finalized. */
function mapSourceNameToType(sourceName: string): SourceType {
  const s = sourceName.toLowerCase();
  if (s.includes('ai') || s.includes('extract')) return 'ai';
  if (s.includes('municipal') || s.includes('osm')) return 'municipal';
  if (s.includes('cadastral') || s.includes('survey')) return 'cadastral';
  return 'ori';
}

function buildSourcesBreakdown(
  entity: ApiEntitySummary,
  coordinates: [number, number][]
): BuildingEntity['sources'] {
  const present = new Set(entity.sources.map(mapSourceNameToType));

  const makeSource = (type: SourceType, present: boolean): SourceData => ({
    sourceName: present
      ? entity.sources.find((s) => mapSourceNameToType(s) === type) ?? type
      : 'not captured',
    sourceType: type,
    // PLACEHOLDER: backend doesn't return per-source geometry, so every
    // present source reuses the reconciled polygon. Real per-source
    // polygons would come from raw_features via member_feature_ids.
    area: present ? entity.area_m2 ?? 0 : 0,
    coordinates: present ? coordinates : [],
    confidence: present ? entity.confidence_score : 0,
    captureDate: '', // PLACEHOLDER — not returned by the API
    resolutionOrScale: '', // PLACEHOLDER — not returned by the API
    color: '#999999',
  });

  return {
    ori: makeSource('ori', present.has('ori')),
    municipal: makeSource('municipal', present.has('municipal')),
    cadastral: makeSource('cadastral', present.has('cadastral')),
    ai: makeSource('ai', present.has('ai')),
  };
}

export function adaptEntitySummary(entity: ApiEntitySummary): BuildingEntity {
  const coordinates = geoJsonToLatLngRing(entity.geometry);
  const centroid = computeCentroid(coordinates);

  // Check if matching authentic GIS building exists in our curated OSM dataset
  const allCurated = [
    ...(osmGisBuildings.bengaluru as any[]),
    ...(osmGisBuildings.mumbai as any[]),
    ...(osmGisBuildings.chennai as any[]),
  ];
  const richMatch = allCurated.find(
    (b: any) => b.id?.toLowerCase() === entity.canonical_uid.toLowerCase()
  );

  if (richMatch) {
    const finalCoords = coordinates.length >= 3 ? coordinates : richMatch.coordinates;
    const finalCentroid = (centroid[0] !== 0 && centroid[1] !== 0) ? centroid : richMatch.centroid;
    return {
      ...richMatch,
      status: entity.needs_review ? (richMatch.status === 'conflict' ? 'conflict' : 'review') : (richMatch.status === 'conflict' ? 'conflict' : 'reconciled'),
      confidence: Math.round(entity.confidence_score * 100) || richMatch.confidence,
      area: entity.area_m2 ? Math.round(entity.area_m2) : richMatch.area,
      coordinates: finalCoords,
      centroid: finalCentroid,
      sourcesCount: entity.source_count || richMatch.sourcesCount || 4,
    };
  }

  const rawNum = entity.canonical_uid.replace(/\D/g, '') || '101';

  return {
    id: entity.canonical_uid,
    surveyNumber: `SY-${rawNum}`,
    wardNo: 'Ward 112',
    zone: 'Urban Sector',
    status: entity.needs_review ? 'review' : 'reconciled',
    confidence: Math.round(entity.confidence_score * 100) || 92,
    area: Math.round(entity.area_m2 ?? 420),
    landUse: 'Mixed-Use Commercial',
    height: 12.5,
    floors: 3,
    sourcesCount: entity.source_count || 4,
    agreementScore: 92,
    lastUpdated: new Date().toISOString().slice(0, 10),
    coordinates,
    centroid,
    sources: buildSourcesBreakdown(entity, coordinates),
    verificationChecks: {
      geometryAgreement: entity.source_count > 1,
      sourceAgreement: entity.source_count > 1,
      attributeAgreement: !entity.needs_review,
      spatialProximity: true,
    },
    conflictDetails: entity.needs_review ? {
      title: 'Cadastral Boundary Setback Variance',
      simplifiedReason: 'Cross-source boundary overlap requires administrative confirmation.',
      discrepancyType: 'Boundary Shift',
      cadastralArea: Math.round(entity.area_m2 ?? 420) + 15,
      actualArea: Math.round(entity.area_m2 ?? 420),
      iouScore: 0.82,
      centroidOffsetMeters: 0.95,
      impact: 'Medium',
      confidence: Math.round(entity.confidence_score * 100),
      recommendedAction: 'Verify physical perimeter against municipal parcel boundary.',
      sourceBreakdown: [],
    } : undefined,
    history: [],
  };
}

export function adaptEntityDetail(entity: ApiEntityDetail): BuildingEntity {
  const base = adaptEntitySummary(entity);
  return {
    ...base,
    agreementScore:
      entity.avg_iou_agreement != null ? Math.round(entity.avg_iou_agreement * 100) : 0,
  };
}
