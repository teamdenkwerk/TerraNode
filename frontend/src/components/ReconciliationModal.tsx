import React, { useState, useEffect, useRef } from 'react';
import { X, CheckCircle2, Loader2, Cpu, ArrowRight, Zap } from 'lucide-react';
import { Language } from '../types';
import { triggerReconcile, getReconcileStatus, ReconcileResponse } from '../api/geoReconciliationClient';

interface ReconciliationModalProps {
  onClose: () => void;
  language: Language;
  onComplete: (result?: { raw_feature_count?: number | null; canonical_entity_count?: number | null; review_queue_count?: number | null }) => void;
  uploadedFilePath?: string;
}

export const ReconciliationModal: React.FC<ReconciliationModalProps> = ({
  onClose,
  language,
  onComplete,
  uploadedFilePath,
}) => {
  const [status, setStatus] = useState<'starting' | 'running' | 'complete' | 'error'>('starting');
  const [result, setResult] = useState<ReconcileResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function start() {
      try {
        const started = await triggerReconcile(uploadedFilePath);
        if (cancelled) return;
        setStatus('running');

        pollRef.current = window.setInterval(async () => {
          try {
            const s = await getReconcileStatus(started.run_id);
            if (cancelled) return;
            if (s.status === 'complete') {
              setResult(s);
              setStatus('complete');
              if (pollRef.current) window.clearInterval(pollRef.current);
            }
          } catch (e) {
            if (cancelled) return;
            setError(e instanceof Error ? e.message : String(e));
            setStatus('error');
            if (pollRef.current) window.clearInterval(pollRef.current);
          }
        }, 3000);
      } catch (e) {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : String(e));
        setStatus('error');
      }
    }

    start();
    return () => {
      cancelled = true;
      if (pollRef.current) window.clearInterval(pollRef.current);
    };
  }, [uploadedFilePath]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-white rounded-3xl shadow-2xl border border-[#E7DFD3] w-full max-w-lg overflow-hidden flex flex-col max-h-[92vh] text-[#241D16]">

        {/* Header */}
        <div className="p-5 border-b border-[#E7DFD3] flex items-center justify-between bg-[#FAF8F3]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-[#FDF1EB] border border-[#F3CEBD] flex items-center justify-center text-[#A86236] shadow-xs">
              <Cpu className={`w-5 h-5 ${status === 'running' || status === 'starting' ? 'animate-pulse text-[#A86236]' : ''}`} />
            </div>
            <div>
              <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-[#A86236]">
                TERRANODE Autonomous Core
              </span>
              <h3 className="text-lg font-bold text-[#241D16]">Harmonizing Spatial Entities</h3>
            </div>
          </div>
          <button onClick={onClose} className="p-2 rounded-xl text-[#7D7063] hover:text-[#241D16] hover:bg-[#FAF8F3] transition cursor-pointer">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 overflow-y-auto space-y-5 flex-1">
          {status === 'error' && (
            <div className="p-4 rounded-2xl border border-[#F3CEBD] bg-[#FDF1EB] text-[#C87958] text-xs">
              Reconciliation execution encountered an error: {error}
            </div>
          )}

          {(status === 'starting' || status === 'running') && (
            <div className="bg-[#FAF8F3] text-[#241D16] rounded-2xl p-6 border border-[#E7DFD3] flex flex-col items-center gap-3 text-center">
              <div className="relative">
                <div className="w-12 h-12 rounded-full border-2 border-[#A86236]/20 border-t-[#A86236] animate-spin" />
                <Zap className="w-5 h-5 text-[#A86236] absolute inset-0 m-auto" />
              </div>
              <span className="text-sm font-bold text-[#241D16]">
                {status === 'starting' ? 'Initializing spatial consensus engine…' : 'Running AI reconciliation pipeline across cadastral & imagery vectors'}
              </span>
              <span className="text-[11px] text-[#7D7063]">
                Executing CRS normalization, polygon overlay computation, and IoU threshold clustering. Updates poll every 3s.
              </span>
            </div>
          )}

          {status === 'complete' && result && (
            <div className="space-y-4">
              <div className="flex items-center gap-2 text-[#3F6452] font-bold text-sm bg-[#EAF2EB] p-3 rounded-xl border border-[#C5DAC9]">
                <CheckCircle2 className="w-5 h-5 text-[#3F6452]" />
                <span>Consensus Pipeline Execution Succeeded</span>
              </div>
              <div className="grid grid-cols-3 gap-2.5 text-xs">
                <div className="bg-[#FAF8F3] border border-[#E7DFD3] p-3 rounded-xl">
                  <span className="text-[10px] uppercase font-mono font-bold text-[#7D7063] block">Raw Features</span>
                  <span className="text-lg font-mono font-bold text-[#241D16] mt-0.5">{result.raw_feature_count ?? '—'}</span>
                </div>
                <div className="bg-[#EAF2EB] border border-[#C5DAC9] p-3 rounded-xl">
                  <span className="text-[10px] uppercase font-mono font-bold text-[#3F6452] block">Canonical Entities</span>
                  <span className="text-lg font-mono font-bold text-[#3F6452] mt-0.5">{result.canonical_entity_count ?? '—'}</span>
                </div>
                <div className="bg-[#FAF3E6] border border-[#EDDCBA] p-3 rounded-xl">
                  <span className="text-[10px] uppercase font-mono font-bold text-[#966B24] block">Needs Review</span>
                  <span className="text-lg font-mono font-bold text-[#966B24] mt-0.5">{result.review_queue_count ?? '—'}</span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-[#E7DFD3] flex items-center justify-end bg-[#FAF8F3]">
          <button
            onClick={() => { onComplete(result ?? undefined); onClose(); }}
            disabled={status !== 'complete'}
            className="px-5 py-2.5 rounded-xl bg-[#A86236] hover:bg-[#8F4F28] disabled:opacity-40 disabled:cursor-not-allowed text-white text-xs font-bold shadow-xs transition active:scale-95 flex items-center gap-2 cursor-pointer"
          >
            <span>Apply Results & View Map</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
};