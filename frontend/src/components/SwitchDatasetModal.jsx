import React, { useEffect } from 'react';
import { MessageSquarePlus, Database, ArrowRight, X, Sparkles } from 'lucide-react';

export default function SwitchDatasetModal({
  isOpen,
  targetDb,
  currentDbName,
  currentChatTitle,
  onConfirm,
  onClose,
  isDark = true,
}) {
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen || !targetDb) return null;

  return (
    <div 
      className="fixed inset-0 z-50 overflow-y-auto bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 animate-fadeIn"
      onClick={onClose}
    >
      <div 
        className={`w-full max-w-md rounded-2xl p-6 shadow-2xl border transition-all ${
          isDark ? 'bg-slate-900 border-slate-800 text-slate-100' : 'bg-white border-slate-200 text-slate-900'
        }`}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-indigo-500/10 border border-indigo-500/30 text-indigo-400">
              <MessageSquarePlus className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-semibold text-sm">Start New Conversation?</h3>
              <p className="text-xs text-slate-400">Switching data source</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors cursor-pointer"
            aria-label="Close modal"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content Body */}
        <div className="py-4 space-y-3.5">
          <p className="text-sm font-medium leading-relaxed">
            Do you want to create a new conversation using{' '}
            <span className="font-bold text-indigo-400">{targetDb.name}</span>?
          </p>

          {/* Context Comparison Card */}
          <div className={`p-3 rounded-xl border text-xs space-y-2.5 ${
            isDark ? 'bg-slate-950/70 border-slate-800/80' : 'bg-slate-50 border-slate-200'
          }`}>
            <div className="flex items-center justify-between text-slate-400">
              <span className="font-mono text-[10px] uppercase font-bold tracking-wider">Current Chat</span>
              <span className="font-mono text-[10px] uppercase font-bold tracking-wider text-indigo-400">New Chat</span>
            </div>

            <div className="flex items-center justify-between gap-2">
              <div className="flex-1 min-w-0 p-2.5 rounded-lg bg-slate-900/90 border border-slate-800">
                <div className="text-[11px] font-semibold truncate text-slate-200">
                  {currentChatTitle || 'Active Chat'}
                </div>
                <div className="text-[10px] text-slate-400 flex items-center gap-1 mt-0.5 truncate">
                  <Database className="w-3 h-3 text-slate-500 shrink-0" />
                  <span className="truncate">{currentDbName || 'Current Data Source'}</span>
                </div>
              </div>

              <ArrowRight className="w-4 h-4 text-indigo-400 shrink-0" />

              <div className="flex-1 min-w-0 p-2.5 rounded-lg bg-indigo-500/10 border border-indigo-500/30">
                <div className="text-[11px] font-semibold text-indigo-300 truncate">
                  New Conversation
                </div>
                <div className="text-[10px] text-indigo-400 flex items-center gap-1 mt-0.5 truncate">
                  <Sparkles className="w-3 h-3 text-indigo-400 shrink-0" />
                  <span className="truncate font-medium">{targetDb.name}</span>
                </div>
              </div>
            </div>

            <p className="text-[11px] text-slate-400 leading-normal pt-1 border-t border-slate-800/60">
              Each conversation is locked to one dataset. Your current conversation will remain saved in your sidebar history.
            </p>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center justify-end gap-2.5 pt-3 border-t border-slate-800">
          <button
            type="button"
            onClick={onClose}
            className={`px-3.5 py-2 rounded-xl text-xs font-medium transition-colors cursor-pointer border ${
              isDark
                ? 'bg-slate-800 hover:bg-slate-700 text-slate-300 border-slate-700'
                : 'bg-slate-100 hover:bg-slate-200 text-slate-700 border-slate-200'
            }`}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-xs shadow-indigo-600/30 transition-all cursor-pointer"
          >
            <MessageSquarePlus className="w-3.5 h-3.5" />
            <span>Create New Conversation</span>
          </button>
        </div>
      </div>
    </div>
  );
}

