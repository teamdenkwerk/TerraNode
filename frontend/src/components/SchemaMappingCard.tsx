import React, { useState } from 'react';
import {
  CheckCircle2,
  AlertTriangle,
  HelpCircle,
  Sparkles,
  Lock,
  RotateCcw,
  Check,
  ChevronDown,
  Info,
  Layers,
  ArrowRight,
  ShieldAlert
} from 'lucide-react';
import {
  SchemaMappingResponse,
  FieldMappingSuggestion,
  ConfirmedSchemaRecord
} from '../types';
import { confirmSchemaMapping } from '../api/geoReconciliationClient';

interface SchemaMappingCardProps {
  mapping: SchemaMappingResponse;
  datasetName?: string;
  onConfirmSuccess?: (record: ConfirmedSchemaRecord) => void;
  onClose?: () => void;
}

const CANONICAL_FIELD_OPTIONS = [
  { value: 'parcel_id', label: 'parcel_id (Cadastral / Land ID)' },
  { value: 'survey_number', label: 'survey_number (Revenue Khasra / CTS / Sy No)' },
  { value: 'property_id', label: 'property_id (Municipal Tax / PID)' },
  { value: 'area', label: 'area (Reported or computed m² / sqft)' },
  { value: 'geometry', label: 'geometry (Polygonal spatial boundary)' },
  { value: 'latitude', label: 'latitude (Centroid North Coordinate)' },
  { value: 'longitude', label: 'longitude (Centroid East Coordinate)' },
  { value: 'source', label: 'source (Dataset provenance / layer type)' },
  { value: 'date', label: 'date (Survey or capture timestamp)' },
  { value: 'owner_reference', label: 'owner_reference (Owner or taxpayer record)' },
];

