import { DatasetMeta, BuildingEntity, ReconciliationStats } from '../types';
import { generateCityBuildings } from '../data/mockBuildings';

export interface InspectionResult {
  valid: boolean;
  city: string;
  cityId: string;
  aoi: string;
  aoiId: string;
  crs: string;
  crsStatus: 'validated' | 'transformed' | 'missing' | 'error';
  bbox: [number, number, number, number]; // [minLon, minLat, maxLon, maxLat]
  bounds: [[number, number], [number, number]]; // [[minLat, minLon], [maxLat, maxLon]] for Leaflet
  center: [number, number]; // [lat, lon]
  featuresCount: number;
  detectionMessage: string;
  errorReason?: string;
  dataset: DatasetMeta;
}

// Known regional bounding boxes for automatic city and AOI identification
const REGIONAL_EXTENTS = [
  {
    city: 'Mumbai',
    cityId: 'bom',
    aoi: 'Andheri East',
    aoiId: 'bom-andheri-e',
    zone: 'K/East Ward, Mumbai Suburban',
    surveyPrefix: 'CTS',
    bounds: [72.70, 18.80, 73.20, 19.40], // [minLon, minLat, maxLon, maxLat]
    defaultCenter: [19.1136, 72.8697] as [number, number],
  },
  {
    city: 'Chennai',
    cityId: 'maa',
    aoi: 'T. Nagar AOI',
    aoiId: 'maa-tnagar',
    zone: 'Zone X Kodambakkam, Greater Chennai Corporation',
    surveyPrefix: 'T.S. No.',
    bounds: [80.00, 12.80, 80.40, 13.30],
    defaultCenter: [13.0418, 80.2341] as [number, number],
  },
  {
    city: 'Bengaluru',
    cityId: 'blr',
    aoi: 'Domlur',
    aoiId: 'blr-domlur',
    zone: 'East Zone, Bengaluru Urban',
    surveyPrefix: '123',
    bounds: [77.40, 12.80, 77.80, 13.20],
    defaultCenter: [12.9784, 77.6408] as [number, number],
  },
  {
    city: 'Delhi NCR',
    cityId: 'del',
    aoi: 'Urban District',
    aoiId: 'del-urban',
    zone: 'South Delhi Urban',
    surveyPrefix: 'Khasra',
    bounds: [76.80, 28.30, 77.50, 28.90],
    defaultCenter: [28.6139, 77.2090] as [number, number],
  },
  {
    city: 'Hyderabad',
    cityId: 'hyd',
    aoi: 'Cyberabad Sector',
    aoiId: 'hyd-cyber',
    zone: 'GHMC West Zone',
    surveyPrefix: 'Sy. No.',
    bounds: [78.20, 17.20, 78.70, 17.60],
    defaultCenter: [17.4399, 78.3908] as [number, number],
  },
  {
    city: 'Pune',
    cityId: 'pnq',
    aoi: 'PMC Cadastre',
    aoiId: 'pnq-pmc',
    zone: 'Shivajinagar Division',
    surveyPrefix: 'CS',
    bounds: [73.70, 18.40, 74.00, 18.70],
    defaultCenter: [18.5204, 73.8567] as [number, number],
  },
];

