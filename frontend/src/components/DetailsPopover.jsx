import React, { useState, useEffect, useRef } from 'react';
import { Info, ShieldCheck, CheckCircle2, AlertTriangle, X } from 'lucide-react';

export default function DetailsPopover({ telemetry, isDark }) {
  const [isOpen, setIsOpen] = useState(false);
  const popoverRef = useRef(null);

  // Auto-close when clicking outside
  useEffect(() => {
    function handleClickOutside(event) {
      if (popoverRef.current && !popoverRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  if (!telemetry) return null;

  const { confidence_score = 0, latency_ms = 0, attempts = 1, status = "SUCCESS" } = telemetry;
  const confidencePercent = Math.round(confidence_score * 100);
  const latencySec = (latency_ms / 1000).toFixed(2);

  return (
    <div className="relative inline-block mt-3" ref={popoverRef}>
      {/* Subtle trigger button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium transition-all cursor-pointer ${
          isDark
            ? 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
            : 'text-slate-500 hover:text-slate-800 hover:bg-slate-200/60'
        }`}
        aria-label="View response technical details"
      >
        <Info className="w-3.5 h-3.5 text-indigo-400" />
        <span>Response Details</span>
      </button>

      {/* Floating details card */}
      {isOpen && (
        <div
          className={`absolute left-0 bottom-8 z-50 w-72 rounded-xl p-4 shadow-xl border backdrop-blur-md transition-all text-xs ${
            isDark
              ? 'bg-slate-900/95 border-slate-700/80 text-slate-200 shadow-black/50'
              : 'bg-white/95 border-slate-200 text-slate-800 shadow-slate-300/50'
          }`}
        >
          {/* Header */}
          <div className="flex items-center justify-between pb-2 mb-3 border-b border-slate-700/40">
            <span className="font-semibold flex items-center gap-1.5 text-slate-300">
              <ShieldCheck className="w-4 h-4 text-indigo-400" /> Technical Details
            </span>
            <button
              onClick={() => setIsOpen(false)}
              className="text-slate-400 hover:text-slate-200 p-0.5 rounded cursor-pointer"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Key Metric Rows */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-slate-400">Confidence Score:</span>
              <span className={`font-mono font-bold ${confidencePercent >= 80 ? 'text-emerald-400' : 'text-amber-400'}`}>
                {confidencePercent}%
              </span>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-slate-400">Pipeline Latency:</span>
              <span className="font-mono font-medium">{latencySec}s ({latency_ms} ms)</span>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-slate-400">Correction Attempts:</span>
              <span className="font-mono font-medium">{attempts} / 3</span>
            </div>

            <div className="flex items-center justify-between pt-1 border-t border-slate-700/30">
              <span className="text-slate-400">Execution Status:</span>
              <div className="flex items-center gap-1">
                {status === "SUCCESS" ? (
                  <>
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    <span className="font-semibold text-emerald-400">Successful</span>
                  </>
                ) : (
                  <>
                    <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />
                    <span className="font-semibold text-rose-400">Blocked / Failed</span>
                  </>
                )}
              </div>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-slate-400">Guardrails:</span>
              <span className="text-emerald-400 font-medium">AST & Allowlist Passed</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
