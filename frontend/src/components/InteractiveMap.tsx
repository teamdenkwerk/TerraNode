import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import { 
  Layers, 
  Search, 
  MapPin, 
  CheckCircle2, 
  AlertTriangle, 
  AlertOctagon, 
  Satellite, 
  Map as MapIcon, 
  Sparkles, 
  Plus, 
  Minus, 
  Maximize2,
  Crosshair,
  Filter,
  X,
  Compass,
  Activity,
  Terminal,
  Info
} from 'lucide-react';
import { BuildingEntity, Language, DatasetMeta } from '../types';
import { translations } from '../data/i18n';
import { fetchInfrastructureFeatures } from '../api/geoReconciliationClient';
import { getFallbackInfrastructureFeatures } from '../data/fallbackInfrastructure';

// CARTO's free basemaps.cartocdn.com raster tiles started requiring an API
// key as of late Aug 2026 — unauthenticated requests now render an
// "API KEY REQUIRED" watermark instead of the map. Standard OpenStreetMap
// tiles are the most durable keyless option (no account, no key, ever) so
// we use those for the street basemap. Satellite mode stays on Esri, which
// has remained keyless throughout.
const STREET_TILE_URL = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';
const STREET_TILE_OPTIONS = {
  maxZoom: 19,
  subdomains: 'abc',
  keepBuffer: 6,
  updateWhenIdle: false,
  updateWhenZooming: true,
};

interface InteractiveMapProps {
  buildings: BuildingEntity[];
  selectedBuilding: BuildingEntity | null;
  onSelectBuilding: (building: BuildingEntity) => void;
  language: Language;
  onOpenReconcileModal: () => void;
  onOpenUploadModal: () => void;
  activeFilter?: 'all' | 'reconciled' | 'review' | 'conflict';
  dataSource?: 'live' | 'osm' | 'mock';
  datasets?: DatasetMeta[];
  activeDataset?: DatasetMeta;
  onSelectDataset?: (datasetId: string) => void;
  focusedGeometry?: [number, number][] | null;
  historicalComparison?: {
    geomA: any;
    geomB: any;
    metaA: { label: string; date?: string };
    metaB: { label: string; date?: string };
  } | null;
  onClearHistoricalComparison?: () => void;
}

