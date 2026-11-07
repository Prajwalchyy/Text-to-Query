import React, { useState, useRef } from 'react';
import { 
  Upload, 
  X, 
  Database, 
  CheckCircle2, 
  AlertTriangle, 
  Loader2, 
  Trash2, 
  Lock, 
  Layers, 
  FileJson,
  FileSpreadsheet,
  Check,
  Sparkles
} from 'lucide-react';

/**
 * Extracts normalized file extension (e.g. '.csv', '.db').
 */
const getFileExtension = (filename = '') => {
  const parts = filename.toLowerCase().split('.');
  return parts.length > 1 ? `.${parts.pop()}` : '';
};

/**
 * Detects the engine type and supported query languages/tools from file extension.
 */
const detectFileTypeInfo = (filename = '') => {
  const ext = getFileExtension(filename);
  if (!ext) return null;

  // 1. Relational SQL (.db, .sqlite, .sql, etc.)
  if (['.db', '.sqlite', '.sqlite3', '.s3db', '.sl3', '.sql'].includes(ext)) {
    return {
      ext,
      category: 'SQL Database',
      dbType: 'sql',
      badgeColor: 'indigo',
      tools: [
        { name: 'SQL', color: 'indigo' },
        { name: 'Python (Pandas)', color: 'amber' },
        { name: 'R', color: 'blue' }
      ]
    };
  }

  // 2. NoSQL Document Store (.json, .jsonl, .bson)
  if (['.json', '.jsonl', '.bson'].includes(ext)) {
    return {
      ext,
      category: 'NoSQL Document Store',
      dbType: 'nosql',
      badgeColor: 'amber',
      tools: [
        { name: 'NoSQL', color: 'amber' },
        { name: 'Python', color: 'emerald' },
        { name: 'R', color: 'blue' }
      ]
    };
  }

  // 3. Spreadsheets: .csv, .tsv
  if (['.csv', '.tsv'].includes(ext)) {
    return {
      ext,
      category: 'CSV Spreadsheet',
      dbType: 'csv',
      badgeColor: 'emerald',
      tools: [
        { name: 'Python (Pandas)', color: 'amber' },
        { name: 'Excel', color: 'emerald' },
        { name: 'R', color: 'blue' }
      ]
    };
  }

  // 4. Spreadsheets: .xlsx, .xls
  if (['.xlsx', '.xls'].includes(ext)) {
    return {
      ext,
      category: 'Excel Workbook',
      dbType: 'excel',
      badgeColor: 'emerald',
      tools: [
        { name: 'Python (Pandas)', color: 'amber' },
        { name: 'Excel', color: 'emerald' },
        { name: 'R', color: 'blue' }
      ]
    };
  }

  // 5. Other file formats supported by Pandas or R that contain tabular data
  if (['.parquet', '.feather', '.orc', '.h5', '.hdf5', '.dta', '.sav', '.sas7bdat'].includes(ext)) {
    return {
      ext,
      category: 'Tabular Dataset',
      dbType: 'csv',
      badgeColor: 'purple',
      tools: [
        { name: 'Python (Pandas)', color: 'amber' },
        { name: 'R', color: 'blue' }
      ]
    };
  }

  return null;
};

