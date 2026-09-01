import React from 'react';
import { User, Sparkles, Database } from 'lucide-react';
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

  const dbName = message.telemetry?.db_name || message.db_name;
  const hasSql = Boolean(message.sql);
  const hasData = Boolean(message.data && message.data.length > 0);

  // Combine telemetry with message error details if needed
  const telemetryData = {
    ...message.telemetry,
    status: message.telemetry?.status || message.status,
    error: message.telemetry?.error || (message.status === 'FAILED' ? message.content : null)
  };

  // AI Assistant Message (Clean Query + Data Output)
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
          {/* Database Source Badge */}
          {dbName && (
            <div className="flex items-center gap-1.5 mb-2.5">
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-medium bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                <Database className="w-3 h-3" />
                <span>{dbName}</span>
              </span>
            </div>
          )}

          {/* Conversational text fallback (only shown if no SQL/data exists, like a simple greeting) */}
          {!hasSql && !hasData && (
            <div className="text-sm leading-relaxed mb-2">
              <p className="whitespace-pre-wrap">{message.content}</p>
            </div>
          )}

          {/* 1. Generated SQL Query */}
          {hasSql && (
            <SqlCodeBlock sql={message.sql} isDark={isDark} />
          )}

          {/* 2. Direct Result Data Table */}
          {hasData && (
            <DataTable data={message.data} isDark={isDark} />
          )}

          {/* 3. Technical Details Popover (Includes Guardrail reason and Latency) */}
          <DetailsPopover telemetry={telemetryData} isDark={isDark} />
        </div>
      </div>
    </div>
  );
}
