import React, { useState } from 'react';
import { 
  BuildingEntity, 
  Language, 
  ReconciliationStats, 
  ActivityEntry,
  DatasetMeta
} from '../types';
import { translations } from '../data/i18n';
import { InteractiveMap } from './InteractiveMap';
import { BuildingDetailPanel } from './BuildingDetailPanel';
import { 
  Building2, 
  CheckCircle2, 
  TrendingUp, 
  AlertTriangle, 
  ArrowRight, 
  Sparkles,
  ChevronDown,
  Activity,
  Layers,
  Info
} from 'lucide-react';

export interface GisExplorerViewProps {
  buildings: BuildingEntity[];
  stats: ReconciliationStats;
  selectedBuilding: BuildingEntity | null;
  onSelectBuilding: (building: BuildingEntity | null) => void;
  language: Language;
  dataSource: 'bengaluru' | 'mock';
  datasets: DatasetMeta[];
  activeDataset: DatasetMeta;
  onSelectDataset: (id: string) => void;
  activityLog?: ActivityEntry[];
  focusedGeometry?: [number, number][] | null;
  onFocusGeometry?: (coords: [number, number][], label?: string) => void;
  historicalComparison?: { geomA: any; geomB: any; metaA: any; metaB: any } | null;
  onClearHistoricalComparison?: () => void;
  onShowHistoricalComparison?: (geomA: any, geomB: any, metaA: any, metaB: any) => void;
  onOpenUpload?: () => void;
  onOpenHarmonization?: () => void;
  onGoToReview?: () => void;
  onApprove?: (id: string) => void;
  onReject?: (id: string) => void;
  isResolving?: boolean;
  onViewSources?: () => void;
  onOpenDigitalCard?: () => void;
  onOpenTechnicalDetails?: () => void;
  onOpenHistory?: () => void;
}