export const SchemaMappingCard: React.FC<SchemaMappingCardProps> = ({
  mapping: initialMapping,
  datasetName,
  onConfirmSuccess,
  onClose,
}) => {
  // Current user selections: source_field -> canonical_field (or empty string for unmapped)
  const [selectedMappings, setSelectedMappings] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {};
    for (const m of initialMapping.mappings) {
      init[m.source_field] = m.suggested_canonical_field || '';
    }
    return init;
  });

  const [officerNotes, setOfficerNotes] = useState<string>('');
  const [officerName, setOfficerName] = useState<string>('Field / Land Officer');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [confirmedRecord, setConfirmedRecord] = useState<ConfirmedSchemaRecord | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleFieldChange = (sourceField: string, canonicalField: string) => {
    setSelectedMappings(prev => ({
      ...prev,
      [sourceField]: canonicalField,
    }));
  };

  const handleResetToSuggested = () => {
    const init: Record<string, string> = {};
    for (const m of initialMapping.mappings) {
      init[m.source_field] = m.suggested_canonical_field || '';
    }
    setSelectedMappings(init);
    setConfirmedRecord(null);
  };

  const handleConfirm = async () => {
    setIsSubmitting(true);
    setErrorMsg(null);
    try {
      const payloadMappings: Record<string, string | null> = {};
      for (const [src, tgt] of Object.entries(selectedMappings)) {
        payloadMappings[src] = tgt.trim() === '' ? null : tgt.trim();
      }

      const res = await confirmSchemaMapping(initialMapping.dataset_id, {
        dataset_version: initialMapping.dataset_version,
        confirmed_by: officerName || 'Field / Land Officer',
        mappings: payloadMappings,
        notes: officerNotes || undefined,
      });

      setConfirmedRecord(res);
      if (onConfirmSuccess) {
        onConfirmSuccess(res);
      }
    } catch (err: any) {
      setErrorMsg(err?.message || 'Failed to submit schema confirmation to backend.');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Compute live conflicts and counts
  const targetCounts: Record<string, number> = {};
  for (const [src, tgt] of Object.entries(selectedMappings)) {
    if (tgt) {
      targetCounts[tgt] = (targetCounts[tgt] || 0) + 1;
    }
  }

  const mappedCount = Object.values(selectedMappings).filter(Boolean).length;
  const unmappedCount = initialMapping.mappings.length - mappedCount;
  const conflictCount = Object.values(targetCounts).filter(c => c > 1).length;

  return (
    <div className="p-6 rounded-3xl bg-white border-2 border-[#A86236]/30 shadow-md animate-in fade-in space-y-5">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-[#E7DFD3]">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-2xl bg-[#FDF1EB] text-[#A86236] border border-[#F3CEBD] flex items-center justify-center font-bold text-lg">
            <Sparkles className="w-5 h-5 text-[#A86236]" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-[#A86236] bg-[#FDF1EB] px-2 py-0.5 rounded-full border border-[#F3CEBD]">
                TERRANODE FEATURE 01
              </span>
              <span className="text-xs font-mono text-[#7D7063]">
                Dataset: {initialMapping.dataset_id} ({initialMapping.dataset_version})
              </span>
            </div>
            <h3 className="text-lg font-bold text-[#241D16] mt-0.5">
              Smart Schema Mapping & Semantic Equivalence
            </h3>
          </div>
        </div>

        {onClose && (
          <button
            onClick={onClose}
            className="text-xs text-[#7D7063] hover:text-[#241D16] underline self-start sm:self-auto cursor-pointer"
          >
            Dismiss
          </button>
        )}
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5 text-xs">
        <div className="p-3 rounded-2xl bg-[#FAF8F3] border border-[#E7DFD3]">
          <span className="text-[10px] font-mono font-bold uppercase text-[#7D7063] block">Total Attributes</span>
          <span className="text-base font-bold text-[#241D16] font-mono mt-0.5 block">{initialMapping.total_fields}</span>
          <span className="text-[10px] text-[#7D7063]">Source columns</span>
        </div>

        <div className="p-3 rounded-2xl bg-[#FAF8F3] border border-[#E7DFD3]">
          <span className="text-[10px] font-mono font-bold uppercase text-[#3F6452] block">Mapped Canonical</span>
          <span className="text-base font-bold text-[#3F6452] font-mono mt-0.5 block">{mappedCount}</span>
          <span className="text-[10px] text-[#7D7063]">Active targets</span>
        </div>

        <div className="p-3 rounded-2xl bg-[#FAF8F3] border border-[#E7DFD3]">
          <span className="text-[10px] font-mono font-bold uppercase text-[#7D7063] block">Unmapped</span>
          <span className="text-base font-bold text-[#7D7063] font-mono mt-0.5 block">{unmappedCount}</span>
          <span className="text-[10px] text-[#7D7063]">Ignored / Aux</span>
        </div>

        <div className="p-3 rounded-2xl bg-[#FAF8F3] border border-[#E7DFD3]">
          <span className="text-[10px] font-mono font-bold uppercase text-[#C87958] block">Low-Confidence</span>
          <span className="text-base font-bold text-[#C87958] font-mono mt-0.5 block">{initialMapping.low_confidence_fields_count}</span>
          <span className="text-[10px] text-[#7D7063]">Confidence &lt; 70%</span>
        </div>

        <div className="p-3 rounded-2xl bg-[#FAF8F3] border border-[#E7DFD3]">
          <span className="text-[10px] font-mono font-bold uppercase text-[#A86236] block">Conflicting</span>
          <span className="text-base font-bold text-[#A86236] font-mono mt-0.5 block">{conflictCount}</span>
          <span className="text-[10px] text-[#7D7063]">Competing fields</span>
        </div>
      </div>

      {/* Explanatory Policy Callout */}
      <div className="p-3.5 rounded-2xl bg-[#FAF8F3] border border-[#E7DFD3] text-xs text-[#241D16] flex items-start gap-3">
        <Info className="w-4 h-4 text-[#A86236] shrink-0 mt-0.5" />
        <div className="leading-relaxed">
          <strong>Non-Silent Mapping Guarantee:</strong> Low-confidence mappings (&lt;70%) and unknown attributes are never silently attached to canonical fields. Officers must explicitly review suggestions, adjust canonical assignments if needed, and confirm to persist.
        </div>
      </div>

      {/* Confirmed Banner */}
      {confirmedRecord && (
        <div className="p-4 rounded-2xl bg-[#EAF2EB] border border-[#C5DAC9] text-[#3F6452] flex items-center justify-between gap-3 animate-in fade-in">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-5 h-5 text-[#3F6452] shrink-0" />
            <div className="text-xs">
              <span className="font-bold block">Schema Mapping Confirmed & Locked</span>
              <span className="text-[11px] text-[#241D16]">
                Signed by <strong>{confirmedRecord.confirmed_by}</strong> on {confirmedRecord.confirmed_at} • Applied to {confirmedRecord.dataset_id}
              </span>
            </div>
          </div>
          <span className="px-2.5 py-1 rounded-full bg-[#3F6452] text-white text-[10px] font-mono font-bold uppercase">
            Audited v{confirmedRecord.dataset_version}
          </span>
        </div>
      )}

      {/* Error Banner */}
      {errorMsg && (
        <div className="p-3.5 rounded-2xl bg-[#FDF1EB] border border-[#C87958] text-[#8F4F28] text-xs flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-[#C87958] shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Mapping Table */}
      <div className="border border-[#E7DFD3] rounded-2xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="bg-[#FAF8F3] border-b border-[#E7DFD3] text-[#7D7063] font-mono font-bold uppercase tracking-wider text-[10px]">
                <th className="py-2.5 pl-3">Source Field (Raw)</th>
                <th className="py-2.5">Normalized Token</th>
                <th className="py-2.5">Canonical Target</th>
                <th className="py-2.5">Match Type</th>
                <th className="py-2.5">Confidence</th>
                <th className="py-2.5 pr-3">Sample Values / Logic</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E7DFD3] text-[#241D16]">
              {initialMapping.mappings.map((item) => {
                const currentSelected = selectedMappings[item.source_field] || '';
                const isConflict = currentSelected && (targetCounts[currentSelected] || 0) > 1;
                const isLowConf = item.is_low_confidence;
                const pct = Math.round(item.confidence * 100);

                let badgeColor = 'bg-[#FAF8F3] text-[#7D7063] border-[#E7DFD3]';
                if (item.match_type === 'EXACT') badgeColor = 'bg-[#EAF2EB] text-[#3F6452] border-[#C5DAC9]';
                else if (item.match_type === 'ABBREVIATION' || item.match_type === 'SYNONYM') badgeColor = 'bg-[#FDF1EB] text-[#A86236] border-[#F3CEBD]';
                else if (item.match_type === 'FUZZY_STRING') badgeColor = 'bg-[#FAF3E6] text-[#966B24] border-[#EDDCBA]';

                return (
                  <tr
                    key={item.source_field}
                    className={`hover:bg-[#FAF8F3] transition ${
                      isConflict ? 'bg-[#FDF1EB]/40' : ''
                    }`}
                  >
                    {/* Source Field */}
                    <td className="py-3 pl-3 align-top">
                      <div className="font-mono font-bold text-[#241D16]">{item.source_field}</div>
                      {isConflict && (
                        <span className="inline-flex items-center gap-1 text-[10px] text-[#C87958] font-bold mt-0.5">
                          <AlertTriangle className="w-3 h-3" /> Target conflict
                        </span>
                      )}
                    </td>

                    {/* Normalized Source Token */}
                    <td className="py-3 align-top font-mono text-[11px] text-[#7D7063]">
                      {item.normalized_source_field}
                    </td>

                    {/* Target Selector */}
                    <td className="py-3 align-top">
                      <select
                        value={currentSelected}
                        onChange={(e) => handleFieldChange(item.source_field, e.target.value)}
                        className={`w-full text-xs font-mono font-semibold py-1 px-2 rounded-lg border focus:ring-1 focus:ring-[#A86236] focus:outline-hidden cursor-pointer ${
                          currentSelected
                            ? isConflict
                              ? 'bg-[#FDF1EB] border-[#C87958] text-[#8F4F28]'
                              : 'bg-white border-[#E7DFD3] text-[#241D16]'
                            : 'bg-[#FAF8F3] border-[#E7DFD3] text-[#7D7063]'
                        }`}
                      >
                        <option value="">-- Ignore / Unmapped --</option>
                        {CANONICAL_FIELD_OPTIONS.map((opt) => (
                          <option key={opt.value} value={opt.value}>
                            {opt.label}
                          </option>
                        ))}
                      </select>
                    </td>

                    {/* Match Type */}
                    <td className="py-3 align-top">
                      <span className={`inline-block px-2 py-0.5 rounded-md text-[10px] font-mono font-bold border ${badgeColor}`}>
                        {item.match_type}
                      </span>
                    </td>

                    {/* Confidence Score */}
                    <td className="py-3 align-top">
                      <div className="space-y-1">
                        <div className="flex items-center justify-between text-[11px] font-mono">
                          <span className={`font-bold ${
                            pct >= 85 ? 'text-[#3F6452]' : pct >= 70 ? 'text-[#966B24]' : 'text-[#C87958]'
                          }`}>
                            {pct}%
                          </span>
                        </div>
                        <div className="w-20 bg-[#E7DFD3] h-1.5 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all duration-300 ${
                              pct >= 85 ? 'bg-[#3F6452]' : pct >= 70 ? 'bg-[#D9A036]' : 'bg-[#C87958]'
                            }`}
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                        {isLowConf && (
                          <span className="text-[9px] text-[#C87958] font-bold block uppercase tracking-tight">
                            Low Conf
                          </span>
                        )}
                      </div>
                    </td>

                    {/* Sample Values & Decision Reason */}
                    <td className="py-3 pr-3 align-top space-y-1">
                      {item.sample_values && item.sample_values.length > 0 && (
                        <div className="flex flex-wrap gap-1">
                          {item.sample_values.slice(0, 3).map((val, idx) => (
                            <span
                              key={idx}
                              className="px-1.5 py-0.5 rounded bg-[#FAF8F3] border border-[#E7DFD3] text-[10px] font-mono text-[#7D7063]"
                            >
                              {String(val)}
                            </span>
                          ))}
                        </div>
                      )}
                      <div className="text-[11px] text-[#7D7063] leading-tight">
                        {item.decision_reason}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Confirmation & Officer Controls */}
      <div className="p-4 rounded-2xl bg-[#FAF8F3] border border-[#E7DFD3] flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex flex-col sm:flex-row items-center gap-3 w-full sm:w-auto">
          <div>
            <label className="text-[10px] font-mono font-bold uppercase text-[#7D7063] block mb-1">
              Confirming Officer
            </label>
            <input
              type="text"
              value={officerName}
              onChange={(e) => setOfficerName(e.target.value)}
              placeholder="Officer Name / Role"
              className="text-xs py-1.5 px-3 rounded-xl border border-[#E7DFD3] bg-white font-medium text-[#241D16] focus:ring-1 focus:ring-[#A86236] focus:outline-hidden"
            />
          </div>

          <div className="w-full sm:w-72">
            <label className="text-[10px] font-mono font-bold uppercase text-[#7D7063] block mb-1">
              Officer Notes / Justification
            </label>
            <input
              type="text"
              value={officerNotes}
              onChange={(e) => setOfficerNotes(e.target.value)}
              placeholder="e.g., Verified against local revenue record standards"
              className="text-xs py-1.5 px-3 rounded-xl border border-[#E7DFD3] bg-white font-medium text-[#241D16] w-full focus:ring-1 focus:ring-[#A86236] focus:outline-hidden"
            />
          </div>
        </div>

        <div className="flex items-center gap-2.5 w-full sm:w-auto justify-end">
          <button
            type="button"
            onClick={handleResetToSuggested}
            className="px-3 py-2 rounded-xl border border-[#E7DFD3] bg-white text-xs font-semibold text-[#7D7063] hover:text-[#241D16] hover:bg-[#F3EFE6] transition cursor-pointer flex items-center gap-1.5"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Reset</span>
          </button>

          <button
            type="button"
            onClick={handleConfirm}
            disabled={isSubmitting}
            className={`px-5 py-2 rounded-xl bg-[#A86236] hover:bg-[#8F4F28] text-white text-xs font-bold shadow-xs transition active:scale-95 cursor-pointer flex items-center gap-2 ${
              isSubmitting ? 'opacity-60 pointer-events-none' : ''
            }`}
          >
            <Lock className="w-3.5 h-3.5" />
            <span>{isSubmitting ? 'Persisting Audit Record…' : 'Confirm & Lock Schema Mappings'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
