import React, { useState, useRef, useEffect } from 'react';
import { Send, Loader2, Code2, ChevronDown, Check, Sparkles } from 'lucide-react';

const getAvailableLanguages = (dbType) => {
  const type = (dbType || 'sql').toLowerCase();

  if (type === 'sql') {
    return [
      { id: 'auto', name: 'Auto (SQL)', badge: 'Default', desc: 'Native SQLite query', color: 'indigo' },
      { id: 'sql', name: 'SQL', badge: 'SQLite Dialect', desc: 'Direct ANSI/SQLite query', color: 'indigo' },
      { id: 'pandas', name: 'Python (Pandas)', badge: 'Pandas', desc: 'pd.read_sql_query execution', color: 'cyan' },
      { id: 'javascript', name: 'JavaScript', badge: 'Node.js', desc: 'better-sqlite3 driver code', color: 'amber' },
      { id: 'java', name: 'Java', badge: 'JDBC', desc: 'JDBC PreparedStatement code', color: 'orange' },
      { id: 'r', name: 'R', badge: 'tidyverse', desc: 'DBI / RSQLite script', color: 'sky' },
      { id: 'csharp', name: 'C#', badge: '.NET', desc: 'Microsoft.Data.Sqlite code', color: 'purple' },
    ];
  }

  if (type === 'nosql') {
    return [
      { id: 'auto', name: 'Auto (MQL)', badge: 'Default', desc: 'Native MongoDB query', color: 'emerald' },
      { id: 'nosql', name: 'MongoDB MQL', badge: 'MQL', desc: 'Aggregation & find filter', color: 'emerald' },
      { id: 'pandas', name: 'Python (PyMongo)', badge: 'Python', desc: 'PyMongo client code', color: 'cyan' },
      { id: 'javascript', name: 'JavaScript', badge: 'Node.js', desc: 'MongoDB Node driver code', color: 'amber' },
      { id: 'java', name: 'Java', badge: 'Driver', desc: 'MongoDB Java SDK code', color: 'orange' },
      { id: 'r', name: 'R', badge: 'mongolite', desc: 'mongolite package code', color: 'sky' },
      { id: 'csharp', name: 'C#', badge: '.NET', desc: 'MongoDB.Driver C# code', color: 'purple' },
    ];
  }

  if (type === 'csv') {
    return [
      { id: 'auto', name: 'Auto (Pandas)', badge: 'Default', desc: 'Vectorized Pandas operations', color: 'cyan' },
      { id: 'pandas', name: 'Python (Pandas)', badge: 'Pandas', desc: 'Vectorized DataFrame filters', color: 'cyan' },
      { id: 'sql', name: 'SQL (In-Memory)', badge: 'ANSI SQL', desc: 'Execute SQL directly on CSV data', color: 'indigo' },
      { id: 'excel_formula', name: 'Excel Formula', badge: 'Formula', desc: 'Excel compatible formula', color: 'emerald' },
      { id: 'javascript', name: 'JavaScript', badge: 'Danfo.js', desc: 'Danfo.js DataFrame operations', color: 'amber' },
      { id: 'java', name: 'Java', badge: 'OpenCSV', desc: 'Java CSV processing stream', color: 'orange' },
      { id: 'r', name: 'R', badge: 'tidyverse', desc: 'readr & dplyr pipeline', color: 'sky' },
      { id: 'csharp', name: 'C#', badge: 'CsvHelper', desc: 'CsvHelper strongly typed query', color: 'purple' },
    ];
  }

  if (type === 'excel') {
    return [
      { id: 'auto', name: 'Auto (Formula)', badge: 'Default', desc: 'Standard Excel calculation formula', color: 'emerald' },
      { id: 'excel_formula', name: 'Excel Formula', badge: 'Formula', desc: 'VLOOKUP, SUMIFS, XLOOKUP formula', color: 'emerald' },
      { id: 'sql', name: 'SQL (In-Memory)', badge: 'ANSI SQL', desc: 'Execute SQL directly on Excel sheets', color: 'indigo' },
      { id: 'pandas', name: 'Python (Pandas)', badge: 'Pandas', desc: 'openpyxl / pandas manipulation', color: 'cyan' },
      { id: 'javascript', name: 'JavaScript', badge: 'SheetJS', desc: 'SheetJS / xlsx script', color: 'amber' },
      { id: 'java', name: 'Java', badge: 'Apache POI', desc: 'Apache POI spreadsheet code', color: 'orange' },
      { id: 'r', name: 'R', badge: 'readxl', desc: 'readxl data manipulation', color: 'sky' },
      { id: 'csharp', name: 'C#', badge: 'ClosedXML', desc: 'ClosedXML spreadsheet operations', color: 'purple' },
    ];
  }

  return [
    { id: 'auto', name: 'Auto', badge: 'Default', desc: 'Auto dialect', color: 'indigo' },
    { id: 'sql', name: 'SQL', badge: 'SQL', desc: 'ANSI SQL', color: 'indigo' },
    { id: 'pandas', name: 'Python (Pandas)', badge: 'Pandas', desc: 'Pandas query', color: 'cyan' },
  ];
};

