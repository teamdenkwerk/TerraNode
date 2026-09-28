import { BuildingEntity, ReconciliationStats, UploadedFile, DatasetMeta } from '../types';
import osmGisBuildings from './osmGisBuildings.json';

// Anchor point: Indiranagar / Halasuru zone, Bengaluru (NAKSHA Urban Pilot Sector 4)
const CENTER_LAT = 12.9784;
const CENTER_LNG = 77.6408;

// Helper to create polygon coordinates with jitter/variation
export function generateFootprint(
  baseLat: number,
  baseLng: number,
  widthMeters: number,
  heightMeters: number,
  offsetLatMeters: number = 0,
  offsetLngMeters: number = 0,
  scale: number = 1.0,
  rotationDeg: number = 0
): [number, number][] {
  const degPerMeterLat = 1 / 110574;
  const degPerMeterLng = 1 / (111320 * Math.cos((baseLat * Math.PI) / 180));

  const centerLat = baseLat + offsetLatMeters * degPerMeterLat;
  const centerLng = baseLng + offsetLngMeters * degPerMeterLng;

  const w = (widthMeters * scale * degPerMeterLng) / 2;
  const h = (heightMeters * scale * degPerMeterLat) / 2;

  const rad = (rotationDeg * Math.PI) / 180;
  const cos = Math.cos(rad);
  const sin = Math.sin(rad);

  const localCorners = [
    [-w, -h],
    [w, -h],
    [w, h],
    [-w, h],
  ];

  return localCorners.map(([dx, dy]) => {
    const rotX = dx * cos - dy * sin;
    const rotY = dx * sin + dy * cos;
    return [centerLat + rotY, centerLng + rotX] as [number, number];
  });
}

// ============================================================================
// AUTHENTIC OPENSTREETMAP GIS BUILDING FOOTPRINTS (ZERO SYNTHETIC DRIFT ONTO ROADS)
// ============================================================================

// Curated Showcase Buildings backed by authentic GIS footprints
export const showcaseBuilding1028: BuildingEntity = (osmGisBuildings.bengaluru[0] as unknown as BuildingEntity);
export const showcaseBuilding1044: BuildingEntity = (osmGisBuildings.bengaluru[1] as unknown as BuildingEntity);
export const showcaseBuilding1015: BuildingEntity = (osmGisBuildings.bengaluru[2] as unknown as BuildingEntity);

// Real GIS buildings from OpenStreetMap / municipal cadastre
export function generateGridBuildings(): BuildingEntity[] {
  return osmGisBuildings.bengaluru as unknown as BuildingEntity[];
}

export const mockBuildings: BuildingEntity[] = generateGridBuildings();

export const defaultStats: ReconciliationStats = {
  totalBuildings: 1248,
  matched: 1103,
  averageConfidence: 94,
  requiresReview: 37,
  conflictsDetected: 42,
  autoResolved: 31,
  beforeConflicts: 42,
  afterConflicts: 11,
  beforeAvgConfidence: 82,
  afterAvgConfidence: 94,
};
export const initialStats = defaultStats;

// Specialized Generator for Mumbai (Andheri East MIDC / SEEPZ Corridor)
// Backed by authentic OpenStreetMap GIS building footprints matching the basemap
export function generateMumbaiBuildings(): BuildingEntity[] {
  return osmGisBuildings.mumbai as unknown as BuildingEntity[];
}

// Specialized Generator for Chennai (T. Nagar Commercial & Residential Fabric)
// Backed by authentic OpenStreetMap GIS building footprints matching the basemap
export function generateChennaiBuildings(): BuildingEntity[] {
  return osmGisBuildings.chennai as unknown as BuildingEntity[];
}

// Specialized Generator for Delhi NCR (Central Secretariat / Rajpath / Connaught Place District)
// Backed by authentic OpenStreetMap GIS building footprints matching the basemap
export function generateDelhiBuildings(): BuildingEntity[] {
  return osmGisBuildings.delhi as unknown as BuildingEntity[];
}


