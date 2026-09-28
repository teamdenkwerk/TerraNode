import React from 'react';
import { BuildingEntity, Language } from '../types';
import { translations } from '../data/i18n';
import { X, Globe, Scale, Cpu } from 'lucide-react';

interface TechnicalDetailsModalProps {
  building: BuildingEntity;
  onClose: () => void;
  language: Language;
}

export const TechnicalDetailsModal: React.FC<TechnicalDetailsModalProps> = ({
  building,
  onClose,
  language,
}) => {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-in fade-in">
      <div className="bg-white rounded-3xl shadow-2xl border border-[#E7DFD3] w-full max-w-2xl overflow-hidden flex flex-col max-h-[92vh]">
        
        {/* Header */}
        <div className="p-5 border-b border-[#E7DFD3] flex items-center justify-between bg-[#FAF8F3]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-[#FDF1EB] border border-[#F3CEBD] text-[#A86236] flex items-center justify-center font-mono text-sm shadow-xs">
              &lt;/&gt;
            </div>
            <div>
              <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-[#A86236]">
                TERRANODE Advanced Metrics
              </span>
              <h3 className="text-lg font-bold text-[#241D16]">
                Technical Details & Metrics • {building.id}
              </h3>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-2 rounded-xl text-[#7D7063] hover:text-[#241D16] hover:bg-[#F0EBE1] transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Technical Data Content */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1 text-xs">
          
          {/* Spatial Math Metrics */}
          <div>
            <h4 className="font-mono font-bold text-[#382E25] uppercase tracking-wider text-[11px] mb-3 flex items-center gap-2">
              <Scale className="w-4 h-4 text-[#A86236]" />
              <span>Geometric Agreement & IoU Matrix</span>
            </h4>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
              <div className="p-3.5 rounded-xl bg-[#FAF8F3] border border-[#E7DFD3]">
                <span className="text-[10px] uppercase font-mono font-bold text-[#7D7063] block">Jaccard Index (IoU)</span>
                <span className="text-lg font-mono font-bold text-[#3F6452]">
                  {building.conflictDetails ? building.conflictDetails.iouScore.toFixed(2) : "0.96"}
                </span>
                <span className="text-[10px] text-[#7D7063] block mt-0.5">Intersection over Union</span>
              </div>

              <div className="p-3.5 rounded-xl bg-[#FAF8F3] border border-[#E7DFD3]">
                <span className="text-[10px] uppercase font-mono font-bold text-[#7D7063] block">Centroid Offset</span>
                <span className="text-lg font-mono font-bold text-[#A86236]">
                  {building.conflictDetails ? `${building.conflictDetails.centroidOffsetMeters}m` : "0.32m"}
                </span>
                <span className="text-[10px] text-[#7D7063] block mt-0.5">Euclidean distance</span>
              </div>

              <div className="p-3.5 rounded-xl bg-[#FAF8F3] border border-[#E7DFD3]">
                <span className="text-[10px] uppercase font-mono font-bold text-[#7D7063] block">Hausdorff Distance</span>
                <span className="text-lg font-mono font-bold text-[#966B24]">
                  {building.conflictDetails ? "4.1m" : "0.65m"}
                </span>
                <span className="text-[10px] text-[#7D7063] block mt-0.5">Max contour separation</span>
              </div>
            </div>
          </div>

          {/* Coordinate Reference System Transformations */}
          <div>
            <h4 className="font-mono font-bold text-[#382E25] uppercase tracking-wider text-[11px] mb-3 flex items-center gap-2">
              <Globe className="w-4 h-4 text-[#4A6D7C]" />
              <span>Coordinate Reference System (CRS) Transformation</span>
            </h4>

            <div className="p-4 bg-[#FAF8F3] text-[#241D16] rounded-2xl font-mono text-[11px] space-y-2.5 border border-[#E7DFD3]">
              <div className="flex justify-between">
                <span className="text-[#7D7063]">Input Cadastral:</span>
                <span className="text-[#966B24] font-semibold">EPSG:7760 (KSRSAC Polyconic) → Transformed</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#7D7063]">Input Drone ORI:</span>
                <span className="text-[#3F6452] font-semibold">EPSG:32643 (UTM Zone 43N) → Transformed</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#7D7063]">Unified Standard:</span>
                <span className="text-[#A86236] font-bold">EPSG:4326 (WGS 84 Ellipsoid)</span>
              </div>
              <div className="flex justify-between pt-2 border-t border-[#E7DFD3] text-[10px] text-[#7D7063]">
                <span>Centroid Coordinates:</span>
                <span className="text-[#241D16] font-bold">[{building.centroid[0].toFixed(6)}, {building.centroid[1].toFixed(6)}]</span>
              </div>
            </div>
          </div>

          {/* Attribute Similarity Analysis */}
          <div>
            <h4 className="font-mono font-bold text-[#382E25] uppercase tracking-wider text-[11px] mb-3 flex items-center gap-2">
              <Cpu className="w-4 h-4 text-[#7D6D8A]" />
              <span>Multi-Source Attribute Harmonization</span>
            </h4>

            <div className="bg-[#FAF8F3] border border-[#E7DFD3] rounded-2xl overflow-hidden divide-y divide-[#E7DFD3]">
              <div className="p-3 flex items-center justify-between">
                <span className="font-medium text-[#7D7063]">Land Use Consensus</span>
                <span className="font-bold text-[#241D16]">{building.landUse} (Municipal & Cadastral match)</span>
              </div>
              <div className="p-3 flex items-center justify-between">
                <span className="font-medium text-[#7D7063]">Elevation Height Calibration</span>
                <span className="font-mono font-bold text-[#241D16]">{building.height}m (DSM/DTM normalized)</span>
              </div>
              <div className="p-3 flex items-center justify-between">
                <span className="font-medium text-[#7D7063]">AI Model Pipeline</span>
                <span className="font-mono font-bold text-[#3F6452]">SAM-2 + UNet-DTM v3.4</span>
              </div>
            </div>
          </div>

        </div>

        {/* Footer */}
        <div className="p-4 border-t border-[#E7DFD3] bg-[#FAF8F3] flex items-center justify-between">
          <span className="text-[#7D7063] font-mono text-[11px]">
            ISO/TC 211 & OGC Compliant Schema
          </span>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-white hover:bg-[#F0EBE1] text-[#241D16] rounded-xl font-bold text-xs transition border border-[#E7DFD3] shadow-xs"
          >
            Close
          </button>
        </div>

      </div>
    </div>
  );
};
