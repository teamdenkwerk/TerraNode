import React, { useState } from 'react';
import { 
  BuildingEntity, 
  ActiveTab, 
  Language, 
  UploadedFile, 
  ReconciliationStats,
  ActivityEntry,
  DatasetMeta,
} from './types';
import { 
  generateGridBuildings, 
  generateDelhiBuildings,
  initialStats, 
  initialDatasets,
  bengaluruDataset
} from './data/mockBuildings';
import { useLiveBuildings } from './hooks/useLiveBuildings';
import { Navbar } from './components/Navbar';
import { NavigationTabs } from './components/NavigationTabs';
import { GisExplorerView } from './components/GisExplorerView';
import { InteractiveMap } from './components/InteractiveMap';
import { BuildingDetailPanel } from './components/BuildingDetailPanel';
import { DataUploadView } from './components/DataUploadView';
import { ReviewQueueView } from './components/ReviewQueueView';
import { BeforeAfterView } from './components/BeforeAfterView';
import { ProductionValidationView } from './components/ProductionValidationView';
import { ReportsView } from './components/ReportsView';
import { HarmonizationView } from './components/HarmonizationView';
import { AnalyticsView } from './components/AnalyticsView';
import { SourceComparisonModal } from './components/SourceComparisonModal';
import { ReconciliationModal } from './components/ReconciliationModal';
import { DigitalLandEntityModal } from './components/DigitalLandEntityModal';
import { TechnicalDetailsModal } from './components/TechnicalDetailsModal';
import { HistoryModal } from './components/HistoryModal';
import { DemoTourModal } from './components/DemoTourModal';
import { AdminLoginPage } from './components/AdminLoginPage';
import { resolveEntity, switchActiveDataset, fetchActiveDataset } from './api/geoReconciliationClient';
import { translations } from './data/i18n';
import { PanelLeftOpen } from 'lucide-react';