export default function UploadDatasets({ 
  isOpen, 
  onClose, 
  databases = [], 
  onUploadSuccess, 
  onDeleteDatabase,
  isDark, 
  apiBaseUrl 
}) {
  const [file, setFile] = useState(null);
  const [dbName, setDbName] = useState('');
  const [isUploading, setIsUploading] = useState(false);
  const [deletingId, setDeletingId] = useState(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState(null);
  const [errorMsg, setErrorMsg] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);
  const fileInputRef = useRef(null);

  if (!isOpen) return null;

  // Real-time detected file type and supported languages from active file
  const detectedInfo = file ? detectFileTypeInfo(file.name) : null;

  const handleFileChange = (e) => {
    const selectedFile = e.target.files?.[0];
    if (!selectedFile) return;

    setErrorMsg(null);
    setSuccessMsg(null);

    // Validate that the file has a supported format
    const info = detectFileTypeInfo(selectedFile.name);
    if (!info) {
      setErrorMsg(`Unsupported file type: '${selectedFile.name}'. Please choose a supported dataset file (.db, .sqlite, .sql, .json, .csv, .xlsx, or .parquet).`);
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      return;
    }

    setFile(selectedFile);

    if (!dbName.trim()) {
      const cleanName = selectedFile.name
        .replace(/\.(db|sqlite|sqlite3|s3db|sl3|sql|json|jsonl|bson|csv|tsv|xlsx|xls|parquet|feather|orc)$/i, '')
        .replace(/[_-]/g, ' ');
      setDbName(cleanName.charAt(0).toUpperCase() + cleanName.slice(1));
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) {
      setErrorMsg("Please select a dataset file first.");
      return;
    }

    if (!dbName.trim()) {
      setErrorMsg("Please provide a custom display name for this dataset.");
      return;
    }

    setIsUploading(true);
    setErrorMsg(null);
    setSuccessMsg(null);

    const primaryType = detectedInfo?.dbType || 'sql';

    const formData = new FormData();
    formData.append("file", file);
    formData.append("name", dbName.trim());
    formData.append("type", primaryType);

    try {
      const response = await fetch(`${apiBaseUrl}/databases/upload`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || "Upload failed.");
      }

      const result = await response.json();
      if (result.databases) {
        onUploadSuccess(result.databases);
      } else {
        onUploadSuccess(result);
      }

      setFile(null);
      setDbName('');
      onClose();
    } catch (err) {
      setErrorMsg(err.message || "Failed to upload file.");
    } finally {
      setIsUploading(false);
    }
  };

  const handleDelete = async (dbId, name) => {
    setDeletingId(dbId);
    setConfirmDeleteId(null);
    setErrorMsg(null);
    setSuccessMsg(null);

    try {
      const response = await fetch(`${apiBaseUrl}/databases/${dbId}`, {
        method: "DELETE",
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || "Failed to delete data source.");
      }

      setSuccessMsg(`Data source "${name}" deleted successfully.`);
      if (onDeleteDatabase) {
        onDeleteDatabase(dbId);
      }
    } catch (err) {
      setErrorMsg(err.message || "Failed to delete data source.");
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 animate-fadeIn">
      <div className={`w-full max-w-lg rounded-2xl p-6 shadow-2xl border transition-all my-8 ${
        isDark ? 'bg-slate-900 border-slate-700/80 text-slate-100' : 'bg-white border-slate-200 text-slate-900'
      }`}>
        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-indigo-500/10 border border-indigo-500/30 text-indigo-400">
              <Database className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold">Manage Data Sources</h3>
              <p className="text-xs text-slate-400">View active data sources or connect new SQL, NoSQL & Tabular datasets</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-200 cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Global Success / Feedback Message */}
        {successMsg && (
          <div className="mb-4 p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-xs text-emerald-400 flex items-start gap-2 animate-fadeIn">
            <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
            <span className="leading-relaxed font-medium">{successMsg}</span>
          </div>
        )}

        {/* SECTION 1: INSTALLED DATASETS LIST (CATEGORIZED) */}
        <div className="mb-5 space-y-3">
          <div className="flex items-center justify-between px-0.5">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              Installed Data Sources ({databases.length})
            </span>
          </div>

          <div className="max-h-52 overflow-y-auto custom-scrollbar space-y-3 pr-1">
            {/* Category A: Relational SQL Databases */}
            {databases.some(d => d.type === 'sql' || (!d.type && !['nosql', 'csv', 'excel'].includes(d.type))) && (
              <div>
                <div className="flex items-center gap-1.5 mb-1.5 px-1 text-[10px] font-bold text-indigo-400 uppercase tracking-wider">
                  <Database className="w-3 h-3" />
                  <span>Relational SQL Databases ({databases.filter(d => d.type === 'sql' || (!d.type && !['nosql', 'csv', 'excel'].includes(d.type))).length})</span>
                </div>
                <div className={`divide-y rounded-xl border overflow-hidden ${
                  isDark ? 'bg-slate-950/60 border-slate-800 divide-slate-800/80' : 'bg-slate-50 border-slate-200 divide-slate-200'
                }`}>
                  {databases.filter(d => d.type === 'sql' || (!d.type && !['nosql', 'csv', 'excel'].includes(d.type))).map((db) => {
                    const isDefault = Boolean(db.is_default || db.id === 'chinook');
                    return (
                      <div key={db.id} className="flex items-center justify-between p-2.5 text-xs">
                        <div className="flex items-center gap-2.5 truncate pr-2">
                          <Database className={`w-4 h-4 shrink-0 ${isDefault ? 'text-indigo-400' : 'text-emerald-400'}`} />
                          <div className="truncate">
                            <div className="flex items-center gap-1.5 flex-wrap">
                              <p className="font-semibold truncate">{db.name}</p>
                              <span className="px-1.5 py-0.2 rounded text-[9px] font-mono uppercase font-semibold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                                SQL
                              </span>
                            </div>
                            <p className="text-[10px] text-slate-400 flex items-center gap-1 mt-0.5 font-mono">
                              <Layers className="w-3 h-3" /> {db.table_count || 0} tables
                            </p>
                          </div>
                        </div>

                        {isDefault ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 shrink-0">
                            <Lock className="w-3 h-3" /> Default (Locked)
                          </span>
                        ) : (
                          <div className="flex items-center gap-1.5 shrink-0">
                            {confirmDeleteId === db.id ? (
                              <div className="flex items-center gap-1 shrink-0 animate-fadeIn">
                                <button
                                  onClick={() => handleDelete(db.id, db.name)}
                                  disabled={deletingId === db.id}
                                  className="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] font-bold bg-rose-600 hover:bg-rose-500 text-white transition-all cursor-pointer shadow-xs shadow-rose-600/30"
                                  title="Permanently delete this database"
                                >
                                  {deletingId === db.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <Trash2 className="w-3 h-3" />}
                                  <span>Confirm</span>
                                </button>
                                <button
                                  onClick={() => setConfirmDeleteId(null)}
                                  className="p-1 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-slate-200 cursor-pointer"
                                  title="Cancel"
                                >
                                  <X className="w-3 h-3" />
                                </button>
                              </div>
                            ) : (
                              <button
                                onClick={() => setConfirmDeleteId(db.id)}
                                className="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] font-medium bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 transition-all cursor-pointer shrink-0"
                                title="Delete this custom SQL database"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                                <span>Delete</span>
                              </button>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Category B: NoSQL Document Databases */}
            {databases.some(d => d.type === 'nosql') && (
              <div>
                <div className="flex items-center gap-1.5 mb-1.5 px-1 text-[10px] font-bold text-amber-400 uppercase tracking-wider">
                  <FileJson className="w-3 h-3" />
                  <span>NoSQL Document Databases ({databases.filter(d => d.type === 'nosql').length})</span>
                </div>
                <div className={`divide-y rounded-xl border overflow-hidden ${
                  isDark ? 'bg-slate-950/60 border-slate-800 divide-slate-800/80' : 'bg-slate-50 border-slate-200 divide-slate-200'
                }`}>
                  {databases.filter(d => d.type === 'nosql').map((db) => {
                    const isDefault = Boolean(db.is_default || db.id === 'ecommerce_store');
                    return (
                      <div key={db.id} className="flex items-center justify-between p-2.5 text-xs">
                        <div className="flex items-center gap-2.5 truncate pr-2">
                          <FileJson className="w-4 h-4 shrink-0 text-amber-400" />
                          <div className="truncate">
                            <div className="flex items-center gap-1.5 flex-wrap">
                              <p className="font-semibold truncate">{db.name}</p>
                              <span className="px-1.5 py-0.2 rounded text-[9px] font-mono uppercase font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">
                                NoSQL
                              </span>
                            </div>
                            <p className="text-[10px] text-slate-400 flex items-center gap-1 mt-0.5 font-mono">
                              <Layers className="w-3 h-3" /> {db.table_count || 1} {db.table_count === 1 ? 'collection' : 'collections'}
                            </p>
                          </div>
                        </div>

                        {isDefault ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20 shrink-0">
                            <Lock className="w-3 h-3" /> Default (Locked)
                          </span>
                        ) : (
                          <div className="flex items-center gap-1.5 shrink-0">
                            {confirmDeleteId === db.id ? (
                              <div className="flex items-center gap-1 shrink-0 animate-fadeIn">
                                <button
                                  onClick={() => handleDelete(db.id, db.name)}
                                  disabled={deletingId === db.id}
                                  className="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] font-bold bg-rose-600 hover:bg-rose-500 text-white transition-all cursor-pointer shadow-xs shadow-rose-600/30"
                                  title="Permanently delete this database"
                                >
                                  {deletingId === db.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <Trash2 className="w-3 h-3" />}
                                  <span>Confirm</span>
                                </button>
                                <button
                                  onClick={() => setConfirmDeleteId(null)}
                                  className="p-1 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-slate-200 cursor-pointer"
                                  title="Cancel"
                                >
                                  <X className="w-3 h-3" />
                                </button>
                              </div>
                            ) : (
                              <button
                                onClick={() => setConfirmDeleteId(db.id)}
                                className="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] font-medium bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 transition-all cursor-pointer shrink-0"
                                title="Delete this custom NoSQL database"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                                <span>Delete</span>
                              </button>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Category C: Tabular Datasets (CSV & Excel) */}
            {databases.some(d => d.type === 'csv' || d.type === 'excel') && (
              <div>
                <div className="flex items-center gap-1.5 mb-1.5 px-1 text-[10px] font-bold text-emerald-400 uppercase tracking-wider">
                  <FileSpreadsheet className="w-3 h-3" />
                  <span>Tabular Datasets ({databases.filter(d => d.type === 'csv' || d.type === 'excel').length})</span>
                </div>
                <div className={`divide-y rounded-xl border overflow-hidden ${
                  isDark ? 'bg-slate-950/60 border-slate-800 divide-slate-800/80' : 'bg-slate-50 border-slate-200 divide-slate-200'
                }`}>
                  {databases.filter(d => d.type === 'csv' || d.type === 'excel').map((db) => {
                    const isDefault = Boolean(db.is_default || db.id === 'sales_performance' || db.id === 'financial_budget');
                    const isExcel = db.type === 'excel';
                    return (
                      <div key={db.id} className="flex items-center justify-between p-2.5 text-xs">
                        <div className="flex items-center gap-2.5 truncate pr-2">
                          <FileSpreadsheet className={`w-4 h-4 shrink-0 ${isDefault ? 'text-emerald-400' : 'text-teal-400'}`} />
                          <div className="truncate">
                            <div className="flex items-center gap-1.5 flex-wrap">
                              <p className="font-semibold truncate">{db.name}</p>
                              <span className="px-1.5 py-0.2 rounded text-[9px] font-mono uppercase font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                                {isExcel ? 'Excel' : 'CSV'}
                              </span>
                            </div>
                            <p className="text-[10px] text-slate-400 flex items-center gap-1 mt-0.5 font-mono">
                              <Layers className="w-3 h-3" /> {(db.sheet_count || db.table_count || 1) <= 1 && db.column_count
                                ? `${db.column_count} ${db.column_count === 1 ? 'column' : 'columns'}, ${(db.row_count || 0).toLocaleString()} rows`
                                : (db.sheet_count || db.table_count || 1) > 1
                                  ? `${(db.row_count || 0).toLocaleString()} rows (${db.sheet_count || db.table_count} sheets)`
                                  : `${(db.row_count || 0).toLocaleString()} rows`}
                            </p>
                          </div>
                        </div>

                        {isDefault ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-slate-500/10 text-slate-400 border border-slate-500/20 shrink-0">
                            <Lock className="w-3 h-3" /> Default
                          </span>
                        ) : (
                          <div className="flex items-center gap-1 shrink-0">
                            {confirmDeleteId === db.id ? (
                              <div className="flex items-center gap-1 shrink-0 animate-fadeIn">
                                <button
                                  onClick={() => handleDelete(db.id, db.name)}
                                  disabled={deletingId === db.id}
                                  className="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] font-bold bg-rose-600 hover:bg-rose-500 text-white transition-all cursor-pointer shadow-xs shadow-rose-600/30"
                                  title="Permanently delete this tabular dataset"
                                >
                                  {deletingId === db.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <Trash2 className="w-3 h-3" />}
                                  <span>Confirm</span>
                                </button>
                                <button
                                  onClick={() => setConfirmDeleteId(null)}
                                  className="p-1 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-slate-200 cursor-pointer"
                                  title="Cancel"
                                >
                                  <X className="w-3 h-3" />
                                </button>
                              </div>
                            ) : (
                              <button
                                onClick={() => setConfirmDeleteId(db.id)}
                                className="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] font-medium bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 transition-all cursor-pointer shrink-0"
                                title="Delete this custom tabular dataset"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                                <span>Delete</span>
                              </button>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* SECTION 2: UPLOAD DATASET */}
        <div className="pt-4 border-t border-slate-700/40">
          {/* 1. Supported File Types Display */}
          <div className="mb-4">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1.5 px-0.5">
              1. Supported File Types
            </span>
            <div className="grid grid-cols-3 gap-2">
              <div className={`p-2.5 rounded-xl border text-xs transition-all ${
                isDark ? 'bg-slate-950/40 border-slate-800' : 'bg-slate-50 border-slate-200'
              }`}>
                <div className="flex items-center gap-1.5 mb-1">
                  <Database className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                  <span className="text-xs font-bold text-slate-200 truncate">SQL Database</span>
                </div>
                <div className="text-[10px] text-slate-400 font-mono truncate">
                  .db, .sqlite, .sql
                </div>
              </div>

              <div className={`p-2.5 rounded-xl border text-xs transition-all ${
                isDark ? 'bg-slate-950/40 border-slate-800' : 'bg-slate-50 border-slate-200'
              }`}>
                <div className="flex items-center gap-1.5 mb-1">
                  <FileJson className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                  <span className="text-xs font-bold text-slate-200 truncate">NoSQL Store</span>
                </div>
                <div className="text-[10px] text-slate-400 font-mono truncate">
                  .json, .jsonl, .bson
                </div>
              </div>

              <div className={`p-2.5 rounded-xl border text-xs transition-all ${
                isDark ? 'bg-slate-950/40 border-slate-800' : 'bg-slate-50 border-slate-200'
              }`}>
                <div className="flex items-center gap-1.5 mb-1">
                  <FileSpreadsheet className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                  <span className="text-xs font-bold text-slate-200 truncate">Tabular Dataset</span>
                </div>
                <div className="text-[10px] text-slate-400 font-mono truncate">
                  .csv, .xlsx, .parquet
                </div>
              </div>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* 2. File Picker */}
            <div>
              <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1.5 px-0.5">
                2. Choose Dataset File
              </span>
              <div 
                onClick={() => fileInputRef.current?.click()}
                className={`border-2 border-dashed rounded-xl p-4 text-center cursor-pointer transition-colors ${
                  file 
                    ? 'border-emerald-500/50 bg-emerald-500/5' 
                    : isDark ? 'border-slate-700 hover:border-indigo-500 bg-slate-950/40' : 'border-slate-300 hover:border-indigo-500 bg-slate-50'
                }`}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".db,.sqlite,.sqlite3,.s3db,.sl3,.sql,.json,.jsonl,.bson,.csv,.tsv,.xlsx,.xls,.parquet,.feather,.orc"
                  onChange={handleFileChange}
                  className="hidden"
                />

                {file ? (
                  <div className="flex items-center justify-center gap-2 text-xs font-medium text-emerald-400">
                    <CheckCircle2 className="w-4 h-4 shrink-0" />
                    <span className="truncate">{file.name} ({(file.size / 1024).toFixed(1)} KB)</span>
                  </div>
                ) : (
                  <div>
                    <Database className="w-5 h-5 mx-auto mb-1 text-indigo-400" />
                    <p className="text-xs font-medium">
                      Click to browse or drag and drop
                    </p>
                    <p className="text-[10px] text-slate-400 mt-0.5">
                      Select a .db, .sqlite, .sql, .json, .csv, .xlsx, or .parquet file
                    </p>
                  </div>
                )}
              </div>

              {/* Dynamic Auto-Detected Engine & Supported Languages/Tools Display */}
              {detectedInfo && (
                <div className={`mt-2.5 p-2.5 rounded-xl border flex flex-col sm:flex-row sm:items-center justify-between gap-2 animate-fadeIn ${
                  isDark ? 'bg-slate-950/60 border-slate-800' : 'bg-slate-50 border-slate-200'
                }`}>
                  <div className="flex items-center gap-2">
                    <Sparkles className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                    <div className="text-[11px] font-semibold text-slate-200">
                      <span>Detected: </span>
                      <span className="text-indigo-400 font-mono font-bold">{detectedInfo.category}</span>
                      <span className="text-[10px] text-slate-400 font-mono ml-1">({detectedInfo.ext})</span>
                    </div>
                  </div>

                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="text-[10px] text-slate-400 font-medium">Supported Tools:</span>
                    {detectedInfo.tools.map((tool, idx) => (
                      <span
                        key={idx}
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-semibold border ${
                          tool.color === 'indigo'
                            ? 'bg-indigo-500/15 text-indigo-300 border-indigo-500/30'
                            : tool.color === 'amber'
                              ? 'bg-amber-500/15 text-amber-300 border-amber-500/30'
                              : tool.color === 'emerald'
                                ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                                : 'bg-blue-500/15 text-blue-300 border-blue-500/30'
                        }`}
                      >
                        <Check className="w-2.5 h-2.5" />
                        {tool.name}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* 3. Custom Display Name */}
            <div>
              <label className="block text-xs font-semibold mb-1 text-slate-300">
                3. Custom Display Name
              </label>
              <input
                type="text"
                value={dbName}
                onChange={(e) => setDbName(e.target.value)}
                placeholder={
                  detectedInfo?.dbType === 'sql'
                    ? 'e.g. Sales 2025 (SQL)'
                    : detectedInfo?.dbType === 'nosql'
                      ? 'e.g. Product Catalog (JSON)'
                      : detectedInfo?.dbType === 'excel'
                        ? 'e.g. Financial Budget (Excel)'
                        : detectedInfo?.dbType === 'csv'
                          ? 'e.g. Sales Performance (CSV)'
                          : 'e.g. My Dataset'
                }
                className={`w-full px-3 py-2 rounded-xl border text-xs focus:outline-none focus:border-indigo-500 transition-colors ${
                  isDark ? 'bg-slate-950 border-slate-700 text-white placeholder-slate-500' : 'bg-slate-50 border-slate-300 text-slate-900 placeholder-slate-400'
                }`}
              />
            </div>

            {/* Error Message */}
            {errorMsg && (
              <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-xs text-rose-400 flex items-start gap-2 animate-fadeIn">
                <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                <span className="leading-relaxed">{errorMsg}</span>
              </div>
            )}

            {/* Action Buttons */}
            <div className="flex items-center justify-end gap-2.5 pt-1">
              <button
                type="button"
                onClick={onClose}
                className={`px-4 py-2 rounded-xl text-xs font-medium cursor-pointer ${
                  isDark ? 'text-slate-400 hover:text-slate-200' : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                Close
              </button>
              <button
                type="submit"
                disabled={isUploading || !file || !dbName.trim()}
                className="flex items-center gap-2 px-5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white text-xs font-semibold shadow-xs shadow-indigo-600/30 transition-all cursor-pointer"
              >
                {isUploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                <span>
                  {isUploading ? "Uploading..." : "Save & Register"}
                </span>
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