// Helper to create synthetic parcels around any custom coordinates
export function createParcelsAroundCenter(
  centerLat: number,
  centerLng: number,
  cityPrefix: string = "PARCEL",
  surveyPrefix: string = "SURV",
  aoiName: string = "Regional Sector",
  zoneName: string = "Municipal Zone"
): BuildingEntity[] {
  const rows = 8;
  const cols = 9;
  const buildings: BuildingEntity[] = [];
  const landUses = ["Commercial", "Residential", "Mixed Use", "Institutional"];

  let counter = 101;
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      if (buildings.length >= 72) break;
      const lat = centerLat + (r - 3.5) * 0.00062 + ((c % 2) * 0.00007);
      const lng = centerLng + (c - 4.0) * 0.00078 + ((r % 2) * 0.00005);
      const width = 18 + ((r * 5 + c * 7) % 14);
      const length = 20 + ((r * 10 + c * 4) % 15);
      const area = Math.round(width * length * 1.6);
      const hash = (r * 19 + c * 37) % 100;
      const status: 'reconciled' | 'review' | 'conflict' = hash < 8 ? 'conflict' : hash < 22 ? 'review' : 'reconciled';
      const confidence = status === 'conflict' ? 62 + (hash % 10) : status === 'review' ? 78 + (hash % 10) : 93 + (hash % 6);
      const coords = generateFootprint(lat, lng, width, length, 0, 0, 1.0, (r * 7 + c * 11) % 30);
      const centroid: [number, number] = [lat, lng];

      buildings.push({
        id: `${cityPrefix.toUpperCase().slice(0, 4)}-${counter}`,
        osmId: 500000000 + counter,
        name: `${aoiName} Parcel #${counter}`,
        surveyNumber: `${surveyPrefix}-${100 + r}/${c + 1}`,
        wardNo: aoiName,
        zone: zoneName,
        status,
        confidence,
        area,
        landUse: landUses[(r + c) % landUses.length],
        height: 14 + ((r * 5 + c * 3) % 20),
        floors: 3 + ((r + c) % 6),
        sourcesCount: 4,
        agreementScore: confidence,
        lastUpdated: "Just now",
        centroid,
        coordinates: coords,
        sources: {
          cadastral: { coordinates: coords, confidence: 90, source: "Cadastral Survey" },
          municipal: { coordinates: coords, confidence: 88, source: "Municipal GIS" },
          drone: { coordinates: coords, confidence: 95, source: "Drone Survey" },
          ai: { coordinates: coords, confidence: 92, source: "AI Extraction" },
        },
      });
      counter++;
    }
  }
  return buildings;
}

// General fallback generator for user-uploaded custom regional datasets
export function generateCityBuildings(
  centerLat: number,
  centerLng: number,
  cityPrefix: string = "PARCEL",
  surveyPrefix: string = "SURV",
  aoiName: string = "Regional Sector",
  zoneName: string = "Municipal Zone"
): BuildingEntity[] {
  const norm = (cityPrefix || '').toUpperCase();
  if (norm.includes('DEL') || (centerLat >= 28.0 && centerLat <= 29.5 && centerLng >= 76.5 && centerLng <= 78.0)) {
    return generateDelhiBuildings();
  }
  if (norm.includes('MUM') || (centerLat >= 18.5 && centerLat <= 19.5 && centerLng >= 72.5 && centerLng <= 73.2)) {
    return generateMumbaiBuildings();
  }
  if (norm.includes('CHN') || (centerLat >= 12.5 && centerLat <= 13.5 && centerLng >= 80.0 && centerLng <= 80.5)) {
    return generateChennaiBuildings();
  }
  if (norm.includes('BLR') || norm.includes('BEN') || (centerLat >= 12.5 && centerLat <= 13.5 && centerLng >= 77.2 && centerLng <= 77.9)) {
    return generateGridBuildings();
  }
  return createParcelsAroundCenter(centerLat, centerLng, cityPrefix, surveyPrefix, aoiName, zoneName);
}