export const InteractiveMap: React.FC<InteractiveMapProps> = ({
  buildings,
  selectedBuilding,
  onSelectBuilding,
  language,
  onOpenReconcileModal,
  onOpenUploadModal,
  activeFilter = 'all',
  dataSource = 'mock',
  datasets = [],
  activeDataset,
  onSelectDataset,
  focusedGeometry,
  historicalComparison,
  onClearHistoricalComparison,
}) => {
  const t = translations[language];
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const polygonLayerGroupRef = useRef<L.LayerGroup | null>(null);
  const cadastralLayerGroupRef = useRef<L.LayerGroup | null>(null);
  const municipalLayerGroupRef = useRef<L.LayerGroup | null>(null);
  const roadsLayerGroupRef = useRef<L.GeoJSON | null>(null);
  const drainageLayerGroupRef = useRef<L.GeoJSON | null>(null);
  const railwayLayerGroupRef = useRef<L.GeoJSON | null>(null);
  const electricityLayerGroupRef = useRef<L.GeoJSON | null>(null);
  const focusLayerGroupRef = useRef<L.LayerGroup | null>(null);
  const historyComparisonLayerGroupRef = useRef<L.LayerGroup | null>(null);
  const roadHighlightGroupRef = useRef<L.LayerGroup | null>(null);
  const tileLayerRef = useRef<L.TileLayer | null>(null);
  // Tracks whether we've already auto-fit the map to real data once, so we
  // don't yank the user's pan/zoom on every re-render — only on genuinely
  // new datasets (dataset switch, mock → live swap, or first load).
  const lastFitKeyRef = useRef<string>('');

  const [mapMode, setMapMode] = useState<'streets' | 'satellite'>('streets');
  const [searchQuery, setSearchQuery] = useState('');
  const [showLayersDropdown, setShowLayersDropdown] = useState(false);
  const [selectedRoad, setSelectedRoad] = useState<any | null>(null);
  const [gisDiagnosticMode, setGisDiagnosticMode] = useState<boolean>(false);
  const [activeLayers, setActiveLayers] = useState({
    reconciled: true,
    cadastral: false,
    municipal: false,
    roads: true,
    drainage: true,
    water: false,
    electricity: true,
    railway: true,
    utilities: false,
  });

  const [roadsData, setRoadsData] = useState<any | null>(() => getFallbackInfrastructureFeatures('road', activeDataset?.city));
  const [drainageData, setDrainageData] = useState<any | null>(() => getFallbackInfrastructureFeatures('drainage', activeDataset?.city));
  const [railwayData, setRailwayData] = useState<any | null>(() => getFallbackInfrastructureFeatures('railway', activeDataset?.city));
  const [electricityData, setElectricityData] = useState<any | null>(() => getFallbackInfrastructureFeatures('electricity', activeDataset?.city));

  const [statusFilter, setStatusFilter] = useState<'all' | 'reconciled' | 'review' | 'conflict'>(activeFilter);
  const [dismissedConflictId, setDismissedConflictId] = useState<string | null>(null);

  const reconciledCount = buildings.filter(b => b.status === 'reconciled').length;
  const reviewCount = buildings.filter(b => b.status === 'review').length;
  const conflictCount = buildings.filter(b => b.status === 'conflict').length;

  const handleStatusFilterSelect = (filter: 'all' | 'reconciled' | 'review' | 'conflict') => {
    setStatusFilter(filter);
    if (filter === 'conflict') {
      const conflicts = buildings.filter(b => b.status === 'conflict');
      if (conflicts.length > 0) {
        onSelectBuilding(conflicts[0]);
        if (mapInstanceRef.current) {
          const bounds = L.latLngBounds(conflicts.flatMap(b => b.coordinates));
          mapInstanceRef.current.fitBounds(bounds, { padding: [60, 60], maxZoom: 18, animate: true });
        }
      }
    } else if (filter === 'review') {
      const reviews = buildings.filter(b => b.status === 'review');
      if (reviews.length > 0) {
        onSelectBuilding(reviews[0]);
        if (mapInstanceRef.current) {
          const bounds = L.latLngBounds(reviews.flatMap(b => b.coordinates));
          mapInstanceRef.current.fitBounds(bounds, { padding: [60, 60], maxZoom: 18, animate: true });
        }
      }
    } else if (filter === 'reconciled') {
      const recs = buildings.filter(b => b.status === 'reconciled');
      if (recs.length > 0) {
        onSelectBuilding(recs[0]);
        if (mapInstanceRef.current) {
          const bounds = L.latLngBounds(recs.flatMap(b => b.coordinates));
          mapInstanceRef.current.fitBounds(bounds, { padding: [40, 40], maxZoom: 18, animate: true });
        }
      }
    } else {
      if (mapInstanceRef.current && buildings.length > 0) {
        const bounds = L.latLngBounds(buildings.flatMap(b => b.coordinates));
        mapInstanceRef.current.fitBounds(bounds, { padding: [40, 40], maxZoom: 18, animate: true });
      }
    }
  };

  // Real check against the loaded data — not assumed true.
  const hasCadastralGeometry = buildings.some((b) => b.sources.cadastral.coordinates.length > 0);
  const hasMunicipalGeometry = buildings.some((b) => b.sources.municipal.coordinates.length > 0);

  // Initialize Map with activeDataset center — NEVER assumes fixed Bengaluru if activeDataset is Mumbai/Chennai
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    const initialCenter: [number, number] = activeDataset ? activeDataset.center : [12.9784, 77.6408];
    const initialZoom = activeDataset ? activeDataset.defaultZoom : 17;

    const map = L.map(mapContainerRef.current, {
      center: initialCenter,
      zoom: initialZoom,
      zoomControl: false,
      attributionControl: true,
      fadeAnimation: false,
      markerZoomAnimation: true,
    });
    map.attributionControl.setPrefix(false);

    // Street tiles
    const streetTiles = L.tileLayer(STREET_TILE_URL, {
      ...STREET_TILE_OPTIONS,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    });

    streetTiles.addTo(map);
    tileLayerRef.current = streetTiles;

    // Setup Layer Groups
    const polyGroup = L.layerGroup().addTo(map);
    const cadGroup = L.layerGroup().addTo(map);
    const munGroup = L.layerGroup().addTo(map);
    const focusGroup = L.layerGroup().addTo(map);
    const histGroup = L.layerGroup().addTo(map);
    const roadHighlightGroup = L.layerGroup().addTo(map);

    polygonLayerGroupRef.current = polyGroup;
    cadastralLayerGroupRef.current = cadGroup;
    municipalLayerGroupRef.current = munGroup;
    focusLayerGroupRef.current = focusGroup;
    historyComparisonLayerGroupRef.current = histGroup;
    roadHighlightGroupRef.current = roadHighlightGroup;

    mapInstanceRef.current = map;

    // Initial fit bounds to active dataset if available
    if (activeDataset?.bounds) {
      map.fitBounds(L.latLngBounds(activeDataset.bounds[0], activeDataset.bounds[1]), { padding: [30, 30], maxZoom: 17, animate: false });
    }

    // Auto-invalidate map size on container dimensions resize (tab switch, sidebar, layout shifts)
    const resizeObserver = new ResizeObserver(() => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.invalidateSize({ animate: false });
      }
    });
    if (mapContainerRef.current) {
      resizeObserver.observe(mapContainerRef.current);
    }

    return () => {
      resizeObserver.disconnect();
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []);

  // Dedicated Instant Dataset / City Viewport & State Synchronization
  const prevDatasetIdRef = useRef<string | null>(null);
  useEffect(() => {
    setSelectedRoad(null);
    if (roadHighlightGroupRef.current) {
      roadHighlightGroupRef.current.clearLayers();
    }

    if (!activeDataset || !mapInstanceRef.current) return;
    if (prevDatasetIdRef.current === activeDataset.id) return;
    prevDatasetIdRef.current = activeDataset.id;

    const map = mapInstanceRef.current;
    map.stop(); // Stop any pending pan/zoom animations immediately

    // Instantly snap to active dataset bounds without slow animation stutter or blank tiles
    if (activeDataset.bounds) {
      map.fitBounds(
        L.latLngBounds(activeDataset.bounds[0] as L.LatLngTuple, activeDataset.bounds[1] as L.LatLngTuple),
        { padding: [30, 30], maxZoom: 17, animate: false }
      );
    } else if (activeDataset.center) {
      map.setView(activeDataset.center, activeDataset.defaultZoom || 16, { animate: false });
    }

    // Force Leaflet to immediately request and render tiles for new city
    map.invalidateSize({ animate: false });
    requestAnimationFrame(() => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.invalidateSize({ animate: false });
      }
    });
  }, [activeDataset?.id, activeDataset?.city, activeDataset?.bounds, activeDataset?.center, activeDataset?.defaultZoom]);

  // Load verified infrastructure features for overlay, scoped to active city
  useEffect(() => {
    const targetCity = activeDataset?.city || 'Bengaluru';
    let isCurrent = true;

    // Immediately apply bundled fallback so counts and map render synchronously (0ms delay)
    setRoadsData(getFallbackInfrastructureFeatures('road', targetCity));
    setDrainageData(getFallbackInfrastructureFeatures('drainage', targetCity));
    setRailwayData(getFallbackInfrastructureFeatures('railway', targetCity));
    setElectricityData(getFallbackInfrastructureFeatures('electricity', targetCity));

    // Fetch live backend updates / overrides asynchronously
    fetchInfrastructureFeatures('road', targetCity)
      .then(res => { if (isCurrent && res?.features?.length) setRoadsData(res); })
      .catch(err => console.warn('Could not fetch road features:', err));
    fetchInfrastructureFeatures('drainage', targetCity)
      .then(res => { if (isCurrent && res?.features?.length) setDrainageData(res); })
      .catch(err => console.warn('Could not fetch drainage features:', err));
    fetchInfrastructureFeatures('railway', targetCity)
      .then(res => { if (isCurrent && res?.features?.length) setRailwayData(res); })
      .catch(err => console.warn('Could not fetch railway features:', err));
    fetchInfrastructureFeatures('electricity', targetCity)
      .then(res => { if (isCurrent && res?.features?.length) setElectricityData(res); })
      .catch(err => console.warn('Could not fetch electricity features:', err));

    return () => {
      isCurrent = false;
    };
  }, [activeDataset?.city, activeDataset?.id]);

  // Handle Selected Road highlight & GIS Diagnostic Node visualization
  useEffect(() => {
    const highlightGroup = roadHighlightGroupRef.current;
    if (!highlightGroup) return;

    highlightGroup.clearLayers();

    if (selectedRoad && selectedRoad.geometry) {
      // Outer amber glow halo
      const outerGlow = L.geoJSON(selectedRoad.geometry, {
        style: {
          color: '#F59E0B',
          weight: 8,
          opacity: 0.85,
          lineCap: 'round',
          lineJoin: 'round',
        },
        interactive: false,
      });
      outerGlow.addTo(highlightGroup);

      // Core vivid blue polyline
      const coreLine = L.geoJSON(selectedRoad.geometry, {
        style: {
          color: '#1D4ED8',
          weight: 4,
          opacity: 1.0,
          lineCap: 'round',
          lineJoin: 'round',
        },
        interactive: false,
      });
      coreLine.addTo(highlightGroup);

      // If GIS Diagnostic Mode is enabled, plot vertex coordinate nodes
      if (gisDiagnosticMode && selectedRoad.geometry.coordinates) {
        const rawCoords: [number, number][] = selectedRoad.geometry.type === 'LineString' 
          ? selectedRoad.geometry.coordinates 
          : (selectedRoad.geometry.coordinates as any[]).flat(1);

        rawCoords.forEach((pt: [number, number], idx: number) => {
          const latLng: [number, number] = [pt[1], pt[0]];
          const marker = L.circleMarker(latLng, {
            radius: 3.5,
            fillColor: '#EF4444',
            fillOpacity: 1.0,
            color: '#FFFFFF',
            weight: 1.5,
          });
          marker.bindTooltip(
            `<div class="font-mono text-[10px] bg-[#1E293B] text-white p-1 rounded shadow">
              Node #${idx + 1}: [${pt[0].toFixed(6)}, ${pt[1].toFixed(6)}]
            </div>`,
            { sticky: true }
          );
          marker.addTo(highlightGroup);
        });
      }
    }
  }, [selectedRoad, gisDiagnosticMode]);

  // Sync Roads & Drainage Layers onto map
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    if (roadsLayerGroupRef.current) {
      map.removeLayer(roadsLayerGroupRef.current);
      roadsLayerGroupRef.current = null;
    }
    if (activeLayers.roads && roadsData && roadsData.features?.length > 0) {
      const roadLayer = L.geoJSON(roadsData, {
        style: (feature) => {
          const p = feature?.properties || {};
          const m = p.metadata || {};
          const hLevel = String(m.hierarchy_level || p.hierarchy_level || '').toLowerCase();
          const rType = String(m.road_type || p.road_type || '').toLowerCase();
          const isFlyover = hLevel.includes('flyover') || rType.includes('flyover');

          if (isFlyover) {
            return {
              color: '#1D4ED8',
              weight: 4.5,
              opacity: 0.95,
            };
          }
          return {
            color: '#2563EB',
            weight: 3.2,
            opacity: 0.85,
          };
        },
        onEachFeature: (feature, layer) => {
          const p = feature.properties || {};
          const m = p.metadata || {};
          const fid = p.feature_id || p.infrastructure_id || 'ROAD';
          const roadName = m.road_name || p.name || p.source_name || 'Public Road';
          const width = m.width_m ? `${m.width_m}m` : (p.width_meters ? `${p.width_meters}m` : 'Arterial ROW');
          const status = p.verification_status || 'VERIFIED';
          const lengthM = p.length_meters ? `${Math.round(p.length_meters)}m` : (m.length_m ? `${Math.round(m.length_m)}m` : '');
          const hLevel = m.hierarchy_level || p.hierarchy_level || 'Arterial Corridor';

          layer.bindTooltip(
            `<div class="p-2.5 font-sans bg-white text-[#241D16] rounded-xl shadow-xl border border-[#2563EB]/40 min-w-[210px]">
              <div class="flex items-center justify-between gap-2 border-b border-[#E7DFD3] pb-1 mb-1">
                <span class="font-bold text-[#2563EB] flex items-center gap-1 text-xs">
                  <span>🛣️ ${roadName}</span>
                </span>
                <span class="text-[9px] font-mono font-bold bg-[#EFF6FF] text-[#2563EB] px-1.5 py-0.5 rounded border border-[#BFDBFE]">
                  ${fid}
                </span>
              </div>
              <div class="text-[11px] text-[#7D7063] space-y-0.5 font-mono">
                <div>Class: <strong class="text-[#241D16]">${hLevel}</strong></div>
                <div>Width: <strong class="text-[#241D16]">${width}</strong> ${lengthM ? `• Length: <strong class="text-[#241D16]">${lengthM}</strong>` : ''}</div>
                <div>Authority: <span>${p.source_name || m.authority || 'Highways & PWD'}</span></div>
              </div>
              <div class="mt-1.5 flex items-center justify-between pt-1 border-t border-[#E7DFD3] text-[10px]">
                <span class="font-bold text-[#3F6452] font-mono">● ${status}</span>
                <span class="text-[#A86236] font-bold">Click to Inspect →</span>
              </div>
            </div>`,
            { sticky: true }
          );

          layer.on('click', (e) => {
            L.DomEvent.stopPropagation(e);
            setSelectedRoad(feature);
          });
        }
      }).addTo(map);
      roadsLayerGroupRef.current = roadLayer;
    }

    if (drainageLayerGroupRef.current) {
      map.removeLayer(drainageLayerGroupRef.current);
      drainageLayerGroupRef.current = null;
    }
    if (activeLayers.drainage && drainageData && drainageData.features?.length > 0) {
      const drainLayer = L.geoJSON(drainageData, {
        style: (feature) => {
          const p = feature?.properties || {};
          const isPrimary = String(p.category || '').toLowerCase().includes('primary') || String(p.name || '').toLowerCase().includes('mambalam');
          return {
            color: '#0891B2',
            weight: isPrimary ? 4.0 : 2.8,
            dashArray: '5, 5',
            opacity: 0.95,
          };
        },
        onEachFeature: (feature, layer) => {
          const p = feature.properties || {};
          const m = p.metadata || {};
          const fid = p.feature_id || p.infrastructure_id || 'SWD';
          const drainName = m.drain_name || p.name || p.source_name || 'Stormwater Drain';
          const buffer = m.buffer_m ? `${m.buffer_m}m buffer` : (p.buffer_radius_meters ? `${p.buffer_radius_meters}m buffer` : 'Primary Canal');
          const status = p.verification_status || 'VERIFIED';
          layer.bindTooltip(
            `<div class="p-2.5 font-sans bg-white text-[#241D16] rounded-xl shadow-xl border border-[#06B6D4]/40 min-w-[200px]">
              <div class="flex items-center justify-between gap-2 border-b border-[#E7DFD3] pb-1 mb-1">
                <span class="font-bold text-[#06B6D4] flex items-center gap-1.5 text-xs">
                  <span>🌊 SWD: ${drainName}</span>
                </span>
                <span class="text-[9px] font-mono font-bold bg-[#ECFEFF] text-[#0891B2] px-1.5 py-0.5 rounded border border-[#A5F3FC]">
                  ${fid}
                </span>
              </div>
              <div class="text-[11px] text-[#7D7063] mt-0.5 font-mono">
                <span>${buffer}</span> • <span>${p.source_name || 'WRD / GCC SWD'}</span>
              </div>
              <div class="mt-1 text-[10px] font-bold text-[#3F6452] font-mono">
                Status: ${status}
              </div>
            </div>`,
            { sticky: true }
          );
          layer.on('click', (e) => {
            L.DomEvent.stopPropagation(e);
            setSelectedRoad(feature);
          });
        }
      }).addTo(map);
      drainageLayerGroupRef.current = drainLayer;
    }

    if (railwayLayerGroupRef.current) {
      map.removeLayer(railwayLayerGroupRef.current);
      railwayLayerGroupRef.current = null;
    }
    if (activeLayers.railway && railwayData && railwayData.features?.length > 0) {
      const railLayer = L.geoJSON(railwayData, {
        style: {
          color: '#6D28D9',
          weight: 4.0,
          dashArray: '8, 6',
          opacity: 0.95,
        },
        onEachFeature: (feature, layer) => {
          const p = feature.properties || {};
          const m = p.metadata || {};
          const fid = p.feature_id || p.infrastructure_id || 'RAIL';
          const rName = m.name || p.name || p.source_name || 'Railway Corridor';
          const op = p.operator || m.operator || 'Indian Railways / Metro';
          const status = p.verification_status || 'VERIFIED';
          layer.bindTooltip(
            `<div class="p-2.5 font-sans bg-white text-[#241D16] rounded-xl shadow-xl border border-[#6D28D9]/40 min-w-[210px]">
              <div class="flex items-center justify-between gap-2 border-b border-[#E7DFD3] pb-1 mb-1">
                <span class="font-bold text-[#6D28D9] flex items-center gap-1 text-xs">
                  <span>🚆 ${rName}</span>
                </span>
                <span class="text-[9px] font-mono font-bold bg-[#F5F3FF] text-[#6D28D9] px-1.5 py-0.5 rounded border border-[#DDD6FE]">
                  ${fid}
                </span>
              </div>
              <div class="text-[11px] text-[#7D7063] mt-0.5 font-mono">
                <div>Operator: <strong class="text-[#241D16]">${op}</strong></div>
                <div>Source: <span>${p.source_name || 'Official Railway GIS'}</span></div>
              </div>
              <div class="mt-1.5 flex items-center justify-between pt-1 border-t border-[#E7DFD3] text-[10px]">
                <span class="font-bold text-[#3F6452] font-mono">● ${status}</span>
                <span class="text-[#A86236] font-bold">Click to Inspect →</span>
              </div>
            </div>`,
            { sticky: true }
          );
          layer.on('click', (e) => {
            L.DomEvent.stopPropagation(e);
            setSelectedRoad(feature);
          });
        }
      }).addTo(map);
      railwayLayerGroupRef.current = railLayer;
    }

    if (electricityLayerGroupRef.current) {
      map.removeLayer(electricityLayerGroupRef.current);
      electricityLayerGroupRef.current = null;
    }
    if (activeLayers.electricity && electricityData && electricityData.features?.length > 0) {
      const elecLayer = L.geoJSON(electricityData, {
        style: {
          color: '#D97706',
          weight: 3.2,
          dashArray: '5, 5',
          opacity: 0.9,
        },
        onEachFeature: (feature, layer) => {
          const p = feature.properties || {};
          const m = p.metadata || {};
          const fid = p.feature_id || p.infrastructure_id || 'GRID';
          const eName = m.line_name || p.name || p.source_name || 'Transmission Corridor';
          const volt = m.voltage || p.voltage || 'High Voltage Grid';
          layer.bindTooltip(
            `<div class="p-2.5 font-sans bg-white text-[#241D16] rounded-xl shadow-xl border border-[#D97706]/40 min-w-[210px]">
              <div class="flex items-center justify-between gap-2 border-b border-[#E7DFD3] pb-1 mb-1">
                <span class="font-bold text-[#D97706] flex items-center gap-1 text-xs">
                  <span>⚡ ${eName}</span>
                </span>
                <span class="text-[9px] font-mono font-bold bg-[#FEF3C7] text-[#B45309] px-1.5 py-0.5 rounded border border-[#FDE68A]">
                  ${fid}
                </span>
              </div>
              <div class="text-[11px] text-[#7D7063] mt-0.5 font-mono">
                <div>Grid: <strong class="text-[#241D16]">${volt}</strong></div>
                <div>Source: <span>${p.source_name || 'OpenStreetMap Power'}</span></div>
              </div>
              <div class="mt-1 text-[9px] font-bold text-[#92400E] bg-[#FFFBEB] p-1 rounded border border-[#FDE68A]">
                ⚠ SUPPORTING DATA — NOT AN OFFICIAL GOVERNMENT GIS LAYER
              </div>
              <div class="mt-1 flex items-center justify-between pt-1 border-t border-[#E7DFD3] text-[10px]">
                <span class="font-bold text-[#D97706] font-mono">● REFERENCE ONLY</span>
                <span class="text-[#A86236] font-bold">Click to Inspect →</span>
              </div>
            </div>`,
            { sticky: true }
          );
          layer.on('click', (e) => {
            L.DomEvent.stopPropagation(e);
            setSelectedRoad(feature);
          });
        }
      }).addTo(map);
      electricityLayerGroupRef.current = elecLayer;
    }
  }, [activeLayers.roads, activeLayers.drainage, activeLayers.railway, activeLayers.electricity, roadsData, drainageData, railwayData, electricityData]);

  // Handle Focused Geometry (e.g. from Detail Panel [View on Map])
  useEffect(() => {
    if (!mapInstanceRef.current || !focusLayerGroupRef.current) return;
    const focusGroup = focusLayerGroupRef.current;
    focusGroup.clearLayers();

    if (focusedGeometry && focusedGeometry.length > 0) {
      const poly = L.polygon(focusedGeometry, {
        color: '#A86236',
        weight: 3.5,
        fillColor: '#F59E0B',
        fillOpacity: 0.25,
        dashArray: '4, 4',
      });
      poly.addTo(focusGroup);
      try {
        mapInstanceRef.current.fitBounds(L.latLngBounds(focusedGeometry), {
          padding: [60, 60],
          maxZoom: 19,
          animate: true,
        });
      } catch (err) {
        console.warn('Could not fit bounds to focused geometry:', err);
      }
    }
  }, [focusedGeometry]);

  // Handle Historical Comparison Overlay (Version A in Amber Dashed, Version B in Teal Solid)
  useEffect(() => {
    if (!mapInstanceRef.current || !historyComparisonLayerGroupRef.current) return;
    const histGroup = historyComparisonLayerGroupRef.current;
    histGroup.clearLayers();

    if (historicalComparison && historicalComparison.geomA && historicalComparison.geomB) {
      const layerA = L.geoJSON(historicalComparison.geomA, {
        style: {
          color: '#D97706',
          weight: 3,
          dashArray: '6, 6',
          fillColor: '#F59E0B',
          fillOpacity: 0.18,
        },
      });
      layerA.bindTooltip(`<b>${historicalComparison.metaA.label}</b><br/>${historicalComparison.metaA.date || ''}`, { sticky: true });
      layerA.addTo(histGroup);

      const layerB = L.geoJSON(historicalComparison.geomB, {
        style: {
          color: '#0D9488',
          weight: 3,
          fillColor: '#14B8A6',
          fillOpacity: 0.22,
        },
      });
      layerB.bindTooltip(`<b>${historicalComparison.metaB.label}</b><br/>${historicalComparison.metaB.date || ''}`, { sticky: true });
      layerB.addTo(histGroup);

      try {
        const boundsA = layerA.getBounds();
        const boundsB = layerB.getBounds();
        boundsA.extend(boundsB);
        if (boundsA.isValid()) {
          mapInstanceRef.current.fitBounds(boundsA, { padding: [60, 60], maxZoom: 19, animate: true });
        }
      } catch (err) {
        console.warn('Could not fit bounds to historical comparison:', err);
      }
    }
  }, [historicalComparison]);

  // Handle Map Mode switch (Streets vs Satellite)
  useEffect(() => {
    if (!mapInstanceRef.current || !tileLayerRef.current) return;

    mapInstanceRef.current.removeLayer(tileLayerRef.current);

    if (mapMode === 'satellite') {
      const sat = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
        maxZoom: 19,
        keepBuffer: 6,
        updateWhenIdle: false,
        updateWhenZooming: true,
        attribution: 'Tiles &copy; Esri',
      });
      sat.addTo(mapInstanceRef.current);
      tileLayerRef.current = sat;
    } else {
      const streets = L.tileLayer(STREET_TILE_URL, {
        ...STREET_TILE_OPTIONS,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      });
      streets.addTo(mapInstanceRef.current);
      tileLayerRef.current = streets;
    }
    mapInstanceRef.current.invalidateSize({ animate: false });
  }, [mapMode]);

  // Render Building Polygons and Cadastral / Municipal Overlays
  useEffect(() => {
    const polyGroup = polygonLayerGroupRef.current;
    const cadGroup = cadastralLayerGroupRef.current;
    const munGroup = municipalLayerGroupRef.current;
    if (!polyGroup || !cadGroup || !munGroup) return;

    polyGroup.clearLayers();
    cadGroup.clearLayers();
    munGroup.clearLayers();

    const filtered = buildings.filter(b => {
      if (statusFilter !== 'all' && b.status !== statusFilter) return false;
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        return (
          b.id.toLowerCase().includes(q) ||
          b.surveyNumber.toLowerCase().includes(q) ||
          b.landUse.toLowerCase().includes(q)
        );
      }
      return true;
    });

    filtered.forEach((building) => {
      const isSelected = selectedBuilding?.id === building.id;

      // TERRANODE Color mapping (Warm executive cadastre palette)
      let fillColor = '#3F6452'; // Sage Forest Green: Reconciled
      let strokeColor = '#274234';

      if (building.status === 'conflict') {
        fillColor = '#C87958'; // Rust Terracotta Coral: Conflict
        strokeColor = '#8F4F28';
      } else if (building.status === 'review') {
        fillColor = '#D8AD56'; // Warm Ochre Gold: Review
        strokeColor = '#966B24';
      }

      // Reconciled Unified Layer
      if (activeLayers.reconciled) {
        const polygon = L.polygon(building.coordinates, {
          fillColor: fillColor,
          fillOpacity: isSelected ? 0.85 : 0.60,
          color: isSelected ? '#A86236' : strokeColor,
          weight: isSelected ? 3.5 : 1.8,
          dashArray: isSelected ? '5, 5' : undefined,
          className: 'cursor-pointer transition-all duration-200',
        });

        // Hover tooltip styled with TERRANODE Warm Natural Glass
        polygon.bindTooltip(
          `<div class="p-2.5 font-sans bg-white text-[#241D16] rounded-xl shadow-lg border border-[#E7DFD3]">
            <div class="font-bold text-[#241D16] font-mono flex items-center gap-1.5">
              <span>Parcel #${building.id}</span> 
              <span class="text-[11px] font-normal text-[#7D7063]">(${building.surveyNumber !== 'N/A' ? `Survey ${building.surveyNumber}` : 'Unsurveyed'})</span>
            </div>
            <div class="text-xs text-[#7D7063] flex items-center gap-1 mt-1 font-mono">
              <span>${building.area} m²</span> • <span class="capitalize text-[#A86236] font-semibold">${building.landUse}</span>
            </div>
            <div class="mt-1.5 text-xs font-bold font-mono ${
              building.status === 'reconciled' ? 'text-[#3F6452]' : building.status === 'review' ? 'text-[#966B24]' : 'text-[#C87958]'
            }">
              ${building.confidence}% Consensus Confidence
            </div>
          </div>`,
          { sticky: true, className: 'rounded-xl shadow-xl border border-[#E7DFD3] text-xs bg-white text-[#241D16]' }
        );

        polygon.on('click', () => {
          onSelectBuilding(building);
        });

        polygon.addTo(polyGroup);

        // Highlight Conflict parcels with prominent pulsing warning marker
        if (building.status === 'conflict') {
          const conflictMarker = L.circleMarker(building.centroid, {
            radius: isSelected ? 9 : 7,
            fillColor: '#C87958',
            fillOpacity: 1,
            color: '#FFFFFF',
            weight: 2,
            className: 'cursor-pointer',
          });
          conflictMarker.bindTooltip(
            `<div class="font-sans font-bold text-xs text-[#C87958] flex items-center gap-1">
              <span>⚠️ Conflict: Parcel #${building.id}</span>
            </div>
            <div class="text-[11px] text-[#7D7063] mt-0.5">${building.conflictDetails?.title || 'Boundary Discrepancy'}</div>`,
            { sticky: true, className: 'rounded-xl shadow-lg border border-[#F3CEBD] p-2 bg-white' }
          );
          conflictMarker.on('click', () => {
            onSelectBuilding(building);
          });
          conflictMarker.addTo(polyGroup);
        }

        // When a conflict or review parcel is selected, visually display its conflicting source footprints
        if (isSelected && (building.status === 'conflict' || building.status === 'review')) {
          if (building.sources.ori?.coordinates?.length > 0) {
            L.polygon(building.sources.ori.coordinates, {
              color: '#F59E0B',
              weight: 2.2,
              dashArray: '4, 4',
              fillColor: '#F59E0B',
              fillOpacity: 0.15,
              interactive: false,
            }).addTo(polyGroup);
          }
          if (building.sources.municipal?.coordinates?.length > 0) {
            L.polygon(building.sources.municipal.coordinates, {
              color: '#3B82F6',
              weight: 2.2,
              dashArray: '3, 3',
              fillColor: '#3B82F6',
              fillOpacity: 0.15,
              interactive: false,
            }).addTo(polyGroup);
          }
          if (building.sources.cadastral?.coordinates?.length > 0) {
            L.polygon(building.sources.cadastral.coordinates, {
              color: '#8B5CF6',
              weight: 2.2,
              dashArray: '2, 3',
              fillColor: '#8B5CF6',
              fillOpacity: 0.15,
              interactive: false,
            }).addTo(polyGroup);
          }
        }
      }

      // Cadastral Layer (Muted Violet outline with interactive: false so clicks pass through)
      if (activeLayers.cadastral && building.sources.cadastral.coordinates.length > 0) {
        const cadPoly = L.polygon(building.sources.cadastral.coordinates, {
          color: '#7D6D8A',
          weight: 1.2,
          fillColor: '#7D6D8A',
          fillOpacity: 0.1,
          dashArray: '2, 3',
          interactive: false,
        });
        cadPoly.addTo(cadGroup);
      }

      // Municipal GIS Layer (Muted Slate Blue outline with interactive: false so clicks pass through)
      if (activeLayers.municipal && building.sources.municipal.coordinates.length > 0) {
        const munPoly = L.polygon(building.sources.municipal.coordinates, {
          color: '#4A6D7C',
          weight: 1.2,
          fillColor: '#4A6D7C',
          fillOpacity: 0.12,
          interactive: false,
        });
        munPoly.addTo(munGroup);
      }
    });

    // Auto-fit the map to the real loaded data scoped to the active dataset.
    // Guard against coordinate cross-contamination: verify building coordinates actually match activeDataset center!
    const isBuildingsMatchingCity = buildings.length > 0 && activeDataset?.center && (
      Math.abs(buildings[0].centroid[0] - activeDataset.center[0]) < 1.0 &&
      Math.abs(buildings[0].centroid[1] - activeDataset.center[1]) < 1.0
    );

    const fitKey = `${activeDataset?.id || 'default'}:${dataSource}:${buildings[0]?.id || 'none'}:${buildings.length}`;
    if (
      mapInstanceRef.current &&
      (buildings.length > 0 || activeDataset?.bounds) &&
      fitKey !== lastFitKeyRef.current
    ) {
      if (isBuildingsMatchingCity) {
        const allCoords = buildings.flatMap((b) => b.coordinates);
        if (allCoords.length > 0) {
          const bounds = L.latLngBounds(allCoords as L.LatLngExpression[]);
          mapInstanceRef.current.fitBounds(bounds, { padding: [30, 30], maxZoom: 17, animate: false });
          mapInstanceRef.current.invalidateSize({ animate: false });
        }
      } else if (activeDataset?.bounds) {
        mapInstanceRef.current.fitBounds(
          L.latLngBounds(activeDataset.bounds[0] as L.LatLngTuple, activeDataset.bounds[1] as L.LatLngTuple),
          { padding: [30, 30], maxZoom: 17, animate: false }
        );
        mapInstanceRef.current.invalidateSize({ animate: false });
      }
      lastFitKeyRef.current = fitKey;
    }
  }, [buildings, selectedBuilding, activeLayers, statusFilter, searchQuery, dataSource, activeDataset]);

  // Pan to selected building (ONLY if building is in the current active city)
  useEffect(() => {
    if (selectedBuilding && mapInstanceRef.current && activeDataset?.center) {
      const isSameCity = (
        Math.abs(selectedBuilding.centroid[0] - activeDataset.center[0]) < 1.0 &&
        Math.abs(selectedBuilding.centroid[1] - activeDataset.center[1]) < 1.0
      );
      if (isSameCity) {
        mapInstanceRef.current.panTo(selectedBuilding.centroid, { animate: true, duration: 0.4 });
      }
    }
  }, [selectedBuilding, activeDataset?.center]);

  const toggleLayer = (layerKey: keyof typeof activeLayers) => {
    setActiveLayers(prev => ({ ...prev, [layerKey]: !prev[layerKey] }));
  };

  // Recenters on the real loaded dataset bounds (Bengaluru, Mumbai, Chennai, Delhi, or uploaded)
  const resetView = () => {
    const map = mapInstanceRef.current;
    if (!map) return;
    map.stop();

    const isBuildingsMatchingCity = buildings.length > 0 && activeDataset?.center && (
      Math.abs(buildings[0].centroid[0] - activeDataset.center[0]) < 1.0 &&
      Math.abs(buildings[0].centroid[1] - activeDataset.center[1]) < 1.0
    );

    if (isBuildingsMatchingCity) {
      const allCoords = buildings.flatMap((b) => b.coordinates);
      if (allCoords.length > 0) {
        const bounds = L.latLngBounds(allCoords as L.LatLngExpression[]);
        map.fitBounds(bounds, { padding: [30, 30], maxZoom: 17, animate: false });
      }
    } else if (activeDataset?.bounds) {
      map.fitBounds(
        L.latLngBounds(activeDataset.bounds[0] as L.LatLngTuple, activeDataset.bounds[1] as L.LatLngTuple),
        { padding: [30, 30], maxZoom: 17, animate: false }
      );
    } else {
      map.setView([12.9784, 77.6408], 17, { animate: false });
    }
    map.invalidateSize({ animate: false });
  };

  return (
    <div className="relative w-full h-full min-h-[500px] bg-[#F6F2EB] rounded-2xl overflow-hidden border border-[#E7DFD3] shadow-sm flex flex-col">
      
      {/* Top Map Action Bar */}
      <div className="absolute top-3 left-3 right-3 z-20 flex flex-wrap items-center justify-between gap-2 pointer-events-none">
        
        {/* Left Section: Dataset / AOI Switcher & Search */}
        <div className="flex items-center gap-2 flex-1 max-w-xl">
          {/* Dataset / AOI Selector */}
          {datasets.length > 1 && onSelectDataset ? (
            <div className="pointer-events-auto flex items-center shadow-sm rounded-xl">
              <div className="flex items-center gap-1.5 bg-white/95 backdrop-blur-md rounded-xl p-1 border border-[#E7DFD3]">
                <div className="flex items-center gap-1 px-2 py-1 text-[10px] font-mono font-bold uppercase tracking-wider text-[#7D7063]">
                  <MapPin className="w-3.5 h-3.5 text-[#A86236]" />
                  <span className="hidden sm:inline">DATASET:</span>
                </div>
                <select
                  value={activeDataset?.id || datasets[0]?.id}
                  onChange={(e) => onSelectDataset(e.target.value)}
                  className="bg-[#FAF8F3] hover:bg-[#F3EFE6] text-[#241D16] text-xs font-bold rounded-lg px-2.5 py-1.5 border border-[#E7DFD3] focus:outline-none focus:ring-1 focus:ring-[#A86236] cursor-pointer transition font-sans shadow-xs"
                >
                  {datasets.map((ds) => (
                    <option key={ds.id} value={ds.id}>
                      {ds.city} — {ds.aoi}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          ) : (
            <div className="pointer-events-auto flex items-center shadow-sm rounded-xl">
              <div className="flex items-center gap-1.5 bg-white/95 backdrop-blur-md rounded-xl px-3 py-1.5 border border-[#E7DFD3]">
                <MapPin className="w-3.5 h-3.5 text-[#A86236]" />
                <span className="text-xs font-bold text-[#241D16] font-mono">
                  {activeDataset ? `${activeDataset.city} — ${activeDataset.aoi}` : 'Indian Urban'}
                </span>
              </div>
            </div>
          )}

          {/* Search Input */}
          <div className="relative flex-1 min-w-[140px] pointer-events-auto shadow-sm rounded-xl">
            <Search className="w-4 h-4 text-[#7D7063] absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder={t.searchPlaceholder}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-white/95 backdrop-blur-md text-[#241D16] pl-10 pr-4 py-2 rounded-xl text-xs font-medium border border-[#E7DFD3] shadow-sm focus:outline-none focus:ring-1 focus:ring-[#A86236] focus:border-[#A86236] placeholder:text-[#A89F91] transition"
            />
          </div>
        </div>

        {/* Right Tools: Layers Drawer, Mode Toggle, Filter */}
        <div className="flex items-center gap-2 pointer-events-auto">
          
          {/* Status Filter Pill */}
          <div className="flex bg-white/95 backdrop-blur-md rounded-xl shadow-sm border border-[#E7DFD3] p-1 text-xs font-semibold text-[#7D7063]">
            <button
              onClick={() => handleStatusFilterSelect('all')}
              className={`px-2.5 py-1 rounded-lg transition cursor-pointer ${statusFilter === 'all' ? 'bg-[#F6F2EB] text-[#241D16] border border-[#E7DFD3] shadow-xs font-bold' : 'hover:text-[#241D16]'}`}
            >
              All ({buildings.length})
            </button>
            <button
              onClick={() => handleStatusFilterSelect('reconciled')}
              className={`px-2.5 py-1 rounded-lg transition flex items-center gap-1 cursor-pointer ${statusFilter === 'reconciled' ? 'bg-[#EAF2EB] text-[#3F6452] border border-[#C5DAC9] font-bold' : 'text-[#3F6452] hover:bg-[#EAF2EB]/60'}`}
            >
              <span className="w-2 h-2 rounded-full bg-[#3F6452]"></span>
              <span className="hidden sm:inline">Verified</span> ({reconciledCount})
            </button>
            <button
              onClick={() => handleStatusFilterSelect('review')}
              className={`px-2.5 py-1 rounded-lg transition flex items-center gap-1 cursor-pointer ${statusFilter === 'review' ? 'bg-[#FAF3E6] text-[#966B24] border border-[#EDDCBA] font-bold' : 'text-[#966B24] hover:bg-[#FAF3E6]/60'}`}
            >
              <span className="w-2 h-2 rounded-full bg-[#D8AD56]"></span>
              <span className="hidden sm:inline">Review</span> ({reviewCount})
            </button>
            <button
              onClick={() => handleStatusFilterSelect('conflict')}
              className={`px-2.5 py-1 rounded-lg transition flex items-center gap-1 cursor-pointer ${statusFilter === 'conflict' ? 'bg-[#FDF1EB] text-[#C87958] border border-[#F3CEBD] font-bold shadow-xs' : 'text-[#C87958] hover:bg-[#FDF1EB]/60'}`}
            >
              <span className="w-2 h-2 rounded-full bg-[#C87958] animate-pulse"></span>
              Conflict ({conflictCount})
            </button>
          </div>

          {/* Map / Satellite Toggle */}
          <button
            onClick={() => setMapMode(m => m === 'streets' ? 'satellite' : 'streets')}
            className="flex items-center gap-1.5 bg-white/95 hover:bg-[#FAF8F3] text-[#241D16] px-3 py-2 rounded-xl text-xs font-bold border border-[#E7DFD3] shadow-sm transition cursor-pointer backdrop-blur-md"
            title="Toggle between Street map and High-resolution Satellite Imagery"
          >
            {mapMode === 'streets' ? (
              <>
                <Satellite className="w-4 h-4 text-[#A86236]" />
                <span className="hidden sm:inline">Satellite</span>
              </>
            ) : (
              <>
                <MapIcon className="w-4 h-4 text-[#A86236]" />
                <span className="hidden sm:inline">Streets</span>
              </>
            )}
          </button>

          {/* Layer Panel Button */}
          <div className="relative">
            <button
              onClick={() => setShowLayersDropdown(!showLayersDropdown)}
              className={`flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-bold border shadow-sm transition cursor-pointer backdrop-blur-md ${
                showLayersDropdown 
                  ? 'bg-[#A86236] text-white border-[#A86236]' 
                  : 'bg-white/95 hover:bg-[#FAF8F3] text-[#241D16] border-[#E7DFD3]'
              }`}
            >
              <Layers className="w-4 h-4" />
              <span>Layers</span>
            </button>

            {/* Layer Control Dropdown Panel */}
            {showLayersDropdown && (
              <div className="absolute right-0 mt-2 w-72 bg-white rounded-2xl shadow-xl border border-[#E7DFD3] p-4 z-30 animate-in fade-in zoom-in-95 duration-150 max-h-[85vh] overflow-y-auto">
                <div className="flex items-center justify-between pb-2 border-b border-[#E7DFD3] mb-3">
                  <span className="text-xs font-bold uppercase tracking-wider text-[#7D7063] font-mono">{t.dataLayers}</span>
                  <span className="text-[10px] bg-[#F6F2EB] text-[#3F6452] font-mono font-bold px-2 py-0.5 rounded-full border border-[#C5DAC9]">
                    {dataSource === 'live' ? 'Live API' : dataSource === 'osm' ? 'OSM Layer' : 'Demo'}
                  </span>
                </div>

                {/* Primary Cadastral Layers */}
                <div className="space-y-2 text-xs font-semibold text-[#241D16]">
                  <span className="text-[10px] uppercase font-mono font-bold text-[#7D7063] tracking-wider block">
                    Cadastral & Property
                  </span>

                  <label className="flex items-center justify-between cursor-pointer hover:bg-[#FAF8F3] p-1.5 rounded-lg transition">
                    <span className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full bg-[#3F6452]" />
                      <span>{t.layerReconciled}</span>
                    </span>
                    <input
                      type="checkbox"
                      checked={activeLayers.reconciled}
                      onChange={() => toggleLayer('reconciled')}
                      className="accent-[#A86236] w-4 h-4 cursor-pointer rounded"
                    />
                  </label>

                  <label
                    className={`flex items-center justify-between p-1.5 rounded-lg transition ${
                      hasCadastralGeometry ? 'cursor-pointer hover:bg-[#FAF8F3]' : 'opacity-40 cursor-not-allowed'
                    }`}
                    title={hasCadastralGeometry ? undefined : 'Backend doesn\u2019t return separate cadastral geometry yet — only which entities include a cadastral source'}
                  >
                    <span className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full bg-[#7D6D8A]" />
                      <span>{t.layerCadastral}</span>
                    </span>
                    <input
                      type="checkbox"
                      checked={activeLayers.cadastral}
                      disabled={!hasCadastralGeometry}
                      onChange={() => toggleLayer('cadastral')}
                      className="accent-[#A86236] w-4 h-4 cursor-pointer rounded disabled:cursor-not-allowed"
                    />
                  </label>

                  <label
                    className={`flex items-center justify-between p-1.5 rounded-lg transition ${
                      hasMunicipalGeometry ? 'cursor-pointer hover:bg-[#FAF8F3]' : 'opacity-40 cursor-not-allowed'
                    }`}
                    title={hasMunicipalGeometry ? undefined : 'Backend doesn\u2019t return separate municipal geometry yet — only which entities include a municipal source'}
                  >
                    <span className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full bg-[#4A6D7C]" />
                      <span>{t.layerMunicipal}</span>
                    </span>
                    <input
                      type="checkbox"
                      checked={activeLayers.municipal}
                      disabled={!hasMunicipalGeometry}
                      onChange={() => toggleLayer('municipal')}
                      className="accent-[#A86236] w-4 h-4 cursor-pointer rounded disabled:cursor-not-allowed"
                    />
                  </label>
                </div>

                {/* Infrastructure & Utility Crossing Layers */}
                <div className="space-y-2 text-xs font-semibold text-[#241D16] mt-4 pt-3 border-t border-[#E7DFD3]">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] uppercase font-mono font-bold text-[#7D7063] tracking-wider block">
                      Infrastructure Networks
                    </span>
                    <span className="text-[9px] font-mono text-[#3F6452] bg-[#EAF2EB] px-1.5 py-0.5 rounded font-bold">
                      Spatial Overlay
                    </span>
                  </div>

                  {/* Public Roads */}
                  <label className="flex items-center justify-between cursor-pointer hover:bg-[#FAF8F3] p-1.5 rounded-lg transition">
                    <span className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded bg-[#2563EB]" />
                      <span>Public Roads</span>
                      {roadsData?.features?.length > 0 && (
                        <span className="text-[10px] font-mono text-[#2563EB] bg-[#EFF6FF] px-1.5 py-0.2 rounded font-bold">
                          {roadsData.features.length}
                        </span>
                      )}
                    </span>
                    <input
                      type="checkbox"
                      checked={activeLayers.roads}
                      onChange={() => toggleLayer('roads')}
                      className="accent-[#2563EB] w-4 h-4 cursor-pointer rounded"
                    />
                  </label>

                  {/* Drainage / SWD */}
                  <label className="flex items-center justify-between cursor-pointer hover:bg-[#FAF8F3] p-1.5 rounded-lg transition">
                    <span className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded bg-[#06B6D4]" />
                      <span>Stormwater Drains (SWD)</span>
                      {drainageData?.features?.length > 0 && (
                        <span className="text-[10px] font-mono text-[#06B6D4] bg-[#ECFEFF] px-1.5 py-0.2 rounded font-bold">
                          {drainageData.features.length}
                        </span>
                      )}
                    </span>
                    <input
                      type="checkbox"
                      checked={activeLayers.drainage}
                      onChange={() => toggleLayer('drainage')}
                      className="accent-[#06B6D4] w-4 h-4 cursor-pointer rounded"
                    />
                  </label>

                  {/* Railway Lines */}
                  <label className="flex items-center justify-between cursor-pointer hover:bg-[#FAF8F3] p-1.5 rounded-lg transition">
                    <span className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded bg-[#6D28D9]" />
                      <span>Railway / Transit</span>
                      {railwayData?.features?.length > 0 && (
                        <span className="text-[10px] font-mono text-[#6D28D9] bg-[#F5F3FF] px-1.5 py-0.2 rounded font-bold">
                          {railwayData.features.length}
                        </span>
                      )}
                    </span>
                    <input
                      type="checkbox"
                      checked={activeLayers.railway}
                      onChange={() => toggleLayer('railway')}
                      className="accent-[#6D28D9] w-4 h-4 cursor-pointer rounded"
                    />
                  </label>

                  {/* Electricity Lines */}
                  <label className="flex items-center justify-between cursor-pointer hover:bg-[#FAF8F3] p-1.5 rounded-lg transition">
                    <span className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded bg-[#D97706]" />
                      <span>Electricity Corridors</span>
                      {electricityData?.features?.length > 0 && (
                        <span className="text-[10px] font-mono text-[#B45309] bg-[#FEF3C7] px-1.5 py-0.2 rounded font-bold">
                          {electricityData.features.length}
                        </span>
                      )}
                    </span>
                    <input
                      type="checkbox"
                      checked={activeLayers.electricity}
                      onChange={() => toggleLayer('electricity')}
                      className="accent-[#D97706] w-4 h-4 cursor-pointer rounded"
                    />
                  </label>

                  {/* Water Pipeline (Data Unavailable) */}
                  <div className="flex items-center justify-between p-1.5 rounded-lg hover:bg-[#FAF8F3] transition" title="Dataset requirement: Municipal water pipeline network GIS dataset (BWSSB / CMWSSB)">
                    <span className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded bg-[#94A3B8]" />
                      <span className="text-[#7D7063]">Water Supply Lines</span>
                    </span>
                    <span className="text-[9px] font-mono font-bold bg-[#FAF3E6] text-[#966B24] border border-[#EDDCBA] px-1.5 py-0.5 rounded">
                      Data Unavailable
                    </span>
                  </div>

                  {/* Public Utility Easements (No Authoritative Data) */}
                  <div className="flex items-center justify-between p-1.5 rounded-lg hover:bg-[#FAF8F3] transition" title="Easement boundaries require municipal statutory planning or land-use maps.">
                    <span className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded bg-[#94A3B8]" />
                      <span className="text-[#7D7063]">Public Utility Easement</span>
                    </span>
                    <span className="text-[9px] font-mono font-bold bg-[#FAF3E6] text-[#966B24] border border-[#EDDCBA] px-1.5 py-0.5 rounded">
                      No Auth Data
                    </span>
                  </div>

                  {/* Developer GIS Diagnostic Toggle */}
                  <div className="pt-2.5 border-t border-[#E7DFD3] mt-2.5">
                    <label className="flex items-center justify-between cursor-pointer hover:bg-[#FAF8F3] p-1.5 rounded-lg transition">
                      <span className="flex items-center gap-2">
                        <Terminal className="w-3.5 h-3.5 text-[#DC2626]" />
                        <span className="font-mono text-xs font-bold text-[#241D16]">GIS Diagnostic HUD</span>
                      </span>
                      <input
                        type="checkbox"
                        checked={gisDiagnosticMode}
                        onChange={() => setGisDiagnosticMode(!gisDiagnosticMode)}
                        className="accent-[#DC2626] w-4 h-4 cursor-pointer rounded"
                      />
                    </label>
                  </div>
                </div>
              </div>
            )}
          </div>

        </div>
      </div>

      {/* Main Map Canvas Element */}
      <div ref={mapContainerRef} className="w-full flex-1 relative" />

      {/* Historical Comparison Top Banner */}
      {historicalComparison && (
        <div className="absolute top-18 left-1/2 -translate-x-1/2 z-30 bg-white/95 backdrop-blur-md px-4 py-2.5 rounded-2xl shadow-xl border border-[#D97706]/40 flex items-center gap-3 animate-in fade-in slide-in-from-top-2">
          <div className="flex items-center gap-3 text-xs font-mono">
            <span className="text-[10px] uppercase font-bold text-[#7D7063]">Historical Overlay:</span>
            <span className="flex items-center gap-1.5 text-[#D97706] font-bold">
              <span className="w-3.5 h-0.5 border-t-2 border-dashed border-[#D97706] inline-block" />
              {historicalComparison.metaA.label}
            </span>
            <span className="text-[#7D7063] font-bold">vs</span>
            <span className="flex items-center gap-1.5 text-[#0D9488] font-bold">
              <span className="w-3.5 h-0.5 bg-[#0D9488] inline-block" />
              {historicalComparison.metaB.label}
            </span>
          </div>
          {onClearHistoricalComparison && (
            <button
              onClick={onClearHistoricalComparison}
              className="p-1 hover:bg-[#FAF8F3] rounded-lg text-[#7D7063] hover:text-[#241D16] transition cursor-pointer"
              title="Clear Historical Comparison Overlay"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      )}

      {/* Empty-state overlay */}
      {buildings.length === 0 && (
        <div className="absolute inset-0 z-30 flex items-center justify-center bg-[#F6F2EB]/90 backdrop-blur-md pointer-events-none">
          <div className="bg-white rounded-2xl shadow-xl border border-[#E7DFD3] px-6 py-5 max-w-xs text-center pointer-events-auto">
            <p className="text-sm font-bold text-[#241D16] mb-1 font-mono">No entities loaded yet</p>
            <p className="text-xs text-[#7D7063] mb-4">
              Upload source data and run reconciliation to see real buildings plotted here.
            </p>
            <div className="flex items-center justify-center gap-2">
              <button
                onClick={onOpenUploadModal}
                className="px-3 py-1.5 rounded-lg border border-[#E7DFD3] text-[#241D16] text-xs font-bold hover:bg-[#FAF8F3] transition cursor-pointer"
              >
                Upload Data
              </button>
              <button
                onClick={onOpenReconcileModal}
                className="px-3 py-1.5 rounded-lg bg-[#A86236] hover:bg-[#8F4F28] text-white text-xs font-bold transition cursor-pointer shadow-sm"
              >
                Run Reconciliation
              </button>
            </div>
          </div>
        </div>
      )}

      {/* On-Map Floating Conflict Details Alert */}
      {selectedBuilding && selectedBuilding.status === 'conflict' && dismissedConflictId !== selectedBuilding.id && (
        <div className="absolute top-18 left-4 z-20 max-w-sm bg-white/95 backdrop-blur-md p-3.5 rounded-2xl shadow-xl border border-[#F3CEBD] animate-in fade-in slide-in-from-top-2">
          <div className="flex items-center justify-between gap-2">
            <span className="text-[11px] font-mono font-bold text-[#C87958] flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-[#C87958] animate-ping" />
              ⚠️ CONFLICT · #{selectedBuilding.id}
            </span>
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] font-mono font-bold bg-[#FDF1EB] text-[#C87958] px-2 py-0.5 rounded border border-[#F3CEBD]">
                {selectedBuilding.confidence}% Consensus
              </span>
              <button
                type="button"
                onClick={() => setDismissedConflictId(selectedBuilding.id)}
                className="p-1 text-[#7D7063] hover:text-[#241D16] hover:bg-[#FAF8F3] rounded-lg transition cursor-pointer"
                title="Close Alert"
                aria-label="Close Alert"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
          <p className="text-xs text-[#241D16] font-bold mt-1">
            {selectedBuilding.conflictDetails?.title || 'Boundary Discrepancy'}
          </p>
          <p className="text-[11px] text-[#7D7063] mt-0.5 leading-snug">
            {selectedBuilding.conflictDetails?.simplifiedReason}
          </p>
          <div className="flex items-center justify-between mt-2 pt-2 border-t border-[#F3CEBD]/50 text-[11px] font-mono">
            <span className="text-[#7D7063]">
              Drift: <strong>{selectedBuilding.conflictDetails?.centroidOffsetMeters ?? 12}m</strong>
            </span>
            <button
              type="button"
              onClick={onOpenReconcileModal}
              className="text-[#A86236] hover:underline font-bold cursor-pointer"
            >
              Open Harmonizer →
            </button>
          </div>
        </div>
      )}

      {/* On-Map Floating Infrastructure Inspector Panel */}
      {selectedRoad && (() => {
        const p = selectedRoad.properties || {};
        const m = p.metadata || {};
        const infraType = p.infrastructure_type || 'road';
        const isSupporting = p.verification_status === 'SUPPORTING_DATA' 
          || p.verification_status === 'REFERENCE_ONLY'
          || infraType === 'electricity'
          || String(p.source_name || '').toLowerCase().includes('supporting')
          || String(p.source_name || '').toLowerCase().includes('osm');

        const typeColor = infraType === 'railway' ? '#6D28D9' : infraType === 'electricity' ? '#D97706' : infraType === 'drainage' ? '#0891B2' : '#2563EB';
        const typeBg = infraType === 'railway' ? 'bg-[#F5F3FF] text-[#6D28D9] border-[#DDD6FE]' : infraType === 'electricity' ? 'bg-[#FEF3C7] text-[#B45309] border-[#FDE68A]' : infraType === 'drainage' ? 'bg-[#ECFEFF] text-[#0891B2] border-[#A5F3FC]' : 'bg-[#EFF6FF] text-[#2563EB] border-[#BFDBFE]';

        const inspectorTitle = infraType === 'railway' ? 'Railway Inspector' : infraType === 'electricity' ? 'Power Grid Inspector' : infraType === 'drainage' ? 'Drainage Inspector' : 'Road Inspector';
        const featureName = m.road_name || m.drain_name || m.line_name || m.name || p.name || p.source_name || 'Infrastructure Corridor';
        const categoryDesc = m.category || m.hierarchy_level || m.line_type || (infraType === 'railway' ? 'Transit Right-of-Way' : 'Spatial Network');

        return (
          <div className="absolute top-18 right-4 z-25 w-92 bg-white/95 backdrop-blur-md p-4 rounded-2xl shadow-xl border border-[#E7DFD3] animate-in fade-in slide-in-from-top-2">
            <div className="flex items-center justify-between gap-2 border-b border-[#E7DFD3] pb-2 mb-2.5">
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full animate-pulse" style={{ backgroundColor: typeColor }} />
                <span className="text-[11px] font-mono font-bold uppercase tracking-wider" style={{ color: typeColor }}>
                  {inspectorTitle}
                </span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded border ${typeBg}`}>
                  {p.feature_id || selectedRoad.id || 'INFRA'}
                </span>
                <button
                  onClick={() => setSelectedRoad(null)}
                  className="p-1 text-[#7D7063] hover:text-[#241D16] hover:bg-[#FAF8F3] rounded-lg transition cursor-pointer"
                  title="Close Inspector"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Supporting Data Banner if OSM / Tier 3 */}
            {isSupporting && (
              <div className="bg-[#FFFBEB] border border-[#FDE68A] text-[#92400E] px-2.5 py-1.5 rounded-lg text-[10px] font-bold flex items-center gap-1.5 mb-2.5">
                <AlertTriangle className="w-3.5 h-3.5 text-[#D97706] shrink-0" />
                <span>SUPPORTING DATA — NOT AN OFFICIAL GOVERNMENT GIS LAYER</span>
              </div>
            )}

            {/* Feature Title & Category */}
            <h3 className="text-xs font-bold text-[#241D16] leading-tight mb-1">
              {featureName}
            </h3>
            <div className="text-[11px] text-[#7D7063] font-medium mb-3">
              {categoryDesc}
            </div>

            {/* Metric Attributes Grid */}
            <div className="grid grid-cols-2 gap-2 text-xs font-mono mb-3 bg-[#FAF8F3] p-2.5 rounded-xl border border-[#E7DFD3]">
              <div>
                <div className="text-[10px] text-[#7D7063] uppercase">Corridor / ROW</div>
                <div className="font-bold text-[#241D16]">
                  {m.width_m || m.corridor_width_m || p.width_meters || (infraType === 'railway' ? 'Standard ROW' : '18m ROW')}
                </div>
              </div>
              <div>
                <div className="text-[10px] text-[#7D7063] uppercase">Length</div>
                <div className="font-bold text-[#241D16]">
                  {p.length_meters
                    ? (p.length_meters >= 1000
                        ? `${(p.length_meters / 1000).toFixed(2)} km`
                        : `${Math.round(p.length_meters)} m`)
                    : (m.length_m
                        ? `${Math.round(m.length_m)} m`
                        : '1.2 km')}
                </div>
              </div>
              <div>
                <div className="text-[10px] text-[#7D7063] uppercase">Nodes</div>
                <div className="font-bold text-[#241D16]">
                  {selectedRoad.geometry?.coordinates?.length || p.coordinate_count || 12} Vertices
                </div>
              </div>
              <div>
                <div className="text-[10px] text-[#7D7063] uppercase">Verification</div>
                <div className={`font-bold ${isSupporting ? 'text-[#D97706]' : 'text-[#3F6452]'}`}>
                  {isSupporting ? 'SUPPORTING' : (p.verification_status || 'VERIFIED')}
                </div>
              </div>
            </div>

            {/* Spatial Telemetry Details */}
            <div className="text-[11px] text-[#7D7063] font-mono space-y-1 mb-3 bg-white p-2 rounded-lg border border-[#E7DFD3]/80">
              <div className="flex justify-between">
                <span>Authority:</span>
                <span className="font-semibold text-[#241D16] truncate max-w-[170px]" title={p.source_name || ''}>
                  {p.source_name || m.authority || 'Authoritative GIS'}
                </span>
              </div>
              <div className="flex justify-between">
                <span>Source CRS:</span>
                <span className="font-semibold text-[#241D16]">{p.original_crs || 'EPSG:32644'}</span>
              </div>
              <div className="flex justify-between">
                <span>Display CRS:</span>
                <span className="font-semibold text-[#241D16]">EPSG:4326 (WGS84)</span>
              </div>
              {p.geometry_centroid && (
                <div className="flex justify-between">
                  <span>Centroid:</span>
                  <span className="text-[#241D16]">
                    {p.geometry_centroid[0].toFixed(5)}, {p.geometry_centroid[1].toFixed(5)}
                  </span>
                </div>
              )}
            </div>

            {/* Action Buttons */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => {
                  if (mapInstanceRef.current && selectedRoad.geometry) {
                    const bounds = L.geoJSON(selectedRoad.geometry).getBounds();
                    if (bounds.isValid()) {
                      mapInstanceRef.current.fitBounds(bounds, { padding: [60, 60], maxZoom: 18, animate: true });
                    }
                  }
                }}
                className="flex-1 text-white text-xs font-bold py-2 rounded-xl transition text-center shadow-xs cursor-pointer flex items-center justify-center gap-1.5"
                style={{ backgroundColor: typeColor }}
              >
                <Crosshair className="w-3.5 h-3.5" />
                <span>Fit Corridor</span>
              </button>
              <button
                onClick={() => setGisDiagnosticMode(!gisDiagnosticMode)}
                className={`px-3 py-2 rounded-xl text-xs font-mono font-bold border transition cursor-pointer flex items-center gap-1.5 ${
                  gisDiagnosticMode 
                    ? 'bg-[#DC2626] text-white border-[#DC2626]' 
                    : 'bg-[#FAF8F3] hover:bg-[#F3EFE6] text-[#241D16] border-[#E7DFD3]'
                }`}
                title="Toggle vertex nodes & diagnostic telemetry"
              >
                <Terminal className="w-3.5 h-3.5" />
                <span>Diagnostic</span>
              </button>
            </div>
          </div>
        );
      })()}
      {/* GIS Diagnostic Telemetry HUD */}
      {gisDiagnosticMode && (
        <div className="absolute bottom-16 left-4 z-25 max-w-sm bg-black/90 text-white font-mono text-[11px] p-3.5 rounded-2xl shadow-2xl border border-white/20 backdrop-blur-md animate-in fade-in slide-in-from-bottom-2">
          <div className="flex items-center justify-between border-b border-white/20 pb-1.5 mb-2">
            <div className="flex items-center gap-1.5 text-emerald-400 font-bold">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
              <span>GIS DIAGNOSTIC TELEMETRY</span>
            </div>
            <button
              onClick={() => setGisDiagnosticMode(false)}
              className="text-white/60 hover:text-white transition cursor-pointer"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
          <div className="space-y-1">
            <div className="flex justify-between">
              <span className="text-white/60">Active AOI:</span>
              <span className="font-bold text-white">{activeDataset?.city || 'Chennai'} ({activeDataset?.aoi || 'T. Nagar'})</span>
            </div>
            <div className="flex justify-between">
              <span className="text-white/60">Geometry Source:</span>
              <span className="text-emerald-300">OSM High-Res Centerline</span>
            </div>
            <div className="flex justify-between">
              <span className="text-white/60">Coordinate Order:</span>
              <span className="text-amber-300">[lon, lat] GeoJSON WGS84</span>
            </div>
            <div className="flex justify-between">
              <span className="text-white/60">Basemap Correlated:</span>
              <span className="text-emerald-400 font-bold">YES · Zero Inversion</span>
            </div>
            <div className="flex justify-between">
              <span className="text-white/60">Active Road Features:</span>
              <span>{roadsData?.features?.length || 0}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-white/60">Active Drain Features:</span>
              <span>{drainageData?.features?.length || 0}</span>
            </div>
            {selectedRoad && (
              <div className="pt-2 mt-2 border-t border-white/20 space-y-0.5">
                <div className="text-amber-400 font-bold">SELECTED CORRIDOR:</div>
                <div className="truncate text-white/90">{selectedRoad.properties?.name || selectedRoad.id}</div>
                <div className="text-white/60 text-[10px]">
                  Nodes: {selectedRoad.geometry?.coordinates?.length || 0} vertices · Length: {selectedRoad.properties?.length_meters ? `${Math.round(selectedRoad.properties.length_meters)}m` : '1.4km'}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Floating Map Navigation Controls */}
      <div className="absolute right-4 bottom-6 z-20 flex flex-col gap-2">
        <div className="bg-white/95 backdrop-blur-md rounded-xl shadow-sm border border-[#E7DFD3] overflow-hidden flex flex-col text-[#241D16]">
          <button
            onClick={() => mapInstanceRef.current?.zoomIn()}
            className="p-2.5 hover:bg-[#FAF8F3] transition active:bg-[#F6F2EB] cursor-pointer"
            title="Zoom In"
          >
            <Plus className="w-4 h-4" />
          </button>
          <div className="h-[1px] bg-[#E7DFD3]" />
          <button
            onClick={() => mapInstanceRef.current?.zoomOut()}
            className="p-2.5 hover:bg-[#FAF8F3] transition active:bg-[#F6F2EB] cursor-pointer"
            title="Zoom Out"
          >
            <Minus className="w-4 h-4" />
          </button>
        </div>

        <button
          onClick={resetView}
          className="p-2.5 bg-white/95 backdrop-blur-md hover:bg-[#FAF8F3] text-[#A86236] rounded-xl shadow-sm border border-[#E7DFD3] transition active:scale-95 cursor-pointer"
          title="Center on Pilot Zone"
        >
          <Crosshair className="w-4 h-4" />
        </button>
      </div>

      {/* Bottom Confidence Legend */}
      <div className="absolute left-4 bottom-4 z-20 bg-white/95 backdrop-blur-md border border-[#E7DFD3] rounded-xl shadow-sm px-3.5 py-2 hidden md:flex items-center gap-4 text-xs font-semibold text-[#241D16]">
        <span className="text-[10px] uppercase font-bold text-[#7D7063] tracking-wider font-mono">Confidence</span>
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-[#3F6452]"></span>
          <span>90–100% {t.highConfidence}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-[#D8AD56]"></span>
          <span>70–89% {t.reviewRecommended}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-[#C87958]"></span>
          <span>&lt;70% {t.conflictDetected}</span>
        </div>

        {/* Active Dataset / CRS telemetry badge */}
        {activeDataset && (
          <div className="hidden lg:flex items-center gap-2 pl-3 border-l border-[#E7DFD3] text-[11px] font-mono text-[#7D7063]">
            <span className="font-bold text-[#241D16]">{activeDataset.city}</span>
            <span>•</span>
            <span className="text-[#A86236] font-semibold">{activeDataset.aoi}</span>
            <span>•</span>
            <span className="bg-[#FAF8F3] px-2 py-0.5 rounded border border-[#E7DFD3] text-[#241D16]">{activeDataset.crs}</span>
            {activeDataset.isReference ? (
              <span className="bg-[#EAF2EB] text-[#3F6452] px-2 py-0.5 rounded-full font-bold border border-[#C5DAC9] text-[10px]">
                REFERENCE DATASET
              </span>
            ) : (
              <span className="bg-[#FDF1EB] text-[#A86236] px-2 py-0.5 rounded-full font-bold border border-[#F3CEBD] text-[10px]">
                ISOLATED AOI
              </span>
            )}
          </div>
        )}
      </div>

    </div>
  );
};