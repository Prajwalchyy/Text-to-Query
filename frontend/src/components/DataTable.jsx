import React, { useState } from 'react';
import { Table as TableIcon, ChevronDown, ChevronUp, Download } from 'lucide-react';

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

  const exportToCsv = (e) => {
    e.stopPropagation();
    if (!data || data.length === 0) return;

    const escapeCsvValue = (val) => {
      if (val === null || val === undefined) return '';
      let str = typeof val === 'object' ? JSON.stringify(val) : String(val);
      if (str.includes(',') || str.includes('"') || str.includes('\n') || str.includes('\r')) {
        return `"${str.replace(/"/g, '""')}"`;
      }
      return str;
    };

    const headerLine = columns.map(escapeCsvValue).join(',');
    const rowLines = data.map(row => 
      columns.map(col => escapeCsvValue(row[col])).join(',')
    );

    // Include UTF-8 BOM so Microsoft Excel renders accents and unicode accurately
    const csvContent = '\uFEFF' + [headerLine, ...rowLines].join('\r\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    link.href = url;
    link.setAttribute('download', `query_results_${timestamp}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const exportToJson = (e) => {
    e.stopPropagation();
    if (!data || data.length === 0) return;

    const jsonContent = JSON.stringify(data, null, 2);
    const blob = new Blob([jsonContent], { type: 'application/json;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    link.href = url;
    link.setAttribute('download', `query_results_${timestamp}.json`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="mt-3 w-full max-w-full overflow-hidden">
      {/* Collapsible toggle header with Export Controls */}
      <div
        onClick={() => setIsExpanded(!isExpanded)}
        className={`w-full flex items-center justify-between px-3.5 py-2 rounded-lg text-xs font-medium border transition-colors cursor-pointer select-none ${
          isDark
            ? 'bg-slate-900/60 border-slate-800 text-slate-300 hover:bg-slate-800/80'
            : 'bg-slate-100 border-slate-200 text-slate-700 hover:bg-slate-200/60'
        }`}
      >
        <span className="flex items-center gap-2">
          <TableIcon className="w-3.5 h-3.5 text-indigo-400" />
          <span>Query Results ({data.length} {data.length === 1 ? 'record' : 'records'}, {columns.length} columns)</span>
        </span>

        <div className="flex items-center gap-2">
          {/* Export CSV Button */}
          <button
            type="button"
            onClick={exportToCsv}
            className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-[11px] font-semibold border transition-all cursor-pointer ${
              isDark
                ? 'bg-slate-800/90 hover:bg-emerald-600/20 text-slate-300 hover:text-emerald-300 border-slate-700/80 hover:border-emerald-500/40'
                : 'bg-white hover:bg-emerald-50 text-slate-700 hover:text-emerald-700 border-slate-300 hover:border-emerald-300 shadow-xs'
            }`}
            title="Download table data as CSV (opens in Microsoft Excel)"
          >
            <Download className="w-3 h-3 text-emerald-500" />
            <span>CSV</span>
          </button>

          {/* Export JSON Button */}
          <button
            type="button"
            onClick={exportToJson}
            className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-[11px] font-semibold border transition-all cursor-pointer ${
              isDark
                ? 'bg-slate-800/90 hover:bg-indigo-600/20 text-slate-300 hover:text-indigo-300 border-slate-700/80 hover:border-indigo-500/40'
                : 'bg-white hover:bg-indigo-50 text-slate-700 hover:text-indigo-700 border-slate-300 hover:border-indigo-300 shadow-xs'
            }`}
            title="Download raw data as JSON file"
          >
            <Download className="w-3 h-3 text-indigo-500" />
            <span>JSON</span>
          </button>

          <div className={`w-[1px] h-3.5 mx-0.5 ${isDark ? 'bg-slate-700/70' : 'bg-slate-300'}`} />

          {isExpanded ? <ChevronUp className="w-3.5 h-3.5 text-slate-400" /> : <ChevronDown className="w-3.5 h-3.5 text-slate-400" />}
        </div>
      </div>

      {/* Table Body with Localized Container Scrolling (Horizontal & Vertical) */}
      {isExpanded && (
        <div className={`mt-2 border rounded-xl overflow-x-auto overflow-y-auto max-h-60 custom-scrollbar w-full max-w-full ${
          isDark ? 'border-slate-800 bg-slate-950/40' : 'border-slate-200 bg-white'
        }`}>
          <table className="text-left text-xs border-collapse min-w-full">
            <thead className={`sticky top-0 uppercase tracking-wider font-semibold border-b z-10 ${
              isDark 
                ? 'bg-slate-900 text-slate-300 border-slate-800' 
                : 'bg-slate-100 text-slate-700 border-slate-200'
            }`}>
              <tr>
                {columns.map((col) => (
                  <th 
                    key={col} 
                    className="px-3.5 py-2.5 whitespace-nowrap min-w-[120px] max-w-[200px] truncate text-[11px]"
                    title={col}
                  >
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className={`divide-y ${isDark ? 'divide-slate-800/80' : 'divide-slate-200'}`}>
              {data.map((row, rIdx) => (
                <tr key={rIdx} className={isDark ? 'hover:bg-slate-800/30 transition-colors' : 'hover:bg-slate-50 transition-colors'}>
                  {columns.map((col, cIdx) => {
                    const formatted = formatCellValue(row[col]);
                    const isObj = typeof row[col] === 'object' && row[col] !== null;
                    return (
                      <td 
                        key={cIdx} 
                        className={`px-3.5 py-2 font-mono text-xs whitespace-nowrap min-w-[120px] max-w-[200px] truncate ${
                          isDark ? 'text-slate-300' : 'text-slate-700'
                        } ${isObj ? 'text-amber-300/90' : ''}`} 
                        title={formatted}
                      >
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
