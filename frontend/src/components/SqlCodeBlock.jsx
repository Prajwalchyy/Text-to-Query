import React, { useState } from 'react';
import { Terminal, Copy, Check } from 'lucide-react';

export default function SqlCodeBlock({ sql, isDark }) {
  const [copied, setCopied] = useState(false);

  if (!sql) return null;

  const handleCopy = () => {
    navigator.clipboard.writeText(sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={`mt-3 rounded-xl border overflow-hidden transition-all shadow-sm ${
      isDark ? 'bg-slate-950 border-slate-800/90' : 'bg-slate-900 border-slate-800'
    }`}>
      {/* Top Bar with SQLite Badge & Copy Button */}
      <div className="flex items-center justify-between px-4 py-2 bg-slate-900/90 border-b border-slate-800 text-xs font-mono">
        <span className="flex items-center gap-1.5 text-slate-300 font-semibold text-[11px]">
          <Terminal className="w-3.5 h-3.5 text-indigo-400" /> SQLite Dialect
        </span>
        <button
          onClick={handleCopy}
          className="px-2.5 py-1 rounded-md bg-slate-800 hover:bg-slate-700 text-slate-200 transition-colors flex items-center gap-1.5 cursor-pointer text-[11px]"
          aria-label="Copy SQL query"
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

      {/* Code Area */}
      <div className="p-4 overflow-x-auto">
        <pre className="font-mono text-xs text-emerald-400 whitespace-pre-wrap break-words leading-relaxed m-0 selection:bg-emerald-950 selection:text-emerald-200">
          {sql}
        </pre>
      </div>
    </div>
  );
}
