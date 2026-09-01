import React, { useState } from 'react';
import { Database, X, Search, ChevronRight, ChevronDown, Table as TableIcon, Sparkles } from 'lucide-react';

export default function SchemaDrawer({ isOpen, onClose, tables, onSelectPrompt, isDark }) {
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedTable, setExpandedTable] = useState(tables.length > 0 ? tables[0].name : null);

  if (!isOpen) return null;

  const filteredTables = tables.filter(t => 
    t.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    t.cols.some(c => c.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-black/60 backdrop-blur-xs flex justify-end animate-fadeIn">
      <div 
        className={`w-full max-w-md h-full flex flex-col shadow-2xl transition-all border-l ${
          isDark ? 'bg-slate-900 border-slate-800 text-slate-100' : 'bg-white border-slate-200 text-slate-900'
        }`}
      >
        {/* Header */}
        <div className="p-4 border-b border-slate-700/40 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-indigo-500/10 border border-indigo-500/30 text-indigo-400">
              <Database className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm font-bold">Database Schema Explorer</h2>
              <p className="text-[11px] text-slate-400">Chinook SQLite • {tables.length} Tables Available</p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Search Bar */}
        <div className="p-3 border-b border-slate-700/30">
          <div className={`flex items-center gap-2 px-3 py-2 rounded-xl border text-xs ${
            isDark ? 'bg-slate-950 border-slate-800 focus-within:border-indigo-500' : 'bg-slate-50 border-slate-300 focus-within:border-indigo-500'
          }`}>
            <Search className="w-4 h-4 text-slate-400 shrink-0" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search tables or column names..."
              className="w-full bg-transparent focus:outline-none"
            />
          </div>
        </div>

        {/* Tables & Schema Accordion */}
        <div className="flex-1 overflow-y-auto p-4 space-y-2.5">
          {filteredTables.length === 0 ? (
            <div className="py-12 text-center text-xs text-slate-400">
              No matching tables or columns found.
            </div>
          ) : (
            filteredTables.map((t) => {
              const isExpanded = expandedTable === t.name;
              return (
                <div
                  key={t.name}
                  className={`border rounded-xl transition-all overflow-hidden ${
                    isDark ? 'border-slate-800 bg-slate-950/40' : 'border-slate-200 bg-slate-50'
                  }`}
                >
                  {/* Table Title Bar */}
                  <div
                    onClick={() => setExpandedTable(isExpanded ? null : t.name)}
                    className={`flex items-center justify-between px-3.5 py-3 cursor-pointer select-none transition-colors ${
                      isExpanded
                        ? isDark ? 'bg-slate-800/60' : 'bg-slate-200/50'
                        : isDark ? 'hover:bg-slate-800/30' : 'hover:bg-slate-100'
                    }`}
                  >
                    <div className="flex items-center gap-2.5 text-xs font-semibold">
                      <TableIcon className="w-4 h-4 text-indigo-400" />
                      <span>{t.name}</span>
                    </div>

                    <div className="flex items-center gap-2">
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 font-mono">
                        {t.cols.length} cols
                      </span>
                      {isExpanded ? <ChevronDown className="w-4 h-4 text-slate-400" /> : <ChevronRight className="w-4 h-4 text-slate-400" />}
                    </div>
                  </div>

                  {/* Expanded Columns List */}
                  {isExpanded && (
                    <div className="p-3 border-t border-slate-800/40 space-y-2">
                      <ul className="space-y-1 text-xs">
                        {t.cols.map((col, idx) => (
                          <li key={idx} className="flex items-center gap-2 py-0.5 px-2 rounded hover:bg-slate-800/20">
                            <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 shrink-0" />
                            <code className={`font-mono text-[11px] ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                              {col}
                            </code>
                          </li>
                        ))}
                      </ul>

                      {/* Quick Prompt Button */}
                      <button
                        onClick={() => {
                          onSelectPrompt(`Show me the top 5 records from the ${t.name} table.`);
                          onClose();
                        }}
                        className="w-full mt-2 flex items-center justify-center gap-1.5 py-1.5 px-3 rounded-lg text-xs font-medium bg-indigo-600/10 hover:bg-indigo-600/20 text-indigo-400 border border-indigo-500/20 transition-all cursor-pointer"
                      >
                        <Sparkles className="w-3.5 h-3.5" />
                        <span>Query `{t.name}` in Chat</span>
                      </button>
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>

        {/* Footer */}
        <div className={`p-4 border-t text-xs ${isDark ? 'border-slate-800 bg-slate-950/60 text-slate-400' : 'border-slate-200 bg-slate-100 text-slate-600'}`}>
          <p className="text-center text-[11px]">
            Tip: You can mention any column or table name directly in your natural questions.
          </p>
        </div>
      </div>
    </div>
  );
}
