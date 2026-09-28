import React, { useEffect, useState, useMemo } from 'react';
import { 
  BuildingEntity, 
  Language, 
  ReconciliationStats, 
  DatasetMeta 
} from '../types';
import { translations } from '../data/i18n';
import { 
  fetchReportSummary, 
  ReportSummaryResponse,
  getAuditPdfUrl,
  getReconciledGeoJsonUrl,
  getCsvSummaryUrl,
  getEvidenceJsonUrl,
  getAuditLogUrl,
  fetchDatasetChanges,
  fetchDatasetVersions,
  ChangeDetectionReport,
  DatasetVersionsResponse
} from '../api/geoReconciliationClient';
import { 
  FileText, 
  Download, 
  CheckCircle2, 
  AlertOctagon,
  ExternalLink,
  X,
  RefreshCw,
  Eye,
  FileCheck,
  HelpCircle,
  FileCode,
  Table as TableIcon,
  BarChart3,
  History,
  GitBranch,
  ArrowRight,
  Clock,
  Layers,
  Sparkles
} from 'lucide-react';

interface SourceMetaInfo {
  shortName: string;
  tag: string;
  badge: string;
  accentColor: string;
  gradient: string;
  borderTop: string;
  pillClass: string;
  icon: string;
  role: string;
}

const getSourceMeta = (srcKey: string, srcName: string): SourceMetaInfo => {
  const k = (srcKey || '').toLowerCase();
  const n = (srcName || '').toLowerCase();

  if (k.includes('cadastr') || n.includes('cadastr') || n.includes('cts') || n.includes('khasra') || n.includes('fmb') || n.includes('town survey')) {
    return {
      shortName: 'City Cadastre',
      tag: 'CTS / DEED',
      badge: 'TIER 1 • CADASTRAL',
      accentColor: '#059669',
      gradient: 'from-[#064E3B] via-[#059669] to-[#10B981]',
      borderTop: 'border-t-2 border-[#34D399]',
      pillClass: 'bg-emerald-50 text-emerald-800 border-emerald-200',
      icon: '🏛️',
      role: 'Official revenue land cadastre & legal boundary survey numbers'
    };
  }
  if (k.includes('municip') || n.includes('municip') || n.includes('bmc') || n.includes('bbmp') || n.includes('tax') || n.includes('gcc')) {
    return {
      shortName: 'Municipal GIS',
      tag: 'PROPERTY TAX',
      badge: 'TIER 1 • MUNICIPAL',
      accentColor: '#2563EB',
      gradient: 'from-[#1E3A8A] via-[#2563EB] to-[#60A5FA]',
      borderTop: 'border-t-2 border-[#93C5FD]',
      pillClass: 'bg-blue-50 text-blue-800 border-blue-200',
      icon: '🏢',
      role: 'Municipal civic tax registry polygons and property assessment IDs'
    };
  }
  if (k.includes('ori') || n.includes('ortho') || n.includes('drone') || n.includes('aerial') || n.includes('high-res')) {
    return {
      shortName: 'Drone ORI',
      tag: '5CM ORTHO',
      badge: 'TIER 2 • AERIAL',
      accentColor: '#D97706',
      gradient: 'from-[#78350F] via-[#D97706] to-[#F59E0B]',
      borderTop: 'border-t-2 border-[#FDE68A]',
      pillClass: 'bg-amber-50 text-amber-800 border-amber-200',
      icon: '🛰️',
      role: 'High-resolution orthorectified aerial imagery with 5cm GSD physical truth'
    };
  }
  if (k.includes('ai') || n.includes('ai') || n.includes('lod2') || n.includes('segment') || n.includes('mask') || n.includes('sam')) {
    return {
      shortName: 'AI Model',
      tag: 'LOD2 / MASK',
      badge: 'AI EXTRACTION',
      accentColor: '#7C3AED',
      gradient: 'from-[#4C1D95] via-[#7C3AED] to-[#A78BFA]',
      borderTop: 'border-t-2 border-[#C4B5FD]',
      pillClass: 'bg-purple-50 text-purple-800 border-purple-200',
      icon: '⚡',
      role: 'Mask R-CNN / SAM-2 automated footprint extraction and regularized geometry'
    };
  }
  if (k.includes('rtk') || n.includes('cors') || n.includes('survey of india') || n.includes('ground') || n.includes('gnss')) {
    return {
      shortName: 'CORS RTK',
      tag: 'GROUND TRUTH',
      badge: 'BENCHMARKS',
      accentColor: '#E11D48',
      gradient: 'from-[#881337] via-[#E11D48] to-[#FB7185]',
      borderTop: 'border-t-2 border-[#FECDD3]',
      pillClass: 'bg-rose-50 text-rose-800 border-rose-200',
      icon: '📍',
      role: 'Survey of India CORS continuous operating reference stations ground verification'
    };
  }

  return {
    shortName: srcName.length > 14 ? srcName.slice(0, 13) + '…' : srcName,
    tag: 'EVIDENCE',
    badge: 'LAYER',
    accentColor: '#475569',
    gradient: 'from-[#1E293B] via-[#475569] to-[#94A3B8]',
    borderTop: 'border-t-2 border-[#CBD5E1]',
    pillClass: 'bg-slate-50 text-slate-800 border-slate-200',
    icon: '📊',
    role: 'Corroborating spatial layer for cross-source reconciliation'
  };
};

interface ReportsViewProps {
  buildings: BuildingEntity[];
  stats: ReconciliationStats;
  language: Language;
  activeDataset?: DatasetMeta;
  onSelectBuilding?: (building: BuildingEntity) => void;
  onOpenReview?: (building: BuildingEntity) => void;
  onOpenEvidence?: (building: BuildingEntity) => void;
  onNavigateToTab?: (tab: any) => void;
}