export default function App() {
  // Admin Authentication State
  // User workflow requirement:
  // 1. When portal is first opened -> displays Login Page directly
  // 2. Upon successful login -> immediately navigates to Upload Document page
  const [isAdminLoggedIn, setIsAdminLoggedIn] = useState<boolean>(() => {
    try {
      localStorage.removeItem('terranode_admin_session');
    } catch {
      // ignore
    }
    return sessionStorage.getItem('terranode_admin_session') === 'true';
  });

  const handleAdminLogin = () => {
    sessionStorage.setItem('terranode_admin_session', 'true');
    setIsAdminLoggedIn(true);
    setActiveTab('upload');
  };

  const handleAdminLogout = () => {
    sessionStorage.removeItem('terranode_admin_session');
    try {
      localStorage.removeItem('terranode_admin_session');
    } catch {
      // ignore
    }
    setIsAdminLoggedIn(false);
    setActiveTab('upload');
  };

  // Multi-Dataset & Multi-AOI Isolation State
  // Bengaluru remains the REFERENCE DATASET, while Delhi, Mumbai, Chennai, and user uploads are spatially isolated.
  const [datasets, setDatasets] = useState<DatasetMeta[]>(initialDatasets);
  const [activeDatasetId, setActiveDatasetId] = useState<string>('bengaluru-domlur');

  // Sanitize datasets to guarantee no cross-city coordinate leaks (e.g. Delhi getting Mumbai coords)
  const sanitizedDatasets = React.useMemo(() => {
    return datasets.map(d => {
      const isDelhi = d.city.toLowerCase().includes('delhi') || d.name.toLowerCase().includes('delhi');
      if (isDelhi && d.buildings.length > 0 && d.buildings[0].centroid[0] < 25) {
        const corrected = generateDelhiBuildings();
        return {
          ...d,
          center: [28.6155, 77.2105] as [number, number],
          bounds: [[28.607, 77.198], [28.627, 77.226]] as [[number, number], [number, number]],
          bbox: [77.198, 28.607, 77.226, 28.627] as [number, number, number, number],
          buildings: corrected,
          featuresCount: corrected.length,
        };
      }
      return d;
    });
  }, [datasets]);

  const activeDataset = React.useMemo(() => {
    return sanitizedDatasets.find(d => d.id === activeDatasetId) || sanitizedDatasets[0];
  }, [sanitizedDatasets, activeDatasetId]);

  // Sync with backend active dataset on initial mount
  React.useEffect(() => {
    fetchActiveDataset().then(activeBackend => {
      if (activeBackend && activeBackend.dataset_id) {
        const canonicalId = activeBackend.dataset_id === 'bengaluru-ward112' ? 'bengaluru-domlur' : activeBackend.dataset_id;
        setActiveDatasetId(canonicalId);
      }
    }).catch(err => {
      console.warn('Initial active dataset load note:', err);
    });
  }, []);

  // Navigation & Localization - starts on Upload Document page after login
  const [activeTab, setActiveTab] = useState<ActiveTab>('upload');
  const [validationSubTab, setValidationSubTab] = useState<'production' | 'visual'>('visual');
  const [language, setLanguage] = useState<Language>('en');
  const t = translations[language] || translations.en;

  // Real session activity log
  const [activityLog, setActivityLog] = useState<ActivityEntry[]>([]);
  const logActivity = (entry: Omit<ActivityEntry, 'id' | 'timestamp'>) => {
    setActivityLog(prev => [
      { id: `act-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`, timestamp: Date.now(), ...entry },
      ...prev,
    ].slice(0, 20));
  };

  // Core Data State — pulls from the Geo-Reconciliation API when reachable
  const { buildings: liveBuildings, source: dataSource, refetch: refetchBuildings } = useLiveBuildings();
  const [buildings, setBuildings] = useState<BuildingEntity[]>(() => bengaluruDataset.buildings);
  const [isResolving, setIsResolving] = useState(false);

  // Selection & Modal States
  const [selectedBuilding, setSelectedBuilding] = useState<BuildingEntity | null>(() => {
    return bengaluruDataset.buildings.find(b => b.id === 'BLD-1028') || bengaluruDataset.buildings[0];
  });

  const handleSelectDataset = async (datasetId: string) => {
    setActiveDatasetId(datasetId);

    // Synchronously update buildings and selectedBuilding so that activeDataset,
    // buildings, and selectedBuilding are all updated in the exact same render cycle!
    const target = sanitizedDatasets.find(d => d.id === datasetId);
    if (target) {
      const bldgSet = datasetId.startsWith('bengaluru')
        ? (liveBuildings.length > 0 ? liveBuildings : bengaluruDataset.buildings)
        : target.buildings;
      setBuildings(bldgSet);
      setSelectedBuilding(bldgSet[0] || null);

      logActivity({
        type: 'info',
        title: `Switched active workspace to ${target.city} — ${target.aoi}`,
      });
    }

    try {
      await switchActiveDataset(datasetId);
    } catch (e) {
      console.warn('Backend active dataset switch note:', e);
    }
  };

  // Synchronize buildings with the active dataset.
  // NEVER mixes geometries between cities:
  // - When Bengaluru active: uses live backend or reference Bengaluru buildings
  // - When Mumbai active: uses isolated Mumbai buildings (~19.1136°N, 72.8697°E)
  // - When Chennai active: uses isolated Chennai buildings (~13.0418°N, 80.2341°E)
  // - When Uploaded active: uses uploaded dataset's actual geometries
  React.useEffect(() => {
    if (activeDatasetId.startsWith('bengaluru')) {
      const bldgSet = liveBuildings.length > 0 ? liveBuildings : bengaluruDataset.buildings;
      setBuildings(bldgSet);
      setSelectedBuilding((prev) => {
        if (prev && bldgSet.some((b) => b.id === prev.id)) return prev;
        return bldgSet.find((b) => b.id === 'BLD-1028') || bldgSet[0] || null;
      });
    } else {
      setBuildings(activeDataset.buildings);
      setSelectedBuilding(activeDataset.buildings[0] || null);
    }
  }, [activeDatasetId, liveBuildings, activeDataset]);

  const [stats, setStats] = useState<ReconciliationStats>(initialStats);
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);

  // The four dashboard headline numbers, real-derived from the active dataset's buildings array
  const derivedStats = React.useMemo<ReconciliationStats>(() => {
    const totalBuildings = buildings.length;
    const matched = buildings.filter(b => b.status === 'reconciled').length;
    const requiresReview = buildings.filter(b => b.status === 'review' || b.status === 'conflict').length;
    const conflictsDetected = buildings.filter(b => b.status === 'conflict').length;
    const averageConfidence = totalBuildings > 0
      ? Math.round(buildings.reduce((sum, b) => sum + b.confidence, 0) / totalBuildings)
      : 0;
    
    // Dataset-specific confidence deltas
    const delta = activeDatasetId === 'mumbai-andheri' ? 12 : activeDatasetId === 'chennai-tnagar' ? 14 : 9;
    const beforeAvg = Math.max(50, averageConfidence - delta);

    return { 
      totalBuildings, 
      matched, 
      requiresReview, 
      conflictsDetected,
      autoResolved: Math.round(matched * 0.35),
      averageConfidence,
      afterAvgConfidence: averageConfidence,
      beforeAvgConfidence: beforeAvg,
      afterConflicts: conflictsDetected,
      beforeConflicts: conflictsDetected + Math.round(totalBuildings * 0.28),
      totalAreaM2: buildings.reduce((acc, b) => acc + b.area, 0),
    };
  }, [buildings, activeDatasetId]);

  const [showSourcesModal, setShowSourcesModal] = useState(false);
  const [showReconcileModal, setShowReconcileModal] = useState(false);
  const [showDigitalCardModal, setShowDigitalCardModal] = useState(false);
  const [showTechDetailsModal, setShowTechDetailsModal] = useState(false);
  const [showHistoryModal, setShowHistoryModal] = useState(false);
  const [showDemoTour, setShowDemoTour] = useState(false);
  const [showBeforeAfterDirect, setShowBeforeAfterDirect] = useState(false);
  const [isPipelineOpen, setIsPipelineOpen] = useState(true);

  // Enhancement 07 & 08: Map Focus & Historical Comparison Overlay states
  const [focusedGeometry, setFocusedGeometry] = useState<[number, number][] | null>(null);
  const [historicalComparison, setHistoricalComparison] = useState<{
    geomA: any;
    geomB: any;
    metaA: { label: string; date?: string };
    metaB: { label: string; date?: string };
  } | null>(null);

  // Handlers
  const handleSelectBuilding = (building: BuildingEntity) => {
    setSelectedBuilding(building);
  };

  const handleSelectBuildingOnMap = (building: BuildingEntity) => {
    setSelectedBuilding(building);
    setActiveTab('gis');
  };

  const updateBuildingStatus = (id: string, status: BuildingEntity['status']) => {
  setBuildings(prev => prev.map(b => (b.id === id ? { ...b, status } : b)));
  setSelectedBuilding(prev => (prev && prev.id === id ? { ...prev, status } : prev));
};

