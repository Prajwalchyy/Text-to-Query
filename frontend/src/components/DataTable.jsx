import React, { useState } from 'react';
import { Table as TableIcon, ChevronDown, ChevronUp } from 'lucide-react';

export default function DataTable({ data, isDark }) {
  const [isExpanded, setIsExpanded] = useState(true);

  if (!data || data.length === 0) return null;

  const columns = Object.keys(data[0]);

  const formatCellValue = (val) => {
    if (val === null || val === undefined) return 'NULL';
    if (typeof val === 'object') {
      return JSON.stringify(val);
    }
    if (typeof val === 'boolean') {
      return val ? 'true' : 'false';
    }
    return String(val);
  };

  return (
    <div className="mt-3">
      {/* Collapsible toggle header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className={`w-full flex items-center justify-between px-3.5 py-2 rounded-lg text-xs font-medium border transition-colors cursor-pointer ${
          isDark
            ? 'bg-slate-900/60 border-slate-800 text-slate-300 hover:bg-slate-800/80'
            : 'bg-slate-100 border-slate-200 text-slate-700 hover:bg-slate-200/60'
        }`}
      >
        <span className="flex items-center gap-2">
          <TableIcon className="w-3.5 h-3.5 text-indigo-400" />
          <span>Query Results ({data.length} {data.length === 1 ? 'record' : 'records'})</span>
        </span>
        {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
      </button>

      {/* Table Body with Localized Container Scrolling */}
      {isExpanded && (
        <div className={`mt-2 border rounded-xl overflow-hidden max-h-64 overflow-y-auto overflow-x-auto custom-scrollbar ${
          isDark ? 'border-slate-800 bg-slate-950/40' : 'border-slate-200 bg-white'
        }`}>
          <table className="w-full text-left text-xs border-collapse">
            <thead className={`sticky top-0 uppercase tracking-wider font-semibold border-b z-10 ${
              isDark 
                ? 'bg-slate-900 text-slate-300 border-slate-800' 
                : 'bg-slate-100 text-slate-700 border-slate-200'
            }`}>
              <tr>
                {columns.map((col) => (
                  <th key={col} className="px-4 py-2.5 whitespace-nowrap">{col}</th>
                ))}
              </tr>
            </thead>
            <tbody className={`divide-y ${isDark ? 'divide-slate-800/80' : 'divide-slate-200'}`}>
              {data.map((row, rIdx) => (
                <tr key={rIdx} className={isDark ? 'hover:bg-slate-800/30 transition-colors' : 'hover:bg-slate-50 transition-colors'}>
                  {columns.map((col, cIdx) => {
                    const formatted = formatCellValue(row[col]);
                    const isLongJson = typeof row[col] === 'object' && row[col] !== null;
                    return (
                      <td key={cIdx} className={`px-4 py-2.5 font-mono text-xs whitespace-nowrap ${
                        isDark ? 'text-slate-300' : 'text-slate-700'
                      } ${isLongJson ? 'max-w-xs truncate' : ''}`} title={isLongJson ? formatted : undefined}>
                        {formatted}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
