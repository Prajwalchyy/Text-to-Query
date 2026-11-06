import React, { useState, useRef, useEffect } from 'react';
import { Send, Loader2, Code2, ChevronDown, Check } from 'lucide-react';

const getAvailableLanguages = (dbType) => {
  const type = (dbType || 'sql').toLowerCase();

  if (type === 'sql') {
    return [
      { id: 'sql', name: 'SQL', color: 'indigo' },
      { id: 'excel_formula', name: 'Excel', color: 'emerald' },
      { id: 'pandas', name: 'Python (Pandas)', color: 'cyan' },
      { id: 'r', name: 'R', color: 'sky' },
    ];
  }

  if (type === 'nosql') {
    return [
      { id: 'nosql', name: 'MongoDB MQL', color: 'emerald' },
      { id: 'excel_formula', name: 'Excel', color: 'emerald' },
      { id: 'pandas', name: 'Python (Pandas)', color: 'cyan' },
      { id: 'r', name: 'R', color: 'sky' },
    ];
  }

  if (type === 'csv') {
    return [
      { id: 'sql', name: 'SQL', color: 'indigo' },
      { id: 'excel_formula', name: 'Excel', color: 'emerald' },
      { id: 'pandas', name: 'Python (Pandas)', color: 'cyan' },
      { id: 'r', name: 'R', color: 'sky' },
    ];
  }

  if (type === 'excel') {
    return [
      { id: 'excel_formula', name: 'Excel', color: 'emerald' },
      { id: 'sql', name: 'SQL', color: 'indigo' },
      { id: 'pandas', name: 'Python (Pandas)', color: 'cyan' },
      { id: 'r', name: 'R', color: 'sky' },
    ];
  }

  return [
    { id: 'sql', name: 'SQL', color: 'indigo' },
    { id: 'excel_formula', name: 'Excel', color: 'emerald' },
    { id: 'pandas', name: 'Python (Pandas)', color: 'cyan' },
    { id: 'r', name: 'R', color: 'sky' },
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
  const availableLanguages = getAvailableLanguages(currentDb?.type);
  const defaultLangId = availableLanguages[0]?.id || 'sql';
  const [targetLanguage, setTargetLanguage] = useState(defaultLangId);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const textareaRef = useRef(null);
  const dropdownRef = useRef(null);

  const activeLangConfig = availableLanguages.find(l => l.id === targetLanguage) || availableLanguages[0];
  const isCustomLang = targetLanguage !== defaultLangId;

  // Auto-reset language if database type changes and language is incompatible
  useEffect(() => {
    const validLangs = getAvailableLanguages(currentDb?.type);
    if (!validLangs.some(l => l.id === targetLanguage)) {
      setTargetLanguage(validLangs[0]?.id || 'sql');
    }
  }, [currentDb?.type, currentDb?.id, targetLanguage]);

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
                  isCustomLang
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
                <div className={`absolute left-0 bottom-full mb-2 w-56 rounded-2xl border shadow-2xl p-1.5 z-50 backdrop-blur-xl animate-fadeIn ${
                  isDark ? 'bg-slate-900/95 border-slate-700/90 text-slate-200 shadow-black/60' : 'bg-white/95 border-slate-200 text-slate-800 shadow-slate-300/60'
                }`}>
                  <div className="px-3 py-1.5 border-b border-slate-800/60 text-[10px] uppercase font-bold text-slate-400">
                    Compatible Languages
                  </div>

                  <div className="py-1">
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
                          className={`w-full text-left px-3 py-2 rounded-xl text-xs flex items-center justify-between transition-all cursor-pointer ${
                            isSelected
                              ? isDark 
                                ? 'bg-indigo-600/20 text-indigo-300 font-semibold' 
                                : 'bg-indigo-50 text-indigo-700 font-semibold'
                              : isDark
                                ? 'hover:bg-slate-800/70 text-slate-300'
                                : 'hover:bg-slate-100 text-slate-700'
                          }`}
                        >
                          <span className="font-medium">{lang.name}</span>
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