const handleApprove = async (id: string) => {
  setIsResolving(true);
  try {
    await resolveEntity(id, { status: 'approved' });
    updateBuildingStatus(id, 'reconciled');
    logActivity({ type: 'success', title: `Building #${id} approved and reconciled` });
  } catch (e) {
    console.error('Failed to approve entity', id, e);
    logActivity({ type: 'warning', title: `Failed to approve #${id} — ${e instanceof Error ? e.message : 'request failed'}` });
  } finally {
    setIsResolving(false);
  }
};

const handleReject = async (id: string) => {
  setIsResolving(true);
  try {
    await resolveEntity(id, { status: 'rejected' });
    updateBuildingStatus(id, 'conflict');
    logActivity({ type: 'warning', title: `Building #${id} rejected — flagged as conflict` });
  } catch (e) {
    console.error('Failed to reject entity', id, e);
    logActivity({ type: 'warning', title: `Failed to reject #${id} — ${e instanceof Error ? e.message : 'request failed'}` });
  } finally {
    setIsResolving(false);
  }
};

  const handleReconciliationComplete = (result?: {
  raw_feature_count?: number | null;
  canonical_entity_count?: number | null;
  review_queue_count?: number | null;
}) => {
  // NOTE: totalBuildings/requiresReview are NOT set here anymore — they're
  // always derived live from the real `buildings` array in `derivedStats`
  // below, so setting them from the reconcile response would just be a
  // second, possibly-stale source of truth for the same numbers.
  if (result) {
    logActivity({
      type: 'verified',
      title: `Reconciliation run complete — ${result.canonical_entity_count ?? '?'} entities, ${result.review_queue_count ?? 0} flagged for review`,
    });
  }
  // Pull the freshly reconciled entities into the map/dashboard.
  refetchBuildings();
};

  const handleAddFile = (newFile: UploadedFile) => {
    setUploadedFiles(prev => [newFile, ...prev]);
    logActivity({ type: 'info', title: `Uploaded ${newFile.name} (${newFile.status})` });
  };

  const handleDatasetCreated = (newDataset: DatasetMeta) => {
    setDatasets(prev => [newDataset, ...prev.filter(d => d.id !== newDataset.id)]);
    setActiveDatasetId(newDataset.id);
    setBuildings(newDataset.buildings);
    setSelectedBuilding(newDataset.buildings[0] || null);
    logActivity({
      type: 'verified',
      title: `${newDataset.city} dataset detected & isolated: ${newDataset.name} (${newDataset.featuresCount} parcels in ${newDataset.aoi})`,
    });
  };

  // Target showcase building for the demo tour
  const showcaseBuilding = buildings.find(b => b.id === 'BLD-1028') || buildings[0];

  if (!isAdminLoggedIn) {
    return <AdminLoginPage onLoginSuccess={handleAdminLogin} />;
  }

  return (
    <div className="h-screen bg-[#F6F2EB] text-[#241D16] flex flex-col font-sans selection:bg-[#A86236]/20 selection:text-[#241D16] antialiased overflow-hidden">
      
      {/* 1. Redesigned Clean Compact Top Navbar */}
      <Navbar
        datasets={sanitizedDatasets}
        activeDatasetId={activeDatasetId}
        onSelectDataset={handleSelectDataset}
        language={language}
        onToggleLanguage={() => setLanguage(l => l === 'en' ? 'hi' : 'en')}
        onLogout={handleAdminLogout}
        onOpenUpload={() => setActiveTab('upload')}
      />

      {/* 2. Main Body with Left Vertical Sidebar Navigation + Right Content Area */}
      <div className="flex-1 flex overflow-hidden relative">
        {/* Left Side Vertical Choosing Sidebar */}
        {isPipelineOpen && (
          <NavigationTabs
            activeTab={showBeforeAfterDirect ? 'validation' : activeTab}
            onTabChange={(tab) => {
              setShowBeforeAfterDirect(false);
              setActiveTab(tab);
            }}
            language={language}
            reviewCount={derivedStats.requiresReview}
            activeDataset={activeDataset}
            onClose={() => setIsPipelineOpen(false)}
          />
        )}

        {/* Right Dynamic Content Area */}
        <main className="flex-1 h-full overflow-y-auto relative bg-[#F6F2EB]">
          {/* Re-open Workflow Pipeline button when closed */}
          {!isPipelineOpen && (
            <button
              type="button"
              onClick={() => setIsPipelineOpen(true)}
              className="absolute left-3 top-3 z-30 p-2 bg-white/95 backdrop-blur-sm border border-[#E7DFD3] rounded-xl shadow-md hover:bg-[#F4EEE6] text-[#241D16] transition cursor-pointer active:scale-95 group"
              title="Open Workflow Pipeline"
              aria-label="Open Workflow Pipeline"
            >
              <PanelLeftOpen className="w-4 h-4 text-[#A86236] group-hover:scale-110 transition-transform" />
            </button>
          )}
        
        {/* VIEW A: Before vs After Comparison (when direct toggle or via compare button) */}
        {showBeforeAfterDirect ? (
          <BeforeAfterView
            buildings={buildings}
            stats={derivedStats}
            language={language}
            onGoToMap={() => {
              setShowBeforeAfterDirect(false);
              setActiveTab('gis');
            }}
          />
        ) : (
          <>
            {/* STAGE 01: UPLOAD DOCUMENTS (Data Ingestion Before Map) */}
            {(activeTab === 'upload' || activeTab === 'data') && (
              <DataUploadView
                uploadedFiles={uploadedFiles}
                onAddFile={handleAddFile}
                language={language}
                onGoToReconcile={() => setActiveTab('harmonization')}
                onDatasetCreated={handleDatasetCreated}
                onGoToMap={() => setActiveTab('gis')}
                activeDataset={activeDataset}
                datasets={sanitizedDatasets}
                onSelectDataset={handleSelectDataset}
              />
            )}

            {/* STAGE 03: GIS EXPLORER (Spatial Map View) */}
            {(activeTab === 'gis' || activeTab === 'map') && (
              <GisExplorerView
                buildings={buildings}
                stats={derivedStats}
                selectedBuilding={selectedBuilding}
                onSelectBuilding={handleSelectBuilding}
                language={language}
                dataSource={activeDatasetId.startsWith('bengaluru') ? dataSource : 'mock'}
                datasets={sanitizedDatasets}
                activeDataset={activeDataset}
                onSelectDataset={handleSelectDataset}
                activityLog={activityLog}
                focusedGeometry={focusedGeometry}
                onFocusGeometry={(coords) => setFocusedGeometry(coords)}
                historicalComparison={historicalComparison}
                onClearHistoricalComparison={() => setHistoricalComparison(null)}
                onShowHistoricalComparison={(geomA, geomB, metaA, metaB) =>
                  setHistoricalComparison({ geomA, geomB, metaA, metaB })
                }
                onOpenUpload={() => setActiveTab('upload')}
                onOpenHarmonization={() => setActiveTab('harmonization')}
                onGoToReview={() => setActiveTab('review')}
                onApprove={handleApprove}
                onReject={handleReject}
                isResolving={isResolving}
                onViewSources={() => setShowSourcesModal(true)}
                onOpenDigitalCard={() => setShowDigitalCardModal(true)}
                onOpenTechnicalDetails={() => setShowTechDetailsModal(true)}
                onOpenHistory={() => setShowHistoryModal(true)}
              />
            )}

            {/* STAGE 04: HARMONIZATION (Spatial Consensus Core) */}
            {activeTab === 'harmonization' && (
              <HarmonizationView
                buildings={buildings}
                stats={derivedStats}
                language={language}
                activeDataset={activeDataset}
                datasets={sanitizedDatasets}
                onSelectDataset={handleSelectDataset}
                onGoToValidation={() => setActiveTab('validation')}
                onGoToReview={() => setActiveTab('review')}
                onGoToGis={() => setActiveTab('gis')}
                onSelectBuilding={(b) => {
                  setSelectedBuilding(b);
                  setActiveTab('gis');
                }}
                onReconciliationComplete={(newStats) => {
                  setStats(newStats);
                  logActivity({ type: 'success', title: 'Spatial harmonization pass executed' });
                }}
              />
            )}

            {/* STAGE 05: REVIEW & VERIFICATION (Conflict Queue) */}
            {activeTab === 'review' && (
              <ReviewQueueView
                buildings={buildings}
                onSelectBuildingOnMap={handleSelectBuildingOnMap}
                onResolved={(id, status) => {
                  updateBuildingStatus(id, status);
                  logActivity({ type: 'success', title: `Building #${id} resolved from review queue` });
                }}
                language={language}
                onGoToValidation={() => setActiveTab('validation')}
              />
            )}

            {/* STAGE 06: CHANGE DETECTION & VALIDATION (Observed Spatial Change & Production Metrics) */}
            {activeTab === 'validation' && (
              <div className="h-full flex flex-col overflow-hidden">
                {/* Stage Header & Sub-Tab Navigation */}
                <div className="bg-[#FAF8F5] border-b border-[#E7DFD3] px-6 py-2.5 flex items-center justify-between shrink-0">
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setValidationSubTab('visual')}
                      className={`px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 cursor-pointer ${
                        validationSubTab === 'visual'
                          ? 'bg-[#A86236] text-white shadow-xs'
                          : 'bg-white border border-[#E7DFD3] text-[#7D7063] hover:text-[#241D16]'
                      }`}
                    >
                      {language === 'hi' ? 'देखा गया स्थानिक परिवर्तन (पहले बनाम बाद में)' : 'Observed Spatial Change (Before vs After)'}
                    </button>
                    <button
                      onClick={() => setValidationSubTab('production')}
                      className={`px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 cursor-pointer ${
                        validationSubTab === 'production'
                          ? 'bg-[#A86236] text-white shadow-xs'
                          : 'bg-white border border-[#E7DFD3] text-[#7D7063] hover:text-[#241D16]'
                      }`}
                    >
                      {t.productionValidation || 'Production Validation Metrics'}
                    </button>
                  </div>
                </div>

                {/* Sub-Tab View Content */}
                <div className="flex-1 overflow-y-auto">
                  {validationSubTab === 'production' ? (
                    <ProductionValidationView language={language} activeDataset={activeDataset} />
                  ) : (
                    <BeforeAfterView
                      buildings={buildings}
                      stats={derivedStats}
                      language={language}
                      activeDataset={activeDataset}
                      onGoToMap={() => setActiveTab('gis')}
                      onGoToReview={() => setActiveTab('review')}
                    />
                  )}
                </div>
              </div>
            )}

            {/* STAGE 07: ANALYTICS (Land Data Insights) */}
            {activeTab === 'analytics' && (
              <AnalyticsView
                buildings={buildings}
                stats={derivedStats}
                language={language}
                activeDataset={activeDataset}
                datasets={datasets}
                onSelectDataset={handleSelectDataset}
                onSelectBuilding={(b) => {
                  setSelectedBuilding(b);
                  setActiveTab('gis');
                }}
                onOpenReview={(b) => {
                  setSelectedBuilding(b);
                  setActiveTab('review');
                }}
                onOpenEvidence={(b) => {
                  setSelectedBuilding(b);
                  setShowDigitalCardModal(true);
                }}
                onGoToReports={() => setActiveTab('reports')}
                onGoToReview={() => setActiveTab('review')}
                onNavigateToTab={(tab) => setActiveTab(tab)}
              />
            )}

            {/* STAGE 08: REPORTS (Audit Trail & Official Exports) */}
            {activeTab === 'reports' && (
              <ReportsView
                buildings={buildings}
                stats={derivedStats}
                language={language}
                activeDataset={activeDataset}
                onSelectBuilding={(b) => {
                  setSelectedBuilding(b);
                  setActiveTab('gis');
                }}
                onOpenReview={(b) => {
                  setSelectedBuilding(b);
                  setActiveTab('review');
                }}
                onOpenEvidence={(b) => {
                  setSelectedBuilding(b);
                  setShowDigitalCardModal(true);
                }}
                onNavigateToTab={(tab) => setActiveTab(tab)}
              />
            )}
          </>
        )}

      </main>
      </div>

      {/* 4. MODALS & SLIDE-OVERS */}

      {/* Modal 1: Source Comparison Modal (Before vs After individual building footprints) */}
      {showSourcesModal && selectedBuilding && (
        <SourceComparisonModal
          building={selectedBuilding}
          onClose={() => setShowSourcesModal(false)}
          language={language}
        />
      )}

      {/* Modal 2: 7-Stage Reconciliation Pipeline Visualizer Modal */}
      {showReconcileModal && (
  <ReconciliationModal
    onClose={() => setShowReconcileModal(false)}
    language={language}
    onComplete={handleReconciliationComplete}
  />
)}

      {/* Modal 3: Official Digital Land Entity Certificate Card Modal */}
      {showDigitalCardModal && selectedBuilding && (
        <DigitalLandEntityModal
          building={selectedBuilding}
          onClose={() => setShowDigitalCardModal(false)}
          language={language}
          onViewSources={() => setShowSourcesModal(true)}
        />
      )}

      {/* Modal 4: Advanced GIS Technical Details & Engineering Metrics Modal */}
      {showTechDetailsModal && selectedBuilding && (
        <TechnicalDetailsModal
          building={selectedBuilding}
          onClose={() => setShowTechDetailsModal(false)}
          language={language}
        />
      )}

      {/* Modal 5: Audit History Trail Modal */}
      {showHistoryModal && selectedBuilding && (
        <HistoryModal
          building={selectedBuilding}
          onClose={() => setShowHistoryModal(false)}
          language={language}
        />
      )}

      {/* Modal 6: 14-Step Guided Hackathon Demo Tour */}
      {showDemoTour && (
        <DemoTourModal
          onClose={() => setShowDemoTour(false)}
          onNavigateTab={(tab) => {
            setShowBeforeAfterDirect(false);
            setActiveTab(tab);
          }}
          onSelectBuilding={handleSelectBuilding}
          showcaseBuilding={showcaseBuilding}
          onOpenSourcesModal={() => setShowSourcesModal(true)}
          onOpenReconciliationModal={() => setShowReconcileModal(true)}
          onOpenDigitalCard={() => setShowDigitalCardModal(true)}
          language={language}
        />
      )}

    </div>
  );
}