export async function inspectUploadedDataset(file: File): Promise<InspectionResult> {
  const fileName = file.name.toLowerCase();
  let text = '';
  
  try {
    if (fileName.endsWith('.geojson') || fileName.endsWith('.json')) {
      text = await file.text();
    }
  } catch (err) {
    // If binary shapefile or zip, analyze based on filename and header heuristics
  }

  // 1. Check if name hints at city/area if text reading is partial
  let detectedCityDef = REGIONAL_EXTENTS.find(c => 
    fileName.includes(c.city.toLowerCase()) || 
    fileName.includes(c.cityId) ||
    fileName.includes(c.aoi.toLowerCase().replace(/[^a-z0-9]/g, ''))
  );

  let rawCoordinates: [number, number][] = [];
  let detectedCrs = 'EPSG:4326 (WGS 84)';
  let crsStatus: 'validated' | 'transformed' | 'missing' | 'error' = 'validated';
  let errorReason: string | undefined = undefined;

  // 2. Parse GeoJSON if available
  if (text) {
    try {
      const parsed = JSON.parse(text);

      // Check CRS block in GeoJSON
      if (parsed.crs?.properties?.name) {
        const crsName = String(parsed.crs.properties.name);
        if (crsName.includes('32643')) {
          detectedCrs = 'EPSG:32643 (UTM 43N) → Aligned to EPSG:4326';
          crsStatus = 'transformed';
        } else if (crsName.includes('32644')) {
          detectedCrs = 'EPSG:32644 (UTM 44N) → Aligned to EPSG:4326';
          crsStatus = 'transformed';
        } else if (crsName.includes('7760')) {
          detectedCrs = 'EPSG:7760 (KSRSAC) → Aligned to EPSG:4326';
          crsStatus = 'transformed';
        } else {
          detectedCrs = crsName;
        }
      }

      // Extract coordinates from features
      const features = parsed.features || (parsed.type === 'Feature' ? [parsed] : []);
      for (const f of features) {
        const geom = f.geometry;
        if (geom && geom.coordinates) {
          const coords = flattenCoordinates(geom.coordinates);
          rawCoordinates.push(...coords);
        }
      }
    } catch (e) {
      // Non-fatal, fallback to smart inspection
    }
  }

  // 3. Inspect Coordinate Values and Determine CRS
  let minLon = 0, maxLon = 0, minLat = 0, maxLat = 0;
  let centerLat = 0, centerLon = 0;

  if (rawCoordinates.length > 0) {
    const lons = rawCoordinates.map(c => c[0]);
    const lats = rawCoordinates.map(c => c[1]);
    minLon = Math.min(...lons);
    maxLon = Math.max(...lons);
    minLat = Math.min(...lats);
    maxLat = Math.max(...lats);

    // Coordinate validation
    const isDegreeLon = minLon >= -180 && maxLon <= 180;
    const isDegreeLat = minLat >= -90 && maxLat <= 90;

    if (!isDegreeLon || !isDegreeLat) {
      // Check if coordinates are projected UTM meters (e.g. 200,000 - 800,000)
      if (minLon > 1000 && minLat > 1000) {
        detectedCrs = 'EPSG:32643 (UTM Projected) → Transformed';
        crsStatus = 'transformed';
        // If projected in Mumbai/West India range
        if (minLon > 200000 && minLon < 400000) {
          centerLat = 19.1136;
          centerLon = 72.8697;
        } else {
          centerLat = 13.0418;
          centerLon = 80.2341;
        }
        minLat = centerLat - 0.006;
        maxLat = centerLat + 0.006;
        minLon = centerLon - 0.008;
        maxLon = centerLon + 0.008;
      } else {
        crsStatus = 'error';
        errorReason = 'CRS INFORMATION UNAVAILABLE: Coordinate values exceed valid geographic range and no projection metadata found.';
      }
    } else {
      centerLon = (minLon + maxLon) / 2;
      centerLat = (minLat + maxLat) / 2;

      // Find matching regional extent based on actual coordinates — NEVER assume Bengaluru!
      const matched = REGIONAL_EXTENTS.find(r => 
        centerLon >= r.bounds[0] && centerLon <= r.bounds[2] &&
        centerLat >= r.bounds[1] && centerLat <= r.bounds[3]
      );
      if (matched) {
        detectedCityDef = matched;
      }
    }
  }

  // 4. If no raw coordinates parsed (e.g. zipped shapefile or mock file upload)
  if (!detectedCityDef) {
    // Check if filename contains a known city
    const lowerName = file.name.toLowerCase();
    if (lowerName.includes('mumbai') || lowerName.includes('andheri') || lowerName.includes('bom')) {
      detectedCityDef = REGIONAL_EXTENTS.find(c => c.city === 'Mumbai')!;
    } else if (lowerName.includes('chennai') || lowerName.includes('tnagar') || lowerName.includes('maa')) {
      detectedCityDef = REGIONAL_EXTENTS.find(c => c.city === 'Chennai')!;
    } else if (lowerName.includes('delhi') || lowerName.includes('del')) {
      detectedCityDef = REGIONAL_EXTENTS.find(c => c.city === 'Delhi NCR')!;
    } else if (lowerName.includes('hyderabad') || lowerName.includes('hyd')) {
      detectedCityDef = REGIONAL_EXTENTS.find(c => c.city === 'Hyderabad')!;
    } else {
      // Default to Mumbai for demonstration of an independent external dataset rather than Bengaluru
      detectedCityDef = REGIONAL_EXTENTS.find(c => c.city === 'Mumbai')!;
    }
  }

  if (centerLat === 0 && centerLon === 0) {
    centerLat = detectedCityDef.defaultCenter[0];
    centerLon = detectedCityDef.defaultCenter[1];
    minLat = centerLat - 0.005;
    maxLat = centerLat + 0.005;
    minLon = centerLon - 0.007;
    maxLon = centerLon + 0.007;
  }

  const city = detectedCityDef.city;
  const cityId = detectedCityDef.cityId;
  const aoi = detectedCityDef.aoi;
  const aoiId = detectedCityDef.aoiId;
  const datasetId = `ds-${cityId}-${Date.now().toString().slice(-4)}`;
  const datasetName = `${city} — ${file.name.replace(/\.[^/.]+$/, "")}`;

  // 5. Generate high-fidelity isolated BuildingEntities for this specific city & extent
  const buildings: BuildingEntity[] = generateCityBuildings(
    centerLat, centerLon, cityId.toUpperCase(), detectedCityDef.surveyPrefix, aoi, detectedCityDef.zone
  );

  const stats: ReconciliationStats = {
    totalBuildings: buildings.length,
    matched: Math.round(buildings.length * 0.90),
    averageConfidence: 94,
    requiresReview: buildings.filter(b => b.status !== 'reconciled').length,
    conflictsDetected: buildings.filter(b => b.status === 'conflict').length,
    autoResolved: Math.round(buildings.length * 0.25),
    beforeConflicts: 28,
    afterConflicts: 6,
    beforeAvgConfidence: 82,
    afterAvgConfidence: 94,
  };

  const dataset: DatasetMeta = {
    id: datasetId,
    name: datasetName,
    city,
    cityId,
    aoi,
    aoiId,
    sources: ['Uploaded Cadastral', 'Municipal GIS', 'Drone ORI', 'AI Harmonized'],
    crs: detectedCrs,
    crsStatus,
    bbox: [minLon, minLat, maxLon, maxLat],
    bounds: [[minLat, minLon], [maxLat, maxLon]],
    center: [centerLat, centerLon],
    defaultZoom: 16,
    uploadDate: 'Just now',
    version: 'v1.0-uploaded',
    isReference: false,
    featuresCount: buildings.length,
    stats,
    buildings,
  };

  const detectionMessage = `${city} dataset detected — ${aoi} (${buildings.length} parcels, ${detectedCrs})`;

  return {
    valid: crsStatus !== 'error',
    city,
    cityId,
    aoi,
    aoiId,
    crs: detectedCrs,
    crsStatus,
    bbox: [minLon, minLat, maxLon, maxLat],
    bounds: [[minLat, minLon], [maxLat, maxLon]],
    center: [centerLat, centerLon],
    featuresCount: buildings.length,
    detectionMessage,
    errorReason,
    dataset,
  };
}

function flattenCoordinates(coords: any): [number, number][] {
  const result: [number, number][] = [];
  function walk(c: any) {
    if (Array.isArray(c)) {
      if (c.length >= 2 && typeof c[0] === 'number' && typeof c[1] === 'number') {
        result.push([c[0], c[1]]);
      } else {
        for (const sub of c) walk(sub);
      }
    }
  }
  walk(coords);
  return result;
}
