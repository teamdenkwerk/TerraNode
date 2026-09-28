export type ConfidenceTier = 'high' | 'medium' | 'low';

export type BuildingStatus = 'reconciled' | 'review' | 'conflict';

export type SourceType = 'ori' | 'municipal' | 'cadastral' | 'ai';

export interface SourceData {
  sourceName: string;
  sourceType: SourceType;
  area: number;
  coordinates: [number, number][];
  confidence: number;
  captureDate: string;
  resolutionOrScale: string;
  color: string;
}

export interface VerificationChecks {
  geometryAgreement: boolean;
  sourceAgreement: boolean;
  attributeAgreement: boolean;
  spatialProximity: boolean;
}

export interface ConflictDetails {
  severity: 'high' | 'medium' | 'low';
  title: string;
  simplifiedReason: string;
  technicalReason: string;
  iouScore: number;
  centroidOffsetMeters: number;
  recommendedArea: number;
  recommendedSource: string;
  sourcesDiff: {
    source: string;
    area: number;
    difference: number;
    note: string;
  }[];
}

export interface BuildingEntity {
  id: string;
  surveyNumber: string;
  wardNo: string;
  zone: string;
  status: BuildingStatus;
  confidence: number;
  area: number;
  landUse: 'Residential' | 'Commercial' | 'Institutional' | 'Mixed Use' | 'Industrial' | 'Not classified';
  height: number | null;
  floors: number | null;
  sourcesCount: number;
  agreementScore: number;
  lastUpdated: string;
  coordinates: [number, number][]; // Reconciled polygon [lat, lng]
  beforeCoordinates?: [number, number][]; // Inconsistent source polygon before reconciliation
  centroid: [number, number];
  sources: {
    ori: SourceData;
    municipal: SourceData;
    cadastral: SourceData;
    ai: SourceData;
  };
  verificationChecks: VerificationChecks;
  conflictDetails?: ConflictDetails;
  history: {
    date: string;
    action: string;
    actor: string;
    note: string;
  }[];
}

export interface UploadedFile {
  id: string;
  name: string;
  dataType: string;
  size: string;
  uploadDate: string;
  status: 'processed' | 'processing' | 'ready' | 'flagged';
  crsDetected: string;
  featuresCount: number;
  errorCount: number;
  city?: string;
  aoi?: string;
  datasetId?: string;
  bounds?: [[number, number], [number, number]];
  detectionMessage?: string;
}

export type DatasetStatus = 'ACTIVE' | 'PROCESSING' | 'ARCHIVED' | 'FAILED' | 'REPLACED';
export type ProcessingStatus = 'READY' | 'SCANNING' | 'VALIDATING' | 'PROCESSING' | 'ERROR';

export interface StandardLayerInfo {
  category: string;
  title: string;
  description: string;
  files_count?: number;
  features_count?: number;
  required?: boolean;
  status: 'present' | 'missing';
}

export interface DatasetScanReport {
  valid: boolean;
  area: string;
  city_id?: string;
  aoi: string;
  aoi_id?: string;
  folders_count: number;
  files_count: number;
  detected_layers: StandardLayerInfo[];
  missing_layers: StandardLayerInfo[];
  warnings: string[];
  crs_detected: string;
  bbox: [number, number, number, number];
  center: [number, number];
  features_count: number;
  current_active_area?: string;
  current_active_aoi?: string;
  requires_replacement_confirmation?: boolean;
}

export interface DatasetMeta {
  id: string;
  name: string;
  city: string;
  cityId: string;
  aoi: string;
  aoiId: string;
  sources: string[];
  crs: string;
  crsStatus: 'validated' | 'transformed' | 'missing' | 'error';
  bbox: [number, number, number, number]; // [minLon, minLat, maxLon, maxLat]
  bounds: [[number, number], [number, number]]; // [[minLat, minLon], [maxLat, maxLon]] for Leaflet
  center: [number, number]; // [lat, lon]
  defaultZoom: number;
  uploadDate: string;
  version: string;
  isReference: boolean;
  featuresCount: number;
  stats?: ReconciliationStats;
  buildings: BuildingEntity[];
  dataset_status?: DatasetStatus;
  processing_status?: ProcessingStatus;
  coverage?: string;
  layers_count?: number;
  detected_layers?: StandardLayerInfo[];
  archived_at?: string;
  is_active?: boolean;
}

export interface ReconciliationStats {
  totalBuildings: number;
  matched: number;
  averageConfidence: number;
  requiresReview: number;
  conflictsDetected: number;
  autoResolved: number;
  beforeConflicts: number;
  afterConflicts: number;
  beforeAvgConfidence: number;
  afterAvgConfidence: number;
}

export interface ActivityEntry {
  id: string;
  timestamp: number; // real Date.now(), not an invented "X mins ago" string
  type: 'success' | 'warning' | 'verified' | 'info';
  title: string;
}

export type ActiveTab = 
  | 'upload'          // 01 UPLOAD DOCUMENTS
  | 'gis'              // 02 GIS EXPLORER
  | 'harmonization'    // 03 HARMONIZATION
  | 'review'           // 04 REVIEW & VERIFICATION
  | 'validation'       // 05 VALIDATION
  | 'analytics'        // 06 LAND DATA INSIGHTS
  | 'reports'          // 07 REPORTS
  | 'data'             // alias for upload
  | 'map'              // alias for gis
  | 'dashboard';       // legacy alias (mapped to gis)

export type Language = 'en' | 'hi';

export type MatchType = 'EXACT' | 'SYNONYM' | 'ABBREVIATION' | 'TOKEN_OVERLAP' | 'FUZZY_STRING' | 'UNKNOWN';

export type MappingStatus = 'suggested' | 'confirmed' | 'rejected' | 'low_confidence' | 'conflicting' | 'unmapped';

export interface FieldMappingSuggestion {
  source_field: string;
  normalized_source_field: string;
  suggested_canonical_field: string | null;
  confidence: number;
  match_type: MatchType;
  status: MappingStatus;
  is_low_confidence: boolean;
  is_conflicting: boolean;
  sample_values: any[];
  decision_reason: string;
}

export interface SchemaMappingResponse {
  success: boolean;
  dataset_id: string;
  dataset_version: string;
  total_fields: number;
  mapped_fields_count: number;
  unmapped_fields_count: number;
  low_confidence_fields_count: number;
  conflicting_fields_count: number;
  mappings: FieldMappingSuggestion[];
  audit_metadata?: {
    generated_at?: string;
    is_confirmed?: boolean;
    confirmed_by?: string;
    engine?: string;
    [key: string]: any;
  };
}

export interface ConfirmMappingRequest {
  dataset_version?: string;
  confirmed_by?: string;
  mappings: Record<string, string | null>;
  notes?: string;
}

export interface ConfirmedSchemaRecord {
  dataset_id: string;
  dataset_version: string;
  confirmed_by: string;
  confirmed_at: string;
  mappings: Record<string, string | null>;
  notes?: string;
  applied_to_dataset: boolean;
}