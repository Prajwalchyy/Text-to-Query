import React, { useState, useRef, useEffect, useMemo } from 'react';
import { 
  Database, FileJson, ChevronDown, Check, Plus, Search, 
  Layers, Sparkles, FileSpreadsheet, Table2
} from 'lucide-react';

export default function DatabaseSelectorPopover({
  databases = [],
  selectedDbId,
  onSelectDb,
  onOpenUpload,
  isDark
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const popoverRef = useRef(null);
  const searchInputRef = useRef(null);

  // Active database object
  const currentDb = useMemo(() => {
    return databases.find(d => d.id === selectedDbId) || databases[0] || { 
      name: "Select Database", 
      type: "sql", 
      table_count: 0 
    };
  }, [databases, selectedDbId]);

  const isCurrentNoSql = currentDb.type === 'nosql';

  // Filter databases by search query
  const filteredDbs = useMemo(() => {
    if (!searchQuery.trim()) return databases;
    const q = searchQuery.toLowerCase();
    return databases.filter(d => 
      (d.name && d.name.toLowerCase().includes(q)) || 
      (d.filename && d.filename.toLowerCase().includes(q))
    );
  }, [databases, searchQuery]);

  const sqlDatabases = filteredDbs.filter(d => d.type !== 'nosql');
  const noSqlDatabases = filteredDbs.filter(d => d.type === 'nosql');

  // Handle outside click to close
  useEffect(() => {
    const handleOutsideClick = (e) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    };

    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleOutsideClick);
      document.addEventListener('keydown', handleKeyDown);
      // Auto-focus search input
      setTimeout(() => searchInputRef.current?.focus(), 50);
    }

    return () => {
      document.removeEventListener('mousedown', handleOutsideClick);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen]);

  const handleSelect = (dbId) => {
    onSelectDb(dbId);
    setIsOpen(false);
    setSearchQuery('');
  };

  const handleUploadClick = () => {
    setIsOpen(false);
    onOpenUpload();
  };

  return (
    <div className="relative inline-block text-left" ref={popoverRef}>
      {/* TRIGGER BUTTON */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`flex items-center gap-2.5 px-3 py-1.5 rounded-xl border text-xs font-semibold transition-all cursor-pointer shadow-xs ${
          isOpen
            ? 'border-indigo-500 ring-2 ring-indigo-500/20'
            : isDark 
              ? 'bg-slate-900/90 border-slate-700/80 hover:border-slate-600 text-slate-200' 
              : 'bg-white border-slate-300 hover:border-slate-400 text-slate-800'
        }`}
        title="Switch data source"
      >
        {/* Type Icon */}
        <div className={`p-1 rounded-lg ${
          isCurrentNoSql 
            ? 'bg-amber-500/15 text-amber-400' 
            : 'bg-indigo-500/15 text-indigo-400'
        }`}>
          {isCurrentNoSql ? (
            <FileJson className="w-3.5 h-3.5" />
          ) : (
            <Database className="w-3.5 h-3.5" />
          )}
        </div>

        {/* Database Name & Count */}
        <div className="flex items-center gap-1.5 text-left truncate max-w-[170px] sm:max-w-[210px]">
          <span className="truncate">{currentDb.name}</span>
          <span className={`px-1.5 py-0.2 rounded text-[10px] font-mono shrink-0 ${
            isCurrentNoSql 
              ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' 
              : 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20'
          }`}>
            {isCurrentNoSql ? `${currentDb.doc_count || 0} docs` : `${currentDb.table_count || 0} tables`}
          </span>
        </div>

        {/* Rotating Chevron */}
        <ChevronDown className={`w-3.5 h-3.5 text-slate-400 shrink-0 transition-transform duration-200 ${
          isOpen ? 'rotate-180 text-indigo-400' : ''
        }`} />
      </button>

      {/* FLOATING POPOVER MODAL */}
      {isOpen && (
        <div className={`absolute right-0 top-full mt-2 w-80 sm:w-96 rounded-2xl shadow-2xl border backdrop-blur-md z-50 overflow-hidden animate-fadeIn ${
          isDark 
            ? 'bg-slate-900/95 border-slate-700/80 text-slate-100 shadow-black/60' 
            : 'bg-white/95 border-slate-200 text-slate-900 shadow-slate-300/60'
        }`}>
          {/* POPOVER HEADER */}
          <div className={`px-4 py-3 border-b flex items-center justify-between ${
            isDark ? 'bg-slate-950/60 border-slate-800' : 'bg-slate-50 border-slate-200'
          }`}>
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-indigo-400" />
              <h4 className="text-xs font-bold uppercase tracking-wider">Select Data Source</h4>
            </div>
            <span className="text-[10px] text-slate-400 font-mono">
              {databases.length} sources
            </span>
          </div>

          {/* SEARCH BOX */}
          <div className="p-3 border-b border-slate-800/40">
            <div className="relative">
              <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-slate-400 pointer-events-none" />
              <input
                ref={searchInputRef}
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search databases by name..."
                className={`w-full pl-9 pr-3 py-1.5 text-xs rounded-xl border focus:outline-none focus:border-indigo-500 transition-colors ${
                  isDark 
                    ? 'bg-slate-950 border-slate-800 text-white placeholder-slate-500' 
                    : 'bg-slate-50 border-slate-200 text-slate-900 placeholder-slate-400'
                }`}
              />
            </div>
          </div>

          {/* DATABASE LISTING (CATEGORIZED) */}
          <div className="max-h-72 overflow-y-auto p-2 space-y-3 custom-scrollbar">
            {/* Section 1: Relational SQL Databases */}
            {sqlDatabases.length > 0 && (
              <div>
                <div className="flex items-center gap-1.5 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-indigo-400">
                  <Database className="w-3 h-3" />
                  <span>Relational SQL ({sqlDatabases.length})</span>
                </div>
                <div className="space-y-1 mt-0.5">
                  {sqlDatabases.map((db) => {
                    const isSelected = db.id === selectedDbId;
                    return (
                      <button
                        key={db.id}
                        onClick={() => handleSelect(db.id)}
                        className={`w-full flex items-center justify-between p-2.5 rounded-xl text-left transition-all cursor-pointer group ${
                          isSelected
                            ? isDark 
                              ? 'bg-indigo-600/20 border border-indigo-500/40 text-white shadow-xs' 
                              : 'bg-indigo-50 border border-indigo-200 text-indigo-950 shadow-xs'
                            : isDark 
                              ? 'hover:bg-slate-800/60 text-slate-300 hover:text-white border border-transparent' 
                              : 'hover:bg-slate-100 text-slate-700 hover:text-slate-900 border border-transparent'
                        }`}
                      >
                        <div className="flex items-center gap-2.5 truncate pr-2">
                          <div className={`p-1.5 rounded-lg shrink-0 ${
                            isSelected 
                              ? 'bg-indigo-500 text-white' 
                              : isDark ? 'bg-slate-800 text-indigo-400' : 'bg-slate-100 text-indigo-600'
                          }`}>
                            <Database className="w-3.5 h-3.5" />
                          </div>
                          <div className="truncate">
                            <p className="text-xs font-semibold truncate group-hover:text-indigo-400 transition-colors">
                              {db.name}
                            </p>
                            <p className="text-[10px] text-slate-400 flex items-center gap-1 mt-0.5 font-mono">
                              <Layers className="w-3 h-3" /> {db.table_count || 0} tables · SQLite
                            </p>
                          </div>
                        </div>

                        {isSelected && (
                          <div className="p-1 rounded-full bg-indigo-500/20 text-indigo-400 shrink-0">
                            <Check className="w-3.5 h-3.5" />
                          </div>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Section 2: NoSQL Document Databases */}
            {noSqlDatabases.length > 0 && (
              <div>
                <div className="flex items-center gap-1.5 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-amber-400">
                  <FileJson className="w-3 h-3" />
                  <span>NoSQL Document Stores ({noSqlDatabases.length})</span>
                </div>
                <div className="space-y-1 mt-0.5">
                  {noSqlDatabases.map((db) => {
                    const isSelected = db.id === selectedDbId;
                    return (
                      <button
                        key={db.id}
                        onClick={() => handleSelect(db.id)}
                        className={`w-full flex items-center justify-between p-2.5 rounded-xl text-left transition-all cursor-pointer group ${
                          isSelected
                            ? isDark 
                              ? 'bg-amber-500/20 border border-amber-500/40 text-white shadow-xs' 
                              : 'bg-amber-50 border border-amber-200 text-amber-950 shadow-xs'
                            : isDark 
                              ? 'hover:bg-slate-800/60 text-slate-300 hover:text-white border border-transparent' 
                              : 'hover:bg-slate-100 text-slate-700 hover:text-slate-900 border border-transparent'
                        }`}
                      >
                        <div className="flex items-center gap-2.5 truncate pr-2">
                          <div className={`p-1.5 rounded-lg shrink-0 ${
                            isSelected 
                              ? 'bg-amber-500 text-white' 
                              : isDark ? 'bg-slate-800 text-amber-400' : 'bg-slate-100 text-amber-600'
                          }`}>
                            <FileJson className="w-3.5 h-3.5" />
                          </div>
                          <div className="truncate">
                            <p className="text-xs font-semibold truncate group-hover:text-amber-400 transition-colors">
                              {db.name}
                            </p>
                            <p className="text-[10px] text-slate-400 flex items-center gap-1 mt-0.5 font-mono">
                              <Layers className="w-3 h-3" /> {db.doc_count || 0} documents · JSON
                            </p>
                          </div>
                        </div>

                        {isSelected && (
                          <div className="p-1 rounded-full bg-amber-500/20 text-amber-400 shrink-0">
                            <Check className="w-3.5 h-3.5" />
                          </div>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {filteredDbs.length === 0 && (
              <div className="py-6 text-center text-xs text-slate-400">
                No databases matching "{searchQuery}"
              </div>
            )}

            {/* Section 3: Coming Soon Expansion Formats */}
            <div className="pt-2 border-t border-slate-800/40 px-2.5">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block mb-1.5">
                Coming Soon (Roadmap)
              </span>
              <div className="grid grid-cols-2 gap-1.5 opacity-60 text-[10px]">
                <div className="flex items-center gap-1.5 p-1.5 rounded-lg border border-dashed border-slate-700 bg-slate-800/20">
                  <FileSpreadsheet className="w-3 h-3 text-emerald-400" />
                  <span>Excel (.xlsx)</span>
                </div>
                <div className="flex items-center gap-1.5 p-1.5 rounded-lg border border-dashed border-slate-700 bg-slate-800/20">
                  <Table2 className="w-3 h-3 text-cyan-400" />
                  <span>CSV Tables</span>
                </div>
              </div>
            </div>
          </div>

          {/* POPOVER FOOTER: UPLOAD NEW ACTION */}
          <div className={`p-2.5 border-t ${
            isDark ? 'bg-slate-950/80 border-slate-800' : 'bg-slate-50 border-slate-200'
          }`}>
            <button
              onClick={handleUploadClick}
              className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs transition-all shadow-sm cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Upload Custom Data Source...</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
