import { 
  BuildingEntity, 
  Language, 
  ReconciliationStats, 
  ActivityEntry,
  DatasetMeta
} from '../types';
import { translations } from '../data/i18n';
import { 
  UploadCloud, 
  Sparkles, 
  CheckCircle2, 
  AlertTriangle, 
  Building2, 
  TrendingUp, 
  Compass, 
  ArrowRight, 
  Activity, 
  Split, 
  Maximize2, 
  Wifi, 
  WifiOff,
  MapPin
} from 'lucide-react';
import { InteractiveMap } from './InteractiveMap';

interface DashboardViewProps {
  buildings: BuildingEntity[];
  stats: ReconciliationStats;
  dataSource: 'live' | 'osm' | 'mock';
  activityLog: ActivityEntry[];
  showcaseBuilding: BuildingEntity | null;
  selectedBuilding: BuildingEntity | null;
  onSelectBuilding: (building: BuildingEntity) => void;
  language: Language;
  onOpenUpload: () => void;
  onOpenGis?: () => void;
  onOpenHarmonization?: () => void;
  onOpenValidation?: () => void;
  onOpenAnalytics?: () => void;
  onOpenReports?: () => void;
  onOpenReconciliation: () => void;
  onGoToBeforeAfter: () => void;
  onGoToFullMap: () => void;
  onGoToReview: () => void;
  datasets?: DatasetMeta[];
  activeDataset?: DatasetMeta;
  onSelectDataset?: (datasetId: string) => void;
}

function formatRelativeTime(timestamp: number): string {
  const diffMs = Date.now() - timestamp;
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return 'Just now';
  if (diffMin < 60) return `${diffMin} min${diffMin === 1 ? '' : 's'} ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr} hour${diffHr === 1 ? '' : 's'} ago`;
  const diffDay = Math.floor(diffHr / 24);
  return `${diffDay} day${diffDay === 1 ? '' : 's'} ago`;
}

const SOURCE_LABELS: Record<string, string> = {
  ori: 'Drone (ORI)',
  municipal: 'Municipal GIS',
  cadastral: 'Cadastral Map',
  ai: 'AI Extraction',
};