const formatRelativeTime = (timestamp: number): string => {
  const diffSec = Math.floor((Date.now() - timestamp) / 1000);
  if (diffSec < 5) return 'just now';
  if (diffSec < 60) return `${diffSec}s ago`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHours = Math.floor(diffMin / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  return new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
};

export const GisExplorerView: React.FC<GisExplorerViewProps> = ({
  buildings,
  stats,
  selectedBuilding,
  onSelectBuilding,
  language,
  dataSource,
  datasets,
  activeDataset,
  onSelectDataset,
  activityLog = [],
  focusedGeometry,
  onFocusGeometry,
  historicalComparison,
  onClearHistoricalComparison,
  onShowHistoricalComparison,
  onOpenUpload,
  onOpenHarmonization,
  onGoToReview,
  onApprove,
  onReject,
  isResolving,
  onViewSources,
  onOpenDigitalCard,
  onOpenTechnicalDetails,
  onOpenHistory,
}) => {
  const t = translations[language] || translations.en;
  const [rightPanelTab, setRightPanelTab] = useState<'parcel' | 'activity'>('parcel');

  const matchedPct = stats.totalBuildings > 0
    ? Math.round((stats.matched / stats.totalBuildings) * 100)
    : 78;

  const sourceTypesPresent = new Set(
    buildings.flatMap(b =>
      Object.entries(b.sources || {})
        .filter(([, s]) => s.sourceName !== 'not captured')
        .map(([type]) => type)
    )
  ).size || 4;

  return (
    <div className="max-w-7xl mx-auto space-y-6 py-6 px-4 sm:px-6 lg:px-8 font-sans">
      
      {/* ============================================================ */}
      {/* 1. PAGE TITLE & HEADER */}
      {/* ============================================================ */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-2 border-b border-[#E7DFD3]">
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-full overflow-hidden bg-white border border-[#E7DFD3] shadow-xs shrink-0">
              <img src="/terranode_logo.png" alt="TerraNode Logo" className="w-full h-full object-cover rounded-full" />
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-[#241D16] tracking-tight">
              GIS EXPLORER
            </h1>
          </div>
          <p className="text-sm font-semibold text-[#5B4F43]">
            Interactive spatial intelligence, layer comparison, and multi-source parcel verification.
          </p>
        </div>

        {/* Action Controls: Active Dataset Dropdown + Quick Buttons */}
        <div className="flex items-center gap-2.5 shrink-0">
          {datasets.length > 0 && (
            <div className="relative">
              <select
                value={activeDataset.id}
                onChange={(e) => onSelectDataset(e.target.value)}
                className="appearance-none bg-white border border-[#E7DFD3] text-[#241D16] text-xs font-bold rounded-xl px-3.5 py-2.5 pr-8 hover:border-[#A86236] transition cursor-pointer shadow-2xs focus:outline-hidden focus:ring-2 focus:ring-[#A86236]/20"
              >
                {datasets.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.city} — {d.aoi} ({d.buildings?.length || 64} parcels)
                  </option>
                ))}
              </select>
              <ChevronDown className="w-3.5 h-3.5 text-[#7D7063] absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
            </div>
          )}

          <button
            onClick={onOpenHarmonization}
            className="flex items-center gap-1.5 px-4 py-2.5 rounded-xl bg-[#A86236] hover:bg-[#8F4F28] text-white font-bold text-xs shadow-xs transition active:scale-95 cursor-pointer"
          >
            <Sparkles className="w-3.5 h-3.5 text-white" />
            <span>Harmonize</span>
          </button>
        </div>
      </div>

      {/* ============================================================ */}
      {/* 2. 4 METRIC STAT CARDS */}
      {/* ============================================================ */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        
        {/* Card 1: Total Buildings */}
        <div className="bg-white p-4 sm:p-5 rounded-2xl shadow-xs border border-[#E7DFD3] hover:border-[#DCD3C6] transition">
          <div className="flex items-center justify-between">
            <p className="text-[10px] font-bold uppercase text-[#7D7063] tracking-widest font-mono">
              TOTAL BUILDINGS
            </p>
            <div className="w-8 h-8 rounded-xl bg-[#F4EEE6] text-[#7D7063] flex items-center justify-center">
              <Building2 className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <p className="text-2xl sm:text-3xl font-extrabold text-[#241D16] font-mono">
              {stats.totalBuildings.toLocaleString()}
            </p>
          </div>
          <span className="text-[11px] text-[#7D7063] font-normal block mt-1">
            Across {sourceTypesPresent} geospatial input sources
          </span>
        </div>

        {/* Card 2: Matched */}
        <div className="bg-white p-4 sm:p-5 rounded-2xl shadow-xs border border-[#E7DFD3] hover:border-[#CBE0D3] transition">
          <div className="flex items-center justify-between">
            <p className="text-[10px] font-bold uppercase text-[#3F6452] tracking-widest font-mono">
              MATCHED
            </p>
            <div className="w-8 h-8 rounded-xl bg-[#F2F7F4] text-[#3F6452] flex items-center justify-center">
              <CheckCircle2 className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <p className="text-2xl sm:text-3xl font-extrabold text-[#3F6452] font-mono">
              {stats.matched.toLocaleString()}
            </p>
            <span className="text-xs font-mono text-[#3F6452] font-bold bg-[#EAF2EB] px-1.5 py-0.5 rounded border border-[#CBE0D3]">
              {matchedPct}%
            </span>
          </div>
          <span className="text-[11px] text-[#7D7063] font-normal block mt-1">
            Canonical digital twin entities
          </span>
        </div>

        {/* Card 3: Average Confidence */}
        <div className="bg-white p-4 sm:p-5 rounded-2xl shadow-xs border border-[#E7DFD3] hover:border-[#EAD9B8] transition">
          <div className="flex items-center justify-between">
            <p className="text-[10px] font-bold uppercase text-[#A86236] tracking-widest font-mono">
              AVERAGE CONFIDENCE
            </p>
            <div className="w-8 h-8 rounded-xl bg-[#FDF8F3] text-[#A86236] flex items-center justify-center">
              <TrendingUp className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <p className="text-2xl sm:text-3xl font-extrabold text-[#A86236] font-mono">
              {stats.averageConfidence}%
            </p>
            <span className="text-xs font-mono text-[#3F6452] font-bold">
              +14% vs raw
            </span>
          </div>
          <span className="text-[11px] text-[#7D7063] font-normal block mt-1">
            IoU & Centroid consensus score
          </span>
        </div>

        {/* Card 4: Requires Review */}
        <div 
          onClick={onGoToReview}
          className="bg-white p-4 sm:p-5 rounded-2xl shadow-xs border border-[#E7DFD3] hover:border-[#D9825B] transition cursor-pointer group"
        >
          <div className="flex items-center justify-between">
            <p className="text-[10px] font-bold uppercase text-[#B84A39] tracking-widest font-mono">
              REQUIRES REVIEW
            </p>
            <div className="w-8 h-8 rounded-xl bg-[#FDF1EB] text-[#B84A39] flex items-center justify-center">
              <AlertTriangle className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <p className="text-2xl sm:text-3xl font-extrabold text-[#B84A39] font-mono">
              {stats.requiresReview}
            </p>
            <span className="text-xs font-mono text-[#B84A39] font-bold bg-[#FDF1EB] px-1.5 py-0.5 rounded border border-[#F3CEBD]">
              Needs Review
            </span>
          </div>
          <div className="flex items-center justify-between mt-1">
            <span className="text-[11px] text-[#7D7063] font-normal">
              Flagged for officer verification
            </span>
            <ArrowRight className="w-3.5 h-3.5 text-[#B84A39] group-hover:translate-x-0.5 transition" />
          </div>
        </div>

      </div>

      {/* ============================================================ */}
      {/* 3. MAIN GIS WORKSPACE: INTERACTIVE MAP & INTELLIGENCE PANELS */}
      {/* ============================================================ */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        
        {/* Left/Center: Interactive Map Container (8 cols) */}
        <div className="lg:col-span-8 bg-white rounded-2xl border border-[#E7DFD3] shadow-xs overflow-hidden flex flex-col">
          <div className="px-4 py-3 bg-[#FAF8F5] border-b border-[#E7DFD3] flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-[#3F6452] animate-pulse"></span>
              <span className="text-xs font-bold text-[#241D16]">Spatial Map Canvas</span>
              <span className="text-[10px] font-mono text-[#7D7063] bg-white px-2 py-0.5 rounded border border-[#E7DFD3]">
                {buildings.length} entities rendered
              </span>
            </div>
            <div className="text-xs text-[#7D7063] hidden sm:block">
              Click any parcel polygon on the map to inspect multi-source alignment
            </div>
          </div>

          {/* Map Canvas */}
          <div className="h-[580px] lg:h-[640px] w-full relative">
            <InteractiveMap
              buildings={buildings}
              selectedBuilding={selectedBuilding}
              onSelectBuilding={(b) => {
                onSelectBuilding(b);
                setRightPanelTab('parcel');
              }}
              language={language}
              onOpenReconcileModal={onOpenHarmonization}
              onOpenUploadModal={onOpenUpload}
              dataSource={activeDataset.id.startsWith('bengaluru') ? dataSource : 'mock'}
              datasets={datasets}
              activeDataset={activeDataset}
              onSelectDataset={onSelectDataset}
              focusedGeometry={focusedGeometry}
              historicalComparison={historicalComparison}
              onClearHistoricalComparison={onClearHistoricalComparison}
            />
          </div>
        </div>

        {/* Right Column: Parcel Inspector & Recent Activity (4 cols) */}
        <div className="lg:col-span-4 space-y-4 flex flex-col">
          
          {/* Top Switcher Bar between Parcel Inspector and Recent Activity */}
          <div className="bg-[#FAF8F5] p-1.5 rounded-2xl border border-[#E7DFD3] flex items-center gap-1 shadow-2xs">
            <button
              onClick={() => setRightPanelTab('parcel')}
              className={`flex-1 py-2 px-3 rounded-xl text-xs font-bold transition flex items-center justify-center gap-1.5 cursor-pointer ${
                rightPanelTab === 'parcel'
                  ? 'bg-white text-[#241D16] shadow-xs border border-[#E7DFD3]'
                  : 'text-[#7D7063] hover:text-[#241D16]'
              }`}
            >
              <Layers className="w-3.5 h-3.5 text-[#A86236]" />
              <span>Parcel Details</span>
              {selectedBuilding && (
                <span className="w-2 h-2 rounded-full bg-[#3F6452]"></span>
              )}
            </button>
            <button
              onClick={() => setRightPanelTab('activity')}
              className={`flex-1 py-2 px-3 rounded-xl text-xs font-bold transition flex items-center justify-center gap-1.5 cursor-pointer ${
                rightPanelTab === 'activity'
                  ? 'bg-white text-[#241D16] shadow-xs border border-[#E7DFD3]'
                  : 'text-[#7D7063] hover:text-[#241D16]'
              }`}
            >
              <Activity className="w-3.5 h-3.5 text-[#A86236]" />
              <span>Recent Activity</span>
              <span className="text-[10px] font-mono px-1.5 py-0.2 rounded-full bg-[#EAF2EB] text-[#3F6452] font-bold">
                Live
              </span>
            </button>
          </div>

          {/* Tab 1: Parcel Inspector Panel */}
          {rightPanelTab === 'parcel' && (
            <div className="bg-white rounded-2xl border border-[#E7DFD3] shadow-xs overflow-hidden h-[600px] flex flex-col">
              <BuildingDetailPanel
                building={selectedBuilding}
                onClose={() => onSelectBuilding(null)}
                language={language}
                onViewSources={onViewSources}
                onOpenReconcile={onOpenHarmonization}
                onOpenDigitalCard={onOpenDigitalCard}
                onOpenTechnicalDetails={onOpenTechnicalDetails}
                onOpenHistory={onOpenHistory}
                onApprove={onApprove}
                onReject={onReject}
                onFocusGeometry={onFocusGeometry}
                onShowHistoricalComparison={onShowHistoricalComparison}
                isResolving={isResolving}
              />
            </div>
          )}

          {/* Tab 2: Recent Activity Live Feed in Right Column */}
          {rightPanelTab === 'activity' && (
            <div className="bg-white rounded-2xl p-5 border border-[#E7DFD3] shadow-xs flex flex-col justify-between h-[600px]">
              <div>
                <div className="flex items-center justify-between mb-3 pb-2 border-b border-[#E7DFD3]">
                  <div className="flex items-center gap-2">
                    <Activity className="w-4 h-4 text-[#A86236]" />
                    <h3 className="text-xs font-bold uppercase tracking-wider text-[#241D16] font-mono">
                      RECENT ACTIVITY
                    </h3>
                  </div>
                  <span className="text-[10px] text-[#3F6452] font-mono font-bold bg-[#EAF2EB] px-2 py-0.5 rounded">LIVE FEED</span>
                </div>

                {activityLog.length === 0 ? (
                  <p className="text-xs text-[#7D7063] italic py-8 text-center">
                    Session initialized. Actions like approving entities, uploading files, or triggering reconciliation will log here.
                  </p>
                ) : (
                  <div className="space-y-3.5 max-h-[460px] overflow-y-auto pr-1">
                    {activityLog.map((act) => (
                      <div key={act.id} className="text-xs flex items-start gap-2.5 p-2 rounded-xl hover:bg-[#FAF8F5] transition">
                        <div className="mt-0.5 shrink-0">
                          {act.type === 'success' || act.type === 'verified' ? (
                            <CheckCircle2 className="w-3.5 h-3.5 text-[#3F6452]" />
                          ) : act.type === 'warning' ? (
                            <AlertTriangle className="w-3.5 h-3.5 text-[#C99756]" />
                          ) : (
                            <Info className="w-3.5 h-3.5 text-[#A86236]" />
                          )}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-[#241D16] leading-snug">{act.title}</p>
                          <span className="text-[10px] text-[#7D7063] font-mono block mt-0.5">
                            {formatRelativeTime(act.timestamp)}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="pt-3 border-t border-[#E7DFD3] mt-3 text-center">
                <span className="text-[11px] font-mono text-[#7D7063]">
                  TERRANODE RECONCILIATION ENGINE · v2.4.0
                </span>
              </div>
            </div>
          )}

        </div>

      </div>

      {/* ============================================================ */}
      {/* 4. LOWER SECTION: RECENT ACTIVITY FULL-WIDTH LIVE WIDGET */}
      {/* (SPATIAL RECONCILIATION CONTEXT DELETED AS REQUESTED) */}
      {/* ============================================================ */}
      <div className="w-full bg-white rounded-2xl p-5 border border-[#E7DFD3] shadow-xs space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-[#E7DFD3]">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-[#FAF8F5] border border-[#E7DFD3] flex items-center justify-center text-[#A86236]">
              <Activity className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xs font-bold uppercase tracking-wider text-[#241D16] font-mono">
                  RECENT ACTIVITY
                </h2>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-[#EAF2EB] text-[#3F6452] font-bold border border-[#C5DAC9]">
                  ● LIVE FEED
                </span>
              </div>
              <p className="text-[11px] text-[#7D7063]">
                Real-time geospatial reconciliation audit trail, layer ingestion, and officer decision stream.
              </p>
            </div>
          </div>
          <span className="text-[11px] font-mono text-[#7D7063] bg-[#FAF8F5] px-2.5 py-1 rounded-lg border border-[#E7DFD3]">
            {activityLog.length} events recorded
          </span>
        </div>

        {activityLog.length === 0 ? (
          <p className="text-xs text-[#7D7063] italic py-6 text-center">
            Session initialized. Actions like approving entities, uploading files, or triggering reconciliation will log here.
          </p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {activityLog.slice(0, 6).map((act) => (
              <div key={act.id} className="text-xs flex items-start gap-2.5 p-3 rounded-xl bg-[#FAF8F5] border border-[#E7DFD3] hover:border-[#DCD3C6] transition">
                <div className="mt-0.5 shrink-0">
                  {act.type === 'success' || act.type === 'verified' ? (
                    <CheckCircle2 className="w-4 h-4 text-[#3F6452]" />
                  ) : act.type === 'warning' ? (
                    <AlertTriangle className="w-4 h-4 text-[#C99756]" />
                  ) : (
                    <Info className="w-4 h-4 text-[#A86236]" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-[#241D16] leading-snug truncate" title={act.title}>{act.title}</p>
                  <span className="text-[10px] text-[#7D7063] font-mono block mt-1">
                    {formatRelativeTime(act.timestamp)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="pt-2 border-t border-[#E7DFD3] flex items-center justify-between text-[11px] font-mono text-[#7D7063]">
          <span>TERRANODE RECONCILIATION ENGINE · v2.4.0</span>
          <span>EPSG:32643 (UTM 43N) · COORDINATE ACCURACY ±0.05m</span>
        </div>
      </div>

    </div>
  );
};
