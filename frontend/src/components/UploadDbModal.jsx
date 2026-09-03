import React, { useState, useRef } from 'react';
import { Upload, X, Database, CheckCircle2, AlertTriangle, Loader2, Trash2, Lock, Layers, FileJson } from 'lucide-react';

export default function UploadDbModal({ 
  isOpen, 
  onClose, 
  databases = [], 
  onUploadSuccess, 
  onDeleteDatabase,
  isDark, 
  apiBaseUrl 
}) {
  const [selectedType, setSelectedType] = useState('sql'); // 'sql' | 'nosql'
  const [file, setFile] = useState(null);
  const [dbName, setDbName] = useState('');
  const [isUploading, setIsUploading] = useState(false);
  const [deletingId, setDeletingId] = useState(null);
  const [errorMsg, setErrorMsg] = useState(null);
  const fileInputRef = useRef(null);

  if (!isOpen) return null;

  const handleTypeChange = (type) => {
    setSelectedType(type);
    setFile(null);
    setDbName('');
    setErrorMsg(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleFileChange = (e) => {
    const selected = e.target.files[0];
    if (!selected) return;

    setErrorMsg(null);
    const fileName = selected.name.toLowerCase();
    const isSqlFile = fileName.endsWith('.db') || fileName.endsWith('.sqlite') || fileName.endsWith('.sqlite3');
    const isNoSqlFile = fileName.endsWith('.json') || fileName.endsWith('.jsonl');

    // Strict validation against user's selected type
    if (selectedType === 'sql' && !isSqlFile) {
      setErrorMsg(`Invalid file type for SQL Database! You selected "${selected.name}", but SQL requires a .db or .sqlite file.`);
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      return;
    }

    if (selectedType === 'nosql' && !isNoSqlFile) {
      setErrorMsg(`Invalid file type for NoSQL Database! You selected "${selected.name}", but NoSQL requires a .json or .jsonl document file.`);
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      return;
    }

    setFile(selected);
    // Auto-populate default name from filename if empty
    if (!dbName.trim()) {
      const cleanName = selected.name.replace(/\.(db|sqlite|sqlite3|json|jsonl)$/i, '').replace(/[_-]/g, ' ');
      setDbName(cleanName.charAt(0).toUpperCase() + cleanName.slice(1));
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) {
      setErrorMsg(`Please select a valid ${selectedType === 'sql' ? '.db / .sqlite' : '.json'} file first.`);
      return;
    }
    if (!dbName.trim()) {
      setErrorMsg("Please provide a custom name for this dataset.");
      return;
    }

    setIsUploading(true);
    setErrorMsg(null);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("name", dbName.trim());
    formData.append("type", selectedType);

    try {
      const response = await fetch(`${apiBaseUrl}/databases/upload`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || "Upload failed.");
      }

      const newDb = await response.json();
      onUploadSuccess(newDb);
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
    if (!window.confirm(`Are you sure you want to delete "${name}"?`)) {
      return;
    }

    setDeletingId(dbId);
    setErrorMsg(null);

    try {
      const response = await fetch(`${apiBaseUrl}/databases/${dbId}`, {
        method: "DELETE",
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || "Failed to delete data source.");
      }

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
              <p className="text-xs text-slate-400">View active databases or upload new SQL/NoSQL datasets</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-200 cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* SECTION 1: INSTALLED DATASETS LIST */}
        {/* SECTION 1: INSTALLED DATASETS LIST (CATEGORIZED) */}
        <div className="mb-5 space-y-3">
          <div className="flex items-center justify-between px-0.5">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              Installed Data Sources ({databases.length})
            </span>
          </div>

          <div className="max-h-52 overflow-y-auto custom-scrollbar space-y-3 pr-1">
            {/* Category A: Relational SQL Databases */}
            {databases.some(d => d.type !== 'nosql') && (
              <div>
                <div className="flex items-center gap-1.5 mb-1.5 px-1 text-[10px] font-bold text-indigo-400 uppercase tracking-wider">
                  <Database className="w-3 h-3" />
                  <span>Relational SQL Databases ({databases.filter(d => d.type !== 'nosql').length})</span>
                </div>
                <div className={`divide-y rounded-xl border overflow-hidden ${
                  isDark ? 'bg-slate-950/60 border-slate-800 divide-slate-800/80' : 'bg-slate-50 border-slate-200 divide-slate-200'
                }`}>
                  {databases.filter(d => d.type !== 'nosql').map((db) => {
                    const isDefault = Boolean(db.is_default || db.id === 'chinook');
                    return (
                      <div key={db.id} className="flex items-center justify-between p-2.5 text-xs">
                        <div className="flex items-center gap-2.5 truncate pr-2">
                          <Database className={`w-4 h-4 shrink-0 ${isDefault ? 'text-indigo-400' : 'text-emerald-400'}`} />
                          <div className="truncate">
                            <div className="flex items-center gap-1.5">
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
                          <button
                            onClick={() => handleDelete(db.id, db.name)}
                            disabled={deletingId === db.id}
                            className="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] font-medium bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 transition-all cursor-pointer shrink-0"
                            title="Delete this custom SQL database"
                          >
                            {deletingId === db.id ? (
                              <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            ) : (
                              <Trash2 className="w-3.5 h-3.5" />
                            )}
                            <span>Delete</span>
                          </button>
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
                            <div className="flex items-center gap-1.5">
                              <p className="font-semibold truncate">{db.name}</p>
                              <span className="px-1.5 py-0.2 rounded text-[9px] font-mono uppercase font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">
                                NoSQL
                              </span>
                            </div>
                            <p className="text-[10px] text-slate-400 flex items-center gap-1 mt-0.5 font-mono">
                              <Layers className="w-3 h-3" /> {db.doc_count || 0} documents
                            </p>
                          </div>
                        </div>

                        {isDefault ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20 shrink-0">
                            <Lock className="w-3 h-3" /> Default (Locked)
                          </span>
                        ) : (
                          <button
                            onClick={() => handleDelete(db.id, db.name)}
                            disabled={deletingId === db.id}
                            className="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] font-medium bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 transition-all cursor-pointer shrink-0"
                            title="Delete this custom NoSQL database"
                          >
                            {deletingId === db.id ? (
                              <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            ) : (
                              <Trash2 className="w-3.5 h-3.5" />
                            )}
                            <span>Delete</span>
                          </button>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* SECTION 2: UPLOAD DATASET (TYPE SELECTOR FIRST) */}
        <div className="pt-4 border-t border-slate-700/40">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-2 px-0.5">
            1. Select Dataset Type to Upload
          </span>

          {/* Type Selector Tabs */}
          <div className="grid grid-cols-2 gap-2 mb-4">
            <button
              type="button"
              onClick={() => handleTypeChange('sql')}
              className={`flex items-center justify-center gap-2 p-3 rounded-xl border text-xs font-semibold transition-all cursor-pointer ${
                selectedType === 'sql'
                  ? 'bg-indigo-600/15 border-indigo-500 text-indigo-400 shadow-sm shadow-indigo-500/20'
                  : isDark ? 'bg-slate-950/40 border-slate-800 text-slate-400 hover:border-slate-700' : 'bg-slate-50 border-slate-200 text-slate-600 hover:border-slate-300'
              }`}
            >
              <Database className="w-4 h-4 text-indigo-400" />
              <div className="text-left">
                <div className="text-xs font-bold">SQL Database</div>
                <div className="text-[10px] text-slate-400 font-normal">.db, .sqlite, .sqlite3</div>
              </div>
            </button>

            <button
              type="button"
              onClick={() => handleTypeChange('nosql')}
              className={`flex items-center justify-center gap-2 p-3 rounded-xl border text-xs font-semibold transition-all cursor-pointer ${
                selectedType === 'nosql'
                  ? 'bg-amber-500/15 border-amber-500 text-amber-400 shadow-sm shadow-amber-500/20'
                  : isDark ? 'bg-slate-950/40 border-slate-800 text-slate-400 hover:border-slate-700' : 'bg-slate-50 border-slate-200 text-slate-600 hover:border-slate-300'
              }`}
            >
              <FileJson className="w-4 h-4 text-amber-400" />
              <div className="text-left">
                <div className="text-xs font-bold">NoSQL Document</div>
                <div className="text-[10px] text-slate-400 font-normal">.json, .jsonl</div>
              </div>
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* 2. File Picker */}
            <div>
              <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1.5 px-0.5">
                2. Choose {selectedType === 'sql' ? 'SQL (.db)' : 'NoSQL (.json)'} File
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
                  accept={selectedType === 'sql' ? '.db,.sqlite,.sqlite3' : '.json,.jsonl'}
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
                    {selectedType === 'sql' ? (
                      <Database className="w-5 h-5 mx-auto mb-1 text-indigo-400" />
                    ) : (
                      <FileJson className="w-5 h-5 mx-auto mb-1 text-amber-400" />
                    )}
                    <p className="text-xs font-medium">
                      Click to select {selectedType === 'sql' ? 'SQLite (.db, .sqlite)' : 'NoSQL JSON (.json, .jsonl)'} file
                    </p>
                    <p className="text-[10px] text-slate-400">
                      {selectedType === 'sql' ? 'Strictly accepts .db, .sqlite, .sqlite3' : 'Strictly accepts .json, .jsonl'}
                    </p>
                  </div>
                )}
              </div>
            </div>

            {/* 3. Custom Name Input */}
            <div>
              <label className="block text-xs font-semibold mb-1 text-slate-300">
                3. Custom Display Name
              </label>
              <input
                type="text"
                value={dbName}
                onChange={(e) => setDbName(e.target.value)}
                placeholder={selectedType === 'sql' ? 'e.g. Sales 2025 (SQL), Inventory DB' : 'e.g. Product Catalog (JSON), User Events'}
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
                <span>{isUploading ? "Uploading..." : "Save & Register"}</span>
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
