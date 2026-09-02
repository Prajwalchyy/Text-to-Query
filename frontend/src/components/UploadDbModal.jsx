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
  const [file, setFile] = useState(null);
  const [dbName, setDbName] = useState('');
  const [isUploading, setIsUploading] = useState(false);
  const [deletingId, setDeletingId] = useState(null);
  const [errorMsg, setErrorMsg] = useState(null);
  const fileInputRef = useRef(null);

  if (!isOpen) return null;

  const handleFileChange = (e) => {
    const selected = e.target.files[0];
    if (selected) {
      setFile(selected);
      // Auto-populate default name from filename if empty
      if (!dbName.trim()) {
        const cleanName = selected.name.replace(/\.(db|sqlite|sqlite3|json|jsonl)$/i, '').replace(/[_-]/g, ' ');
        setDbName(cleanName.charAt(0).toUpperCase() + cleanName.slice(1));
      }
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) {
      setErrorMsg("Please select an SQLite (.db) or NoSQL (.json) file.");
      return;
    }
    if (!dbName.trim()) {
      setErrorMsg("Please provide a name for this dataset.");
      return;
    }

    setIsUploading(true);
    setErrorMsg(null);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("name", dbName.trim());

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
              <p className="text-xs text-slate-400">View active SQL/NoSQL sources or upload new datasets</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-200 cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* SECTION 1: INSTALLED DATABASES LIST */}
        <div className="mb-6">
          <div className="flex items-center justify-between mb-2 px-0.5">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              Installed Data Sources ({databases.length})
            </span>
          </div>

          <div className={`divide-y rounded-xl border overflow-hidden max-h-52 overflow-y-auto ${
            isDark ? 'bg-slate-950/60 border-slate-800 divide-slate-800/80' : 'bg-slate-50 border-slate-200 divide-slate-200'
          }`}>
            {databases.map((db) => {
              const isDefault = Boolean(db.is_default || db.id === 'chinook' || db.id === 'ecommerce_store');
              const isNoSql = db.type === 'nosql';

              return (
                <div key={db.id} className="flex items-center justify-between p-3 text-xs">
                  <div className="flex items-center gap-2.5 truncate pr-2">
                    {isNoSql ? (
                      <FileJson className="w-4 h-4 shrink-0 text-amber-400" />
                    ) : (
                      <Database className={`w-4 h-4 shrink-0 ${isDefault ? 'text-indigo-400' : 'text-emerald-400'}`} />
                    )}
                    <div className="truncate">
                      <div className="flex items-center gap-1.5">
                        <p className="font-semibold truncate">{db.name}</p>
                        <span className={`px-1.5 py-0.2 rounded text-[9px] font-mono uppercase font-semibold ${
                          isNoSql ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                        }`}>
                          {isNoSql ? 'NoSQL' : 'SQL'}
                        </span>
                      </div>
                      <p className="text-[10px] text-slate-400 flex items-center gap-1 mt-0.5 font-mono">
                        <Layers className="w-3 h-3" /> {isNoSql ? `${db.doc_count || 0} docs` : `${db.table_count || 0} tables`}
                      </p>
                    </div>
                  </div>

                  {isDefault ? (
                    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[10px] font-medium bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 shrink-0">
                      <Lock className="w-3 h-3" /> Default (Locked)
                    </span>
                  ) : (
                    <button
                      onClick={() => handleDelete(db.id, db.name)}
                      disabled={deletingId === db.id}
                      className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-medium bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 transition-all cursor-pointer shrink-0"
                      title="Delete this custom data source"
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

        {/* SECTION 2: UPLOAD NEW DATASET FORM */}
        <div className="pt-4 border-t border-slate-700/40">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-3 px-0.5">
            Upload New Data Source (.db, .sqlite, .json)
          </span>

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* File Picker */}
            <div>
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
                  accept=".db,.sqlite,.sqlite3,.json,.jsonl"
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
                    <Upload className="w-5 h-5 mx-auto mb-1 text-indigo-400" />
                    <p className="text-xs font-medium">Click to select SQL (.db) or NoSQL (.json) file</p>
                    <p className="text-[10px] text-slate-400">Supports .db, .sqlite, .json, .jsonl</p>
                  </div>
                )}
              </div>
            </div>

            {/* Dataset Name Input */}
            <div>
              <label className="block text-xs font-semibold mb-1 text-slate-300">
                Custom Display Name
              </label>
              <input
                type="text"
                value={dbName}
                onChange={(e) => setDbName(e.target.value)}
                placeholder="e.g. Sales 2025, Ecommerce Orders, Patient Records"
                className={`w-full px-3 py-2 rounded-xl border text-xs focus:outline-none focus:border-indigo-500 transition-colors ${
                  isDark ? 'bg-slate-950 border-slate-700 text-white placeholder-slate-500' : 'bg-slate-50 border-slate-300 text-slate-900 placeholder-slate-400'
                }`}
              />
            </div>

            {/* Error Message */}
            {errorMsg && (
              <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-xs text-rose-400 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 shrink-0" />
                <span>{errorMsg}</span>
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
