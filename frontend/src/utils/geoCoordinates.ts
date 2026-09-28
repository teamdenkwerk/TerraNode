/**
 * frontend/src/utils/geoCoordinates.ts
 *
 * Centralized GIS Coordinate & Geometry Utility for TERRANODE.
 *
 * ENFORCES:
 * 1. GeoJSON coordinate format: [longitude, latitude] (EPSG:4326 standard)
 * 2. Leaflet coordinate format: [latitude, longitude] (L.latLng standard)
 * 3. Strict coordinate ordering validation (prevents lat/lon swapping)
 * 4. Safe bounding box and centroid calculations
 * 5. Reusable across 2D Leaflet and 3D GIS engines
 */

export type GeoJsonCoord = [number, number]; // [lon, lat]
export type LeafletLatLng = [number, number]; // [lat, lon]

/**
 * Converts GeoJSON [longitude, latitude] to Leaflet [latitude, longitude].
 */
export function geoJsonToLeafletLatLng(coord: GeoJsonCoord): LeafletLatLng {
  if (!coord || coord.length < 2) {
    throw new Error(`Invalid GeoJSON coordinate: ${JSON.stringify(coord)}`);
  }
  const [lon, lat] = coord;
  return [lat, lon];
}

/**
 * Converts Leaflet [latitude, longitude] to GeoJSON [longitude, latitude].
 */
export function leafletLatLngToGeoJson(latLng: LeafletLatLng): GeoJsonCoord {
  if (!latLng || latLng.length < 2) {
    throw new Error(`Invalid Leaflet latLng: ${JSON.stringify(latLng)}`);
  }
  const [lat, lon] = latLng;
  return [lon, lat];
}

/**
 * Converts an array of GeoJSON coordinates [[lon, lat], ...] to Leaflet [[lat, lon], ...].
 */
export function geoJsonLineToLeaflet(coords: GeoJsonCoord[]): LeafletLatLng[] {
  if (!Array.isArray(coords)) return [];
  return coords.map(geoJsonToLeafletLatLng);
}

/**
 * Converts GeoJSON Polygon rings [[[lon, lat], ...], ...] to Leaflet [[[lat, lon], ...], ...].
 */
export function geoJsonPolygonToLeaflet(rings: GeoJsonCoord[][]): LeafletLatLng[][] {
  if (!Array.isArray(rings)) return [];
  return rings.map(ring => ring.map(geoJsonToLeafletLatLng));
}

/**
 * Validates that coordinates are within legitimate geographic ranges:
 * Longitude in [-180, 180], Latitude in [-90, 90].
 * Also flags potential lat/lon inversion if points are outside expected bounding box.
 */
export function validateCoordinates(
  coords: GeoJsonCoord[],
  expectedBounds?: { minLon: number; minLat: number; maxLon: number; maxLat: number }
): { valid: boolean; error?: string } {
  if (!coords || coords.length === 0) {
    return { valid: false, error: 'Empty coordinate sequence' };
  }

  for (let i = 0; i < coords.length; i++) {
    const pt = coords[i];
    if (!Array.isArray(pt) || pt.length < 2) {
      return { valid: false, error: `Point at index ${i} is not a valid coordinate pair` };
    }
    const [lon, lat] = pt;
    if (typeof lon !== 'number' || isNaN(lon) || !isFinite(lon)) {
      return { valid: false, error: `Invalid longitude at index ${i}: ${lon}` };
    }
    if (typeof lat !== 'number' || isNaN(lat) || !isFinite(lat)) {
      return { valid: false, error: `Invalid latitude at index ${i}: ${lat}` };
    }
    if (lon < -180 || lon > 180) {
      return { valid: false, error: `Longitude ${lon} out of WGS84 range [-180, 180]` };
    }
    if (lat < -90 || lat > 90) {
      return { valid: false, error: `Latitude ${lat} out of WGS84 range [-90, 90]` };
    }

    if (expectedBounds) {
      if (
        lon < expectedBounds.minLon ||
        lon > expectedBounds.maxLon ||
        lat < expectedBounds.minLat ||
        lat > expectedBounds.maxLat
      ) {
        return {
          valid: false,
          error: `Point [${lon}, ${lat}] is outside expected geographic bounds [${expectedBounds.minLon}, ${expectedBounds.minLat}, ${expectedBounds.maxLon}, ${expectedBounds.maxLat}]`,
        };
      }
    }
  }

  return { valid: true };
}

/**
 * Computes bounding box [minLon, minLat, maxLon, maxLat] from GeoJSON coordinates.
 */
export function computeBBox(coords: GeoJsonCoord[]): [number, number, number, number] {
  if (!coords || coords.length === 0) return [0, 0, 0, 0];
  let minLon = Infinity;
  let minLat = Infinity;
  let maxLon = -Infinity;
  let maxLat = -Infinity;

  for (const [lon, lat] of coords) {
    if (lon < minLon) minLon = lon;
    if (lat < minLat) minLat = lat;
    if (lon > maxLon) maxLon = lon;
    if (lat > maxLat) maxLat = lat;
  }

  return [minLon, minLat, maxLon, maxLat];
}

/**
 * Computes arithmetic centroid [lat, lon] for Leaflet map centering from GeoJSON coordinates.
 */
export function computeCentroidLeaflet(coords: GeoJsonCoord[]): LeafletLatLng {
  if (!coords || coords.length === 0) return [0, 0];
  let sumLon = 0;
  let sumLat = 0;

  for (const [lon, lat] of coords) {
    sumLon += lon;
    sumLat += lat;
  }

  return [sumLat / coords.length, sumLon / coords.length];
}
