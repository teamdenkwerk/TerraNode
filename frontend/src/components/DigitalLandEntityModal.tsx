import React, { useState } from 'react';
import { BuildingEntity, Language } from '../types';
import { translations } from '../data/i18n';
import { 
  X, 
  Download, 
  QrCode, 
  ShieldCheck, 
  Compass, 
  Copy, 
  Check
} from 'lucide-react';

interface DigitalLandEntityModalProps {
  building: BuildingEntity;
  onClose: () => void;
  language: Language;
  onViewSources: () => void;
}

export const DigitalLandEntityModal: React.FC<DigitalLandEntityModalProps> = ({
  building,
  onClose,
  language,
  onViewSources,
}) => {
  const [copied, setCopied] = useState(false);

  const handleCopyGeoJson = () => {
    const geojson = {
      type: "Feature",
      properties: {
        id: building.id,
        surveyNumber: building.surveyNumber,
        wardNo: building.wardNo,
        zone: building.zone,
        areaM2: building.area,
        landUse: building.landUse,
        heightMeters: building.height,
        confidence: building.confidence,
        status: building.status,
        ecosystem: "TERRANODE / Urban Land Records",
        hash: `0x7F${building.id.replace(/[^0-9]/g, '')}D9C2A`,
      },
      geometry: {
        type: "Polygon",
        coordinates: [building.coordinates.map(([lat, lng]) => [lng, lat])],
      },
    };

    navigator.clipboard.writeText(JSON.stringify(geojson, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 3000);
  };

  const handleDownloadGeoJson = () => {
    const geojson = {
      type: "FeatureCollection",
      features: [
        {
          type: "Feature",
          properties: {
            id: building.id,
            surveyNumber: building.surveyNumber,
            areaM2: building.area,
            landUse: building.landUse,
            confidence: building.confidence,
            verified: true,
          },
          geometry: {
            type: "Polygon",
            coordinates: [building.coordinates.map(([lat, lng]) => [lng, lat])],
          },
        },
      ],
    };

    const blob = new Blob([JSON.stringify(geojson, null, 2)], { type: "application/geo+json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `TERRANODE_${building.id}_Reconciled.geojson`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-in fade-in">
      <div className="bg-white rounded-3xl shadow-2xl border border-[#E7DFD3] w-full max-w-lg overflow-hidden flex flex-col text-[#241D16]">
        
        {/* Header */}
        <div className="p-4 border-b border-[#E7DFD3] flex items-center justify-between bg-[#FAF8F3]">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-full overflow-hidden bg-white border border-[#E7DFD3] shadow-2xs shrink-0">
              <img src="/terranode_logo.png" alt="TerraNode Logo" className="w-full h-full object-cover rounded-full" />
            </div>
            <span className="font-bold text-sm text-[#241D16] tracking-tight">
              TERRANODE Digital Land Record Identity
            </span>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-[#7D7063] hover:text-[#241D16] hover:bg-[#FAF8F3] transition cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Identity Card Container */}
        <div className="p-6 overflow-y-auto">
          
          <div className="bg-[#F6F2EB] text-[#241D16] rounded-3xl p-6 shadow-xs border border-[#E7DFD3] relative overflow-hidden">
            
            {/* Hologram / Security Header */}
            <div className="flex items-start justify-between pb-4 border-b border-[#E7DFD3]">
              <div>
                <span className="text-[10px] uppercase font-mono tracking-widest text-[#A86236] font-bold block">
                  TERRANODE • NAKSHA DIGITAL TWIN
                </span>
                <h3 className="text-sm font-bold text-[#241D16] mt-0.5">
                  URBAN LAND ENTITY CERTIFICATE
                </h3>
              </div>
              <div className="flex items-center gap-1.5 bg-[#EAF2EB] text-[#3F6452] border border-[#C5DAC9] px-2.5 py-1 rounded-full text-xs font-mono font-bold">
                <ShieldCheck className="w-3.5 h-3.5" />
                <span>✓ RECONCILED</span>
              </div>
            </div>

            {/* Entity ID & Icon */}
            <div className="flex items-center justify-between my-5">
              <div>
                <div className="flex items-center gap-2 text-2xl font-bold text-[#241D16] tracking-tight">
                  <span>🏛️</span>
                  <span>{building.id}</span>
                </div>
                <div className="text-xs text-[#7D7063] font-mono mt-0.5">
                  Survey No: <span className="text-[#241D16] font-bold">{building.surveyNumber}</span>
                </div>
              </div>

              {/* Simulated QR Code Stamp */}
              <div className="w-16 h-16 bg-white p-1.5 rounded-xl shadow-xs border border-[#E7DFD3] flex items-center justify-center">
                <QrCode className="w-full h-full text-[#241D16]" />
              </div>
            </div>

            {/* Core Certificate Attributes */}
            <div className="grid grid-cols-2 gap-3 text-xs bg-white p-4 rounded-2xl border border-[#E7DFD3]">
              <div>
                <span className="text-[10px] uppercase font-mono font-bold text-[#7D7063] block">Canonical Area</span>
                <span className="text-base font-bold text-[#241D16] font-mono">{building.area} m²</span>
              </div>

              <div>
                <span className="text-[10px] uppercase font-mono font-bold text-[#7D7063] block">Land Use</span>
                <span className="text-base font-bold text-[#241D16]">{building.landUse}</span>
              </div>

              <div>
                <span className="text-[10px] uppercase font-mono font-bold text-[#7D7063] block">Height</span>
                <span className="text-base font-bold text-[#241D16] font-mono">{building.height} m ({building.floors} fl)</span>
              </div>

              <div>
                <span className="text-[10px] uppercase font-mono font-bold text-[#7D7063] block">Survey Sources</span>
                <span className="text-base font-bold text-[#A86236] font-mono">{building.sourcesCount} Datasets</span>
              </div>

              <div>
                <span className="text-[10px] uppercase font-mono font-bold text-[#7D7063] block">Source Agreement</span>
                <span className="text-base font-bold text-[#3F6452] font-mono">{building.agreementScore}%</span>
              </div>

              <div>
                <span className="text-[10px] uppercase font-mono font-bold text-[#7D7063] block">Confidence Score</span>
                <span className="text-base font-bold text-[#3F6452] font-mono">{building.confidence}%</span>
              </div>
            </div>

            {/* Bottom Metadata & Hash */}
            <div className="mt-4 pt-3 border-t border-[#E7DFD3] flex items-center justify-between text-[10px] text-[#7D7063] font-mono">
              <div>
                Synchronized: <span className="text-[#241D16] font-bold">{building.lastUpdated}</span>
              </div>
              <div>
                Hash: <span className="text-[#A86236]">0x7F{building.id.replace(/[^0-9]/g, '')}D9C</span>
              </div>
            </div>

          </div>

        </div>

        {/* Modal Action Buttons */}
        <div className="p-4 border-t border-[#E7DFD3] bg-[#FAF8F3] flex flex-wrap items-center justify-between gap-2">
          <button
            onClick={() => {
              onClose();
              onViewSources();
            }}
            className="px-3.5 py-2 text-xs font-bold text-[#7D7063] hover:text-[#241D16] transition cursor-pointer"
          >
            Compare Sources
          </button>

          <div className="flex items-center gap-2">
            <button
              onClick={handleCopyGeoJson}
              className="px-3.5 py-2 bg-white hover:bg-[#FAF8F3] text-[#241D16] rounded-xl text-xs font-bold transition flex items-center gap-1.5 border border-[#E7DFD3] cursor-pointer shadow-xs"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-[#3F6452]" /> : <Copy className="w-3.5 h-3.5 text-[#7D7063]" />}
              <span>{copied ? "Copied GeoJSON" : "Copy GeoJSON"}</span>
            </button>

            <button
              onClick={handleDownloadGeoJson}
              className="px-4 py-2 bg-[#A86236] hover:bg-[#8F4F28] text-white rounded-xl text-xs font-bold transition shadow-xs flex items-center gap-1.5 active:scale-95 cursor-pointer"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Export GeoJSON</span>
            </button>
          </div>
        </div>

      </div>
    </div>
  );
};
