import React, { useState, useRef } from 'react';
import { Upload, X, Database, CheckCircle2, AlertTriangle, Loader2 } from 'lucide-react';

export default function UploadDbModal({ isOpen, onClose, onUploadSuccess, isDark, apiBaseUrl }) {
  const [file, setFile] = useState(null);
  const [dbName, setDbName] = useState('');
  const [isUploading, setIsUploading] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);
  const fileInputRef = useRef(null);

  if (!isOpen) return null;

  const handleFileChange = (e) => {
    const selected = e.target.files[0];
    if (selected) {
      setFile(selected);
      // Auto-populate default name from filename if empty
      if (!dbName.trim()) {
        const cleanName = selected.name.replace(/\.(db|sqlite|sqlite3)$/i, '').replace(/[_-]/g, ' ');
        setDbName(cleanName.charAt(0).toUpperCase() + cleanName.slice(1));
      }
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) {
      setErrorMsg("Please select a .db or .sqlite database file.");
      return;
    }
    if (!dbName.trim()) {
      setErrorMsg("Please provide a name for this database.");
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
      onClose();
    } catch (err) {
      setErrorMsg(err.message || "Failed to upload database.");
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 animate-fadeIn">
      <div className={`w-full max-w-md rounded-2xl p-6 shadow-2xl border transition-all ${
        isDark ? 'bg-slate-900 border-slate-700/80 text-slate-100' : 'bg-white border-slate-200 text-slate-900'
      }`}>
        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-indigo-500/10 border border-indigo-500/30 text-indigo-400">
              <Database className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold">Add Custom Database</h3>
              <p className="text-xs text-slate-400">Upload and name your own SQLite file</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-200 cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Upload Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* File Picker */}
          <div>
            <label className="block text-xs font-semibold mb-1.5 text-slate-300">
              Select SQLite File (.db, .sqlite)
            </label>
            <div 
              onClick={() => fileInputRef.current?.click()}
              className={`border-2 border-dashed rounded-xl p-5 text-center cursor-pointer transition-colors ${
                file 
                  ? 'border-emerald-500/50 bg-emerald-500/5' 
                  : isDark ? 'border-slate-700 hover:border-indigo-500 bg-slate-950/40' : 'border-slate-300 hover:border-indigo-500 bg-slate-50'
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".db,.sqlite,.sqlite3"
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
                  <Upload className="w-6 h-6 mx-auto mb-1.5 text-indigo-400" />
                  <p className="text-xs font-medium">Click to browse your .db file</p>
                  <p className="text-[10px] text-slate-400 mt-0.5">Supports SQLite3 formats</p>
                </div>
              )}
            </div>
          </div>

          {/* Database Name Input */}
          <div>
            <label className="block text-xs font-semibold mb-1.5 text-slate-300">
              Custom Database Name
            </label>
            <input
              type="text"
              value={dbName}
              onChange={(e) => setDbName(e.target.value)}
              placeholder="e.g. Sales 2025, Store Inventory, HR Database"
              className={`w-full px-3.5 py-2.5 rounded-xl border text-xs focus:outline-none focus:border-indigo-500 transition-colors ${
                isDark ? 'bg-slate-950 border-slate-700 text-white placeholder-slate-500' : 'bg-slate-50 border-slate-300 text-slate-900 placeholder-slate-400'
              }`}
            />
            <p className="text-[10px] text-slate-400 mt-1">
              This is the display name that will appear in your database selector dropdown.
            </p>
          </div>

          {/* Error Message */}
          {errorMsg && (
            <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-xs text-rose-400 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex items-center justify-end gap-2.5 pt-2">
            <button
              type="button"
              onClick={onClose}
              className={`px-4 py-2 rounded-xl text-xs font-medium cursor-pointer ${
                isDark ? 'text-slate-400 hover:text-slate-200' : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isUploading || !file || !dbName.trim()}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white text-xs font-semibold shadow-sm shadow-indigo-600/30 transition-all cursor-pointer"
            >
              {isUploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
              <span>{isUploading ? "Uploading..." : "Save & Register"}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