export const bengaluruDataset: DatasetMeta = {
  id: "bengaluru-domlur",
  name: "Bengaluru — Domlur",
  city: "Bengaluru",
  cityId: "blr",
  aoi: "Domlur",
  aoiId: "blr-domlur",
  sources: ["Revenue Cadastral (Khasra)", "Drone ORI (5cm)", "BBMP Municipal GIS", "CORS RTK Survey", "AI SAM-2"],
  crs: "EPSG:7760 / EPSG:32643 → EPSG:4326",
  crsStatus: "validated",
  bbox: [77.635, 12.972, 77.647, 12.985],
  bounds: [[12.972, 77.635], [12.985, 77.647]],
  center: [12.9784, 77.6408],
  defaultZoom: 17,
  uploadDate: "03 Sep 2026",
  version: "v2.4",
  isReference: true,
  dataset_status: 'ACTIVE',
  processing_status: 'READY',
  featuresCount: 1248,
  stats: defaultStats,
  buildings: mockBuildings,
};

// 2. Mumbai Independent Dataset (Available for custom upload expansion)
const mumbaiBuildings = generateMumbaiBuildings();

export const mumbaiDataset: DatasetMeta = {
  id: "mumbai-andheri",
  name: "Mumbai — Andheri East",
  city: "Mumbai",
  cityId: "bom",
  aoi: "Andheri East",
  aoiId: "bom-andheri-e",
  sources: ["Cadastral (CTS)", "MCGM Property Tax GIS", "Drone ORI (MMRDA)", "AI Extraction"],
  crs: "EPSG:32643 (UTM 43N) → EPSG:4326",
  crsStatus: "validated",
  bbox: [72.862, 19.108, 72.878, 19.122],
  bounds: [[19.108, 72.862], [19.122, 72.878]],
  center: [19.1136, 72.8697],
  defaultZoom: 16,
  uploadDate: "02 Sep 2026",
  version: "v1.0-cadastre",
  isReference: false,
  dataset_status: 'ARCHIVED',
  processing_status: 'READY',
  featuresCount: 980,
  stats: {
    totalBuildings: 980,
    matched: 874,
    averageConfidence: 93,
    requiresReview: 28,
    conflictsDetected: 34,
    autoResolved: 26,
    beforeConflicts: 34,
    afterConflicts: 8,
    beforeAvgConfidence: 81,
    afterAvgConfidence: 93,
  },
  buildings: mumbaiBuildings,
};

// 3. Chennai Independent Dataset (Available for custom upload expansion)
const chennaiBuildings = generateChennaiBuildings();

export const chennaiDataset: DatasetMeta = {
  id: "chennai-tnagar",
  name: "Chennai — T. Nagar AOI",
  city: "Chennai",
  cityId: "maa",
  aoi: "T. Nagar AOI",
  aoiId: "maa-tnagar",
  sources: ["Revenue Cadastral (Town Survey)", "GCC Municipal GIS", "Drone ORI (TIDCO)"],
  crs: "EPSG:32644 (UTM 44N) → EPSG:4326",
  crsStatus: "validated",
  bbox: [80.226, 13.036, 80.244, 13.048],
  bounds: [[13.036, 80.226], [13.048, 80.244]],
  center: [13.0418, 80.2341],
  defaultZoom: 16,
  uploadDate: "01 Sep 2026",
  version: "v1.1-gcc",
  isReference: false,
  dataset_status: 'ARCHIVED',
  processing_status: 'READY',
  featuresCount: 840,
  stats: {
    totalBuildings: 840,
    matched: 760,
    averageConfidence: 95,
    requiresReview: 18,
    conflictsDetected: 22,
    autoResolved: 17,
    beforeConflicts: 22,
    afterConflicts: 5,
    beforeAvgConfidence: 83,
    afterAvgConfidence: 95,
  },
  buildings: chennaiBuildings,
};

// 4. Delhi NCR Independent Dataset
const delhiBuildings = generateDelhiBuildings();

