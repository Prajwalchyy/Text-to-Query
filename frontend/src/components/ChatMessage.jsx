import React from 'react';
import { User, Sparkles, Database, AlertCircle, Lightbulb, ArrowRight, Inbox } from 'lucide-react';
import SqlCodeBlock from './SqlCodeBlock';
import DataTable from './DataTable';
import JsonDocumentViewer from './JsonDocumentViewer';
import DetailsPopover from './DetailsPopover';

export default function ChatMessage({ message, isDark, onSelectPrompt }) {
  const [activeSubIndex, setActiveSubIndex] = React.useState(0);
  const isUser = message.role === 'user';

  if (isUser) {
    return (
      <div className="flex justify-end mb-6 w-full animate-fadeIn">
        <div className="flex items-start gap-3 max-w-3xl">
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

  const isOutOfDomain = message.status === 'OUT_OF_DOMAIN';
  const neededTables = message.needed_tables || message.telemetry?.needed_tables || [];
  const availableTables = message.available_tables || message.telemetry?.available_tables || [];
  const suggestedQuestions = message.suggested_questions || message.telemetry?.suggested_questions || [];

  const subQueries = (message.sub_queries && message.sub_queries.length > 1) ? message.sub_queries : null;
  const currentSub = subQueries ? (subQueries[activeSubIndex] || subQueries[0]) : null;

  const currentSql = currentSub ? currentSub.sql : message.sql;
  const currentData = currentSub ? currentSub.data : message.data;

  const dbName = message.telemetry?.db_name || message.db_name;
  const hasSql = Boolean(currentSql);
  const hasData = Boolean(currentData && currentData.length > 0);

  const isNoSql = Boolean(
    message.telemetry?.db_type === 'nosql' ||
    (currentSql && (
      currentSql.trim().startsWith("db.") || 
      currentSql.trim().startsWith("[") || 
      currentSql.trim().startsWith("{")
    ))
  );

  // Combine telemetry with message error details if needed
  const telemetryData = {
    ...message.telemetry,
    status: message.telemetry?.status || message.status,
    error: message.telemetry?.error || (message.status === 'FAILED' ? message.content : null)
  };

  // AI Assistant Message (Clean Query + Data Output OR Out-of-Domain Explanation)
  return (
    <div className="flex justify-start mb-6 w-full animate-fadeIn">
      <div className="flex items-start gap-3 max-w-5xl xl:max-w-6xl w-full min-w-0">
        <div className={`p-2 rounded-xl shrink-0 mt-1 ${
          isOutOfDomain
            ? 'bg-amber-500/10 border border-amber-500/30 text-amber-400'
            : isDark 
              ? 'bg-indigo-500/10 border border-indigo-500/30 text-indigo-400' 
              : 'bg-indigo-50 border border-indigo-200 text-indigo-600'
        }`}>
          {isOutOfDomain ? <AlertCircle className="w-4 h-4" /> : <Sparkles className="w-4 h-4" />}
        </div>

        <div className={`flex-1 min-w-0 p-5 rounded-2xl border transition-colors shadow-sm overflow-hidden ${
          isDark 
            ? 'bg-slate-900/60 border-slate-800/90 text-slate-200' 
            : 'bg-white border-slate-200/90 text-slate-800'
        }`}>
          {/* Database Source Badge */}
          {dbName && (
            <div className="flex items-center gap-1.5 mb-2.5">
              <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-medium border ${
                isOutOfDomain
                  ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                  : isNoSql 
                    ? 'bg-amber-500/10 text-amber-400 border-amber-500/20' 
                    : 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20'
              }`}>
                <Database className="w-3 h-3" />
                <span>{dbName} {isNoSql ? '(NoSQL)' : ''}</span>
              </span>
            </div>
          )}

          {/* 🌟 OUT-OF-DOMAIN SCHEMA MISMATCH CARD */}
          {isOutOfDomain ? (
            <div className="space-y-4">
              {/* Notice Box */}
              <div className={`p-4 rounded-xl border ${
                isDark 
                  ? 'bg-amber-500/10 border-amber-500/25 text-amber-200' 
                  : 'bg-amber-50/80 border-amber-200 text-amber-900'
              }`}>
                <div className="flex items-start gap-2.5">
                  <AlertCircle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
                  <div>
                    <h4 className="text-xs font-bold uppercase tracking-wider text-amber-400 mb-1">
                      Schema Mismatch • Question Out of Domain
                    </h4>
                    <p className="text-sm leading-relaxed font-normal">
                      {message.content}
                    </p>
                  </div>
                </div>
              </div>

              {/* Missing Tables vs Available Tables Comparison */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
                {neededTables.length > 0 && (
                  <div className={`p-3 rounded-xl border ${
                    isDark ? 'bg-slate-800/40 border-slate-700/60' : 'bg-slate-50 border-slate-200'
                  }`}>
                    <div className="text-[11px] font-bold text-rose-400 mb-2 flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-rose-500" />
                      <span>Required Tables (Missing):</span>
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {neededTables.map((tbl, i) => (
                        <span 
                          key={i} 
                          className="px-2 py-0.5 rounded-md text-xs font-mono font-medium bg-rose-500/10 text-rose-400 border border-rose-500/20"
                        >
                          {tbl}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {availableTables.length > 0 && (
                  <div className={`p-3 rounded-xl border ${
                    isDark ? 'bg-slate-800/40 border-slate-700/60' : 'bg-slate-50 border-slate-200'
                  }`}>
                    <div className="text-[11px] font-bold text-indigo-400 mb-2 flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-indigo-500" />
                      <span>Available in {dbName || 'Database'}:</span>
                    </div>
                    <div className="flex flex-wrap gap-1.5 max-h-28 overflow-y-auto custom-scrollbar">
                      {availableTables.map((tbl, i) => (
                        <span 
                          key={i} 
                          className="px-2 py-0.5 rounded-md text-xs font-mono font-medium bg-indigo-500/10 text-indigo-400 border border-indigo-500/20"
                        >
                          {tbl}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Clickable Suggested Questions */}
              {suggestedQuestions.length > 0 && (
                <div className="pt-2">
                  <div className="text-xs font-semibold text-slate-400 mb-2 flex items-center gap-1.5">
                    <Lightbulb className="w-3.5 h-3.5 text-amber-400" />
                    <span>Try asking questions related to this database:</span>
                  </div>
                  <div className="flex flex-col gap-2">
                    {suggestedQuestions.map((q, idx) => (
                      <button
                        key={idx}
                        onClick={() => onSelectPrompt && onSelectPrompt(q)}
                        className={`text-left px-3.5 py-2.5 rounded-xl text-xs font-medium transition-all flex items-center justify-between group cursor-pointer border ${
                          isDark 
                            ? 'bg-slate-800/60 hover:bg-indigo-950/40 text-slate-300 hover:text-indigo-300 border-slate-700/70 hover:border-indigo-500/40' 
                            : 'bg-slate-100 hover:bg-indigo-50 text-slate-700 hover:text-indigo-700 border-slate-200 hover:border-indigo-200'
                        }`}
                      >
                        <span className="leading-relaxed">{q}</span>
                        <ArrowRight className="w-3.5 h-3.5 opacity-0 group-hover:opacity-100 transition-opacity text-indigo-400 shrink-0 ml-2" />
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <>
              {/* Conversational text fallback */}
              {!hasSql && !hasData && (
                <div className="text-sm leading-relaxed mb-2">
                  <p className="whitespace-pre-wrap">{message.content}</p>
                </div>
              )}

              {/* Multi-Query Interactive Sub-Tabs for Compound Prompts */}
              {subQueries && subQueries.length > 1 && (
                <div className="mb-3.5">
                  <div className="flex items-center gap-2 mb-1.5 text-xs text-slate-400 font-medium">
                    <span>Multi-Query Reports:</span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 font-mono font-bold">
                      {subQueries.length} Parts
                    </span>
                  </div>
                  <div className="flex items-center gap-2 overflow-x-auto pb-1.5 custom-scrollbar">
                    {subQueries.map((sub, idx) => {
                      const isSelected = activeSubIndex === idx;
                      const rowCount = sub.data?.length || 0;
                      return (
                        <button
                          key={idx}
                          onClick={() => setActiveSubIndex(idx)}
                          className={`px-3 py-1.5 rounded-xl text-xs font-semibold flex items-center gap-2 transition-all cursor-pointer whitespace-nowrap ${
                            isSelected
                              ? 'bg-indigo-600 text-white shadow-sm ring-2 ring-indigo-500/30'
                              : isDark
                                ? 'bg-slate-800/80 hover:bg-slate-700/80 text-slate-300 border border-slate-700/60'
                                : 'bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200'
                          }`}
                        >
                          <span className={`w-4 h-4 rounded-full flex items-center justify-center text-[10px] font-bold ${
                            isSelected ? 'bg-white/25 text-white' : 'bg-slate-700 text-slate-300'
                          }`}>
                            {idx + 1}
                          </span>
                          <span className="truncate max-w-[220px]">{sub.title || `Query ${idx + 1}`}</span>
                          <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-mono ${
                            isSelected ? 'bg-indigo-700/80 text-white' : 'bg-slate-700/40 text-slate-400'
                          }`}>
                            {rowCount} rows
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* 1. Generated SQL / MQL Query Block */}
              {hasSql && (
                <SqlCodeBlock sql={currentSql} isDark={isDark} />
              )}

              {/* 2. Direct Result Data Output: JSON Document Viewer for NoSQL, Data Table for SQL, or 0 Records Found */}
              {hasData ? (
                isNoSql ? (
                  <JsonDocumentViewer data={currentData} isDark={isDark} />
                ) : (
                  <DataTable data={currentData} isDark={isDark} />
                )
              ) : (
                hasSql && (
                  <div className={`mt-3 px-3.5 py-2.5 rounded-xl border flex items-center gap-2 text-xs font-medium ${
                    isDark 
                      ? 'bg-slate-800/40 border-slate-700/60 text-slate-400' 
                      : 'bg-slate-100/80 border-slate-200 text-slate-600'
                  }`}>
                    <Inbox className="w-4 h-4 text-slate-400 shrink-0" />
                    <span>0 records found</span>
                  </div>
                )
              )}
            </>
          )}

          {/* 3. Technical Details Popover (Includes Guardrail reason and Latency) */}
          <DetailsPopover telemetry={telemetryData} isDark={isDark} />
        </div>
      </div>
    </div>
  );
}
