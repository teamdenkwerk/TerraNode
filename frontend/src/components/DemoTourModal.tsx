import React, { useState } from 'react';
import { 
  X, 
  ChevronRight, 
  ChevronLeft, 
  Sparkles, 
  Play
} from 'lucide-react';
import { ActiveTab, BuildingEntity, Language } from '../types';

interface DemoTourModalProps {
  onClose: () => void;
  onNavigateTab: (tab: ActiveTab) => void;
  onSelectBuilding: (building: BuildingEntity) => void;
  showcaseBuilding: BuildingEntity;
  onOpenSourcesModal: () => void;
  onOpenReconciliationModal: () => void;
  onOpenDigitalCard: () => void;
  language: Language;
}

export const DemoTourModal: React.FC<DemoTourModalProps> = ({
  onClose,
  onNavigateTab,
  onSelectBuilding,
  showcaseBuilding,
  onOpenSourcesModal,
  onOpenReconciliationModal,
  onOpenDigitalCard,
  language,
}) => {
  const [currentStep, setCurrentStep] = useState(0);

  const demoSteps = [
    {
      stepNumber: 1,
      title: "1. Open TERRANODE GIS Explorer",
      description: "TERRANODE welcomes spatial engineers and administrators to an executive GIS workspace displaying live multi-source land data under the NAKSHA ecosystem.",
      actionText: "Show GIS Explorer",
      onAction: () => onNavigateTab('gis'),
    },
    {
      stepNumber: 2,
      title: "2. Multi-Source Statistics Overview",
      description: "1,248 total parcels ingested from 4 sources (Drone ORI, Cadastral, Municipal, GNSS). 1,103 matched automatically with 94% average confidence.",
      actionText: "Inspect Pilot Metrics",
      onAction: () => onNavigateTab('gis'),
    },
    {
      stepNumber: 3,
      title: "3. Open Main Interactive Map",
      description: "High-resolution satellite GIS map with dark basemaps, layer controls (Drone, Cadastral, Roads, GNSS, Municipal, Reconciled), and confidence color-coding.",
      actionText: "Switch to Interactive Map",
      onAction: () => onNavigateTab('map'),
    },
    {
      stepNumber: 4,
      title: "4. Select Building #BLD-1028",
      description: "Selecting a building activates the instant side-inspection panel displaying area, land use, height, and source agreement checklist.",
      actionText: "Inspect Building #1028",
      onAction: () => {
        onNavigateTab('map');
        onSelectBuilding(showcaseBuilding);
      },
    },
    {
      stepNumber: 5,
      title: "5. Compare Multiple Source Measurements",
      description: "Notice the raw discrepancy across datasets: ORI (498 m²), Municipal GIS (512 m²), Cadastral (505 m²), AI Extraction (501 m²).",
      actionText: "View Source Comparison",
      onAction: () => {
        onNavigateTab('map');
        onSelectBuilding(showcaseBuilding);
        onOpenSourcesModal();
      },
    },
    {
      stepNumber: 6,
      title: "6. Visual Footprint Overlay",
      description: "See the 4 independent boundaries overlaid simultaneously in distinct colors (Cadastral purple, Municipal blue, Drone amber, AI teal).",
      actionText: "Examine Overlaid Differences",
      onAction: () => {
        onOpenSourcesModal();
      },
    },
    {
      stepNumber: 7,
      title: "7. Run Automated Reconciliation",
      description: "Trigger the TERRANODE automated engine to resolve coordinate shifts, eave overhangs, and boundary conflicts.",
      actionText: "Launch Reconciliation Pipeline",
      onAction: () => {
        onOpenReconciliationModal();
      },
    },
    {
      stepNumber: 8,
      title: "8. 7-Stage Processing Pipeline",
      description: "Live pipeline tracker: CRS aligned to EPSG:4326 → SAM-2 features extracted → spatial matching → conflict resolution → confidence scoring.",
      actionText: "Track Pipeline Stages",
      onAction: () => {
        onOpenReconciliationModal();
      },
    },
    {
      stepNumber: 9,
      title: "9. Produce Unified Reconciled Geometry",
      description: "The 4 disparate source footprints morph into one unified, legally validated land parcel.",
      actionText: "See Morph Transition",
      onAction: () => {
        onOpenSourcesModal();
      },
    },
    {
      stepNumber: 10,
      title: "10. Display Final Reconciled Area",
      description: "Final consensus measurement: 505 m² (aligned strictly with Revenue Cadastral markers and 5cm Drone ground truth).",
      actionText: "Verify Final Measurements",
      onAction: () => {
        onNavigateTab('map');
        onSelectBuilding(showcaseBuilding);
      },
    },
    {
      stepNumber: 11,
      title: "11. Calculate Confidence Reliability Score",
      description: "Clear confidence score: 94% (Highly Reliable / Verified) with full geometry, source, and attribute agreements verified.",
      actionText: "View Confidence Checklist",
      onAction: () => {
        onNavigateTab('map');
        onSelectBuilding(showcaseBuilding);
      },
    },
    {
      stepNumber: 12,
      title: "12. Human-in-the-Loop Review Queue",
      description: "Low-confidence edge cases (e.g. Building #1044, #1015) route automatically to the split-screen operator review queue.",
      actionText: "Open Review Queue",
      onAction: () => onNavigateTab('review'),
    },
    {
      stepNumber: 13,
      title: "13. Compare Data (Before vs After)",
      description: "Wipe between before (42 conflicts, 82% confidence) and after (11 conflicts, 94% confidence) to see the transformative impact.",
      actionText: "Open Before vs After Slider",
      onAction: () => onNavigateTab('validation'),
    },
    {
      stepNumber: 14,
      title: "14. Export Digital Land Entity Card",
      description: "Generate official government certificate with QR verification stamp, survey number, security hash, and standardized GeoJSON download.",
      actionText: "View Digital Land Card",
      onAction: () => {
        onNavigateTab('map');
        onSelectBuilding(showcaseBuilding);
        onOpenDigitalCard();
      },
    },
  ];

  const current = demoSteps[currentStep];

  const handleNext = () => {
    if (currentStep < demoSteps.length - 1) {
      const nextIdx = currentStep + 1;
      setCurrentStep(nextIdx);
      demoSteps[nextIdx].onAction();
    }
  };

  const handlePrev = () => {
    if (currentStep > 0) {
      const prevIdx = currentStep - 1;
      setCurrentStep(prevIdx);
      demoSteps[prevIdx].onAction();
    }
  };

  return (
    <div className="fixed bottom-4 left-4 right-4 sm:left-auto sm:right-6 sm:bottom-6 sm:w-[460px] z-50 bg-white/95 text-[#241D16] rounded-3xl p-5 shadow-2xl border border-[#E7DFD3] backdrop-blur-xl animate-in slide-in-from-bottom-5 duration-200">
      
      {/* Top Header */}
      <div className="flex items-center justify-between pb-3 border-b border-[#E7DFD3]">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-full overflow-hidden bg-white border border-[#E7DFD3] shadow-2xs shrink-0">
            <img src="/terranode_logo.png" alt="TerraNode Logo" className="w-full h-full object-cover rounded-full" />
          </div>
          <span className="text-xs font-mono font-bold uppercase tracking-wider text-[#A86236]">
            TERRANODE Guided Walkthrough
          </span>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-xs font-mono text-[#7D7063] font-bold">
            Step {current.stepNumber} / 14
          </span>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-[#7D7063] hover:text-[#241D16] hover:bg-[#F0EBE1] transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Body */}
      <div className="my-4 space-y-2">
        <h4 className="text-base font-bold text-[#241D16]">
          {current.title}
        </h4>
        <p className="text-xs text-[#7D7063] leading-relaxed">
          {current.description}
        </p>

        {/* Quick Action Button for this step */}
        <button
          onClick={current.onAction}
          className="mt-2 w-full py-2.5 px-3 bg-[#A86236]/10 hover:bg-[#A86236]/20 text-[#A86236] border border-[#A86236]/30 rounded-xl text-xs font-bold transition flex items-center justify-center gap-2 shadow-xs"
        >
          <Sparkles className="w-3.5 h-3.5 text-[#A86236]" />
          <span>Execute: {current.actionText}</span>
        </button>
      </div>

      {/* Stepper Navigation */}
      <div className="flex items-center justify-between pt-3 border-t border-[#E7DFD3]">
        <button
          onClick={handlePrev}
          disabled={currentStep === 0}
          className="px-3 py-1.5 rounded-xl bg-[#FAF8F3] hover:bg-[#F0EBE1] text-xs font-semibold text-[#241D16] border border-[#E7DFD3] disabled:opacity-30 disabled:cursor-not-allowed flex items-center gap-1 transition"
        >
          <ChevronLeft className="w-4 h-4" />
          <span>Back</span>
        </button>

        {/* Step dots */}
        <div className="flex items-center gap-1">
          {demoSteps.map((_, i) => (
            <span
              key={i}
              onClick={() => {
                setCurrentStep(i);
                demoSteps[i].onAction();
              }}
              className={`h-1.5 rounded-full cursor-pointer transition-all ${
                i === currentStep ? 'w-4 bg-[#A86236]' : 'w-1.5 bg-[#E7DFD3] hover:bg-[#D5CBBE]'
              }`}
            />
          ))}
        </div>

        {currentStep < demoSteps.length - 1 ? (
          <button
            onClick={handleNext}
            className="px-4 py-1.5 rounded-xl bg-[#A86236] hover:bg-[#8F4F28] text-white text-xs font-bold flex items-center gap-1 shadow-md transition"
          >
            <span>Next</span>
            <ChevronRight className="w-4 h-4" />
          </button>
        ) : (
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-xl bg-[#A86236] hover:bg-[#8F4F28] text-white text-xs font-bold transition shadow-md"
          >
            <span>Finish Tour</span>
          </button>
        )}
      </div>

    </div>
  );
};
