import React, { useState } from 'react';
import { FileJson, Copy, Check, ChevronDown, ChevronUp, Download } from 'lucide-react';

export default function JsonDocumentViewer({ data, isDark }) {
  const [copied, setCopied] = useState(false);
  const [isExpanded, setIsExpanded] = useState(true);
  const [expandedDocs, setExpandedDocs] = useState(() => {
    // By default, expand first 3 documents
    const initial = {};
    if (Array.isArray(data)) {
      data.slice(0, 3).forEach((_, idx) => {
        initial[idx] = true;
      });
    }
    return initial;
  });

  if (!data || data.length === 0) return null;

  const docs = Array.isArray(data) ? data : [data];

  const handleCopyAll = () => {
    navigator.clipboard.writeText(JSON.stringify(docs, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownloadJson = (e) => {
    e.stopPropagation();
    const jsonContent = JSON.stringify(docs, null, 2);
    const blob = new Blob([jsonContent], { type: 'application/json;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    link.href = url;
    link.setAttribute('download', `nosql_documents_${timestamp}.json`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const handleExportCsv = (e) => {
    e.stopPropagation();
    if (!docs || docs.length === 0) return;
    const keysSet = new Set();
    docs.forEach(doc => {
      if (doc && typeof doc === 'object') {
        Object.keys(doc).forEach(k => keysSet.add(k));
      }
    });
    const columns = Array.from(keysSet);

    const escapeCsvValue = (val) => {
      if (val === null || val === undefined) return '';
      let str = typeof val === 'object' ? JSON.stringify(val) : String(val);
      if (str.includes(',') || str.includes('"') || str.includes('\n') || str.includes('\r')) {
        return `"${str.replace(/"/g, '""')}"`;
      }
      return str;
    };

    const headerLine = columns.map(escapeCsvValue).join(',');
    const rowLines = docs.map(doc => 
      columns.map(col => escapeCsvValue(doc[col])).join(',')
    );

    const csvContent = '\uFEFF' + [headerLine, ...rowLines].join('\r\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    link.href = url;
    link.setAttribute('download', `nosql_documents_${timestamp}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const toggleDoc = (idx) => {
    setExpandedDocs(prev => ({
      ...prev,
      [idx]: !prev[idx]
    }));
  };

  const expandAll = () => {
    const all = {};
    docs.forEach((_, idx) => { all[idx] = true; });
    setExpandedDocs(all);
  };

  const collapseAll = () => {
    setExpandedDocs({});
  };

  // Syntax highlighter for JSON primitives
  const renderFormattedJson = (obj) => {
    const jsonString = JSON.stringify(obj, null, 2);
    return jsonString.split('\n').map((line, lIdx) => {
      // Colorize JSON keys, strings, numbers, booleans
      const keyMatch = line.match(/^(\s*)(".*?")(\s*:\s*)(.*)$/);
      if (keyMatch) {
        const [, indent, key, colon, value] = keyMatch;
        let valColor = 'text-slate-300';
        if (value.startsWith('"')) valColor = 'text-emerald-400';
        else if (value === 'true' || value === 'false') valColor = 'text-purple-400';
        else if (value === 'null') valColor = 'text-rose-400';
        else if (!isNaN(Number(value.replace(/,$/, '')))) valColor = 'text-cyan-400';

        return (
          <div key={lIdx} className="leading-relaxed font-mono">
            <span>{indent}</span>
            <span className="text-amber-300 font-semibold">{key}</span>
            <span className="text-slate-400">{colon}</span>
            <span className={valColor}>{value}</span>
          </div>
        );
      }
      return <div key={lIdx} className="leading-relaxed font-mono text-slate-400">{line}</div>;
    });
  };

  return (
    <div className="mt-3 w-full max-w-full overflow-hidden animate-fadeIn">
      {/* Container Header */}
      <div className={`flex items-center justify-between px-3.5 py-2 rounded-xl border transition-colors ${
        isDark 
          ? 'bg-slate-900/80 border-slate-800 text-slate-200' 
          : 'bg-slate-100 border-slate-200 text-slate-800'
      }`}>
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="flex items-center gap-2 text-xs font-semibold cursor-pointer"
        >
          <FileJson className="w-4 h-4 text-amber-400" />
          <span>NoSQL Documents ({docs.length} {docs.length === 1 ? 'document' : 'documents'})</span>
          {isExpanded ? <ChevronUp className="w-3.5 h-3.5 ml-1 text-slate-400" /> : <ChevronDown className="w-3.5 h-3.5 ml-1 text-slate-400" />}
        </button>

        {isExpanded && (
          <div className="flex items-center gap-2">
            <button
              onClick={expandAll}
              className="text-[10px] text-slate-400 hover:text-indigo-400 transition-colors cursor-pointer"
            >
              Expand All
            </button>
            <span className="text-slate-600 text-xs">|</span>
            <button
              onClick={collapseAll}
              className="text-[10px] text-slate-400 hover:text-indigo-400 transition-colors cursor-pointer"
            >
              Collapse
            </button>
            <span className="text-slate-600 text-xs">|</span>
            <button
              onClick={handleCopyAll}
              className="flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-md bg-slate-800/80 hover:bg-slate-700 text-slate-200 transition-colors cursor-pointer"
              title="Copy entire JSON payload"
            >
              {copied ? (
                <>
                  <Check className="w-3 h-3 text-emerald-400" />
                  <span className="text-emerald-400 font-medium">Copied!</span>
                </>
              ) : (
                <>
                  <Copy className="w-3 h-3 text-slate-400" />
                  <span>Copy JSON</span>
                </>
              )}
            </button>

            <span className="text-slate-600 text-xs">|</span>

            {/* Export CSV Button */}
            <button
              type="button"
              onClick={handleExportCsv}
              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-semibold border transition-all cursor-pointer ${
                isDark
                  ? 'bg-slate-800/90 hover:bg-emerald-600/20 text-slate-300 hover:text-emerald-300 border-slate-700/80 hover:border-emerald-500/40'
                  : 'bg-white hover:bg-emerald-50 text-slate-700 hover:text-emerald-700 border-slate-300 hover:border-emerald-300 shadow-xs'
              }`}
              title="Download flattened NoSQL documents as CSV (opens in Excel)"
            >
              <Download className="w-3 h-3 text-emerald-500" />
              <span>CSV</span>
            </button>

            {/* Download JSON Button */}
            <button
              type="button"
              onClick={handleDownloadJson}
              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-semibold border transition-all cursor-pointer ${
                isDark
                  ? 'bg-slate-800/90 hover:bg-indigo-600/20 text-slate-300 hover:text-indigo-300 border-slate-700/80 hover:border-indigo-500/40'
                  : 'bg-white hover:bg-indigo-50 text-slate-700 hover:text-indigo-700 border-slate-300 hover:border-indigo-300 shadow-xs'
              }`}
              title="Download raw documents as JSON file"
            >
              <Download className="w-3 h-3 text-indigo-500" />
              <span>JSON</span>
            </button>
          </div>
        )}
      </div>

      {/* Document List Container with Localized Scroll */}
      {isExpanded && (
        <div className={`mt-2 space-y-2 max-h-72 overflow-y-auto custom-scrollbar p-1`}>
          {docs.map((doc, idx) => {
            const isDocOpen = Boolean(expandedDocs[idx]);
            const docId = doc._id || doc.id || `Doc #${idx + 1}`;

            return (
              <div 
                key={idx} 
                className={`rounded-xl border overflow-hidden transition-all text-xs ${
                  isDark ? 'bg-slate-950/70 border-slate-800' : 'bg-white border-slate-200 shadow-xs'
                }`}
              >
                {/* Single Document Header */}
                <div 
                  onClick={() => toggleDoc(idx)}
                  className={`flex items-center justify-between px-3.5 py-2 cursor-pointer select-none transition-colors ${
                    isDark 
                      ? 'hover:bg-slate-900/60 bg-slate-900/30 text-slate-300' 
                      : 'hover:bg-slate-50 bg-slate-50/70 text-slate-700'
                  }`}
                >
                  <div className="flex items-center gap-2 truncate">
                    <span className="inline-flex items-center px-2 py-0.2 rounded text-[10px] font-mono font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">
                      #{idx + 1}
                    </span>
                    <span className="font-mono text-xs font-semibold truncate text-indigo-400">
                      {String(docId)}
                    </span>
                    <span className="text-[10px] text-slate-400 hidden sm:inline">
                      ({Object.keys(doc).length} fields)
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    {isDocOpen ? <ChevronUp className="w-3.5 h-3.5 text-slate-400" /> : <ChevronDown className="w-3.5 h-3.5 text-slate-400" />}
                  </div>
                </div>

                {/* Document Body */}
                {isDocOpen && (
                  <div className={`p-3.5 border-t text-[11px] overflow-x-auto custom-scrollbar ${
                    isDark ? 'bg-slate-950 border-slate-800/80' : 'bg-slate-50/50 border-slate-200'
                  }`}>
                    {renderFormattedJson(doc)}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
