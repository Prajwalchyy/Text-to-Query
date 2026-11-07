import React, { useState, useRef, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { Terminal, Copy, Check, FileJson, FileSpreadsheet, Code2, ChevronDown, RotateCcw, Loader2 } from 'lucide-react';

const LANGUAGE_METADATA = {
  sql: {
    id: 'sql',
    name: 'SQL',
    badge: 'SQL',
    color: 'indigo',
    icon: Terminal
  },
  excel_formula: {
    id: 'excel_formula',
    name: 'Excel',
    badge: 'Excel',
    color: 'emerald',
    icon: FileSpreadsheet
  },
  pandas: {
    id: 'pandas',
    name: 'Python (Pandas)',
    badge: 'Python (Pandas)',
    color: 'cyan',
    icon: Terminal
  },
  r: {
    id: 'r',
    name: 'R',
    badge: 'R',
    color: 'sky',
    icon: Code2
  },
  nosql: {
    id: 'nosql',
    name: 'NoSQL',
    badge: 'NoSQL',
    color: 'amber',
    icon: FileJson
  }
};

const getCompatibleLanguages = (dbType) => {
  const type = (dbType || 'sql').toLowerCase();
  if (type === 'nosql') return ['nosql', 'pandas', 'r'];
  if (type === 'excel') return ['excel_formula', 'pandas', 'r'];
  if (type === 'csv') return ['pandas', 'excel_formula', 'r'];
  return ['sql', 'pandas', 'r'];
};

export default function ResultBlock({ 
  sql, 
  isDark, 
  codeType, 
  dbId = 'chinook', 
  dbType = 'sql', 
  apiBaseUrl = 'http://localhost:8000/api' 
}) {
  const originalLanguage = (() => {
    if (codeType) return codeType.toLowerCase();
    const trimmed = (sql || '').trim();
    if (trimmed.startsWith('=')) return 'excel_formula';
    if (trimmed.includes('result_df') || trimmed.startsWith('df[') || trimmed.includes('df.')) return 'pandas';
    if (trimmed.startsWith('db.') || trimmed.startsWith('[') || trimmed.startsWith('{')) return 'nosql';
    return 'sql';
  })();

  const [copied, setCopied] = useState(false);
  const [activeCode, setActiveCode] = useState(sql);
  const [activeLanguage, setActiveLanguage] = useState(originalLanguage);
  const [convertedCache, setConvertedCache] = useState({});
  const [isConverting, setIsConverting] = useState(false);
  const [convertingToLang, setConvertingToLang] = useState(null);
  const [convertMenuOpen, setConvertMenuOpen] = useState(false);
  const [menuPos, setMenuPos] = useState({
    top: 0,
    bottom: 0,
    left: 0,
    width: 190,
    openUpward: false
  });

  const [prevSql, setPrevSql] = useState(sql);
  if (sql !== prevSql) {
    setPrevSql(sql);
    setActiveCode(sql);
    setActiveLanguage(originalLanguage);
    setConvertedCache({});
  }

  const buttonRef = useRef(null);
  const menuRef = useRef(null);

  const updateMenuPosition = useCallback(() => {
    if (!buttonRef.current) return;
    const rect = buttonRef.current.getBoundingClientRect();

    // If button has scrolled off screen, close the menu
    if (rect.bottom < 0 || rect.top > window.innerHeight) {
      setConvertMenuOpen(false);
      return;
    }

    const menuWidth = Math.min(190, Math.max(160, window.innerWidth - 24));
    const menuEstimatedHeight = 190;

    let left = rect.right - menuWidth;
    if (left < 12) left = 12;
    if (left + menuWidth > window.innerWidth - 12) {
      left = window.innerWidth - menuWidth - 12;
    }

    const spaceBelow = window.innerHeight - rect.bottom;
    const spaceAbove = rect.top;
    const openUpward = spaceBelow < menuEstimatedHeight && spaceAbove > spaceBelow;

    setMenuPos({
      top: rect.bottom + 6,
      bottom: window.innerHeight - (rect.top - 6),
      left,
      width: menuWidth,
      openUpward
    });
  }, []);

  useEffect(() => {
    if (!convertMenuOpen) return;

    updateMenuPosition();

    const handleScrollOrResize = () => {
      updateMenuPosition();
    };

    const handleClickOutside = (e) => {
      if (buttonRef.current && buttonRef.current.contains(e.target)) return;
      if (menuRef.current && menuRef.current.contains(e.target)) return;
      setConvertMenuOpen(false);
    };

    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        setConvertMenuOpen(false);
      }
    };

    window.addEventListener('scroll', handleScrollOrResize, true);
    window.addEventListener('resize', handleScrollOrResize);
    document.addEventListener('pointerdown', handleClickOutside);
    document.addEventListener('keydown', handleKeyDown);

    return () => {
      window.removeEventListener('scroll', handleScrollOrResize, true);
      window.removeEventListener('resize', handleScrollOrResize);
      document.removeEventListener('pointerdown', handleClickOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [convertMenuOpen, updateMenuPosition]);

  if (!sql) return null;

  const currentLangMeta = LANGUAGE_METADATA[activeLanguage] || LANGUAGE_METADATA.sql;
  const CurrentIcon = currentLangMeta.icon || Terminal;

  const compatibleLanguages = getCompatibleLanguages(dbType);

  const handleCopy = () => {
    navigator.clipboard.writeText(activeCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleConvertTo = async (targetLang) => {
    setConvertMenuOpen(false);
    if (targetLang === activeLanguage) return;

    // If switching back to original code
    if (targetLang === originalLanguage) {
      setActiveLanguage(originalLanguage);
      setActiveCode(sql);
      return;
    }

    // Check local cache
    if (convertedCache[targetLang]) {
      setActiveLanguage(targetLang);
      setActiveCode(convertedCache[targetLang]);
      return;
    }

    setIsConverting(true);
    setConvertingToLang(targetLang);
    try {
      const res = await fetch(`${apiBaseUrl}/chats/convert-code`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          code: sql,
          from_language: originalLanguage,
          to_language: targetLang,
          db_id: dbId
        })
      });

      if (res.ok) {
        const data = await res.json();
        const converted = data.code || sql;
        setConvertedCache(prev => ({ ...prev, [targetLang]: converted }));
        setActiveLanguage(targetLang);
        setActiveCode(converted);
      }
    } catch (err) {
      console.error('Failed to convert code snippet:', err);
    } finally {
      setIsConverting(false);
      setConvertingToLang(null);
    }
  };

  const handleResetToOriginal = () => {
    setActiveLanguage(originalLanguage);
    setActiveCode(sql);
  };

  return (
    <div className={`mt-3 rounded-xl border transition-all shadow-sm ${
      isDark ? 'bg-slate-950 border-slate-800/90' : 'bg-slate-900 border-slate-800'
    }`}>
      {/* Top Bar with Language Dialect Badge, Convert Menu & Copy Button */}
      <div className="flex items-center justify-between px-3 py-2 bg-slate-900/95 border-b border-slate-800 text-xs font-mono rounded-t-xl">
        {/* Left: Language Badge */}
        <div className="flex items-center gap-2">
          <span className={`inline-flex items-center gap-1.5 font-semibold text-[11px] ${
            activeLanguage === 'excel_formula' ? 'text-emerald-300' :
            activeLanguage === 'pandas' ? 'text-cyan-300' :
            activeLanguage === 'r' ? 'text-sky-300' :
            activeLanguage === 'nosql' ? 'text-emerald-300' :
            'text-indigo-300'
          }`}>
            <CurrentIcon className="w-3.5 h-3.5" />
            <span>{currentLangMeta.badge}</span>
          </span>

          {activeLanguage !== originalLanguage && (
            <span className="text-[9px] px-1.5 py-0.2 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
              Converted
            </span>
          )}
        </div>

        {/* Right: Actions (Convert dropdown, Reset, Copy) */}
        <div className="flex items-center gap-1.5">
          {/* Revert to Original if converted */}
          {activeLanguage !== originalLanguage && (
            <button
              onClick={handleResetToOriginal}
              className="px-2 py-1 rounded-md bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors flex items-center gap-1 cursor-pointer text-[10px] border border-slate-700/60"
              title="Reset to original generated code"
            >
              <RotateCcw className="w-3 h-3 text-slate-400" />
              <span className="hidden sm:inline">Original</span>
            </button>
          )}

          {/* Quick Polyglot Language Switcher */}
          <div className="relative">
            <button
              ref={buttonRef}
              type="button"
              onClick={() => setConvertMenuOpen(prev => !prev)}
              disabled={isConverting}
              className={`px-2 py-1 rounded-md transition-colors flex items-center gap-1 cursor-pointer text-[10px] border ${
                convertMenuOpen
                  ? 'bg-indigo-600/30 text-indigo-200 border-indigo-500/50'
                  : 'bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border-slate-700/60'
              }`}
              title="Convert this query into another language"
            >
              {isConverting ? (
                <Loader2 className="w-3 h-3 animate-spin text-indigo-400" />
              ) : (
                <Code2 className="w-3 h-3 text-indigo-400" />
              )}
              <span className="hidden sm:inline">Convert</span>
              <ChevronDown className={`w-2.5 h-2.5 transition-transform ${convertMenuOpen ? 'rotate-180' : ''}`} />
            </button>
          </div>

          {/* Copy Button */}
          <button
            onClick={handleCopy}
            className="px-2.5 py-1 rounded-md bg-slate-800 hover:bg-slate-700 text-slate-200 transition-colors flex items-center gap-1.5 cursor-pointer text-[11px]"
            aria-label="Copy code"
            title="Copy code to clipboard"
          >
            {copied ? (
              <>
                <Check className="w-3 h-3 text-emerald-400" />
                <span className="text-emerald-400 font-medium">Copied!</span>
              </>
            ) : (
              <>
                <Copy className="w-3 h-3 text-slate-400" />
                <span>Copy</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Floating Convert Language Menu Portaled to Body (Unconstrained & Outside Code Block) */}
      {convertMenuOpen && typeof document !== 'undefined' && createPortal(
        <div
          ref={menuRef}
          style={{
            position: 'fixed',
            top: menuPos.openUpward ? 'auto' : `${menuPos.top}px`,
            bottom: menuPos.openUpward ? `${menuPos.bottom}px` : 'auto',
            left: `${menuPos.left}px`,
            width: `${menuPos.width}px`,
            zIndex: 9999
          }}
          className="rounded-xl bg-slate-900/95 border border-slate-700/90 shadow-2xl p-1.5 text-slate-200 backdrop-blur-md transition-opacity duration-150 animate-fadeIn"
        >
          <div className="px-2 py-1 text-[9px] uppercase font-bold text-slate-400 border-b border-slate-800 flex items-center justify-between">
            <span>Select Language</span>
            <span className="text-[8px] text-slate-500 font-normal">Polyglot</span>
          </div>
          <div className="py-1 max-h-56 overflow-y-auto custom-scrollbar">
            {compatibleLanguages.map((langKey) => {
              const meta = LANGUAGE_METADATA[langKey] || { name: langKey, badge: langKey };
              const isSelected = activeLanguage === langKey;
              const LangIcon = meta.icon || Code2;
              return (
                <button
                  key={langKey}
                  type="button"
                  onClick={() => handleConvertTo(langKey)}
                  className={`w-full text-left px-2.5 py-1.5 rounded-lg text-xs flex items-center justify-between transition-colors cursor-pointer ${
                    isSelected
                      ? 'bg-indigo-600/30 text-indigo-300 font-semibold'
                      : 'hover:bg-slate-800 text-slate-300 hover:text-white'
                  }`}
                >
                  <span className="flex items-center gap-2 text-[11px]">
                    <LangIcon className={`w-3.5 h-3.5 ${
                      isSelected ? 'text-indigo-400' : 'text-slate-400'
                    }`} />
                    <span>{meta.name}</span>
                  </span>
                  {isSelected && <Check className="w-3.5 h-3.5 text-indigo-400 shrink-0" />}
                </button>
              );
            })}
          </div>
        </div>,
        document.body
      )}

      {/* Code / Formula Area with Local Container Scrolling */}
      <div className="p-4 max-h-64 overflow-y-auto overflow-x-auto custom-scrollbar relative rounded-b-xl">
        {isConverting && (
          <div className="absolute inset-0 bg-slate-950/80 backdrop-blur-xs flex items-center justify-center gap-2 text-xs text-indigo-300 z-10 rounded-b-xl">
            <Loader2 className="w-4 h-4 animate-spin text-indigo-400" />
            <span>Converting to {LANGUAGE_METADATA[convertingToLang]?.name || 'target language'}...</span>
          </div>
        )}
        <pre className={`font-mono text-xs whitespace-pre-wrap break-words leading-relaxed m-0 ${
          activeLanguage === 'excel_formula' 
            ? 'text-emerald-300 font-bold selection:bg-emerald-800 selection:text-white' 
            : activeLanguage === 'pandas' 
              ? 'text-cyan-300 selection:bg-cyan-950 selection:text-cyan-200'
              : activeLanguage === 'r'
                ? 'text-sky-300 selection:bg-sky-950 selection:text-sky-200'
                : activeLanguage === 'nosql' 
                  ? 'text-emerald-400 selection:bg-emerald-950 selection:text-emerald-200' 
                  : 'text-emerald-400 selection:bg-emerald-950 selection:text-emerald-200'
        }`}>
          {activeCode}
        </pre>
      </div>
    </div>
  );
}