export const delhiDataset: DatasetMeta = {
  id: "delhi-urban",
  name: "Delhi NCR — Central Secretariat",
  city: "Delhi NCR",
  cityId: "del",
  aoi: "Central Secretariat",
  aoiId: "del-urban",
  sources: ["DDA Master Plan Cadastre", "Revenue Khasra Records", "Drone Orthomosaic (Survey of India)", "NDMC Property GIS"],
  crs: "EPSG:32643 (UTM 43N) → EPSG:4326",
  crsStatus: "validated",
  bbox: [77.198, 28.607, 77.226, 28.627],
  bounds: [[28.607, 77.198], [28.627, 77.226]],
  center: [28.6155, 77.2105],
  defaultZoom: 16,
  uploadDate: "Just now",
  version: "v1.2-dda",
  isReference: false,
  dataset_status: 'ACTIVE',
  processing_status: 'READY',
  featuresCount: 72,
  stats: {
    totalBuildings: 72,
    matched: 44,
    averageConfidence: 94,
    requiresReview: 22,
    conflictsDetected: 6,
    autoResolved: 16,
    beforeConflicts: 28,
    afterConflicts: 6,
    beforeAvgConfidence: 82,
    afterAvgConfidence: 94,
  },
  buildings: delhiBuildings,
};

export const initialDatasets: DatasetMeta[] = [
  bengaluruDataset,
  delhiDataset,
  mumbaiDataset,
  chennaiDataset,
];

export const mockUploadedFiles: UploadedFile[] = [
  {
    id: "UPL-001",
    name: "ORI_Domlur_Zone4_5cm.tif",
    dataType: "Drone / ORI",
    size: "482.6 MB",
    uploadDate: "03 Sep 2026, 08:30 AM",
    status: "processed",
    crsDetected: "EPSG:32643 (UTM 43N) → Harmonized to EPSG:4326",
    featuresCount: 1248,
    errorCount: 0,
    city: "Bengaluru",
    aoi: "Domlur",
    datasetId: "bengaluru-domlur",
  },
  {
    id: "UPL-002",
    name: "BBMP_Domlur_Cadastral_Revenue.shp",
    dataType: "Cadastral",
    size: "28.4 MB",
    uploadDate: "03 Sep 2026, 08:45 AM",
    status: "processed",
    crsDetected: "EPSG:7760 (KSRSAC Grid) → Aligned",
    featuresCount: 1205,
    errorCount: 4,
    city: "Bengaluru",
    aoi: "Domlur",
    datasetId: "bengaluru-domlur",
  },
  {
    id: "UPL-003",
    name: "BBMP_Domlur_PropertyTax_GIS.geojson",
    dataType: "Municipal GIS",
    size: "18.6 MB",
    uploadDate: "02 Sep 2026, 04:10 PM",
    status: "processed",
    crsDetected: "EPSG:32643 (UTM 43N) → Aligned",
    featuresCount: 980,
    errorCount: 0,
    city: "Bengaluru",
    aoi: "Domlur",
    datasetId: "bengaluru-domlur",
    detectionMessage: "BBMP Property Tax Layer — Domlur AOI (EPSG:4326)",
  },
  {
    id: "UPL-004",
    name: "CORS_RTK_Domlur_Field_GroundTruth.csv",
    dataType: "Ground Truth",
    size: "14.2 MB",
    uploadDate: "01 Sep 2026, 02:20 PM",
    status: "processed",
    crsDetected: "EPSG:4326 (WGS 84) → Aligned",
    featuresCount: 840,
    errorCount: 0,
    city: "Bengaluru",
    aoi: "Domlur",
    datasetId: "bengaluru-domlur",
    detectionMessage: "Survey of India CORS RTK Rover points — Domlur AOI",
  },
];
export const initialUploadedFiles = mockUploadedFiles;

export const recentActivities = [
  { id: 1, title: "Spatial reconciliation completed for Domlur Block 4", time: "12 mins ago", type: "success" },
  { id: 2, title: "Building #BLD-1028 unified from 4 multi-source geometries (94% confidence)", time: "24 mins ago", type: "verified" },
  { id: 3, title: "High conflict flagged on Building #BLD-1015 (Road boundary encroachment)", time: "45 mins ago", type: "warning" },
  { id: 4, title: "Drone ORI 5cm GeoTIFF tile aligned automatically to EPSG:4326", time: "1 hour ago", type: "info" },
  { id: 5, title: "Auto-resolved 31 minor eave offsets using DTM elevation filter", time: "2 hours ago", type: "success" },
];
