/**
 * src/hooks/useLiveBuildings.ts
 *
 * Loads buildings from the real Geo-Reconciliation API. Falls back to the
 * existing mock data (src/data/mockBuildings.ts) if the API is unreachable
 * or returns nothing — so the demo never breaks if the backend/DB isn't
 * running, but shows real data the moment it is.
 */

import { useEffect, useState } from 'react';
import { BuildingEntity } from '../types';
import { generateGridBuildings } from '../data/mockBuildings';
import { fetchEntities, fetchReviewQueue, BBox } from '../api/geoReconciliationClient';
import { adaptEntitySummary } from '../api/adapter';
import { fetchOsmFallbackBuildings } from '../data/fetchOsmFallbackBuildings';

// Matches config.DISTRICT_BBOX in the backend repo (Koramangala + HSR +
// Indiranagar demo district). Update this if that changes.
export const DEFAULT_BBOX: BBox = {
  minLon: 77.58,
  minLat: 12.9,
  maxLon: 77.66,
  maxLat: 12.99,
};

// 'live'      — real reconciled entities from the Geo-Reconciliation backend.
// 'osm'       — real building footprints fetched straight from OpenStreetMap
//               in the browser (real positions, but single-source/unreconciled
//               — see fetchOsmFallbackBuildings.ts).
// 'mock'      — fully synthetic procedural grid; last-resort only, used when
//               both the backend AND OpenStreetMap are unreachable (e.g. no
//               network at all).
export type DataSource = 'live' | 'osm' | 'mock';

interface UseLiveBuildingsResult {
  buildings: BuildingEntity[];
  source: DataSource;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

export function useLiveBuildings(bbox: BBox = DEFAULT_BBOX): UseLiveBuildingsResult {
  const [buildings, setBuildings] = useState<BuildingEntity[]>([]);
  const [source, setSource] = useState<DataSource>('mock');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refetchTick, setRefetchTick] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);

      // Tier 1: the real reconciliation backend.
      try {
        const entities = await fetchEntities(bbox);
        if (cancelled) return;
        if (entities.length > 0) {
          setBuildings(entities.map(adaptEntitySummary));
          setSource('live');
          setLoading(false);
          return;
        }
        // Backend reachable but nothing ingested yet — fall through to
        // OSM rather than immediately giving up on real data.
      } catch (e) {
        if (cancelled) return;
        console.warn('Geo-Reconciliation API unreachable, trying OSM fallback:', e);
        setError(e instanceof Error ? e.message : String(e));
      }

      // Tier 2: real OSM building footprints (real positions, unreconciled).
      try {
        const osmBuildings = await fetchOsmFallbackBuildings(bbox);
        if (cancelled) return;
        setBuildings(osmBuildings);
        setSource('osm');
        setLoading(false);
        return;
      } catch (e) {
        if (cancelled) return;
        console.warn('OSM fallback also unreachable, using synthetic demo grid:', e);
      }

      // Tier 3: fully synthetic grid — only reached with no network path to
      // either real source at all.
      if (!cancelled) {
        setBuildings(generateGridBuildings());
        setSource('mock');
        setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [bbox.minLon, bbox.minLat, bbox.maxLon, bbox.maxLat, refetchTick]);

  return {
    buildings,
    source,
    loading,
    error,
    refetch: () => setRefetchTick((t) => t + 1),
  };
}

/** Same idea, scoped to the review queue endpoint — use this in
 *  ReviewQueueView if you want it to reflect the live `needs_review` set
 *  rather than filtering the already-loaded `buildings` array client-side. */
export async function loadReviewQueue(bbox?: BBox): Promise<BuildingEntity[]> {
  const entities = await fetchReviewQueue(bbox);
  return entities.map(adaptEntitySummary);
}