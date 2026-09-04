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
  Plus,
  RefreshCw
} from 'lucide-react';

export default function UploadDbModal({ 
  isOpen, 
  onClose, 
  databases = [], 
  onUploadSuccess, 
  onDeleteDatabase,
  isDark, 
  apiBaseUrl 
}) {
  const [uploadMode, setUploadMode] = useState('full'); // 'full' | 'merge'
  const [selectedType, setSelectedType] = useState('sql'); // 'sql' | 'nosql'
  const [files, setFiles] = useState([]);
  const [dbName, setDbName] = useState('');
  const [groupName, setGroupName] = useState('');
  const [isUploading, setIsUploading] = useState(false);
  const [deletingId, setDeletingId] = useState(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState(null);
  const [appendingDbId, setAppendingDbId] = useState(null);
  const [isAppending, setIsAppending] = useState(false);
  const [appendingColDbId, setAppendingColDbId] = useState(null);
  const [isAppendingCol, setIsAppendingCol] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);
  const [conflictData, setConflictData] = useState(null);
  const fileInputRef = useRef(null);
  const appendFileInputRef = useRef(null);
  const appendCollectionInputRef = useRef(null);

  if (!isOpen) return null;

  const handleModeChange = (mode) => {
    setUploadMode(mode);
    setFiles([]);
    setDbName('');
    setGroupName('');
    setErrorMsg(null);
    setSuccessMsg(null);
    setConflictData(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleTypeChange = (type) => {
    setSelectedType(type);
    setFiles([]);
    setDbName('');
    setGroupName('');
    setErrorMsg(null);
    setSuccessMsg(null);
    setConflictData(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleFileChange = (e) => {
    const selectedList = Array.from(e.target.files || []);
    if (selectedList.length === 0) return;

    setErrorMsg(null);
    setSuccessMsg(null);
    setConflictData(null);

    // =========================================================================
    // CASE A: MERGE MODE
    // =========================================================================
    if (uploadMode === 'merge') {
      if (selectedType === 'sql') {
        const hasDbFile = selectedList.some((f) => {
          const fn = f.name.toLowerCase();
          return fn.endsWith('.db') || fn.endsWith('.sqlite') || fn.endsWith('.sqlite3') || fn.endsWith('.s3db') || fn.endsWith('.sl3');
        });
        if (hasDbFile) {
          setErrorMsg(".db / .sqlite files are full databases, not tables. Please choose 'Full Database(s)' mode or select only .sql table script files.");
          setFiles([]);
          if (fileInputRef.current) fileInputRef.current.value = '';
          return;
        }

        const allSql = selectedList.every((f) => f.name.toLowerCase().endsWith('.sql'));
        if (!allSql) {
          setErrorMsg("In Multiple Tables (Merge) mode, all files must be .sql table script dumps.");
          setFiles([]);
          if (fileInputRef.current) fileInputRef.current.value = '';
          return;
        }

        setFiles(selectedList);
        if (!dbName.trim()) {
          setDbName("Combined SQL Database");
        }
        return;
      }

      if (selectedType === 'nosql') {
        const allDocFiles = selectedList.every((f) => {
          const fn = f.name.toLowerCase();
          return fn.endsWith('.json') || fn.endsWith('.jsonl') || fn.endsWith('.bson');
        });
        if (!allDocFiles) {
          setErrorMsg("In Multiple Collections (Merge) mode, all files must be .json, .jsonl, or .bson collection files.");
          setFiles([]);
          if (fileInputRef.current) fileInputRef.current.value = '';
          return;
        }

        setFiles(selectedList);
        if (!dbName.trim()) {
          setDbName("Combined NoSQL Store");
        }
        return;
      }
    }

    // =========================================================================
    // CASE B: FULL DATABASE(S) MODE (Single or Bulk Import)
    // =========================================================================
    if (selectedType === 'sql') {
      const validSql = selectedList.every((f) => {
        const fn = f.name.toLowerCase();
        return fn.endsWith('.db') || fn.endsWith('.sqlite') || fn.endsWith('.sqlite3') || fn.endsWith('.s3db') || fn.endsWith('.sl3') || fn.endsWith('.sql');
      });
      if (!validSql) {
        setErrorMsg("All selected files must be valid SQL database files (.db, .sqlite, or full .sql dumps).");
        setFiles([]);
        if (fileInputRef.current) fileInputRef.current.value = '';
        return;
      }
    } else if (selectedType === 'nosql') {
      const validNoSql = selectedList.every((f) => {
        const fn = f.name.toLowerCase();
        return fn.endsWith('.json') || fn.endsWith('.jsonl') || fn.endsWith('.bson');
      });
      if (!validNoSql) {
        setErrorMsg("All selected files must be valid NoSQL document files (.json, .jsonl, or MongoDB .bson).");
        setFiles([]);
        if (fileInputRef.current) fileInputRef.current.value = '';
        return;
      }
    } else if (selectedType === 'spreadsheet') {
      const validSpreadsheet = selectedList.every((f) => {
        const fn = f.name.toLowerCase();
        return fn.endsWith('.csv') || fn.endsWith('.xlsx') || fn.endsWith('.xls');
      });
      if (!validSpreadsheet) {
        setErrorMsg("All selected files must be valid spreadsheets (.csv, .xlsx, or .xls).");
        setFiles([]);
        if (fileInputRef.current) fileInputRef.current.value = '';
        return;
      }
    }

    setFiles(selectedList);

    if (selectedList.length === 1 && !dbName.trim()) {
      const cleanName = selectedList[0].name.replace(/\.(db|sqlite|sqlite3|s3db|sl3|sql|json|jsonl|bson|csv|xlsx|xls)$/i, '').replace(/[_-]/g, ' ');
      setDbName(cleanName.charAt(0).toUpperCase() + cleanName.slice(1));
    } else if (selectedList.length > 1 && !groupName.trim()) {
      setGroupName("Imported Batch " + new Date().toLocaleDateString('en-CA'));
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (files.length === 0) {
      setErrorMsg("Please select at least one file first.");
      return;
    }

    // In merge mode or single file mode, name is required
    if (uploadMode === 'merge' && !dbName.trim()) {
      setErrorMsg("Please provide a custom name for this merged database.");
      return;
    }
    if (uploadMode === 'full' && files.length === 1 && !dbName.trim()) {
      setErrorMsg("Please provide a custom display name for this database.");
      return;
    }

    setIsUploading(true);
    setErrorMsg(null);
    setSuccessMsg(null);
    setConflictData(null);

    const formData = new FormData();
    if (files.length === 1) {
      formData.append("file", files[0]);
    } else {
      files.forEach((f) => {
        formData.append("files", f);
      });
    }
    formData.append("name", dbName.trim());
    formData.append("type", selectedType);
    formData.append("mode", uploadMode);
    if (groupName.trim()) {
      formData.append("group_name", groupName.trim());
    }

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

      setFiles([]);
      setDbName('');
      setGroupName('');
      onClose();
    } catch (err) {
      setErrorMsg(err.message || "Failed to upload file(s).");
    } finally {
      setIsUploading(false);
    }
  };

  const handleDelete = async (dbId, name) => {
    setDeletingId(dbId);
    setConfirmDeleteId(null);
    setErrorMsg(null);
    setSuccessMsg(null);
    setConflictData(null);

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

  // Trigger file picker to append SQL table
  const handleTriggerAppend = (dbId) => {
    setAppendingDbId(dbId);
    setErrorMsg(null);
    setSuccessMsg(null);
    setConflictData(null);
    if (appendFileInputRef.current) {
      appendFileInputRef.current.value = '';
      appendFileInputRef.current.click();
    }
  };

  // Upload table script to existing SQL DB
  const handleAppendFileSelected = async (e) => {
    const selected = e.target.files?.[0];
    if (!selected || !appendingDbId) return;

    if (!selected.name.toLowerCase().endsWith('.sql')) {
      setErrorMsg("Only .sql table script files can be appended to an existing SQL database.");
      return;
    }

    setIsAppending(true);
    setErrorMsg(null);
    setSuccessMsg(null);
    setConflictData(null);

    const formData = new FormData();
    formData.append("file", selected);

    try {
      const response = await fetch(`${apiBaseUrl}/databases/${appendingDbId}/append-table`, {
        method: "POST",
        body: formData,
      });

      if (response.status === 409) {
        const conflictRes = await response.json();
        const conflictDetail = conflictRes.detail || {};
        setConflictData({
          type: 'table',
          dbId: appendingDbId,
          file: selected,
          name: conflictDetail.table_name || conflictDetail.conflicts?.[0] || selected.name
        });
        return;
      }

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || "Failed to append table.");
      }

      const result = await response.json();
      setSuccessMsg(result.message || `Table script '${selected.name}' added successfully!`);
      if (onUploadSuccess && result.database) {
        onUploadSuccess(result.database);
      }
    } catch (err) {
      setErrorMsg(err.message || "Failed to append table.");
    } finally {
      setIsAppending(false);
      setAppendingDbId(null);
    }
  };

  // Trigger file picker to append NoSQL collection
  const handleTriggerAppendCollection = (dbId) => {
    setAppendingColDbId(dbId);
    setErrorMsg(null);
    setSuccessMsg(null);
    setConflictData(null);
    if (appendCollectionInputRef.current) {
      appendCollectionInputRef.current.value = '';
      appendCollectionInputRef.current.click();
    }
  };

  // Upload collection file to existing NoSQL DB
  const handleAppendCollectionSelected = async (e) => {
    const selected = e.target.files?.[0];
    if (!selected || !appendingColDbId) return;

    const fn = selected.name.toLowerCase();
    if (!fn.endsWith('.json') && !fn.endsWith('.jsonl') && !fn.endsWith('.bson')) {
      setErrorMsg("Only .json, .jsonl, or .bson collection files can be appended to an existing NoSQL database.");
      return;
    }

    setIsAppendingCol(true);
    setErrorMsg(null);
    setSuccessMsg(null);
    setConflictData(null);

    const formData = new FormData();
    formData.append("file", selected);

    try {
      const response = await fetch(`${apiBaseUrl}/databases/${appendingColDbId}/append-collection`, {
        method: "POST",
        body: formData,
      });

      if (response.status === 409) {
        const conflictRes = await response.json();
        const conflictDetail = conflictRes.detail || {};
        setConflictData({
          type: 'collection',
          dbId: appendingColDbId,
          file: selected,
          name: conflictDetail.collection_name || conflictDetail.conflicts?.[0] || selected.name
        });
        return;
      }

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || "Failed to append collection.");
      }

      const result = await response.json();
      setSuccessMsg(result.message || `Collection '${selected.name}' added successfully!`);
      if (onUploadSuccess && result.database) {
        onUploadSuccess(result.database);
      }
    } catch (err) {
      setErrorMsg(err.message || "Failed to append collection.");
    } finally {
      setIsAppendingCol(false);
      setAppendingColDbId(null);
    }
  };

  // Confirm overwrite and replace existing table or collection
  const handleConfirmOverwrite = async () => {
    if (!conflictData) return;

    const isCol = conflictData.type === 'collection';
    if (isCol) setIsAppendingCol(true);
    else setIsAppending(true);

    setErrorMsg(null);
    setSuccessMsg(null);

    const formData = new FormData();
    formData.append("file", conflictData.file);
    formData.append("overwrite", "true");

    const endpoint = isCol
      ? `${apiBaseUrl}/databases/${conflictData.dbId}/append-collection`
      : `${apiBaseUrl}/databases/${conflictData.dbId}/append-table`;

    try {
      const response = await fetch(endpoint, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || `Failed to overwrite ${conflictData.type}.`);
      }

      const result = await response.json();
      setSuccessMsg(result.message || `${isCol ? 'Collection' : 'Table'} '${conflictData.name}' replaced successfully!`);
      setConflictData(null);
      if (onUploadSuccess && result.database) {
        onUploadSuccess(result.database);
      }
    } catch (err) {
      setErrorMsg(err.message || `Failed to overwrite ${conflictData.type}.`);
    } finally {
      setIsAppending(false);
      setIsAppendingCol(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 animate-fadeIn">
      {/* Hidden file input for appending SQL table */}
      <input
        ref={appendFileInputRef}
        type="file"
        accept=".sql"
        onChange={handleAppendFileSelected}
        className="hidden"
      />

      {/* Hidden file input for appending NoSQL collection */}
      <input
        ref={appendCollectionInputRef}
        type="file"
        accept=".json,.jsonl,.bson"
        onChange={handleAppendCollectionSelected}
        className="hidden"
      />

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
              <p className="text-xs text-slate-400">View active data sources or connect new SQL, NoSQL & Spreadsheet datasets</p>
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

        {/* Table / Collection Collision Confirmation Banner */}
        {conflictData && (
          <div className="mb-4 p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/30 text-xs text-amber-300 space-y-2.5 animate-fadeIn">
            <div className="flex items-center gap-2 font-bold text-amber-400">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>{conflictData.type === 'collection' ? 'Collection Collision Warning' : 'Table Collision Warning'}</span>
            </div>
            <p className="text-slate-300 leading-relaxed text-[11px]">
              {conflictData.type === 'collection' ? 'Collection' : 'Table'}{' '}
              <code className="px-1.5 py-0.5 rounded bg-slate-800 text-amber-300 font-mono text-[11px] font-semibold">{conflictData.name}</code>{' '}
              already exists in this dataset. Do you want to overwrite and replace it with this new file, or cancel?
            </p>
            <div className="flex items-center gap-2 pt-0.5">
              <button
                type="button"
                onClick={handleConfirmOverwrite}
                disabled={isAppending || isAppendingCol}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-500 text-white font-semibold text-[11px] transition-all cursor-pointer shadow-xs shadow-amber-600/30"
              >
                {(isAppending || isAppendingCol) ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
                <span>Overwrite & Replace</span>
              </button>
              <button
                type="button"
                onClick={() => setConflictData(null)}
                className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-[11px] font-medium transition-all cursor-pointer"
              >
                Cancel
              </button>
            </div>
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
                              {db.upload_mode === 'multiple' && (
                                <span className="px-1.5 py-0.2 rounded text-[9px] font-medium bg-purple-500/10 text-purple-400 border border-purple-500/20 flex items-center gap-1">
                                  📁 {db.group_name || 'Group'}
                                </span>
                              )}
                              {db.upload_mode === 'single' && (
                                <span className="px-1.5 py-0.2 rounded text-[9px] font-medium bg-slate-500/10 text-slate-400 border border-slate-500/20">
                                  Single File
                                </span>
                              )}
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
                            {/* ➕ APPEND TABLE BUTTON */}
                            <button
                              onClick={() => handleTriggerAppend(db.id)}
                              disabled={isAppending && appendingDbId === db.id}
                              className="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] font-medium bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 transition-all cursor-pointer"
                              title="Append an additional .sql table script to this database"
                            >
                              {isAppending && appendingDbId === db.id ? (
                                <Loader2 className="w-3 h-3 animate-spin" />
                              ) : (
                                <Plus className="w-3 h-3" />
                              )}
                              <span>Add Table</span>
                            </button>

                            {/* 🗑️ DELETE BUTTON WITH INLINE CONFIRM */}
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
                                className="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] font-medium bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 transition-all cursor-pointer"
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
                              {db.upload_mode === 'multiple' && (
                                <span className="px-1.5 py-0.2 rounded text-[9px] font-medium bg-purple-500/10 text-purple-400 border border-purple-500/20 flex items-center gap-1">
                                  📁 {db.group_name || 'Group'}
                                </span>
                              )}
                              {db.upload_mode === 'single' && (
                                <span className="px-1.5 py-0.2 rounded text-[9px] font-medium bg-slate-500/10 text-slate-400 border border-slate-500/20">
                                  Single File
                                </span>
                              )}
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
                          <div className="flex items-center gap-1.5 shrink-0">
                            {/* ➕ APPEND COLLECTION BUTTON */}
                            <button
                              onClick={() => handleTriggerAppendCollection(db.id)}
                              disabled={isAppendingCol && appendingColDbId === db.id}
                              className="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] font-medium bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 border border-amber-500/30 transition-all cursor-pointer"
                              title="Append an additional .json / .bson collection to this NoSQL database"
                            >
                              {isAppendingCol && appendingColDbId === db.id ? (
                                <Loader2 className="w-3 h-3 animate-spin" />
                              ) : (
                                <Plus className="w-3 h-3" />
                              )}
                              <span>Add Collection</span>
                            </button>

                            {/* 🗑️ DELETE BUTTON WITH INLINE CONFIRM */}
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

            {/* Category C: Spreadsheets (CSV & Excel) */}
            {databases.some(d => d.type === 'csv' || d.type === 'excel') && (
              <div>
                <div className="flex items-center gap-1.5 mb-1.5 px-1 text-[10px] font-bold text-emerald-400 uppercase tracking-wider">
                  <FileSpreadsheet className="w-3 h-3" />
                  <span>Spreadsheets & Formulas ({databases.filter(d => d.type === 'csv' || d.type === 'excel').length})</span>
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
                              {db.upload_mode === 'multiple' && (
                                <span className="px-1.5 py-0.2 rounded text-[9px] font-medium bg-purple-500/10 text-purple-400 border border-purple-500/20 flex items-center gap-1">
                                  📁 {db.group_name || 'Group'}
                                </span>
                              )}
                              {db.upload_mode === 'single' && (
                                <span className="px-1.5 py-0.2 rounded text-[9px] font-medium bg-slate-500/10 text-slate-400 border border-slate-500/20">
                                  Single File
                                </span>
                              )}
                            </div>
                            <p className="text-[10px] text-slate-400 flex items-center gap-1 mt-0.5 font-mono">
                              <Layers className="w-3 h-3" /> {isExcel ? `${db.sheet_count || 1} sheets` : `${db.row_count || 0} rows`}
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
                                  title="Permanently delete this spreadsheet"
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
                                title="Delete this custom spreadsheet"
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
          {/* 1. Upload Mode Selector */}
          <div className="mb-3.5">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1.5 px-0.5">
              1. Choose Upload Mode
            </span>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => handleModeChange('full')}
                className={`flex items-center gap-2.5 p-2.5 rounded-xl border text-xs font-semibold transition-all cursor-pointer ${
                  uploadMode === 'full'
                    ? 'bg-indigo-600/15 border-indigo-500 text-indigo-400 shadow-sm shadow-indigo-500/15'
                    : isDark ? 'bg-slate-950/40 border-slate-800 text-slate-400 hover:border-slate-700' : 'bg-slate-50 border-slate-200 text-slate-600 hover:border-slate-300'
                }`}
              >
                <Database className="w-4 h-4 shrink-0 text-indigo-400" />
                <div className="text-left">
                  <div className="text-xs font-bold">Full Data Source(s)</div>
                  <div className="text-[10px] text-slate-400 font-normal">Single dataset or bulk import multiple files</div>
                </div>
              </button>

              <button
                type="button"
                onClick={() => handleModeChange('merge')}
                className={`flex items-center gap-2.5 p-2.5 rounded-xl border text-xs font-semibold transition-all cursor-pointer ${
                  uploadMode === 'merge'
                    ? 'bg-indigo-600/15 border-indigo-500 text-indigo-400 shadow-sm shadow-indigo-500/15'
                    : isDark ? 'bg-slate-950/40 border-slate-800 text-slate-400 hover:border-slate-700' : 'bg-slate-50 border-slate-200 text-slate-600 hover:border-slate-300'
                }`}
              >
                <Layers className="w-4 h-4 shrink-0 text-indigo-400" />
                <div className="text-left">
                  <div className="text-xs font-bold">
                    {selectedType === 'sql' ? 'Multiple Tables (Merge)' : 'Multiple Collections (Merge)'}
                  </div>
                  <div className="text-[10px] text-slate-400 font-normal">
                    {selectedType === 'sql' ? 'Combine .sql tables into 1 Database' : 'Combine files into 1 Dataset'}
                  </div>
                </div>
              </button>
            </div>
          </div>

          {/* 2. Type Selector Tabs */}
          <div className="mb-4">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1.5 px-0.5">
              2. Select Engine Type
            </span>
            <div className="grid grid-cols-3 gap-2">
              <button
                type="button"
                onClick={() => handleTypeChange('sql')}
                className={`flex items-center justify-center gap-2 p-2.5 rounded-xl border text-xs font-semibold transition-all cursor-pointer ${
                  selectedType === 'sql'
                    ? 'bg-indigo-600/15 border-indigo-500 text-indigo-400 shadow-sm shadow-indigo-500/20'
                    : isDark ? 'bg-slate-950/40 border-slate-800 text-slate-400 hover:border-slate-700' : 'bg-slate-50 border-slate-200 text-slate-600 hover:border-slate-300'
                }`}
              >
                <Database className="w-4 h-4 text-indigo-400 shrink-0" />
                <div className="text-left truncate">
                  <div className="text-xs font-bold truncate">SQL Database</div>
                  <div className="text-[9px] text-slate-400 font-normal truncate">
                    .db, .sqlite, .sql
                  </div>
                </div>
              </button>

              <button
                type="button"
                onClick={() => handleTypeChange('nosql')}
                className={`flex items-center justify-center gap-2 p-2.5 rounded-xl border text-xs font-semibold transition-all cursor-pointer ${
                  selectedType === 'nosql'
                    ? 'bg-amber-500/15 border-amber-500 text-amber-400 shadow-sm shadow-amber-500/20'
                    : isDark ? 'bg-slate-950/40 border-slate-800 text-slate-400 hover:border-slate-700' : 'bg-slate-50 border-slate-200 text-slate-600 hover:border-slate-300'
                }`}
              >
                <FileJson className="w-4 h-4 text-amber-400 shrink-0" />
                <div className="text-left truncate">
                  <div className="text-xs font-bold truncate">NoSQL Store</div>
                  <div className="text-[9px] text-slate-400 font-normal truncate">
                    .json, .bson
                  </div>
                </div>
              </button>

              <button
                type="button"
                onClick={() => handleTypeChange('spreadsheet')}
                className={`flex items-center justify-center gap-2 p-2.5 rounded-xl border text-xs font-semibold transition-all cursor-pointer ${
                  selectedType === 'spreadsheet'
                    ? 'bg-emerald-500/15 border-emerald-500 text-emerald-400 shadow-sm shadow-emerald-500/20'
                    : isDark ? 'bg-slate-950/40 border-slate-800 text-slate-400 hover:border-slate-700' : 'bg-slate-50 border-slate-200 text-slate-600 hover:border-slate-300'
                }`}
              >
                <FileSpreadsheet className="w-4 h-4 text-emerald-400 shrink-0" />
                <div className="text-left truncate">
                  <div className="text-xs font-bold truncate">Spreadsheet</div>
                  <div className="text-[9px] text-slate-400 font-normal truncate">
                    .csv, .xlsx
                  </div>
                </div>
              </button>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* 3. File Picker */}
            <div>
              <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1.5 px-0.5">
                3. Choose {selectedType === 'spreadsheet' ? 'Spreadsheet (.csv / .xlsx) File(s)' : uploadMode === 'merge' ? (selectedType === 'sql' ? 'Table Script (.sql) Files' : 'Collection (.json / .bson) Files') : (selectedType === 'sql' ? 'SQL (.db / .sqlite / .sql) File(s)' : 'NoSQL (.json / .bson) File(s)')}
              </span>
              <div 
                onClick={() => fileInputRef.current?.click()}
                className={`border-2 border-dashed rounded-xl p-4 text-center cursor-pointer transition-colors ${
                  files.length > 0 
                    ? 'border-emerald-500/50 bg-emerald-500/5' 
                    : isDark ? 'border-slate-700 hover:border-indigo-500 bg-slate-950/40' : 'border-slate-300 hover:border-indigo-500 bg-slate-50'
                }`}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  accept={
                    selectedType === 'spreadsheet'
                      ? '.csv,.xlsx,.xls'
                      : uploadMode === 'merge'
                        ? (selectedType === 'sql' ? '.sql' : '.json,.jsonl,.bson')
                        : (selectedType === 'sql' ? '.db,.sqlite,.sqlite3,.s3db,.sl3,.sql' : '.json,.jsonl,.bson')
                  }
                  onChange={handleFileChange}
                  className="hidden"
                />

                {files.length === 1 && (
                  <div className="flex items-center justify-center gap-2 text-xs font-medium text-emerald-400">
                    <CheckCircle2 className="w-4 h-4 shrink-0" />
                    <span className="truncate">{files[0].name} ({(files[0].size / 1024).toFixed(1)} KB)</span>
                  </div>
                )}

                {files.length > 1 && (
                  <div className="space-y-2">
                    <div className="flex items-center justify-center gap-1.5 text-xs font-semibold text-emerald-400">
                      <CheckCircle2 className="w-4 h-4 shrink-0" />
                      <span>
                        {uploadMode === 'merge'
                          ? `${files.length} ${selectedType === 'sql' ? 'Table Scripts' : 'Collections'} (Merged into 1 Database)`
                          : `${files.length} Datasets Selected (Bulk Import as Separate Sources)`}
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-1.5 justify-center max-h-24 overflow-y-auto custom-scrollbar p-1">
                      {files.map((f, i) => (
                        <span key={i} className="px-2 py-0.5 rounded-md text-[10px] font-mono bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                          📄 {f.name}
                        </span>
                      ))}
                    </div>
                    <p className="text-[10px] text-slate-400">Click to replace or select different files</p>
                  </div>
                )}

                {files.length === 0 && (
                  <div>
                    {selectedType === 'spreadsheet' ? (
                      <FileSpreadsheet className="w-5 h-5 mx-auto mb-1 text-emerald-400" />
                    ) : selectedType === 'sql' ? (
                      <Database className="w-5 h-5 mx-auto mb-1 text-indigo-400" />
                    ) : (
                      <FileJson className="w-5 h-5 mx-auto mb-1 text-amber-400" />
                    )}
                    <p className="text-xs font-medium">
                      Click to browse or drag and drop
                    </p>
                    <p className="text-[10px] text-slate-400 mt-0.5">
                      {selectedType === 'spreadsheet'
                        ? 'Select 1 or multiple .csv / .xlsx spreadsheet files'
                        : uploadMode === 'merge'
                          ? (selectedType === 'sql' ? 'Select multiple .sql table dumps to merge' : 'Select multiple .json/.bson collection files to merge')
                          : (selectedType === 'sql' ? 'Select 1 or multiple full .db / .sqlite / .sql files' : 'Select 1 or multiple full .json / .bson files')}
                    </p>
                  </div>
                )}
              </div>
            </div>

            {/* 4. Custom Name Input or Batch Group Name */}
            {(uploadMode === 'merge' || files.length <= 1) ? (
              <div>
                <label className="block text-xs font-semibold mb-1 text-slate-300">
                  4. Custom Display Name
                </label>
                <input
                  type="text"
                  value={dbName}
                  onChange={(e) => setDbName(e.target.value)}
                  placeholder={
                    selectedType === 'spreadsheet'
                      ? 'e.g. Sales Performance (CSV) or Financial Budget (Excel)'
                      : uploadMode === 'merge'
                        ? (selectedType === 'sql' ? 'e.g. Combined Sales DB' : 'e.g. Merged Catalog Store')
                        : (selectedType === 'sql' ? 'e.g. Sales 2025 (SQL)' : 'e.g. Product Catalog (JSON)')
                  }
                  className={`w-full px-3 py-2 rounded-xl border text-xs focus:outline-none focus:border-indigo-500 transition-colors ${
                    isDark ? 'bg-slate-950 border-slate-700 text-white placeholder-slate-500' : 'bg-slate-50 border-slate-300 text-slate-900 placeholder-slate-400'
                  }`}
                />
              </div>
            ) : (
              <div className="space-y-2">
                <div>
                  <label className="block text-xs font-semibold mb-1 text-slate-300">
                    4. Batch / Group Name (Saved to Folder)
                  </label>
                  <input
                    type="text"
                    value={groupName}
                    onChange={(e) => setGroupName(e.target.value)}
                    placeholder="e.g. Q3 Sales Reports, Inventory Batch, Marketing Spreadsheets"
                    className={`w-full px-3 py-2 rounded-xl border text-xs focus:outline-none focus:border-indigo-500 transition-colors ${
                      isDark ? 'bg-slate-950 border-slate-700 text-white placeholder-slate-500' : 'bg-slate-50 border-slate-300 text-slate-900 placeholder-slate-400'
                    }`}
                  />
                </div>
                <div className="p-2.5 rounded-xl bg-purple-500/10 border border-purple-500/20 text-[11px] text-purple-300">
                  📁 <strong>Multi-File Group Storage:</strong> Files are saved together in <code>data/{selectedType === 'spreadsheet' ? 'csv' : selectedType}/multiple/{'{group_folder}'}/</code>. Display names are derived automatically from each file.
                </div>
              </div>
            )}

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
                disabled={isUploading || files.length === 0 || (uploadMode === 'merge' && !dbName.trim()) || (uploadMode === 'full' && files.length === 1 && !dbName.trim())}
                className="flex items-center gap-2 px-5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white text-xs font-semibold shadow-xs shadow-indigo-600/30 transition-all cursor-pointer"
              >
                {isUploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                <span>
                  {isUploading 
                    ? "Processing..." 
                    : uploadMode === 'merge' 
                      ? `Merge & Save (${files.length} ${selectedType === 'sql' ? 'Tables' : 'Collections'})` 
                      : files.length > 1 
                        ? `Bulk Import (${files.length} Data Sources)` 
                        : "Save & Register"}
                </span>
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
