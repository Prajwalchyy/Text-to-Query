import React, { useState } from 'react';
import { Terminal, Copy, Check, FileJson } from 'lucide-react';

export default function SqlCodeBlock({ sql, isDark }) {
  const [copied, setCopied] = useState(false);

  if (!sql) return null;

  const isNoSql = sql.trim().startsWith("db.") || sql.trim().startsWith("[") || sql.trim().startsWith("{");

  const handleCopy = () => {
    navigator.clipboard.writeText(sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={`mt-3 rounded-xl border overflow-hidden transition-all shadow-sm ${
      isDark ? 'bg-slate-950 border-slate-800/90' : 'bg-slate-900 border-slate-800'
    }`}>
      {/* Top Bar with Language Dialect Badge & Copy Button */}
      <div className="flex items-center justify-between px-4 py-2 bg-slate-900/90 border-b border-slate-800 text-xs font-mono">
        <span className="flex items-center gap-1.5 font-semibold text-[11px]">
          {isNoSql ? (
            <>
              <FileJson className="w-3.5 h-3.5 text-amber-400" />
              <span className="text-amber-300">MongoDB MQL</span>
            </>
          ) : (
            <>
              <Terminal className="w-3.5 h-3.5 text-indigo-400" />
              <span className="text-slate-300">SQLite Dialect</span>
            </>
          )}
        </span>
        <button
          onClick={handleCopy}
          className="px-2.5 py-1 rounded-md bg-slate-800 hover:bg-slate-700 text-slate-200 transition-colors flex items-center gap-1.5 cursor-pointer text-[11px]"
          aria-label="Copy query"
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

      {/* Code Area with Local Container Scrolling */}
      <div className="p-4 max-h-56 overflow-y-auto overflow-x-auto custom-scrollbar">
        <pre className={`font-mono text-xs whitespace-pre-wrap break-words leading-relaxed m-0 selection:bg-emerald-950 selection:text-emerald-200 ${
          isNoSql ? 'text-amber-300' : 'text-emerald-400'
        }`}>
          {sql}
        </pre>
      </div>
    </div>
  );
}