export const DashboardView: React.FC<DashboardViewProps> = ({
  buildings,
  stats,
  dataSource,
  activityLog,
  showcaseBuilding,
  selectedBuilding,
  onSelectBuilding,
  language,
  onOpenUpload,
  onOpenGis,
  onOpenHarmonization,
  onOpenValidation,
  onOpenAnalytics,
  onOpenReports,
  onOpenReconciliation,
  onGoToBeforeAfter,
  onGoToFullMap,
  onGoToReview,
  datasets,
  activeDataset,
  onSelectDataset,
}) => {
  const t = translations[language];

  const matchedPct = stats.totalBuildings > 0
    ? Math.round((stats.matched / stats.totalBuildings) * 100)
    : 0;
  const confidenceDelta = stats.afterAvgConfidence - stats.beforeAvgConfidence;
  const sourceTypesPresent = new Set(
    buildings.flatMap(b =>
      Object.entries(b.sources)
        .filter(([, s]) => s.sourceName !== 'not captured')
        .map(([type]) => type)
    )
  ).size;

  const showcaseSourceEntries = showcaseBuilding
    ? (['ori', 'municipal'] as const).map((key) => ({
        key,
        label: SOURCE_LABELS[key],
        source: showcaseBuilding.sources[key],
      }))
    : [];

  return (
    <div className="max-w-7xl mx-auto space-y-6 py-6 px-4 sm:px-6 lg:px-8">
      {/* Header Banner */}
      <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-4 pb-2">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full overflow-hidden bg-white border border-[#E7DFD3] shadow-xs shrink-0">
            <img src="/terranode_logo.png" alt="TerraNode Logo" className="w-full h-full object-cover rounded-full" />
          </div>
          <div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-[#241D16] tracking-tight font-sans">
              TERRANODE Command Center
            </h1>
          <p className="text-sm text-[#7D7063] font-normal mt-1 max-w-3xl leading-relaxed">
            {t.tagline}
          </p>

          {activeDataset && (
            <div className="flex items-center gap-2 mt-2.5 flex-wrap">
              <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono font-bold ${
                activeDataset.isReference 
                  ? 'bg-[#EAF2EB] text-[#3F6452] border border-[#C5DAC9]' 
                  : 'bg-[#FDF1EB] text-[#A86236] border border-[#F3CEBD]'
              }`}>
                <MapPin className="w-3.5 h-3.5" />
                {activeDataset.isReference ? `REFERENCE DATASET: ${activeDataset.name}` : `ACTIVE DATASET: ${activeDataset.name}`}
              </span>
              <span className="text-xs font-mono text-[#7D7063] bg-white px-2.5 py-1 rounded-lg border border-[#E7DFD3] shadow-xs">
                CRS: {activeDataset.crs} • {buildings.length} Parcels
              </span>
            </div>
          )}
        </div>

        {/* Primary Action Buttons */}
        <div className="flex flex-wrap items-center gap-2.5">
          <button
            onClick={onOpenUpload}
            className="flex items-center gap-2 px-4 sm:px-4.5 py-2.5 rounded-xl border border-[#E7DFD3] text-[#382E25] font-semibold text-xs sm:text-sm bg-white hover:bg-[#F4EEE6] shadow-2xs transition active:scale-95 cursor-pointer"
          >
            <UploadCloud className="w-4 h-4 text-[#a86236]" />
            <span>02 Upload Documents</span>
          </button>

          <button
            onClick={onOpenHarmonization || onOpenReconciliation}
            className="flex items-center gap-2 px-5 sm:px-5.5 py-2.5 rounded-xl bg-[#a86236] hover:bg-[#8F4F28] text-white font-bold text-xs sm:text-sm shadow-sm transition active:scale-95 cursor-pointer"
          >
            <Sparkles className="w-4 h-4 text-white" />
            <span>04 Harmonize</span>
          </button>
        </div>
      </div>


      {/* 4 Metric Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Buildings */}
        <div className="bg-white p-4 sm:p-5 rounded-2xl shadow-xs border border-[#E7DFD3] hover:border-[#DCD3C6] transition">
          <div className="flex items-center justify-between">
            <p className="text-[10px] font-bold uppercase text-[#7D7063] tracking-widest font-mono">
              {t.totalBuildings}
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
            {sourceTypesPresent > 0
              ? `Across ${sourceTypesPresent} geospatial input sources`
              : 'Multi-source survey dataset'}
          </span>
        </div>

        {/* Matched / Reconciled */}
        <div className="bg-white p-4 sm:p-5 rounded-2xl shadow-xs border border-[#E7DFD3] hover:border-[#CBE0D3] transition">
          <div className="flex items-center justify-between">
            <p className="text-[10px] font-bold uppercase text-[#3F6452] tracking-widest font-mono">
              {t.matched}
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

        {/* Average Confidence */}
        <div className="bg-white p-4 sm:p-5 rounded-2xl shadow-xs border border-[#E7DFD3] hover:border-[#EAD9B8] transition">
          <div className="flex items-center justify-between">
            <p className="text-[10px] font-bold uppercase text-[#a86236] tracking-widest font-mono">
              {t.averageConfidence}
            </p>
            <div className="w-8 h-8 rounded-xl bg-[#FDF8F3] text-[#a86236] flex items-center justify-center">
              <TrendingUp className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <p className="text-2xl sm:text-3xl font-extrabold text-[#241D16] font-mono">
              {stats.averageConfidence}%
            </p>
            <span className="text-xs font-mono font-bold text-[#3F6452]">
              {confidenceDelta >= 0 ? '+' : ''}{confidenceDelta}% vs raw
            </span>
          </div>
          <span className="text-[11px] text-[#7D7063] font-normal block mt-1">
            IoU & Centroid consensus score
          </span>
        </div>

        {/* Requires Review */}
        <div 
          onClick={onGoToReview}
          className="bg-white p-4 sm:p-5 rounded-2xl shadow-xs border border-[#EAD9B8] hover:border-[#C99756] transition cursor-pointer group"
        >
          <div className="flex items-center justify-between">
            <p className="text-[10px] font-bold uppercase text-[#966B24] tracking-widest font-mono">
              {t.requiresReview}
            </p>
            <div className="w-8 h-8 rounded-xl bg-[#FAF3E6] text-[#966B24] flex items-center justify-center group-hover:scale-105 transition-transform">
              <AlertTriangle className="w-4 h-4 text-[#966B24]" />
            </div>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <p className="text-2xl sm:text-3xl font-extrabold text-[#966B24] font-mono">
              {stats.requiresReview}
            </p>
            <span className="text-xs font-mono font-bold text-[#966B24] bg-[#FAF3E6] px-2 py-0.5 rounded border border-[#EAD9B8]">
              Needs Review
            </span>
          </div>
          <div className="flex items-center justify-between mt-1">
            <span className="text-[11px] text-[#7D7063] font-normal">Flagged for officer verification</span>
            <ArrowRight className="w-3.5 h-3.5 text-[#966B24] group-hover:translate-x-1 transition-transform" />
          </div>
        </div>
      </div>

      {/* Main Console: Map + Showcase & Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Map View */}
        <div className="lg:col-span-8 flex flex-col space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-[#241D16] font-sans">
                Spatial Reconciliation Console
              </h2>
              <span className="text-xs text-[#7D7063] font-mono hidden sm:inline">
                • Click any parcel to inspect source alignment
              </span>
            </div>

            <button
              onClick={onGoToFullMap}
              className="text-xs font-bold text-[#a86236] hover:text-[#8F4F28] flex items-center gap-1.5 transition cursor-pointer"
            >
              <span>Full Screen Map</span>
              <Maximize2 className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="h-[480px] rounded-3xl overflow-hidden shadow-sm border border-[#E7DFD3] bg-[#EFECE6]">
            <InteractiveMap
              buildings={buildings}
              selectedBuilding={selectedBuilding}
              onSelectBuilding={onSelectBuilding}
              language={language}
              onOpenReconcileModal={onOpenReconciliation}
              onOpenUploadModal={onOpenUpload}
              dataSource={dataSource}
              datasets={datasets}
              activeDataset={activeDataset}
              onSelectDataset={onSelectDataset}
            />
          </div>
        </div>

        {/* Right Side: Showcase Building & Activity */}
        <div className="lg:col-span-4 space-y-4 flex flex-col">
          {showcaseBuilding && (
            <div className="bg-white text-[#241D16] rounded-3xl p-5 shadow-xs border border-[#E7DFD3] hover:border-[#DCD3C6] transition">
              <div className="flex items-center justify-between pb-3 border-b border-[#E7DFD3]">
                <span className="text-[10px] font-bold text-[#7D7063] uppercase tracking-wider font-mono">
                  Selected Entity Breakdown
                </span>
                <span className={`text-[10px] font-bold px-2 py-0.5 rounded-md font-mono ${
                  showcaseBuilding.status === 'reconciled'
                    ? 'bg-[#EAF2EB] text-[#3F6452] border border-[#CBE0D3]'
                    : showcaseBuilding.status === 'review'
                    ? 'bg-[#FAF3E6] text-[#966B24] border border-[#EAD9B8]'
                    : 'bg-[#FDF1EB] text-[#C87958] border-[#F0CFC2]'
                }`}>
                  {showcaseBuilding.status === 'reconciled' && '✓ RECONCILED'}
                  {showcaseBuilding.status === 'review' && '⚠ NEEDS REVIEW'}
                  {showcaseBuilding.status === 'conflict' && '✕ CONFLICT'}
                </span>
              </div>

              <div className="my-3">
                <div className="text-xl font-bold flex items-center gap-2 text-[#241D16] font-mono">
                  <span>Parcel #{showcaseBuilding.id}</span>
                </div>
                <span className="text-xs text-[#7D7063] block mt-0.5">
                  {showcaseBuilding.surveyNumber !== 'N/A' ? `Survey No. ${showcaseBuilding.surveyNumber} • ` : ''}
                  Harmonized Area: <strong className="text-[#241D16] font-mono">{showcaseBuilding.area ?? '—'} m²</strong>
                </span>
              </div>

              <div className="grid grid-cols-2 gap-2 text-xs mb-4">
                {showcaseSourceEntries.map(({ key, label, source }) => (
                  <div key={key} className="bg-[#FAF8F3] p-2.5 rounded-xl border border-[#E7DFD3]">
                    <span className="text-[10px] text-[#7D7063] block font-semibold">{label}</span>
                    <span className="font-mono font-bold text-[#966B24]">
                      {source.sourceName !== 'not captured' ? `${source.area} m²` : '—'}
                    </span>
                  </div>
                ))}
              </div>

              <button
                onClick={() => {
                  onSelectBuilding(showcaseBuilding);
                  onGoToFullMap();
                }}
                className="w-full py-2.5 bg-[#a86236] hover:bg-[#8F4F28] text-white font-bold text-xs rounded-xl shadow-xs transition flex items-center justify-center gap-1.5 cursor-pointer"
              >
                <span>Inspect Parcel #{showcaseBuilding.id} on Map</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          {/* Activity Log */}
          <div className="bg-white rounded-3xl p-5 border border-[#E7DFD3] shadow-xs flex-1 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-3 pb-2 border-b border-[#E7DFD3]">
                <div className="flex items-center gap-2">
                  <Activity className="w-4 h-4 text-[#a86236]" />
                  <h3 className="text-xs font-bold uppercase tracking-wider text-[#241D16] font-mono">
                    {t.recentActivity}
                  </h3>
                </div>
                <span className="text-[10px] text-[#7D7063] font-mono">LIVE FEED</span>
              </div>

              {activityLog.length === 0 ? (
                <p className="text-xs text-[#7D7063] italic py-6 text-center">
                  Session initialized. Actions like approving entities, uploading files, or triggering reconciliation will log here.
                </p>
              ) : (
                <div className="space-y-3 max-h-64 overflow-y-auto pr-1">
                  {activityLog.map((act) => (
                    <div key={act.id} className="text-xs flex items-start gap-2.5">
                      <div className="mt-0.5">
                        {act.type === 'success' || act.type === 'verified' ? (
                          <CheckCircle2 className="w-3.5 h-3.5 text-[#3F6452]" />
                        ) : act.type === 'warning' ? (
                          <AlertTriangle className="w-3.5 h-3.5 text-[#C99756]" />
                        ) : (
                          <Compass className="w-3.5 h-3.5 text-[#a86236]" />
                        )}
                      </div>
                      <div className="flex-1">
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
        </div>
      </div>
    </div>
  );
};
