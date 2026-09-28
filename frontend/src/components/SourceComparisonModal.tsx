import React, { useState } from 'react';
import { BuildingEntity, Language } from '../types';
import { translations } from '../data/i18n';
import { 
  X, 
  Sparkles, 
  CheckCircle2, 
  RotateCcw, 
  ShieldCheck
} from 'lucide-react';
import confetti from 'canvas-confetti';

interface SourceComparisonModalProps {
  building: BuildingEntity;
  onClose: () => void;
  language: Language;
}

export const SourceComparisonModal: React.FC<SourceComparisonModalProps> = ({
  building,
  onClose,
  language,
}) => {
  const t = translations[language];
  
  const [animationState, setAnimationState] = useState<'separate' | 'reconciling' | 'merged'>('separate');
  const [activeSourceFilter, setActiveSourceFilter] = useState<'all' | 'ori' | 'municipal' | 'cadastral' | 'ai'>('all');

  const handleReconcileTransition = () => {
    setAnimationState('reconciling');
    setTimeout(() => {
      setAnimationState('merged');
      try {
        confetti({
          particleCount: 50,
          spread: 60,
          origin: { y: 0.6 }
        });
      } catch (e) {
        // ignore if canvas not supported
      }
    }, 1200);
  };

  const handleReset = () => {
    setAnimationState('separate');
  };

  const getNormalizedSvgPoints = (coords: [number, number][], jitterScale = 1.0, jitterRotate = 0, offsetX = 0, offsetY = 0) => {
    if (!coords || coords.length === 0) return "";
    
    const effectiveCoords = (animationState === 'merged') ? building.coordinates : coords;
    const effOffsetX = (animationState === 'merged') ? 0 : offsetX;
    const effOffsetY = (animationState === 'merged') ? 0 : offsetY;

    const lats = building.coordinates.map(c => c[0]);
    const lngs = building.coordinates.map(c => c[1]);
    const minLat = Math.min(...lats);
    const maxLat = Math.max(...lats);
    const minLng = Math.min(...lngs);
    const maxLng = Math.max(...lngs);

    const padLat = (maxLat - minLat) * 0.4 || 0.0001;
    const padLng = (maxLng - minLng) * 0.4 || 0.0001;

    const bMinLat = minLat - padLat;
    const bMaxLat = maxLat + padLat;
    const bMinLng = minLng - padLng;
    const bMaxLng = maxLng + padLng;

    return effectiveCoords.map(([lat, lng]) => {
      const x = ((lng - bMinLng) / (bMaxLng - bMinLng)) * 280 + effOffsetX;
      const y = (1 - (lat - bMinLat) / (bMaxLat - bMinLat)) * 280 + effOffsetY;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(" ");
  };

  const sourcesList = [
    {
      id: 'ori' as const,
      name: "Drone Imagery (ORI)",
      agency: "Survey of India (5cm GSD)",
      area: building.sources.ori.area,
      color: "#D8AD56",
      bgClass: "bg-[#FAF3E6] border-[#EDDCBA] text-[#241D16]",
      coords: building.sources.ori.coordinates,
      offsetX: -6,
      offsetY: 4,
    },
    {
      id: 'municipal' as const,
      name: "Municipal GIS",
      agency: "Property Tax Cadastre",
      area: building.sources.municipal.area,
      color: "#4A6D7C",
      bgClass: "bg-[#FAF8F3] border-[#E7DFD3] text-[#241D16]",
      coords: building.sources.municipal.coordinates,
      offsetX: 8,
      offsetY: -7,
    },
    {
      id: 'cadastral' as const,
      name: "Cadastral Map",
      agency: "Revenue Survey (Khasra)",
      area: building.sources.cadastral.area,
      color: "#7D6D8A",
      bgClass: "bg-[#FAF8F3] border-[#E7DFD3] text-[#241D16]",
      coords: building.sources.cadastral.coordinates,
      offsetX: 0,
      offsetY: 0,
    },
    {
      id: 'ai' as const,
      name: "AI Feature Extraction",
      agency: "SAM-2 + DTM Segmentation",
      area: building.sources.ai.area,
      color: "#3F6452",
      bgClass: "bg-[#EAF2EB] border-[#C5DAC9] text-[#241D16]",
      coords: building.sources.ai.coordinates,
      offsetX: 3,
      offsetY: 2,
    },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-white rounded-3xl shadow-2xl border border-[#E7DFD3] w-full max-w-4xl overflow-hidden flex flex-col max-h-[92vh] text-[#241D16]">
        
        {/* Modal Top Header */}
        <div className="p-5 border-b border-[#E7DFD3] flex items-center justify-between bg-[#FAF8F3]">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-[#A86236] bg-[#FDF1EB] px-2.5 py-0.5 rounded-full border border-[#F3CEBD]">
                TERRANODE Alignment Pipeline
              </span>
              <span className="text-xs text-[#7D7063] font-mono">Entity #{building.id}</span>
            </div>
            <h3 className="text-xl font-bold text-[#241D16] mt-1">
              Geospatial Footprint Comparison & Reconciliation
            </h3>
          </div>

          <button
            onClick={onClose}
            className="p-2 rounded-xl text-[#7D7063] hover:text-[#241D16] hover:bg-[#FAF8F3] transition cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1">
          
          {/* Top Banner: Core Purpose Indicator */}
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-5 rounded-2xl bg-[#FAF8F3] text-[#241D16] shadow-xs border border-[#E7DFD3]">
            <div>
              <span className="text-[10px] font-mono font-bold text-[#A86236] uppercase tracking-wider block">
                Consensus Mechanism
              </span>
              <div className="text-lg font-bold flex items-center gap-2 text-[#241D16]">
                <span>{t.fourSourcesToOne}</span>
              </div>
              <p className="text-xs text-[#7D7063]">
                Harmonizing varying boundaries, scales, coordinate discrepancies, and survey dates into a single trusted polygon.
              </p>
            </div>

            {animationState === 'separate' ? (
              <button
                onClick={handleReconcileTransition}
                className="flex items-center gap-2 px-4 py-2.5 bg-[#A86236] hover:bg-[#8F4F28] text-white font-bold text-xs rounded-xl shadow-xs transition active:scale-95 shrink-0 cursor-pointer"
              >
                <Sparkles className="w-4 h-4" />
                <span>Reconcile to Unified Geometry</span>
              </button>
            ) : animationState === 'reconciling' ? (
              <div className="flex items-center gap-2 px-4 py-2.5 bg-[#FAF3E6] border border-[#EDDCBA] text-[#966B24] font-bold text-xs rounded-xl shrink-0">
                <span className="w-3 h-3 rounded-full border-2 border-[#966B24] border-t-transparent animate-spin"></span>
                <span>Resolving geometric offsets...</span>
              </div>
            ) : (
              <div className="flex items-center gap-2 shrink-0">
                <button
                  onClick={handleReset}
                  className="flex items-center gap-1.5 px-3 py-2 bg-white hover:bg-[#FAF8F3] text-[#241D16] text-xs font-semibold rounded-xl transition border border-[#E7DFD3] cursor-pointer shadow-xs"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  <span>Show Discrepancy</span>
                </button>
                <div className="flex items-center gap-1.5 px-3 py-2 bg-[#EAF2EB] text-[#3F6452] border border-[#C5DAC9] rounded-xl text-xs font-bold font-mono">
                  <ShieldCheck className="w-4 h-4" />
                  <span>Unified: 505 m² (94%)</span>
                </div>
              </div>
            )}
          </div>

          {/* Center Stage: Split Screen with Source Cards on Left and Visual Canvas on Right */}
          <div className="grid grid-cols-1 md:grid-cols-12 gap-6 items-center">
            
            {/* Left 4 Source Cards */}
            <div className="md:col-span-6 space-y-2.5">
              <span className="text-xs font-mono font-bold text-[#7D7063] uppercase tracking-wider block">
                Heterogeneous Input Layers
              </span>

              {sourcesList.map((src) => {
                const isActive = activeSourceFilter === 'all' || activeSourceFilter === src.id;
                const isDiff = src.area !== building.area;

                return (
                  <div
                    key={src.id}
                    onClick={() => setActiveSourceFilter(activeSourceFilter === src.id ? 'all' : src.id)}
                    className={`p-3.5 rounded-2xl border transition cursor-pointer ${
                      isActive 
                        ? `${src.bgClass} shadow-xs` 
                        : 'bg-[#FAF8F3] border-[#E7DFD3] text-[#7D7063] opacity-60'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <span 
                          className="w-3.5 h-3.5 rounded-full shadow-xs"
                          style={{ backgroundColor: src.color }}
                        />
                        <div>
                          <h4 className="font-bold text-xs sm:text-sm text-[#241D16]">{src.name}</h4>
                          <span className="text-[10px] text-[#7D7063] block">{src.agency}</span>
                        </div>
                      </div>

                      <div className="text-right">
                        <span className="font-mono text-base font-bold text-[#241D16]">{src.area} m²</span>
                        {isDiff && (
                          <span className={`text-[10px] font-mono font-bold block ${
                            src.area > building.area ? 'text-[#4A6D7C]' : 'text-[#D8AD56]'
                          }`}>
                            {src.area > building.area ? `+${src.area - building.area} m²` : `${src.area - building.area} m²`}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}

              {/* Bottom Final Result Summary Card */}
              <div className={`p-4 rounded-2xl border transition-all duration-300 ${
                animationState === 'merged' 
                  ? 'bg-[#EAF2EB] border-[#C5DAC9] text-[#241D16] shadow-xs' 
                  : 'bg-[#FAF8F3] border-[#E7DFD3] text-[#241D16]'
              }`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className={`w-4 h-4 ${animationState === 'merged' ? 'text-[#3F6452]' : 'text-[#7D7063]'}`} />
                    <span className="text-xs font-bold uppercase tracking-wider text-[#241D16]">
                      {animationState === 'merged' ? 'Unified Reconciled Parcel' : 'Target Reconciled Entity'}
                    </span>
                  </div>
                  <span className="text-xs font-mono font-bold px-2.5 py-0.5 rounded-full bg-white border border-[#C5DAC9] text-[#3F6452]">
                    94% Confidence
                  </span>
                </div>
                <div className="flex items-baseline gap-2 mt-2">
                  <span className="text-2xl font-mono font-bold text-[#241D16]">505 m²</span>
                  <span className="text-xs text-[#7D7063] font-medium">Cadastral & Drone ORI Convergence</span>
                </div>
              </div>

            </div>

            {/* Right Interactive SVG Overlay Canvas */}
            <div className="md:col-span-6 bg-[#F6F2EB] rounded-3xl p-4 sm:p-6 border border-[#E7DFD3] shadow-xs relative overflow-hidden flex flex-col items-center justify-center min-h-[320px]">
              
              {/* Subtle grid pattern in canvas background */}
              <div className="absolute inset-0 bg-[radial-gradient(#A86236_1px,transparent_1px)] [background-size:16px_16px] opacity-10 pointer-events-none" />

              {/* Status Pill in Canvas */}
              <div className="absolute top-4 left-4 z-10 bg-white/95 backdrop-blur-md border border-[#E7DFD3] px-3 py-1 rounded-full text-[11px] font-mono font-bold text-[#241D16] flex items-center gap-2 shadow-xs">
                <span className={`w-2 h-2 rounded-full ${animationState === 'merged' ? 'bg-[#3F6452] animate-pulse' : 'bg-[#D8AD56]'}`}></span>
                <span>
                  {animationState === 'separate' 
                    ? '4 Discrepant Footprints' 
                    : animationState === 'reconciling' 
                    ? 'Harmonizing Geometries...' 
                    : 'Unified Reconciled Footprint'}
                </span>
              </div>

              {/* Main SVG Visualization */}
              <div className="relative w-64 h-64 flex items-center justify-center my-2">
                <svg
                  viewBox="0 0 280 280"
                  className="w-full h-full overflow-visible"
                >
                  {/* Grid Crosshairs */}
                  <line x1="140" y1="20" x2="140" y2="260" stroke="#E7DFD3" strokeWidth="1" strokeDasharray="3,3" />
                  <line x1="20" y1="140" x2="260" y2="140" stroke="#E7DFD3" strokeWidth="1" strokeDasharray="3,3" />

                  {/* 1. Cadastral (Purple) */}
                  {(activeSourceFilter === 'all' || activeSourceFilter === 'cadastral') && (
                    <polygon
                      points={getNormalizedSvgPoints(building.sources.cadastral.coordinates, 1.0, 0, 0, 0)}
                      fill={animationState === 'merged' ? '#3F6452' : '#7D6D8A'}
                      fillOpacity={animationState === 'merged' ? '0.5' : '0.2'}
                      stroke={animationState === 'merged' ? '#3F6452' : '#7D6D8A'}
                      strokeWidth={animationState === 'merged' ? '2.5' : '1.8'}
                      strokeDasharray={animationState === 'merged' ? undefined : '4, 3'}
                      className="transition-all duration-700 ease-out"
                    />
                  )}

                  {/* 2. Municipal (Blue) */}
                  {(activeSourceFilter === 'all' || activeSourceFilter === 'municipal') && (
                    <polygon
                      points={getNormalizedSvgPoints(building.sources.municipal.coordinates, 1.02, -1, 8, -7)}
                      fill={animationState === 'merged' ? '#3F6452' : '#4A6D7C'}
                      fillOpacity={animationState === 'merged' ? '0.5' : '0.2'}
                      stroke={animationState === 'merged' ? '#3F6452' : '#4A6D7C'}
                      strokeWidth={animationState === 'merged' ? '2.5' : '1.8'}
                      className="transition-all duration-700 ease-out"
                    />
                  )}

                  {/* 3. Drone ORI (Amber) */}
                  {(activeSourceFilter === 'all' || activeSourceFilter === 'ori') && (
                    <polygon
                      points={getNormalizedSvgPoints(building.sources.ori.coordinates, 0.98, 0.5, -6, 4)}
                      fill={animationState === 'merged' ? '#3F6452' : '#D8AD56'}
                      fillOpacity={animationState === 'merged' ? '0.5' : '0.2'}
                      stroke={animationState === 'merged' ? '#3F6452' : '#D8AD56'}
                      strokeWidth={animationState === 'merged' ? '2.5' : '1.8'}
                      className="transition-all duration-700 ease-out"
                    />
                  )}

                  {/* 4. AI Feature Extraction (Teal/Emerald) */}
                  {(activeSourceFilter === 'all' || activeSourceFilter === 'ai') && (
                    <polygon
                      points={getNormalizedSvgPoints(building.sources.ai.coordinates, 0.99, 0.2, 3, 2)}
                      fill={animationState === 'merged' ? '#3F6452' : '#3F6452'}
                      fillOpacity={animationState === 'merged' ? '0.5' : '0.2'}
                      stroke={animationState === 'merged' ? '#3F6452' : '#3F6452'}
                      strokeWidth={animationState === 'merged' ? '2.5' : '1.8'}
                      strokeDasharray={animationState === 'merged' ? undefined : '2, 2'}
                      className="transition-all duration-700 ease-out"
                    />
                  )}

                  {/* Reconciled Clean Boundary Highlight */}
                  {animationState === 'merged' && (
                    <polygon
                      points={getNormalizedSvgPoints(building.coordinates)}
                      fill="#3F6452"
                      fillOpacity="0.4"
                      stroke="#A86236"
                      strokeWidth="3.5"
                      className="transition-all duration-500 animate-pulse"
                    />
                  )}

                  {/* Centroid Marker */}
                  <circle cx="140" cy="140" r="3.5" fill="#A86236" stroke="#ffffff" strokeWidth="2" />
                </svg>
              </div>

              {/* Bottom Canvas Callout */}
              <div className="text-center mt-2 z-10">
                {animationState === 'merged' ? (
                  <div className="text-xs font-mono font-bold text-[#3F6452] flex items-center justify-center gap-1.5">
                    <CheckCircle2 className="w-4 h-4 text-[#3F6452]" />
                    <span>Reconciled Area: 505 m² • IoU Consensus 0.96</span>
                  </div>
                ) : (
                  <div className="text-[11px] text-[#7D7063] flex items-center justify-center gap-2 font-mono">
                    <span className="w-2 h-2 rounded-full bg-[#D8AD56]"></span>
                    <span>Max boundary offset: 1.4m between Municipal & Cadastral</span>
                  </div>
                )}
              </div>

            </div>

          </div>

        </div>

        {/* Modal Footer */}
        <div className="p-4 border-t border-[#E7DFD3] flex items-center justify-between bg-[#FAF8F3]">
          <span className="text-xs text-[#7D7063] font-mono">
            TERRANODE Spatial Agreement Pipeline v3.4 • EPSG:4326
          </span>
          <button
            onClick={onClose}
            className="px-5 py-2 rounded-xl bg-white hover:bg-[#FAF8F3] text-[#241D16] text-xs font-bold transition border border-[#E7DFD3] cursor-pointer shadow-xs"
          >
            Close
          </button>
        </div>

      </div>
    </div>
  );
};