export default function ChatInput({ 
  onSendMessage, 
  isLoading, 
  isDark, 
  prefilledText = '',
  currentDb
}) {
  const [text, setText] = useState('');
  const [targetLanguage, setTargetLanguage] = useState('auto');
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const textareaRef = useRef(null);
  const dropdownRef = useRef(null);

  const availableLanguages = getAvailableLanguages(currentDb?.type);
  const activeLangConfig = availableLanguages.find(l => l.id === targetLanguage) || availableLanguages[0];

  // Auto-reset language if database type changes and language is incompatible
  useEffect(() => {
    if (!availableLanguages.some(l => l.id === targetLanguage)) {
      setTargetLanguage('auto');
    }
  }, [currentDb?.type, currentDb?.id]);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setDropdownOpen(false);
      }
    };
    if (dropdownOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [dropdownOpen]);

  // Sync prefilled text from schema explorer
  useEffect(() => {
    if (prefilledText) {
      setText(prefilledText);
      textareaRef.current?.focus();
    }
  }, [prefilledText]);

  // Dynamic Auto-Expand Textarea (up to 220px height)
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      const scrollHeight = textareaRef.current.scrollHeight;
      const targetHeight = Math.min(Math.max(scrollHeight, 38), 220);
      textareaRef.current.style.height = `${targetHeight}px`;
    }
  }, [text]);

  const handleSubmit = (e) => {
    if (e) e.preventDefault();
    if (!text.trim() || isLoading) return;
    onSendMessage(text, targetLanguage);
    setText('');
    if (textareaRef.current) {
      textareaRef.current.style.height = '38px';
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const isMultiLine = text.includes('\n') || text.length > 80;

  return (
    <div className="w-full max-w-5xl xl:max-w-6xl mx-auto px-4 pb-4">
      {/* Floating Prompt Bar */}
      <form onSubmit={handleSubmit} className="relative">
        <div className={`flex flex-col rounded-2xl border transition-all p-2 shadow-lg ${
          isDark 
            ? 'bg-slate-900 border-slate-700/80 focus-within:border-indigo-500 shadow-black/30' 
            : 'bg-white border-slate-300 focus-within:border-indigo-500 shadow-slate-200/50'
        }`}>
          {/* Main Input Row */}
          <div className="flex items-end gap-2">
            <textarea
              ref={textareaRef}
              rows={1}
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={`Ask anything about ${currentDb?.name || 'your data'} in natural language...`}
              style={{ minHeight: '38px', maxHeight: '220px' }}
              className={`w-full px-3 py-2 text-sm resize-none bg-transparent focus:outline-none custom-scrollbar leading-relaxed ${
                isDark ? 'text-slate-100 placeholder-slate-500' : 'text-slate-900 placeholder-slate-400'
              }`}
            />

            <button
              type="submit"
              disabled={!text.trim() || isLoading}
              className="p-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-30 disabled:hover:bg-indigo-600 text-white transition-all shrink-0 cursor-pointer mb-0.5"
              aria-label="Send message"
              title="Send message (Enter)"
            >
              {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            </button>
          </div>

          {/* Bottom Toolbar Strip with Language Selector Pill */}
          <div className="flex items-center justify-between pt-2 px-1 border-t border-slate-800/40 mt-1">
            <div className="relative" ref={dropdownRef}>
              <button
                type="button"
                onClick={() => setDropdownOpen(!dropdownOpen)}
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium transition-all cursor-pointer border ${
                  targetLanguage !== 'auto'
                    ? isDark 
                      ? 'bg-indigo-950/60 text-indigo-300 border-indigo-500/40 hover:bg-indigo-900/60' 
                      : 'bg-indigo-50 text-indigo-700 border-indigo-200 hover:bg-indigo-100'
                    : isDark
                      ? 'bg-slate-800/80 text-slate-300 border-slate-700/60 hover:bg-slate-700/80'
                      : 'bg-slate-100 text-slate-700 border-slate-200 hover:bg-slate-200'
                }`}
                title="Select target language / dialect for generated query"
              >
                <Code2 className="w-3.5 h-3.5 text-indigo-400" />
                <span>Target:</span>
                <span className="font-semibold">{activeLangConfig.name}</span>
                <ChevronDown className={`w-3 h-3 text-slate-400 transition-transform ${dropdownOpen ? 'rotate-180' : ''}`} />
              </button>

              {/* Language Selector Popover Menu */}
              {dropdownOpen && (
                <div className={`absolute left-0 bottom-full mb-2 w-72 rounded-2xl border shadow-2xl p-1.5 z-50 backdrop-blur-xl animate-fadeIn ${
                  isDark ? 'bg-slate-900/95 border-slate-700/90 text-slate-200 shadow-black/60' : 'bg-white/95 border-slate-200 text-slate-800 shadow-slate-300/60'
                }`}>
                  <div className="px-2.5 py-1.5 border-b border-slate-800/60 text-[10px] uppercase font-bold text-slate-400 flex items-center justify-between">
                    <span>Compatible Languages</span>
                    <span className="text-[9px] px-1.5 py-0.5 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 uppercase">
                      {currentDb?.type || 'SQL'} Engine
                    </span>
                  </div>

                  <div className="py-1 max-h-64 overflow-y-auto custom-scrollbar">
                    {availableLanguages.map((lang) => {
                      const isSelected = targetLanguage === lang.id;
                      return (
                        <button
                          key={lang.id}
                          type="button"
                          onClick={() => {
                            setTargetLanguage(lang.id);
                            setDropdownOpen(false);
                          }}
                          className={`w-full text-left px-2.5 py-2 rounded-xl text-xs flex items-center justify-between transition-all cursor-pointer ${
                            isSelected
                              ? isDark 
                                ? 'bg-indigo-600/20 text-indigo-300 font-semibold' 
                                : 'bg-indigo-50 text-indigo-700 font-semibold'
                              : isDark
                                ? 'hover:bg-slate-800/70 text-slate-300'
                                : 'hover:bg-slate-100 text-slate-700'
                          }`}
                        >
                          <div className="min-w-0 pr-2">
                            <div className="flex items-center gap-1.5">
                              <span>{lang.name}</span>
                              <span className={`text-[9px] px-1.5 py-0.2 rounded font-mono ${
                                isSelected ? 'bg-indigo-500/30 text-indigo-200' : 'bg-slate-700/50 text-slate-400'
                              }`}>
                                {lang.badge}
                              </span>
                            </div>
                            <div className="text-[10px] text-slate-400 truncate mt-0.5 font-normal">
                              {lang.desc}
                            </div>
                          </div>
                          {isSelected && <Check className="w-3.5 h-3.5 text-indigo-400 shrink-0" />}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>

            <div className="text-[10px] text-slate-400 flex items-center gap-2">
              {isMultiLine && (
                <span className="font-mono text-indigo-400/90 font-medium hidden sm:inline">
                  Shift + Enter for new line •
                </span>
              )}
              <span className="hidden md:inline">Multi-Language Code Generation & Live Data Preview</span>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between px-1 text-[10px] text-slate-400 mt-2">
          <span>Enterprise Multi-Engine • SQL, NoSQL & Spreadsheets • AST Sandboxed Guardrails</span>
          <span className="font-mono text-indigo-400/80 font-medium">Enter to execute</span>
        </div>
      </form>
    </div>
  );
}
