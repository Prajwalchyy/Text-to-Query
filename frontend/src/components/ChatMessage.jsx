import React from 'react';
import { User, Sparkles, AlertTriangle } from 'lucide-react';
import SqlCodeBlock from './SqlCodeBlock';
import DataTable from './DataTable';
import DetailsPopover from './DetailsPopover';

export default function ChatMessage({ message, isDark }) {
  const isUser = message.role === 'user';

  if (isUser) {
    return (
      <div className="flex justify-end mb-6 w-full animate-fadeIn">
        <div className="flex items-start gap-3 max-w-2xl">
          <div className={`p-4 rounded-2xl text-sm leading-relaxed ${
            isDark 
              ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/20' 
              : 'bg-indigo-600 text-white shadow-sm'
          }`}>
            <p className="whitespace-pre-wrap">{message.content}</p>
          </div>
          <div className={`p-2 rounded-xl shrink-0 mt-0.5 ${
            isDark ? 'bg-slate-800 text-indigo-300' : 'bg-slate-200 text-indigo-600'
          }`}>
            <User className="w-4 h-4" />
          </div>
        </div>
      </div>
    );
  }

  // AI Assistant Message
  return (
    <div className="flex justify-start mb-6 w-full animate-fadeIn">
      <div className="flex items-start gap-3 max-w-3xl w-full">
        <div className={`p-2 rounded-xl shrink-0 mt-1 ${
          isDark 
            ? 'bg-indigo-500/10 border border-indigo-500/30 text-indigo-400' 
            : 'bg-indigo-50 border border-indigo-200 text-indigo-600'
        }`}>
          <Sparkles className="w-4 h-4" />
        </div>

        <div className={`flex-1 p-5 rounded-2xl border transition-colors shadow-sm ${
          isDark 
            ? 'bg-slate-900/60 border-slate-800/90 text-slate-200' 
            : 'bg-white border-slate-200/90 text-slate-800'
        }`}>
          {/* Security alert banner if blocked */}
          {message.status === 'FAILED' && (
            <div className="mb-3 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-xs text-rose-400 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>Query intercepted by AST guardrails. Destructive operation blocked.</span>
            </div>
          )}

          {/* 1. Plain English Answer / Explanation */}
          <div className="text-sm leading-relaxed prose prose-invert max-w-none">
            <p className="whitespace-pre-wrap">{message.content}</p>
          </div>

          {/* 2. Generated SQL Code Block */}
          {message.sql && (
            <SqlCodeBlock sql={message.sql} isDark={isDark} />
          )}

          {/* 3. Query Results Table (Collapsible) */}
          {message.data && message.data.length > 0 && (
            <DataTable data={message.data} isDark={isDark} />
          )}

          {/* 4. Low-priority Technical Details Popover */}
          <DetailsPopover telemetry={message.telemetry} isDark={isDark} />
        </div>
      </div>
    </div>
  );
}
