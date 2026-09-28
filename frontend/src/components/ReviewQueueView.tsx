import React, { useState, useEffect } from 'react';
import { 
  BuildingEntity, 
  BuildingStatus,
  Language 
} from '../types';
import { translations } from '../data/i18n';
import { 
  AlertTriangle, 
  AlertOctagon, 
  CheckCircle2, 
  MapPin, 
  Eye, 
  Layers, 
  Check, 
  X, 
  Edit3, 
  Send,
  Loader2,
  Sparkles,
  Activity,
  ShieldCheck,
  GitCommit,
  ArrowRight
} from 'lucide-react';
import confetti from 'canvas-confetti';
import { resolveEntity, ConflictRecord, fetchConflicts } from '../api/geoReconciliationClient';
import { ConflictLifecycleModal } from './ConflictLifecycleModal';

interface ReviewQueueViewProps {
  buildings: BuildingEntity[];
  onSelectBuildingOnMap: (building: BuildingEntity) => void;
  language: Language;
  onResolved: (id: string, status: BuildingStatus) => void;
  onGoToValidation?: () => void;
}

export const ReviewQueueView: React.FC<ReviewQueueViewProps> = ({
  buildings,
  onSelectBuildingOnMap,
  language,
  onResolved,
  onGoToValidation,
}) => {
  const t = translations[language];

  // Filter only buildings that have conflict or review status
  const reviewItems = buildings.filter(b => b.status === 'conflict' || b.status === 'review');
  const highCount = reviewItems.filter(b => b.status === 'conflict').length;
  const mediumCount = reviewItems.filter(b => b.status === 'review').length;

  const [activeTab, setActiveTab] = useState<'all' | 'high' | 'medium'>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedReviewBuilding, setSelectedReviewBuilding] = useState<BuildingEntity | null>(null);
  const [actionSuccessMessage, setActionSuccessMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [chosenSource, setChosenSource] = useState<string>('recommendation');

  // Conflict State Machine modal state
  const [activeConflictRef, setActiveConflictRef] = useState<string | null>(null);
  const [conflictsMap, setConflictsMap] = useState<Record<string, ConflictRecord>>({});

  const loadConflicts = async () => {
    try {
      const list = await fetchConflicts();
      const map: Record<string, ConflictRecord> = {};
      list.forEach((c) => {
        if (c.source_parcel_id) map[c.source_parcel_id] = c;
        map[c.parcel_uuid] = c;
        map[c.conflict_id] = c;
      });
      setConflictsMap(map);
    } catch (e) {
      console.error('Failed to load conflicts:', e);
    }
  };

  useEffect(() => {
    loadConflicts();
  }, []);

  const filteredItems = reviewItems.filter(b => {
    if (activeTab === 'high' && b.status !== 'conflict') return false;
    if (activeTab === 'medium' && b.status !== 'review') return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      return b.id.toLowerCase().includes(q) || b.surveyNumber.toLowerCase().includes(q) || b.landUse.toLowerCase().includes(q);
    }
    return true;
  });

  const handleAction = async (actionType: 'accept' | 'source' | 'edit' | 'field') => {
    if (!selectedReviewBuilding) return;
    const id = selectedReviewBuilding.id;

    if (actionType === 'edit') {
      setActionSuccessMessage('Geometry editor is not implemented yet — no backend endpoint exists for it.');
      setTimeout(() => setActionSuccessMessage(null), 4000);
      return;
    }
    if (actionType === 'field') {
      setActionSuccessMessage('Field verification dispatch is not implemented yet — no backend endpoint exists for it.');
      setTimeout(() => setActionSuccessMessage(null), 4000);
      return;
    }

    setIsSubmitting(true);
    try {
      if (actionType === 'accept') {
        await resolveEntity(id, { status: 'approved' });
        onResolved(id, 'reconciled');
        setActionSuccessMessage(
          `Accepted recommendation for ${id} (${selectedReviewBuilding.conflictDetails?.recommendedArea || selectedReviewBuilding.area} m²)`
        );
        try {
          confetti({ particleCount: 40, spread: 50 });
        } catch (e) {
          // ignore
        }
      } else if (actionType === 'source') {
        await resolveEntity(id, { status: 'approved', note: `Operator selected source override: ${chosenSource}` });
        onResolved(id, 'reconciled');
        setActionSuccessMessage(`Saved resolution using ${chosenSource} layer override for ${id}.`);
        try {
          confetti({ particleCount: 40, spread: 50 });
        } catch (e) {
          // ignore
        }
      }

      setTimeout(() => {
        setSelectedReviewBuilding(null);
        setActionSuccessMessage(null);
      }, 1500);
    } catch (e) {
      console.error('Failed to resolve', e);
      setActionSuccessMessage(e instanceof Error ? e.message : 'Resolution failed');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6 py-6 px-4 sm:px-6">
      
      {/* Title & Stats */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2">
        <div>
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-full overflow-hidden bg-white border border-[#E7DFD3] shadow-xs shrink-0">
              <img src="/terranode_logo.png" alt="TerraNode Logo" className="w-full h-full object-cover rounded-full" />
            </div>
            <div className="flex items-center gap-2">
              <h2 className="text-2xl sm:text-3xl font-bold text-[#241D16] tracking-tight font-sans">
                {t.reviewRequired}
              </h2>
              <span className="text-[11px] font-mono font-bold bg-[#FAF3E6] text-[#966B24] border border-[#EDDCBA] px-3 py-0.5 rounded-full">
                {reviewItems.length} cases flagged
              </span>
            </div>
          </div>
          <p className="text-sm text-[#7D7063] mt-1">
            Human-in-the-loop review queue for parcels with multi-source boundary divergence below 90% confidence.
          </p>
        </div>

        {/* Filter Tabs */}
        <div className="flex items-center gap-2">
          <div className="bg-white p-1 rounded-xl flex text-xs font-bold border border-[#E7DFD3] shadow-xs">
            <button
              onClick={() => setActiveTab('all')}
              className={`px-3 py-1.5 rounded-lg transition cursor-pointer ${activeTab === 'all' ? 'bg-[#F6F2EB] text-[#241D16] border border-[#E7DFD3] shadow-xs' : 'text-[#7D7063] hover:text-[#241D16]'}`}
            >
              All ({reviewItems.length})
            </button>
            <button
              onClick={() => setActiveTab('high')}
              className={`px-3 py-1.5 rounded-lg transition flex items-center gap-1 cursor-pointer ${activeTab === 'high' ? 'bg-[#FDF1EB] text-[#C87958] border border-[#F3CEBD]' : 'text-[#C87958] hover:bg-[#FDF1EB]/60'}`}
            >
              <span className="w-2 h-2 rounded-full bg-[#C87958]"></span>
              High Conflict ({highCount})
            </button>
            <button
              onClick={() => setActiveTab('medium')}
              className={`px-3 py-1.5 rounded-lg transition flex items-center gap-1 cursor-pointer ${activeTab === 'medium' ? 'bg-[#FAF3E6] text-[#966B24] border border-[#EDDCBA]' : 'text-[#966B24] hover:bg-[#FAF3E6]/60'}`}
            >
              <span className="w-2 h-2 rounded-full bg-[#D8AD56]"></span>
              Medium ({mediumCount})
            </button>
          </div>

          {onGoToValidation && (
            <button
              onClick={onGoToValidation}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-[#3F6452] hover:bg-[#335343] text-white text-xs font-bold transition shadow-xs cursor-pointer shrink-0"
              title="Proceed to Validation"
            >
              <span>Validation</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {actionSuccessMessage && (
        <div className="p-4 rounded-2xl bg-[#EAF2EB] border border-[#C5DAC9] text-[#3F6452] font-semibold text-xs flex items-center justify-between animate-in fade-in">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-5 h-5 text-[#3F6452]" />
            <span>{actionSuccessMessage}</span>
          </div>
          <span className="text-[11px] text-white bg-[#3F6452] px-2 py-0.5 rounded-md font-bold font-mono">
            Record Updated
          </span>
        </div>
      )}

      {/* Review Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredItems.map((building) => {
          const isHigh = building.status === 'conflict';
          const conf = building.confidence;
          const conflictRecord = conflictsMap[building.id] || conflictsMap[building.id.replace('BLR-', '')];

          return (
            <div
              key={building.id}
              className={`bg-white rounded-2xl p-5 border shadow-sm transition-all hover:shadow-md flex flex-col justify-between ${
                isHigh ? 'border-[#F3CEBD] hover:border-[#C87958]' : 'border-[#EDDCBA] hover:border-[#D8AD56]'
              }`}
            >
              <div>
                <div className="flex items-center justify-between mb-3">
                  <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider font-mono ${
                    isHigh ? 'bg-[#FDF1EB] text-[#C87958] border border-[#F3CEBD]' : 'bg-[#FAF3E6] text-[#966B24] border border-[#EDDCBA]'
                  }`}>
                    {isHigh ? (
                      <>
                        <AlertOctagon className="w-3 h-3 text-[#C87958]" />
                        <span>HIGH CONFLICT</span>
                      </>
                    ) : (
                      <>
                        <AlertTriangle className="w-3 h-3 text-[#D8AD56]" />
                        <span>MEDIUM CONFLICT</span>
                      </>
                    )}
                  </span>

                  <span className="text-xs font-mono font-bold text-[#7D7063]">
                    Survey #{building.surveyNumber}
                  </span>
                </div>

                <h3 className="text-base font-mono font-bold text-[#241D16]">
                  Parcel #{building.id}
                </h3>
                <p className="text-xs text-[#7D7063] mt-0.5 font-mono">
                  {building.wardNo} • {building.landUse} ({building.area} m²)
                </p>

                <div className="my-3 p-2.5 rounded-xl bg-[#FAF8F3] border border-[#E7DFD3] text-xs text-[#241D16]">
                  <span className="font-semibold block text-[#241D16] font-mono">
                    {building.conflictDetails?.title || "Geometry variance detected"}
                  </span>
                  <p className="text-[11px] text-[#7D7063] mt-1 line-clamp-2">
                    {building.conflictDetails?.simplifiedReason || "Sources differ significantly across municipal and revenue boundaries."}
                  </p>
                </div>

                {/* Confidence Bar */}
                <div className="space-y-1 mb-4">
                  <div className="flex justify-between text-[11px] font-semibold text-[#7D7063] font-mono">
                    <span>Confidence</span>
                    <span className={`font-bold ${isHigh ? 'text-[#C87958]' : 'text-[#966B24]'}`}>
                      {conf}%
                    </span>
                  </div>
                  <div className="w-full h-2 bg-[#E7DFD3] rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${isHigh ? 'bg-[#C87958]' : 'bg-[#D8AD56]'}`}
                      style={{ width: `${conf}%` }}
                    />
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="space-y-2 pt-2 border-t border-[#E7DFD3]">
                {/* State Machine Transition Button */}
                <button
                  onClick={() => setActiveConflictRef(conflictRecord ? conflictRecord.conflict_id : building.id)}
                  className="w-full flex items-center justify-between px-3 py-2 bg-[#FAF7F2] hover:bg-[#F3EFE6] text-[#241D16] rounded-xl text-xs font-bold transition border border-[#E7DFD3] cursor-pointer shadow-xs"
                >
                  <div className="flex items-center gap-1.5">
                    <Activity className="w-3.5 h-3.5 text-[#966B24]" />
                    <span>State Machine</span>
                  </div>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded-md bg-amber-100 text-amber-800 font-bold border border-amber-200">
                    {conflictRecord ? conflictRecord.current_state : 'DETECTED'}
                  </span>
                </button>

                <div className="grid grid-cols-2 gap-2">
                  <button
                    onClick={() => onSelectBuildingOnMap(building)}
                    className="flex items-center justify-center gap-1 px-3 py-2 bg-[#FAF8F3] hover:bg-[#F3EFE6] text-[#241D16] rounded-xl text-xs font-bold transition border border-[#E7DFD3] cursor-pointer"
                  >
                    <MapPin className="w-3.5 h-3.5 text-[#3F6452]" />
                    <span>View on Map</span>
                  </button>

                  <button
                    onClick={() => setSelectedReviewBuilding(building)}
                    className={`flex items-center justify-center gap-1 px-3 py-2 rounded-xl text-xs font-bold transition shadow-xs cursor-pointer ${
                      isHigh ? 'bg-[#C87958] hover:bg-[#8F4F28] text-white' : 'bg-[#D8AD56] hover:bg-[#966B24] text-[#241D16]'
                    }`}
                  >
                    <Eye className="w-3.5 h-3.5" />
                    <span>Inspect</span>
                  </button>
                </div>
              </div>

            </div>
          );
        })}

      </div>

      {/* Review Detail Split-Screen Modal */}
      {selectedReviewBuilding && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-in fade-in">
          <div className="bg-white rounded-3xl shadow-2xl border border-[#E7DFD3] w-full max-w-4xl overflow-hidden flex flex-col max-h-[92vh] text-[#241D16]">
            
            {/* Modal Header */}
            <div className="p-5 border-b border-[#E7DFD3] flex items-center justify-between bg-[#FAF8F3]">
              <div className="flex items-center gap-3">
                <div className={`w-10 h-10 rounded-xl flex items-center justify-center font-bold ${
                  selectedReviewBuilding.status === 'conflict' ? 'bg-[#FDF1EB] border border-[#F3CEBD] text-[#C87958]' : 'bg-[#FAF3E6] border border-[#EDDCBA] text-[#966B24]'
                }`}>
                  <AlertTriangle className="w-5 h-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] font-bold uppercase tracking-wider font-mono text-[#C87958]">
                      Conflict Detected
                    </span>
                    <span className="text-xs text-[#7D7063] font-mono">
                      Survey #{selectedReviewBuilding.surveyNumber}
                    </span>
                  </div>
                  <h3 className="text-xl font-mono font-bold text-[#241D16]">
                    Review Parcel #{selectedReviewBuilding.id}
                  </h3>
                </div>
              </div>

              <button
                onClick={() => setSelectedReviewBuilding(null)}
                disabled={isSubmitting}
                className="p-2 rounded-xl text-[#7D7063] hover:text-[#241D16] hover:bg-[#FAF8F3] transition disabled:opacity-40 cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Split Screen Body */}
            <div className="p-6 overflow-y-auto space-y-6 flex-1">
              
              {/* Conflict Explanation Banner */}
              <div className="p-4 rounded-2xl bg-[#FAF8F3] border border-[#EDDCBA] text-xs text-[#241D16]">
                <span className="font-bold text-sm block mb-1 text-[#241D16] font-mono">Reason for Flag:</span>
                <p className="leading-relaxed font-medium text-[#7D7063]">
                  {selectedReviewBuilding.conflictDetails?.simplifiedReason || "Building boundaries differ between cadastral and municipal sources."}
                </p>
                <div className="mt-2 text-[11px] text-[#966B24] font-mono bg-white p-2.5 rounded-lg border border-[#E7DFD3]">
                  {selectedReviewBuilding.conflictDetails?.technicalReason || "Multi-source spatial variance detected in STRtree geometry intersection."}
                </div>
              </div>

              {/* Split Screen Comparison */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                
                {/* LEFT: Source Geometries */}
                <div className="bg-[#FAF8F3] rounded-2xl p-4 border border-[#E7DFD3] flex flex-col justify-between">
                  <div>
                    <div className="flex items-center justify-between pb-2 border-b border-[#E7DFD3] mb-3">
                      <span className="text-xs font-bold text-[#C87958] uppercase tracking-wider font-mono">
                        LEFT: Source Geometries
                      </span>
                    </div>

                    {/* Source Values Table */}
                    <div className="space-y-2 text-xs font-mono">
                      <div className="flex items-center justify-between p-2.5 rounded-xl bg-white border border-[#E7DFD3]">
                        <div className="flex items-center gap-2">
                          <span className="w-3 h-3 rounded-full bg-[#8B5CF6]"></span>
                          <span className="font-semibold text-[#7D7063]">Cadastral Map:</span>
                        </div>
                        <span className="font-bold text-[#241D16]">{selectedReviewBuilding.sources.cadastral.area} m²</span>
                      </div>

                      <div className="flex items-center justify-between p-2.5 rounded-xl bg-white border border-[#E7DFD3]">
                        <div className="flex items-center gap-2">
                          <span className="w-3 h-3 rounded-full bg-[#06B6D4]"></span>
                          <span className="font-semibold text-[#7D7063]">Municipal GIS:</span>
                        </div>
                        <span className="font-bold text-[#241D16]">{selectedReviewBuilding.sources.municipal.area} m²</span>
                      </div>

                      <div className="flex items-center justify-between p-2.5 rounded-xl bg-white border border-[#E7DFD3]">
                        <div className="flex items-center gap-2">
                          <span className="w-3 h-3 rounded-full bg-[#3F6452]"></span>
                          <span className="font-semibold text-[#7D7063]">AI Extraction:</span>
                        </div>
                        <span className="font-bold text-[#241D16]">{selectedReviewBuilding.sources.ai.area} m²</span>
                      </div>

                      <div className="flex items-center justify-between p-2.5 rounded-xl bg-white border border-[#E7DFD3]">
                        <div className="flex items-center gap-2">
                          <span className="w-3 h-3 rounded-full bg-[#D8AD56]"></span>
                          <span className="font-semibold text-[#7D7063]">Drone (ORI):</span>
                        </div>
                        <span className="font-bold text-[#241D16]">{selectedReviewBuilding.sources.ori.area} m²</span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* RIGHT: Reconciled Canonical Geometry */}
                <div className="bg-[#FAF8F3] rounded-2xl p-4 border border-[#E7DFD3] flex flex-col justify-between">
                  <div>
                    <div className="flex items-center justify-between pb-2 border-b border-[#E7DFD3] mb-3">
                      <span className="text-xs font-bold text-[#3F6452] uppercase tracking-wider font-mono">
                        RIGHT: Reconciled Canonical Geometry
                      </span>
                    </div>

                    <div className="p-4 rounded-xl bg-white border-2 border-[#3F6452]/40 text-xs mb-3 shadow-sm">
                      <span className="text-[10px] uppercase font-bold text-[#3F6452] block font-mono">System Canonical Recommendation</span>
                      <div className="text-3xl font-mono font-bold text-[#241D16] my-2">
                        {selectedReviewBuilding.conflictDetails?.recommendedArea || selectedReviewBuilding.area} m²
                      </div>
                      <div className="flex items-center justify-between text-[#7D7063] text-[11px] font-mono">
                        <span>Calculated Confidence:</span>
                        <span className="font-bold text-[#3F6452]">
                          {selectedReviewBuilding.confidence}%
                        </span>
                      </div>
                    </div>
                  </div>
                </div>

              </div>

            </div>

            {/* Human-in-the-Loop Action Buttons */}
            <div className="p-4 border-t border-[#E7DFD3] bg-[#FAF8F3] flex flex-wrap items-center justify-between gap-3">
              <span className="text-xs text-[#7D7063] font-semibold font-mono">
                Administrator Resolution Actions:
              </span>

              <div className="flex flex-wrap items-center gap-2">
                <button
                  onClick={() => {
                    const ref = selectedReviewBuilding.id;
                    const cnf = conflictsMap[ref] || conflictsMap[ref.replace('BLR-', '')];
                    setActiveConflictRef(cnf ? cnf.conflict_id : ref);
                  }}
                  className="px-3.5 py-2 bg-amber-50 hover:bg-amber-100 text-amber-900 border border-amber-200 rounded-xl text-xs font-bold transition flex items-center gap-1.5 cursor-pointer shadow-xs"
                >
                  <Activity className="w-3.5 h-3.5 text-[#966B24]" />
                  <span>Conflict State Machine</span>
                </button>

                <button
                  onClick={() => handleAction('accept')}
                  disabled={isSubmitting}
                  className="px-4 py-2 bg-[#3F6452] hover:bg-[#2C493B] text-white rounded-xl text-xs font-bold shadow-sm transition active:scale-95 flex items-center gap-1.5 disabled:opacity-50 cursor-pointer"
                >
                  {isSubmitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                  <span>Accept Recommendation</span>
                </button>

                <button
                  onClick={() => handleAction('source')}
                  disabled={isSubmitting}
                  className="px-3.5 py-2 bg-white hover:bg-[#FAF8F3] text-[#241D16] border border-[#E7DFD3] rounded-xl text-xs font-bold transition flex items-center gap-1.5 disabled:opacity-50 cursor-pointer shadow-xs"
                >
                  <Layers className="w-3.5 h-3.5 text-[#A86236]" />
                  <span>Select Override Source</span>
                </button>
              </div>
            </div>

          </div>
        </div>
      )}

      {/* Conflict Lifecycle State Machine Modal */}
      {activeConflictRef && (
        <ConflictLifecycleModal
          conflictIdOrParcelRef={activeConflictRef}
          isOpen={true}
          onClose={() => setActiveConflictRef(null)}
          onStateChanged={(updated) => {
            loadConflicts();
            if (updated.current_state === 'APPROVED' || updated.current_state === 'RESOLVED') {
              onResolved(updated.source_parcel_id || updated.parcel_uuid, 'reconciled');
            }
          }}
        />
      )}

    </div>
  );
};