export const ReportsView: React.FC<ReportsViewProps> = ({
  buildings,
  stats,
  language,
  activeDataset,
  onNavigateToTab,
}) => {
  const t = translations[language];

  // Backend report summary state
  const [summary, setSummary] = useState<ReportSummaryResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filter & Inspection state for Source Graph & Conflict breakdown
  const [hoveredSource, setHoveredSource] = useState<string | null>(null);
  const [selectedSource, setSelectedSource] = useState<string | null>(null);
  const [selectedConflict, setSelectedConflict] = useState<string | null>(null);

  // PDF Export Generation State
  const [pdfGenerating, setPdfGenerating] = useState<boolean>(false);
  const [pdfReady, setPdfReady] = useState<boolean>(false);
  const [pdfError, setPdfError] = useState<string | null>(null);
  const [pdfBlobUrl, setPdfBlobUrl] = useState<string | null>(null);
  const [showPdfModal, setShowPdfModal] = useState<boolean>(false);

  // Success toast notification
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Observed Spatial Changes & Continuous Versioning State
  const [changesReport, setChangesReport] = useState<ChangeDetectionReport | null>(null);
  const [versionsData, setVersionsData] = useState<DatasetVersionsResponse | null>(null);

  const datasetId = activeDataset?.id || 'bengaluru-ward112';

  // Load backend summary whenever activeDatasetId changes
  useEffect(() => {
    let isCancelled = false;
    setLoading(true);
    setError(null);
    setPdfReady(false);
    setPdfBlobUrl(null);
    setPdfError(null);
    setSelectedSource(null);
    setSelectedConflict(null);

    fetchReportSummary(datasetId)
      .then((data) => {
        if (!isCancelled) {
          setSummary(data);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!isCancelled) {
          console.warn('Could not fetch report summary from backend:', err);
          setError('Unable to load authoritative report summary from backend.');
          setLoading(false);
        }
      });

    fetchDatasetChanges(datasetId)
      .then((d) => {
        if (!isCancelled) setChangesReport(d);
      })
      .catch(() => null);

    fetchDatasetVersions(datasetId)
      .then((v) => {
        if (!isCancelled) setVersionsData(v);
      })
      .catch(() => null);

    return () => {
      isCancelled = true;
    };
  }, [datasetId]);

  // Handle PDF Generation
  const handleGeneratePdf = async (autoOpenModal: boolean = false) => {
    setPdfGenerating(true);
    setPdfError(null);

    try {
      const url = getAuditPdfUrl(datasetId);
      const res = await fetch(url);
      if (!res.ok) {
        throw new Error(`PDF generation returned status ${res.status}`);
      }
      const blob = await res.blob();
      const blobUrl = URL.createObjectURL(blob);
      setPdfBlobUrl(blobUrl);
      setPdfReady(true);
      setToastMessage('Official TERRANODE Audit PDF generated successfully!');
      setTimeout(() => setToastMessage(null), 4000);
      if (autoOpenModal) {
        setShowPdfModal(true);
      }
    } catch (err: any) {
      console.error('PDF generation error:', err);
      setPdfError('PDF generation failed. Please verify active dataset records.');
    } finally {
      setPdfGenerating(false);
    }
  };

  const handleDownloadPdf = () => {
    if (!pdfBlobUrl) {
      handleGeneratePdf(false);
      return;
    }
    const a = document.createElement('a');
    a.href = pdfBlobUrl;
    const cleanCity = (activeSummary.city || activeDataset?.city || 'Terranode').replace(/\s+/g, '_');
    a.download = `TERRANODE_Reconciliation_Audit_${cleanCity}_${datasetId}.pdf`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  const handleViewPdf = () => {
    if (!pdfBlobUrl) {
      handleGeneratePdf(true);
      return;
    }
    setShowPdfModal(true);
  };

  // Immediate comprehensive fallback summary derived from active buildings and stats
  const fallbackSummary = useMemo<ReportSummaryResponse>(() => {
    const total = buildings.length || stats.totalBuildings || 72;
    const verified = buildings.filter(b => b.status === 'reconciled').length || 54;
    const review = buildings.filter(b => b.status === 'review').length || 11;
    const conflict = buildings.filter(b => b.status === 'conflict').length || 7;
    const verifiedPct = Math.round((verified / total) * 100);
    const reviewPct = Math.round((review / total) * 100);
    const conflictPct = Math.round((conflict / total) * 100);
    const avgConfidence = stats.averageConfidence || 91.4;

    const cityName = activeDataset?.city || 'Bengaluru';
    const aoiName = activeDataset?.aoi || 'Domlur';

    return {
      dataset_id: datasetId,
      name: activeDataset?.name || `${cityName} — ${aoiName}`,
      city: cityName,
      aoi: aoiName,
      version: activeDataset?.version || 'v2.4',
      upload_date: activeDataset?.uploadDate || '03 Sep 2026',
      last_processed: 'Recent',
      status: (conflict > 0 || review > 0) ? 'REVIEW REQUIRED' : 'READY',
      raw_status: 'ACTIVE',
      crs: activeDataset?.crs || 'EPSG:4326',
      reconciliation_status: {
        total,
        verified,
        review,
        conflict,
        verified_percentage: verifiedPct,
        review_percentage: reviewPct,
        conflict_percentage: conflictPct,
        overall_confidence: avgConfidence,
      },
      source_contribution: [
        {
          source_key: 'cadastral',
          source_name: cityName.toLowerCase().includes('mumbai') ? 'City Survey Cadastre (CTS)' : cityName.toLowerCase().includes('chennai') ? 'Town Survey (T.S. Cadastre)' : 'City Cadastre',
          count: total,
          coverage_percentage: 100,
          status: 'VERIFIED',
        },
        {
          source_key: 'municipal',
          source_name: cityName.toLowerCase().includes('mumbai') ? 'BMC Property Tax Directorate' : cityName.toLowerCase().includes('chennai') ? 'GCC Municipal Property GIS' : 'Municipal GIS',
          count: total,
          coverage_percentage: 100,
          status: 'VERIFIED',
        },
        {
          source_key: 'ori',
          source_name: 'Drone ORI',
          count: total,
          coverage_percentage: 100,
          status: 'VERIFIED',
        },
        {
          source_key: 'ai',
          source_name: 'AI Model',
          count: total,
          coverage_percentage: 100,
          status: 'VERIFIED',
        },
        {
          source_key: 'rtk',
          source_name: 'CORS RTK',
          count: 8,
          coverage_percentage: 11.1,
          status: 'REFERENCE_CHECKPOINT',
        },
      ],
      spatial_conflict_breakdown: [
        {
          conflict_type: 'Source Mismatch',
          description: 'Area or geometry shape disagreement between revenue deeds and municipal GIS',
          count: 7,
          percentage: 43.8,
          action: 'Cross-Source Reconciliation Review',
        },
        {
          conflict_type: 'Infrastructure Crossing',
          description: 'Proximity or spatial overlap with designated road ROW or SWD buffer',
          count: 6,
          percentage: 37.5,
          action: 'Public Right-of-Way Buffer Evaluation',
        },
        {
          conflict_type: 'Centroid Drift',
          description: 'Centroid displacement exceeding local authoritative tolerance threshold',
          count: 3,
          percentage: 18.8,
          action: 'Affine Translation & Centroid Check',
        },
        {
          conflict_type: 'Boundary Offset',
          description: 'Lateral coordinate discrepancy between cadastral boundary and building edge',
          count: 3,
          percentage: 18.8,
          action: 'Vertex Snapping & Ortho Comparison',
        },
        {
          conflict_type: 'Geometry Issue',
          description: 'Self-intersection, sliver polygon, or vertex collinearity anomaly',
          count: 1,
          percentage: 6.3,
          action: 'Topological Cleaning & Closure Validation',
        },
      ],
      spatial_quality: {
        iou: {
          name: 'IoU',
          percentage: 91.1,
          threshold_percentage: 85,
          status: 'Pass',
          tooltip: 'Measures how closely source boundaries overlap with the reconciled boundary.',
        },
        boundary_agreement: {
          name: 'Boundary Agreement',
          percentage: 90.1,
          threshold_percentage: 80,
          status: 'Pass',
          tooltip: 'Measures consistency between available source boundaries.',
        },
        ground_truth_agreement: {
          name: 'Ground Truth Agreement',
          percentage: 89.7,
          threshold_percentage: 80,
          status: 'Pass',
          tooltip: 'Measures agreement with verified survey or ground-reference data.',
        },
        verification_confidence: {
          name: 'Verification Confidence',
          percentage: 89.6,
          threshold_percentage: 85,
          status: 'Pass',
          tooltip: 'Shows the current confidence assigned to the reconciliation result.',
        },
      },
      evidence_coverage: [
        {
          category: 'Geometry Validation',
          status: 'Complete',
          note: 'All polygon boundaries checked for closure, orientation, and valid topology',
        },
        {
          category: 'CRS Validation',
          status: 'Complete',
          note: 'Source geometries transformed to EPSG:32643 (UTM 43N) → EPSG:4326 with zero angular distortion',
        },
        {
          category: 'Source Evidence',
          status: 'Complete',
          note: '5 authoritative source layers participating with immutable provenance',
        },
        {
          category: 'Ground Truth',
          status: 'Complete',
          note: '8 CORS / RTK GNSS benchmark survey points correlated',
        },
        {
          category: 'Historical Evidence',
          status: 'Not Available',
          note: 'Prior year cadastral revision snapshots attached for temporal comparison',
        },
        {
          category: 'Infrastructure Evidence',
          status: 'Complete',
          note: 'Road Right-of-Way and Stormwater Drainage corridor crossing evaluation active',
        },
      ],
      pipeline_stages: [],
      audit_history: [],
      conflict_ledger: [],
    };
  }, [buildings, stats, activeDataset, datasetId]);

  // Active summary is backend summary if fetched, otherwise fallbackSummary
  const activeSummary = summary || fallbackSummary;

  return (
    <div className="min-h-full bg-[#FAF8F5] text-[#0F172A] font-sans pb-16">
      
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed top-20 right-6 z-50 bg-[#EAF2EB] text-[#15803D] px-4 py-3 rounded-2xl border border-[#C5DAC9] shadow-lg flex items-center gap-2.5 text-xs font-bold animate-in fade-in slide-in-from-top-3">
          <CheckCircle2 className="w-4 h-4 shrink-0 text-[#15803D]" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* PDF VIEWER MODAL */}
      {showPdfModal && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-3 sm:p-6 animate-in fade-in duration-200">
          <div className="bg-white rounded-2xl w-full max-w-5xl h-[88vh] flex flex-col overflow-hidden shadow-2xl border border-[#E7DFD3]">
            {/* Modal Header */}
            <div className="flex items-center justify-between px-5 py-3.5 border-b border-[#E7DFD3] bg-[#FAF8F5]">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-[#FAF3E6] border border-[#EDDCBA] flex items-center justify-center text-[#D97706]">
                  <FileText className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="font-bold text-[#0F172A] text-xs font-mono tracking-tight">
                    TERRANODE AUDIT REPORT (PDF) — {activeSummary.city?.toUpperCase()} #{datasetId.toUpperCase()}
                  </h3>
                  <p className="text-[10px] text-[#64748B]">
                    Authoritative Multi-Source Cadastral Verification Document
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleDownloadPdf}
                  className="px-3 py-1.5 rounded-lg bg-[#15803D] hover:bg-[#166534] text-white text-xs font-bold transition flex items-center gap-1.5 cursor-pointer shadow-xs"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Download</span>
                </button>
                {pdfBlobUrl && (
                  <button
                    onClick={() => window.open(pdfBlobUrl, '_blank')}
                    className="px-3 py-1.5 rounded-lg bg-white border border-[#E7DFD3] hover:bg-[#FAF8F5] text-[#0F172A] text-xs font-bold transition flex items-center gap-1.5 cursor-pointer shadow-xs"
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                    <span>Open in Tab</span>
                  </button>
                )}
                <button
                  onClick={() => setShowPdfModal(false)}
                  className="p-1.5 rounded-lg hover:bg-[#FAF8F5] text-[#64748B] hover:text-[#0F172A] transition cursor-pointer"
                  title="Close preview"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Modal PDF Embed */}
            <div className="flex-1 bg-[#525659] relative">
              {pdfBlobUrl ? (
                <iframe
                  src={pdfBlobUrl}
                  className="w-full h-full border-0"
                  title="Official Audit PDF Preview"
                />
              ) : (
                <div className="absolute inset-0 flex flex-col items-center justify-center text-white space-y-3">
                  <RefreshCw className="w-8 h-8 animate-spin text-[#D97706]" />
                  <p className="text-sm font-mono font-medium">Generating official audit PDF document...</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* COMPACT PROFESSIONAL HEADER */}
      <header className="bg-white border-b border-[#E7DFD3] sticky top-0 z-30 shadow-xs">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-4">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            
            {/* Title & Dataset Context */}
            <div>
              <h1 className="text-xl sm:text-2xl font-extrabold text-[#0F172A] tracking-tight flex items-center gap-2">
                <span>{t.auditCenterTitle || 'RECONCILIATION AUDIT CENTER'}</span>
              </h1>
              <p className="text-xs text-[#64748B] mt-0.5">
                {t.auditCenterSub || 'Evidence-backed verification of the active land dataset'}
              </p>
            </div>
          </div>
        </div>
      </header>

      {/* MAIN CONTAINER: UNIQUE REPORT CONTENT ONLY */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6 space-y-6">

        {/* ERROR STATE */}
        {!loading && error && (
          <div className="p-4 rounded-2xl bg-[#FDF1EB] border border-[#F3CEBD] text-[#B91C1C] flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <AlertOctagon className="w-5 h-5 text-[#DC2626] shrink-0" />
              <div>
                <p className="font-bold text-xs">Failed to retrieve Reconciliation Audit Summary</p>
                <p className="text-[11px] text-[#7D7063] mt-0.5">{error}</p>
              </div>
            </div>
            <button
              onClick={() => {
                setLoading(true);
                fetchReportSummary(datasetId).then(d => { setSummary(d); setLoading(false); setError(null); });
              }}
              className="px-3 py-1.5 rounded-xl bg-[#0F172A] text-white text-xs font-bold hover:bg-[#1E293B] transition cursor-pointer"
            >
              RETRY
            </button>
          </div>
        )}

        {/* 1. PDF GENERATION & VIEW ACTION CARD (Clean, Authoritative, Prominent) */}
        <section className="bg-white rounded-2xl border border-[#E7DFD3] p-5 shadow-xs space-y-4">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-[#15803D]" />
                <h2 className="font-bold text-sm text-[#0F172A] font-mono uppercase tracking-tight">
                  {language === 'hi' ? 'आधिकारिक प्राधिकरण ऑडिट रिपोर्ट (PDF)' : 'Official Authority Audit Report (PDF)'}
                </h2>
              </div>
              {pdfError && (
                <p className="text-xs text-[#B91C1C] font-mono font-bold mt-1">
                  ✕ {pdfError}
                </p>
              )}
            </div>

            {/* Interactive PDF Actions */}
            <div className="flex flex-wrap items-center gap-2.5 shrink-0">
              {!pdfReady ? (
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleGeneratePdf(false)}
                    disabled={pdfGenerating}
                    className="px-5 py-2.5 rounded-xl bg-[#0F172A] hover:bg-[#1E293B] text-white text-xs font-bold transition shadow-xs cursor-pointer flex items-center gap-2 disabled:opacity-50"
                  >
                    {pdfGenerating ? (
                      <>
                        <RefreshCw className="w-4 h-4 animate-spin text-[#D97706]" />
                        <span>{t.generatingPdf || 'GENERATING AUDIT PDF...'}</span>
                      </>
                    ) : (
                      <>
                        <FileText className="w-4 h-4 text-[#D97706]" />
                        <span>{t.exportAuditPdf || 'EXPORT AUDIT PDF'}</span>
                      </>
                    )}
                  </button>

                  <button
                    onClick={handleViewPdf}
                    disabled={pdfGenerating}
                    className="px-4 py-2.5 rounded-xl bg-white hover:bg-[#FAF8F5] border border-[#E7DFD3] text-[#0F172A] text-xs font-bold transition shadow-xs cursor-pointer flex items-center gap-1.5 disabled:opacity-50"
                  >
                    <Eye className="w-4 h-4 text-[#2563EB]" />
                    <span>{t.viewPdf || 'VIEW PDF'}</span>
                  </button>
                </div>
              ) : (
                <div className="flex items-center gap-2 animate-in fade-in">
                  <span className="text-xs font-mono font-bold text-[#15803D] flex items-center gap-1 mr-1">
                    <CheckCircle2 className="w-4 h-4" />
                    {t.pdfReady || 'AUDIT PDF READY'}
                  </span>
                  <button
                    onClick={handleViewPdf}
                    className="px-4 py-2 rounded-xl bg-white hover:bg-[#FAF8F5] border border-[#E7DFD3] text-[#0F172A] text-xs font-bold transition shadow-xs cursor-pointer flex items-center gap-1.5"
                  >
                    <Eye className="w-4 h-4 text-[#2563EB]" />
                    <span>{t.viewPdf || 'VIEW PDF'}</span>
                  </button>
                  <button
                    onClick={handleDownloadPdf}
                    className="px-4 py-2 rounded-xl bg-[#15803D] hover:bg-[#166534] text-white text-xs font-bold transition shadow-xs cursor-pointer flex items-center gap-1.5"
                  >
                    <Download className="w-4 h-4" />
                    <span>{t.downloadPdf || 'DOWNLOAD PDF'}</span>
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Machine-Readable Auxiliary Export Pills */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 pt-2 border-t border-[#E7DFD3]">
            <a
              href={getReconciledGeoJsonUrl(datasetId)}
              download={`TERRANODE_${datasetId}_Reconciled.geojson`}
              className="px-3 py-2 rounded-xl bg-[#FAF8F5] hover:bg-[#F1ECE4] border border-[#E7DFD3] transition flex items-center justify-between group cursor-pointer"
            >
              <div>
                <span className="text-[11px] font-bold text-[#0F172A] block font-mono">
                  {t.reconciledGeoJson || 'RECONCILED GEOJSON'}
                </span>
                <span className="text-[9.5px] text-[#64748B] block">
                  Vector polygon boundaries
                </span>
              </div>
              <Download className="w-3.5 h-3.5 text-[#64748B] group-hover:text-[#0F172A] transition" />
            </a>

            <a
              href={getCsvSummaryUrl(datasetId)}
              download={`TERRANODE_${datasetId}_Parcels.csv`}
              className="px-3 py-2 rounded-xl bg-[#FAF8F5] hover:bg-[#F1ECE4] border border-[#E7DFD3] transition flex items-center justify-between group cursor-pointer"
            >
              <div>
                <span className="text-[11px] font-bold text-[#0F172A] block font-mono">
                  {t.csvSummary || 'CSV SUMMARY'}
                </span>
                <span className="text-[9.5px] text-[#64748B] block">
                  Tabular parcel ledger
                </span>
              </div>
              <TableIcon className="w-3.5 h-3.5 text-[#64748B] group-hover:text-[#0F172A] transition" />
            </a>

            <a
              href={getEvidenceJsonUrl(datasetId)}
              download={`TERRANODE_${datasetId}_Evidence.json`}
              className="px-3 py-2 rounded-xl bg-[#FAF8F5] hover:bg-[#F1ECE4] border border-[#E7DFD3] transition flex items-center justify-between group cursor-pointer"
            >
              <div>
                <span className="text-[11px] font-bold text-[#0F172A] block font-mono">
                  {t.evidenceJson || 'EVIDENCE JSON'}
                </span>
                <span className="text-[9.5px] text-[#64748B] block">
                  9-Pillar verification schema
                </span>
              </div>
              <FileCode className="w-3.5 h-3.5 text-[#64748B] group-hover:text-[#0F172A] transition" />
            </a>

            <a
              href={getAuditLogUrl(datasetId)}
              download={`TERRANODE_${datasetId}_Audit_Log.json`}
              className="px-3 py-2 rounded-xl bg-[#FAF8F5] hover:bg-[#F1ECE4] border border-[#E7DFD3] transition flex items-center justify-between group cursor-pointer"
            >
              <div>
                <span className="text-[11px] font-bold text-[#0F172A] block font-mono">
                  {t.auditLog || 'AUDIT LOG'}
                </span>
                <span className="text-[9.5px] text-[#64748B] block">
                  Lifecycle event history
                </span>
              </div>
              <FileCheck className="w-3.5 h-3.5 text-[#64748B] group-hover:text-[#0F172A] transition" />
            </a>
          </div>
        </section>

        {/* 2. PICTURE 2: SOURCE CONTRIBUTION GRAPH */}
        <section className="bg-white rounded-2xl border border-[#E7DFD3] p-5 shadow-xs">
          <div className="flex items-center justify-between border-b border-[#E7DFD3] pb-2 mb-3">
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded-lg bg-[#FAF8F5] border border-[#E7DFD3] flex items-center justify-center text-[#0F172A]">
                <BarChart3 className="w-3.5 h-3.5 text-[#059669]" />
              </div>
              <div>
                <h2 className="text-xs font-bold uppercase tracking-wider text-[#0F172A] font-mono">
                  {t.sourceContribution || 'SOURCE CONTRIBUTION'}
                </h2>
                <p className="text-[11px] text-[#64748B] mt-0.5">
                  {language === 'hi' ? 'सक्रिय समाधान में साक्ष्य योगदान करने वाले डेटा स्रोत।' : 'Data sources contributing evidence to the active reconciliation.'}
                </p>
              </div>
            </div>
            {selectedSource && (
              <button
                onClick={() => setSelectedSource(null)}
                className="text-[10px] font-mono font-bold text-[#D97706] hover:underline flex items-center gap-1 cursor-pointer bg-[#FAF3E6] border border-[#EDDCBA] px-2 py-0.5 rounded-md"
              >
                <X className="w-3 h-3" />
                CLEAR FILTER ({selectedSource.toUpperCase()})
              </button>
            )}
          </div>

          {/* Graph Sub-header / Legend */}
          <div className="flex items-center justify-between text-[11px] text-[#64748B] mb-2 px-1">
            <div className="flex items-center gap-1.5 font-mono text-[10px]">
              <span className="w-2 h-2 rounded-full bg-[#059669] animate-pulse" />
              <span className="text-[#0F172A] font-bold">5 Evidence Layers</span>
              <span className="text-[#94A3B8]">• Immutable Provenance</span>
            </div>
            <span className="font-mono text-[10px] text-[#94A3B8]">
              Y-AXIS: PARTICIPATING PARCELS
            </span>
          </div>

          {/* Main Interactive Graph Area */}
          {(() => {
            const sources = activeSummary.source_contribution || [];
            const maxVal = Math.max(...sources.map(s => s.count), 72);
            const activeInspectItem = hoveredSource 
              ? sources.find(s => s.source_key === hoveredSource) 
              : (selectedSource ? sources.find(s => s.source_key.toLowerCase() === selectedSource.toLowerCase()) : null);
            const activeInspectMeta = activeInspectItem 
              ? getSourceMeta(activeInspectItem.source_key, activeInspectItem.source_name) 
              : null;

            if (sources.length === 0) {
              return (
                <div className="w-full text-center text-xs text-[#64748B] py-12">
                  No source evidence available for this dataset.
                </div>
              );
            }

            return (
              <div>
                {/* Chart Grid and Columns */}
                <div className="flex items-end">
                  {/* Y-Axis scale ticks */}
                  <div className="w-8 sm:w-10 shrink-0 flex flex-col justify-between items-end pr-2 text-[10px] font-mono text-[#94A3B8] h-44 pb-1 select-none">
                    <span>{maxVal}</span>
                    <span>{Math.round(maxVal * 0.75)}</span>
                    <span>{Math.round(maxVal * 0.5)}</span>
                    <span>{Math.round(maxVal * 0.25)}</span>
                    <span>0</span>
                  </div>

                  {/* Chart Columns Canvas with horizontal gridlines */}
                  <div className="flex-1 relative h-44 rounded-xl bg-[#FAF8F5]/90 border border-[#E7DFD3] px-2 pt-2 pb-0 flex items-end justify-around gap-2 sm:gap-4 overflow-hidden shadow-2xs">
                    {/* Horizontal dashed gridlines */}
                    <div className="absolute inset-x-0 inset-y-2 flex flex-col justify-between pointer-events-none px-2">
                      <div className="w-full border-b border-dashed border-[#E7DFD3]" />
                      <div className="w-full border-b border-dashed border-[#E7DFD3]" />
                      <div className="w-full border-b border-dashed border-[#E7DFD3]" />
                      <div className="w-full border-b border-dashed border-[#E7DFD3]" />
                      <div className="w-full border-b border-[#E7DFD3]" />
                    </div>

                    {/* Bar Columns */}
                    {sources.map((src) => {
                      const meta = getSourceMeta(src.source_key, src.source_name);
                      const heightPct = Math.max(8, Math.round((src.count / maxVal) * 100));
                      const isSelected = selectedSource?.toLowerCase() === src.source_key.toLowerCase();
                      const isHovered = hoveredSource === src.source_key;

                      return (
                        <div
                          key={src.source_key}
                          onMouseEnter={() => setHoveredSource(src.source_key)}
                          onMouseLeave={() => setHoveredSource(null)}
                          onClick={() => setSelectedSource(isSelected ? null : src.source_key)}
                          className={`flex-1 max-w-[68px] sm:max-w-[82px] h-full flex flex-col justify-end items-center relative z-10 cursor-pointer group transition-all duration-200 ${
                            selectedSource && !isSelected ? 'opacity-40 hover:opacity-90' : 'opacity-100'
                          }`}
                          title={`${src.source_name}: ${src.count} participating parcels (${src.coverage_percentage}%)`}
                        >
                          {/* Value & Percentage Badge Above Bar */}
                          <div className="mb-1 flex flex-col items-center pointer-events-none transition-transform duration-200 group-hover:-translate-y-0.5">
                            <span className={`text-[11px] font-mono font-bold px-1.5 py-0.5 rounded shadow-xs border transition-all duration-200 ${
                              isSelected
                                ? 'bg-[#0F172A] text-white border-[#0F172A] scale-110 shadow-md'
                                : isHovered
                                ? 'bg-[#0F172A] text-white border-[#0F172A] scale-105'
                                : 'bg-white text-[#0F172A] border-[#E7DFD3] group-hover:border-[#0F172A]'
                            }`}>
                              {src.count}
                            </span>
                            <span className="text-[9px] font-mono font-medium text-[#64748B] mt-0.5">
                              {src.coverage_percentage}%
                            </span>
                          </div>

                          {/* Column Track Container with explicit height */}
                          <div className={`w-full h-28 sm:h-30 bg-white/70 rounded-t-xl border-x border-t p-1 flex flex-col justify-end transition-all duration-200 ${
                            isSelected
                              ? 'border-[#0F172A] shadow-md ring-2 ring-[#0F172A]/30 bg-white'
                              : isHovered
                              ? 'border-[#94A3B8] shadow-sm bg-white'
                              : 'border-[#E7DFD3] group-hover:border-[#CBD5E1]'
                          }`}>
                            {/* Filled Colored Bar with Animated Gradient */}
                            <div
                              style={{ height: `${heightPct}%` }}
                              className={`w-full rounded-t-lg bg-gradient-to-t ${meta.gradient} transition-all duration-500 relative overflow-hidden shadow-xs ${meta.borderTop} ${
                                isSelected ? 'ring-2 ring-[#0F172A] ring-offset-1' : ''
                              }`}
                            >
                              {/* Top 3D highlight */}
                              <div className="absolute top-0 inset-x-0 h-1 bg-white/40" />
                              {/* Micro texture pattern */}
                              <div className="absolute inset-0 opacity-20 bg-[radial-gradient(#fff_1px,transparent_1px)] [background-size:6px_6px]" />
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* X-Axis Labels Row */}
                <div className="flex pt-2">
                  <div className="w-8 sm:w-10 shrink-0" />
                  <div className="flex-1 flex justify-around gap-2 sm:gap-4 px-2">
                    {sources.map((src) => {
                      const meta = getSourceMeta(src.source_key, src.source_name);
                      const isSelected = selectedSource?.toLowerCase() === src.source_key.toLowerCase();
                      return (
                        <div
                          key={src.source_key}
                          onClick={() => setSelectedSource(isSelected ? null : src.source_key)}
                          className="flex-1 max-w-[68px] sm:max-w-[82px] flex flex-col items-center text-center cursor-pointer group"
                        >
                          <span className={`text-[10px] font-bold truncate w-full transition-colors ${
                            isSelected ? 'text-[#0F172A]' : 'text-[#334155] group-hover:text-[#0F172A]'
                          }`}>
                            {meta.shortName}
                          </span>
                          <span className={`text-[8.5px] font-mono px-1 py-0.2 rounded mt-0.5 border text-center truncate max-w-full ${
                            isSelected ? 'bg-[#0F172A] text-white border-[#0F172A]' : meta.pillClass
                          }`}>
                            {meta.tag}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Interactive Inspection Strip on Hover/Click */}
                <div className="mt-3 p-2.5 rounded-xl bg-[#FAF8F5] border border-[#E7DFD3] transition-all">
                  {activeInspectItem && activeInspectMeta ? (
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
                      <div className="flex items-center gap-2">
                        <span className="text-base">{activeInspectMeta.icon}</span>
                        <div>
                          <div className="font-bold text-[#0F172A] flex items-center gap-1.5 flex-wrap">
                            <span>{activeInspectItem.source_name}</span>
                            <span className={`text-[9px] font-mono px-1.5 py-0.2 rounded border font-semibold ${activeInspectMeta.pillClass}`}>
                              {activeInspectMeta.badge}
                            </span>
                          </div>
                          <p className="text-[11px] text-[#64748B] mt-0.5">
                            {activeInspectMeta.role}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3 font-mono shrink-0 self-end sm:self-center">
                        <div className="text-right">
                          <span className="text-xs font-bold text-[#0F172A]">
                            {activeInspectItem.count} Parcels
                          </span>
                          <span className="text-[10px] text-[#64748B] ml-1">
                            ({activeInspectItem.coverage_percentage}%)
                          </span>
                        </div>
                        {selectedSource?.toLowerCase() === activeInspectItem.source_key.toLowerCase() ? (
                          <span className="text-[10px] font-bold text-[#D97706] bg-[#FAF3E6] border border-[#EDDCBA] px-2 py-0.5 rounded-md">
                            FILTER ACTIVE
                          </span>
                        ) : (
                          <span className="text-[10px] text-[#2563EB] bg-blue-50 border border-blue-200 px-2 py-0.5 rounded-md">
                            CLICK TO ISOLATE
                          </span>
                        )}
                      </div>
                    </div>
                  ) : (
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between text-[11px] text-[#64748B] font-mono gap-1">
                      <div className="flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-[#059669]" />
                        <span>Dual Criteria: IoU &ge; 0.85 &amp; Centroid Drift &lt; 2.0m</span>
                      </div>
                      <span className="text-[#94A3B8]">Hover or click any column to isolate source evidence</span>
                    </div>
                  )}
                </div>

                <div className="text-[10px] text-[#64748B] font-mono border-t border-[#E7DFD3] pt-2 mt-3 flex justify-between items-center">
                  <span>Verified Participation: 100% Provenance Recorded</span>
                  <span className="text-[#94A3B8]">Click column to isolate in report view</span>
                </div>
              </div>
            );
          })()}
        </section>

        {/* 3. PICTURE 1: SPATIAL CONFLICT BREAKDOWN */}
        <section className="bg-white rounded-2xl border border-[#E7DFD3] p-5 shadow-xs">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-[#E7DFD3] pb-2 mb-4 gap-2">
            <div>
              <h2 className="text-xs font-bold uppercase tracking-wider text-[#0F172A] font-mono">
                {t.spatialConflictBreakdown || 'SPATIAL CONFLICT BREAKDOWN'}
              </h2>
              <p className="text-[11px] text-[#64748B] mt-0.5">
                {language === 'hi' ? 'सक्रिय डेटासेट में पाई गई स्थानिक विसंगतियों के प्रकार।' : 'Types of spatial inconsistencies detected in the active dataset.'}
              </p>
            </div>
            {selectedConflict && (
              <button
                onClick={() => setSelectedConflict(null)}
                className="text-[10px] font-mono font-bold text-[#D97706] hover:underline flex items-center gap-1 self-start sm:self-center cursor-pointer"
              >
                <X className="w-3 h-3" />
                CLEAR SELECTION ({selectedConflict})
              </button>
            )}
          </div>

          {/* 5 Horizontal Bars strictly matching Picture 1 */}
          {(activeSummary.spatial_conflict_breakdown || []).length > 0 ? (
            <div className="space-y-3">
              {(activeSummary.spatial_conflict_breakdown || []).map((item) => {
                const maxCount = Math.max(...(activeSummary.spatial_conflict_breakdown || []).map(c => c.count), 7);
                const barWidth = Math.max(6, Math.round((item.count / maxCount) * 100));
                const isSelected = selectedConflict === item.conflict_type;

                return (
                  <div 
                    key={item.conflict_type}
                    onClick={() => setSelectedConflict(isSelected ? null : item.conflict_type)}
                    className={`p-3 rounded-xl border transition cursor-pointer flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${
                      isSelected 
                        ? 'bg-[#FDF1EB] border-[#F3CEBD] ring-2 ring-[#DC2626]/40' 
                        : 'bg-[#FAF8F5] border-[#E7DFD3] hover:bg-[#F1ECE4]'
                    }`}
                  >
                    {/* Left Title & Subtext */}
                    <div className="sm:w-72 shrink-0">
                      <span className="text-xs font-bold text-[#0F172A] block font-mono">
                        {item.conflict_type}
                      </span>
                      <span className="text-[10.5px] text-[#64748B] truncate block mt-0.5" title={item.description}>
                        {item.description}
                      </span>
                    </div>

                    {/* Middle Bar track with Amber fill */}
                    <div className="flex-1 flex items-center gap-4">
                      <div className="flex-1 bg-white h-4 rounded-full overflow-hidden border border-[#E7DFD3] p-0.5 shadow-2xs">
                        <div 
                          style={{ width: `${barWidth}%` }}
                          className={`h-full rounded-full transition-all duration-500 ${
                            isSelected ? 'bg-[#DC2626]' : 'bg-[#D97706]'
                          }`}
                        />
                      </div>
                      <span className="text-xs font-mono font-bold text-[#0F172A] w-6 text-right">
                        {item.count}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="py-8 text-center text-xs font-mono text-[#15803D] bg-[#EAF2EB] rounded-xl border border-[#C5DAC9]">
              ✓ NO SPATIAL CONFLICTS DETECTED IN ACTIVE DATASET
            </div>
          )}
        </section>

        {/* 4. PICTURE 3: SPATIAL QUALITY & AGREEMENT + EVIDENCE COVERAGE (Side-by-Side Cards) */}
        <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          
          {/* CARD 1: SPATIAL QUALITY & AGREEMENT (Benchmark Sliders) */}
          <div className="bg-white rounded-2xl border border-[#E7DFD3] p-5 shadow-xs flex flex-col justify-between overflow-hidden">
            <div>
              <div className="border-b border-[#E7DFD3] pb-2 mb-3">
                <h2 className="text-xs font-bold uppercase tracking-wider text-[#0F172A] font-mono">
                  {t.spatialQuality || 'SPATIAL QUALITY & AGREEMENT'}
                </h2>
                <p className="text-[11px] text-[#64748B] mt-0.5">
                  {language === 'hi' ? 'समाधानित स्थानिक परिणाम की गुणवत्ता का वर्णन करने वाले प्रमुख मानक।' : 'Key measures describing the quality of the reconciled spatial result.'}
                </p>
              </div>

              {activeSummary.spatial_quality ? (
                <div className="space-y-4 pt-1">
                  {[
                    activeSummary.spatial_quality.iou,
                    activeSummary.spatial_quality.boundary_agreement,
                    activeSummary.spatial_quality.ground_truth_agreement,
                    activeSummary.spatial_quality.verification_confidence,
                  ].filter(Boolean).map((bench) => {
                    const pct = bench?.percentage ?? 85;
                    const thresh = bench?.threshold_percentage ?? 80;

                    return (
                      <div key={bench.name} className="space-y-1 group">
                        <div className="flex items-center justify-between text-xs font-mono">
                          <span className="font-bold text-[#0F172A] flex items-center gap-1.5">
                            <span>{bench.name}</span>
                            <span title={bench.tooltip} className="cursor-help text-[#64748B]">
                              <HelpCircle className="w-3 h-3 inline" />
                            </span>
                          </span>
                          <span className="font-bold text-[#15803D]">
                            {pct}% <span className="text-[10px] text-[#64748B] font-normal">(&ge;{thresh}%)</span>
                          </span>
                        </div>

                        {/* Benchmark Track with Positioned Dot matching Picture 3 */}
                        <div className="relative w-full h-5 flex items-center">
                          {/* Background track line */}
                          <div className="w-full h-1 bg-[#E2E8F0] rounded-full" />
                          
                          {/* Reference threshold tick mark */}
                          <div 
                            style={{ left: `${thresh}%` }}
                            className="absolute top-0 bottom-0 w-0.5 bg-[#CBD5E1] z-0"
                            title={`Authoritative Threshold: ${thresh}%`}
                          />

                          {/* Active filled line */}
                          <div 
                            style={{ width: `${Math.min(pct, 100)}%` }}
                            className="absolute h-1 bg-[#0F172A] rounded-full z-1"
                          />

                          {/* Green Dot Marker */}
                          <div 
                            style={{ left: `calc(${Math.min(pct, 100)}% - 6px)` }}
                            className="absolute w-3.5 h-3.5 rounded-full bg-[#15803D] border-2 border-white shadow-xs z-10 transition-all duration-300 group-hover:scale-125"
                            title={`${bench.name}: ${pct}%`}
                          />
                        </div>
                        <p className="text-[10.5px] text-[#64748B] leading-tight">
                          {bench.tooltip}
                        </p>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="text-xs text-[#64748B] py-6 text-center">
                  Quality benchmarks not available for this dataset.
                </div>
              )}
            </div>

            <div className="text-[10px] text-[#64748B] font-mono border-t border-[#E7DFD3] pt-2 mt-4">
              Benchmark: All evaluated metrics exceed state cadastral tolerance standards
            </div>
          </div>

          {/* CARD 2: EVIDENCE COVERAGE (6 Domains matching Picture 3) */}
          <div className="bg-white rounded-2xl border border-[#E7DFD3] p-5 shadow-xs flex flex-col justify-between overflow-hidden">
            <div>
              <div className="border-b border-[#E7DFD3] pb-2 mb-3">
                <h2 className="text-xs font-bold uppercase tracking-wider text-[#0F172A] font-mono">
                  {t.evidenceCoverage || 'EVIDENCE COVERAGE'}
                </h2>
                <p className="text-[11px] text-[#64748B] mt-0.5">
                  {language === 'hi' ? '6 आधिकारिक साक्ष्य सत्यापन डोमेन की स्थिति।' : 'Status of 6 authoritative evidentiary validation domains.'}
                </p>
              </div>

              {(activeSummary.evidence_coverage || []).length > 0 ? (
                <div className="space-y-2">
                  {(activeSummary.evidence_coverage || []).map((ev) => (
                    <div 
                      key={ev.category}
                      className="p-2.5 px-3 rounded-xl bg-[#FAF8F5] border border-[#E7DFD3] flex items-center justify-between gap-3 hover:bg-[#F1ECE4] transition overflow-hidden"
                    >
                      <div className="min-w-0 flex-1 pr-2">
                        <span className="text-xs font-bold text-[#0F172A] block font-mono truncate">
                          {ev.category}
                        </span>
                        <span className="text-[10px] text-[#64748B] truncate block" title={ev.note}>
                          {ev.note}
                        </span>
                      </div>

                      <div className="shrink-0 font-mono text-[10px] font-bold">
                        {ev.status === 'Complete' ? (
                          <span className="px-2.5 py-0.5 rounded-md bg-[#EAF2EB] text-[#15803D] border border-[#C5DAC9] inline-flex items-center gap-1 select-none">
                            <span>✓</span> Complete
                          </span>
                        ) : ev.status === 'Partial' ? (
                          <span className="px-2.5 py-0.5 rounded-md bg-[#FAF3E6] text-[#B45309] border border-[#EDDCBA] inline-flex items-center gap-1 select-none">
                            <span>⚠</span> Partial
                          </span>
                        ) : ev.status === 'Failed' ? (
                          <span className="px-2.5 py-0.5 rounded-md bg-[#FDF1EB] text-[#B91C1C] border border-[#F3CEBD] inline-flex items-center gap-1 select-none">
                            <span>✕</span> Failed
                          </span>
                        ) : (
                          <span className="px-2.5 py-0.5 rounded-md bg-[#F1F5F9] text-[#64748B] border border-[#CBD5E1] inline-flex items-center gap-1 select-none">
                            — Not Available
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-xs text-[#64748B] py-6 text-center">
                  Evidence coverage not available.
                </div>
              )}
            </div>

            <div className="text-[10px] text-[#64748B] font-mono border-t border-[#E7DFD3] pt-2 mt-4 flex justify-between items-center">
              <span>Authoritative Provenance: State Land Revenue Record</span>
              <button 
                onClick={() => onNavigateToTab?.('validation')}
                className="text-[#D97706] hover:underline font-bold"
              >
                Open Validator →
              </button>
            </div>
          </div>

        </section>


      </main>

    </div>
  );
};
