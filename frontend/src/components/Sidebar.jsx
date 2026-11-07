import React, { useState, useEffect } from 'react';
import { 
  Plus, 
  MessageSquare, 
  Trash2, 
  Pencil, 
  Check, 
  X, 
  Sun, 
  Moon, 
  Sparkles, 
  Table as TableIcon, 
  ChevronDown, 
  ChevronRight, 
  Layers, 
  Search, 
  Maximize2, 
  Minimize2, 
  Network, 
  Key, 
  Link as LinkIcon,
  PanelLeftClose,
  Database,
  FileJson,
  FileSpreadsheet
} from 'lucide-react';

export default function Sidebar({
  chats,
  databases = [],
  activeChatId,
  onSelectChat,
  onNewChat,
  onGoHome,
  onDeleteChat,
  onRenameChat,
  tables = [],
  onSelectPrompt,
  isDark,
  onToggleTheme,
  isOpen,
  onClose,
  onOpenSchemaMap,
  currentDb = null,
  width = 280,
  onWidthChange,
  isCollapsed = false,
  onToggleCollapse
}) {
  const [activeTab, setActiveTab] = useState('chats'); // 'chats' | 'schema'
  // Drag resizing state
  const [isResizing, setIsResizing] = useState(false);
  // Multi-table expansion state (Set of table names currently expanded)
  const [expandedTables, setExpandedTables] = useState(() => new Set(tables.length > 0 ? [tables[0].name] : []));
  const [editingChatId, setEditingChatId] = useState(null);
  const [editTitle, setEditTitle] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  const dbType = currentDb?.type || 'sql';
  const isNoSql = dbType === 'nosql';
  const isExcel = dbType === 'excel';
  const isCsv = dbType === 'csv';

  // Dynamic entity naming: single vs multiple data table or collection
  const entitySingular = isNoSql 
    ? 'Collection' 
    : isExcel 
      ? 'Worksheet' 
      : 'Data Table';
      
  const entityPlural = isNoSql 
    ? 'Collections' 
    : isExcel 
      ? 'Worksheets' 
      : 'Data Tables';

  const entityTypeLabel = tables.length === 1 ? entitySingular : entityPlural;

  const toggleTable = (tableName) => {
    setExpandedTables((prev) => {
      const next = new Set(prev);
      if (next.has(tableName)) {
        next.delete(tableName);
      } else {
        next.add(tableName);
      }
      return next;
    });
  };

  const expandAll = () => {
    setExpandedTables(new Set(tables.map((t) => t.name)));
  };

  const collapseAll = () => {
    setExpandedTables(new Set());
  };

  const startEditing = (chat, e) => {
    e.stopPropagation();
    setEditingChatId(chat.id);
    setEditTitle(chat.title);
  };

  const handleSaveRename = (chatId, e) => {
    if (e) e.stopPropagation();
    if (editTitle.trim() && onRenameChat) {
      onRenameChat(chatId, editTitle.trim());
    }
    setEditingChatId(null);
  };

  const handleCancelRename = (e) => {
    if (e) e.stopPropagation();
    setEditingChatId(null);
  };

  // Drag Resizer Handlers
  const handleMouseDown = (e) => {
    e.preventDefault();
    setIsResizing(true);
  };

  useEffect(() => {
    if (!isResizing) return;

    const handleMouseMove = (e) => {
      const newWidth = Math.min(500, Math.max(220, e.clientX));
      if (onWidthChange) onWidthChange(newWidth);
    };

    const handleMouseUp = () => {
      setIsResizing(false);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isResizing, onWidthChange]);

  const handleDoubleClickResizer = () => {
    if (onWidthChange) onWidthChange(280);
  };

  // Filter tables and columns by search query
  const filteredTables = tables.filter((t) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    const nameMatch = t.name.toLowerCase().includes(q);
    const colMatch = t.cols.some((c) => c.toLowerCase().includes(q));
    return nameMatch || colMatch;
  });

  return (
    <aside
      style={{
        width: isCollapsed ? 0 : `${width}px`
      }}
      className={`fixed inset-y-0 left-0 z-40 flex flex-col relative md:static ${
        isResizing ? 'transition-none select-none' : 'transition-[width] duration-200 ease-in-out'
      } ${
        isCollapsed ? 'w-0 overflow-hidden border-r-0 pointer-events-none md:pointer-events-none' : ''
      } ${
        isOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
      } ${
        isDark ? 'bg-slate-900 border-r border-slate-800 text-slate-200' : 'bg-slate-50 border-r border-slate-200 text-slate-800'
      }`}
    >
      {/* Top Header & App Branding */}
      <div className="p-3.5 border-b border-slate-700/40 shrink-0">
        <div className="flex items-center justify-between mb-3 px-1">
          <button 
            onClick={onGoHome || onNewChat}
            className="flex items-center gap-2.5 text-left group cursor-pointer focus:outline-none"
            title="Go to Home"
          >
            <div className="p-1.5 bg-indigo-500/10 border border-indigo-500/30 rounded-lg text-indigo-400 group-hover:bg-indigo-500/20 group-hover:border-indigo-500/50 transition-all">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-sm font-bold tracking-tight group-hover:text-indigo-400 transition-colors">OmniData AI</h1>
              <p className="text-[10px] text-slate-400">Multi-Engine Data Intelligence</p>
            </div>
          </button>

          {/* Desktop Collapse & Mobile Close Actions */}
          <div className="flex items-center gap-1">
            <button
              onClick={onToggleCollapse}
              className="hidden md:flex p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 transition-colors cursor-pointer"
              title="Collapse Sidebar (Ctrl+B)"
            >
              <PanelLeftClose className="w-4 h-4" />
            </button>

            <button
              onClick={onClose}
              className="p-1.5 rounded-lg md:hidden text-slate-400 hover:text-slate-200 cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Tab Switcher: Chats vs Database Tables */}
        <div className={`flex p-1 rounded-xl border text-xs font-medium mb-3 ${
          isDark ? 'bg-slate-950 border-slate-800' : 'bg-slate-200/60 border-slate-300'
        }`}>
          <button
            onClick={() => setActiveTab('chats')}
            className={`flex-1 py-1.5 rounded-lg flex items-center justify-center gap-1.5 transition-all cursor-pointer ${
              activeTab === 'chats'
                ? isDark ? 'bg-slate-800 text-white shadow-xs' : 'bg-white text-indigo-600 shadow-xs'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <MessageSquare className="w-3.5 h-3.5" />
            <span>Chats</span>
          </button>

          <button
            onClick={() => setActiveTab('schema')}
            title="Data Source Information"
            className={`flex-1 py-1.5 px-2 rounded-lg flex items-center justify-center gap-1.5 transition-all cursor-pointer min-w-0 ${
              activeTab === 'schema'
                ? isDark ? 'bg-slate-800 text-white shadow-xs' : 'bg-white text-indigo-600 shadow-xs'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Database className="w-3.5 h-3.5 shrink-0" />
            <span className="truncate">Data Source Information</span>
          </button>
        </div>

        {/* New Chat Button (Only visible on Chats tab) */}
        {activeTab === 'chats' && (
          <button
            onClick={onNewChat}
            className="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs transition-all shadow-sm shadow-indigo-600/30 cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>New Conversation</span>
          </button>
        )}
      </div>

      {/* Main Content Area: Switch between Chats and Schema Explorer */}
      <div className="flex-1 overflow-y-auto p-3 space-y-1">
        {/* TAB 1: CONVERSATIONS LIST */}
        {activeTab === 'chats' && (
          <div>
            <span className="px-2 text-[10px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">
              Recent Conversations
            </span>

            {chats.length === 0 ? (
              <div className="px-3 py-8 text-center text-xs text-slate-500">
                No conversations
              </div>
            ) : (
              chats.map((chat) => {
                const isActive = chat.id === activeChatId;
                const isEditing = editingChatId === chat.id;
                const chatDb = databases.find((d) => d.id === chat.db_id);
                const dbDisplayName = chatDb?.name || chat.db_name || (chat.db_id ? chat.db_id.replace(/_/g, ' ') : 'Chinook (Music)');
                const dbType = chatDb?.type || (chat.db_id === 'ecommerce_store' ? 'nosql' : chat.db_id === 'sales_performance' ? 'csv' : chat.db_id === 'financial_budget' ? 'excel' : 'sql');

                return (
                  <div
                    key={chat.id}
                    className={`group flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium transition-all cursor-pointer ${
                      isActive
                        ? isDark
                          ? 'bg-slate-800 text-white border border-slate-700'
                          : 'bg-white text-indigo-600 border border-slate-200 shadow-xs'
                        : isDark
                          ? 'text-slate-400 hover:bg-slate-800/50 hover:text-slate-200'
                          : 'text-slate-600 hover:bg-slate-200/50 hover:text-slate-900'
                    }`}
                    onClick={() => {
                      if (!isEditing) {
                        onSelectChat(chat.id);
                        if (onClose) onClose();
                      }
                    }}
                  >
                    {isEditing ? (
                      /* Inline Edit Mode */
                      <div className="flex items-center gap-1.5 w-full py-0.5" onClick={(e) => e.stopPropagation()}>
                        <input
                          type="text"
                          value={editTitle}
                          onChange={(e) => setEditTitle(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') handleSaveRename(chat.id, e);
                            if (e.key === 'Escape') handleCancelRename(e);
                          }}
                          autoFocus
                          className={`w-full px-2 py-1 rounded text-xs focus:outline-none border ${
                            isDark ? 'bg-slate-950 border-indigo-500 text-white' : 'bg-white border-indigo-500 text-slate-900'
                          }`}
                        />
                        <button
                          onClick={(e) => handleSaveRename(chat.id, e)}
                          className="p-1 text-emerald-400 hover:bg-emerald-500/10 rounded cursor-pointer shrink-0"
                          title="Save (Enter)"
                        >
                          <Check className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={handleCancelRename}
                          className="p-1 text-rose-400 hover:bg-rose-500/10 rounded cursor-pointer shrink-0"
                          title="Cancel (Esc)"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ) : (
                      /* Standard View Mode: Title + Dataset Badge */
                      <div className="flex items-start justify-between w-full min-w-0 gap-1.5">
                        <div className="flex flex-col min-w-0 flex-1">
                          <div className="flex items-center gap-2 truncate">
                            <MessageSquare className={`w-3.5 h-3.5 shrink-0 ${isActive ? 'text-indigo-400' : 'text-slate-500'}`} />
                            <span className="truncate font-medium">{chat.title || 'Untitled Conversation'}</span>
                          </div>

                          {/* Dataset Name Badge */}
                          <div className="flex items-center gap-1 mt-1 ml-5.5">
                            <span 
                              className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium tracking-tight truncate max-w-[170px] ${
                                dbType === 'nosql'
                                  ? isDark ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' : 'bg-amber-50 text-amber-700 border border-amber-200'
                                  : dbType === 'excel'
                                    ? isDark ? 'bg-teal-500/10 text-teal-400 border border-teal-500/20' : 'bg-teal-50 text-teal-700 border border-teal-200'
                                    : dbType === 'csv'
                                      ? isDark ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                      : isDark ? 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20' : 'bg-indigo-50 text-indigo-600 border border-indigo-200'
                              }`}
                              title={`Dataset: ${dbDisplayName}`}
                            >
                              {dbType === 'nosql' ? (
                                <FileJson className="w-2.5 h-2.5 shrink-0" />
                              ) : dbType === 'excel' || dbType === 'csv' ? (
                                <FileSpreadsheet className="w-2.5 h-2.5 shrink-0" />
                              ) : (
                                <Database className="w-2.5 h-2.5 shrink-0" />
                              )}
                              <span className="truncate">{dbDisplayName}</span>
                            </span>
                          </div>
                        </div>

                        <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity shrink-0 pt-0.5">
                          {/* Rename Button */}
                          <button
                            onClick={(e) => startEditing(chat, e)}
                            className="p-1 rounded hover:bg-indigo-500/10 hover:text-indigo-400 text-slate-500 transition-all cursor-pointer"
                            title="Rename chat"
                          >
                            <Pencil className="w-3.5 h-3.5" />
                          </button>

                          {/* Delete Button */}
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              onDeleteChat(chat.id);
                            }}
                            className="p-1 rounded hover:bg-rose-500/10 hover:text-rose-400 text-slate-500 transition-all cursor-pointer"
                            title="Delete chat"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        )}

        {/* TAB 2: DATA SOURCE INFORMATION (With Multi-Table / Collection Expansion & Search) */}
        {activeTab === 'schema' && (
          <div className="space-y-2.5">
            {/* Active Data Source Summary Badge */}
            <div className={`p-2.5 rounded-xl border text-xs ${
              isDark ? 'bg-slate-950/60 border-slate-800' : 'bg-white border-slate-200'
            }`}>
              <div className="flex items-center justify-between mb-1.5">
                <span className="font-semibold text-xs truncate text-indigo-400" title={currentDb?.name || 'Active Data Source'}>
                  {currentDb?.name || 'Active Data Source'}
                </span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono font-medium ${
                  isNoSql
                    ? isDark ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' : 'bg-amber-50 text-amber-700 border border-amber-200'
                    : isExcel
                      ? isDark ? 'bg-teal-500/10 text-teal-400 border border-teal-500/20' : 'bg-teal-50 text-teal-700 border border-teal-200'
                      : isCsv
                        ? isDark ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                        : isDark ? 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20' : 'bg-indigo-50 text-indigo-700 border border-indigo-200'
                }`}>
                  {isNoSql ? 'MongoDB JSON' : isExcel ? 'Excel Workbook' : isCsv ? 'CSV Dataset' : 'SQLite Relational'}
                </span>
              </div>
              <div className="flex items-center gap-2 text-[10px] text-slate-400">
                <span className="flex items-center gap-1 font-mono">
                  <Layers className="w-3 h-3 text-slate-500" />
                  {tables.length} {entityTypeLabel}
                </span>
                {tables.length > 0 && (
                  <>
                    <span className="text-slate-600">•</span>
                    <span className="font-mono">
                      {tables.reduce((acc, t) => acc + (typeof t.count === 'number' ? t.count : 0), 0).toLocaleString()} total {isNoSql ? 'docs' : 'rows'}
                    </span>
                  </>
                )}
              </div>
            </div>

            {/* Instant Search Bar */}
            <div className="relative px-0.5">
              <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder={isNoSql ? "Search collections or fields..." : "Search data tables, columns or fields..."}
                className={`w-full pl-8 pr-3 py-1.5 rounded-xl border text-xs focus:outline-none focus:border-indigo-500 transition-colors ${
                  isDark ? 'bg-slate-950 border-slate-800 text-white placeholder-slate-500' : 'bg-white border-slate-300 text-slate-900 placeholder-slate-400'
                }`}
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery('')}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200"
                >
                  <X className="w-3 h-3" />
                </button>
              )}
            </div>

            {/* Quick Actions Header: Table/Collection Count + Expand/Collapse All */}
            <div className="flex items-center justify-between px-1 text-[10px]">
              <span className="font-semibold text-slate-400 uppercase tracking-wider">
                {searchQuery ? `Matches (${filteredTables.length})` : `${tables.length} ${entityTypeLabel}`}
              </span>
              
              <div className="flex items-center gap-2">
                <button
                  onClick={expandAll}
                  className="text-slate-400 hover:text-indigo-400 flex items-center gap-0.5 cursor-pointer"
                  title={`Expand all ${entityPlural.toLowerCase()}`}
                >
                  <Maximize2 className="w-2.5 h-2.5" /> Expand All
                </button>
                <span className="text-slate-600">|</span>
                <button
                  onClick={collapseAll}
                  className="text-slate-400 hover:text-indigo-400 flex items-center gap-0.5 cursor-pointer"
                  title={`Collapse all ${entityPlural.toLowerCase()}`}
                >
                  <Minimize2 className="w-2.5 h-2.5" /> Collapse
                </button>
              </div>
            </div>

            {/* View Schema Map / Relationships Button (Multi-relation SQL and NoSQL only) */}
            {onOpenSchemaMap && currentDb?.type !== 'csv' && currentDb?.type !== 'excel' && (
              <button
                onClick={onOpenSchemaMap}
                className="w-full flex items-center justify-center gap-1.5 py-1.5 px-3 rounded-xl bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-400 border border-indigo-500/20 text-xs font-semibold transition-all cursor-pointer shadow-xs"
              >
                <Network className="w-3.5 h-3.5" />
                <span>View Schema Map (ER)</span>
              </button>
            )}

            {filteredTables.length === 0 ? (
              <div className="text-xs text-slate-500 text-center py-6">
                {searchQuery ? `No ${entityPlural.toLowerCase()} or fields match "${searchQuery}"` : "Connecting to data source..."}
              </div>
            ) : (
              filteredTables.map((t) => {
                // Check if this specific table/collection is expanded
                const isExpanded = expandedTables.has(t.name) || Boolean(searchQuery.trim());
                const colCount = t.columns ? t.columns.length : (t.cols ? t.cols.length : 0);
                const rowCount = typeof t.count === 'number' ? t.count : null;
                const rowUnit = isNoSql ? (rowCount === 1 ? 'doc' : 'docs') : (rowCount === 1 ? 'row' : 'rows');

                return (
                  <div
                    key={t.name}
                    className={`border rounded-xl transition-all overflow-hidden ${
                      isDark ? 'border-slate-800 bg-slate-950/40' : 'border-slate-200 bg-white'
                    }`}
                  >
                    {/* Entity Title Bar (Toggles only this entity independently) */}
                    <div
                      onClick={() => toggleTable(t.name)}
                      className={`flex items-center justify-between px-3 py-2 cursor-pointer select-none transition-colors ${
                        isExpanded
                          ? isDark ? 'bg-slate-800/60' : 'bg-slate-100'
                          : isDark ? 'hover:bg-slate-800/30' : 'hover:bg-slate-50'
                      }`}
                    >
                      <div className="flex items-center gap-2 text-xs font-semibold truncate min-w-0">
                        {isNoSql ? (
                          <FileJson className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                        ) : isExcel || isCsv ? (
                          <FileSpreadsheet className="w-3.5 h-3.5 text-teal-400 shrink-0" />
                        ) : (
                          <TableIcon className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                        )}
                        <span className="truncate" title={t.name}>{t.name}</span>
                      </div>

                      <div className="flex items-center gap-2 shrink-0">
                        <div className="flex items-center gap-1.5 text-[10px] text-slate-400 font-mono">
                          <span>{colCount} {isNoSql ? 'fields' : 'cols'}</span>
                          {rowCount !== null && (
                            <>
                              <span className="text-slate-600">·</span>
                              <span className="text-indigo-400/90 font-medium">
                                {rowCount.toLocaleString()} {rowUnit}
                              </span>
                            </>
                          )}
                        </div>
                        {isExpanded ? <ChevronDown className="w-3.5 h-3.5 text-slate-400" /> : <ChevronRight className="w-3.5 h-3.5 text-slate-400" />}
                      </div>
                    </div>

                    {/* Columns / Fields List */}
                    {isExpanded && (
                      <div className="p-2.5 border-t border-slate-800/40 space-y-1.5">
                        {/* Summary metadata header */}
                        <div className={`flex items-center justify-between px-2 py-1 rounded text-[10px] font-mono mb-2 ${
                          isDark ? 'bg-slate-900/80 text-slate-300 border border-slate-800' : 'bg-slate-100 text-slate-600 border border-slate-200'
                        }`}>
                          <span className="font-semibold text-slate-400 uppercase tracking-wider text-[9px]">
                            {isNoSql ? 'Fields Schema' : 'Column Definitions'}
                          </span>
                          <div className="flex items-center gap-2">
                            <span>{colCount} {isNoSql ? 'fields' : 'columns'}</span>
                            {rowCount !== null && (
                              <>
                                <span className="text-slate-500">•</span>
                                <span className="text-indigo-400 font-semibold">{rowCount.toLocaleString()} {rowUnit}</span>
                              </>
                            )}
                          </div>
                        </div>

                        <ul className="space-y-1 text-xs">
                          {t.columns && t.columns.length > 0 ? (
                            t.columns.map((c, idx) => {
                              const isMatched = searchQuery && (c.name.toLowerCase().includes(searchQuery.toLowerCase()) || (c.fk_to_table && c.fk_to_table.toLowerCase().includes(searchQuery.toLowerCase())));
                              return (
                                <li 
                                  key={idx} 
                                  className={`flex items-center justify-between py-0.5 px-1 rounded ${
                                    isMatched ? 'bg-indigo-500/20 text-indigo-300 font-semibold' : ''
                                  }`}
                                >
                                  <div className="flex items-center gap-1.5 truncate">
                                    {c.is_pk ? (
                                      <Key className="w-3 h-3 text-amber-400 shrink-0" title="Primary Key" />
                                    ) : c.is_fk ? (
                                      <LinkIcon className="w-3 h-3 text-indigo-400 shrink-0" title="Foreign Key" />
                                    ) : (
                                      <span className="w-1 h-1 rounded-full bg-slate-500 shrink-0 mx-1" />
                                    )}
                                    <span className={`font-mono text-[10px] truncate ${c.is_pk ? 'text-amber-300 font-bold' : c.is_fk ? 'text-indigo-300 font-semibold' : isDark ? 'text-slate-300' : 'text-slate-600'}`}>
                                      {c.name}
                                    </span>
                                  </div>

                                  <div className="flex items-center gap-1 shrink-0 text-[9px] font-mono">
                                    <span className="text-slate-500">{c.type}</span>
                                    {c.is_fk && c.fk_to_table && (
                                      <span className="px-1 py-0.1 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                                        ➔ {c.fk_to_table}
                                      </span>
                                    )}
                                  </div>
                                </li>
                              );
                            })
                          ) : (
                            t.cols.map((col, idx) => {
                              const isMatched = searchQuery && col.toLowerCase().includes(searchQuery.toLowerCase());
                              return (
                                <li 
                                  key={idx} 
                                  className={`flex items-center gap-2 py-0.5 px-1 rounded ${
                                    isMatched ? 'bg-indigo-500/20 text-indigo-300 font-semibold' : ''
                                  }`}
                                >
                                  <span className={`w-1 h-1 rounded-full shrink-0 ${isMatched ? 'bg-indigo-400' : 'bg-slate-500'}`} />
                                  <code className={`font-mono text-[10px] ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>
                                    {col}
                                  </code>
                                </li>
                              );
                            })
                          )}
                        </ul>

                        <button
                          onClick={() => {
                            if (onSelectPrompt) {
                              const entityWord = isNoSql ? 'collection' : isExcel ? 'sheet' : 'table';
                              onSelectPrompt(`Show me the top 5 records from the ${t.name} ${entityWord}.`);
                              if (onClose) onClose();
                            }
                          }}
                          className="w-full mt-1.5 flex items-center justify-center gap-1.5 py-1 px-2 rounded text-[11px] font-medium bg-indigo-600/10 hover:bg-indigo-600/20 text-indigo-400 transition-all cursor-pointer"
                        >
                          <Sparkles className="w-3 h-3" />
                          <span>Ask about `{t.name}`</span>
                        </button>
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        )}
      </div>

      {/* Bottom Footer: Database indicator & Theme Toggle */}
      <div className={`p-4 border-t ${isDark ? 'border-slate-800/80 bg-slate-950/40' : 'border-slate-200 bg-white/40'}`}>
        <div className="flex items-center justify-between mb-3 px-1 text-xs">
          <span className="flex items-center gap-1.5 text-slate-400">
            <Layers className="w-3.5 h-3.5 text-indigo-400" /> System Status
          </span>
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-medium">
            Active
          </span>
        </div>

        {/* Theme Toggle Button */}
        <button
          onClick={onToggleTheme}
          className={`w-full flex items-center justify-center gap-2 px-3 py-2 rounded-xl border text-xs font-medium transition-all cursor-pointer ${
            isDark
              ? 'bg-slate-800/80 border-slate-700 text-amber-300 hover:bg-slate-700'
              : 'bg-white border-slate-300 text-indigo-600 hover:bg-slate-100 shadow-xs'
          }`}
        >
          {isDark ? (
            <>
              <Sun className="w-4 h-4 text-amber-400" />
              <span>Light Mode</span>
            </>
          ) : (
            <>
              <Moon className="w-4 h-4 text-indigo-600" />
              <span>Dark Mode</span>
            </>
          )}
        </button>
      </div>

      {/* ↔️ DRAGGABLE RESIZER HANDLE (RIGHT EDGE) */}
      {!isCollapsed && (
        <div
          onMouseDown={handleMouseDown}
          onDoubleClick={handleDoubleClickResizer}
          className={`hidden md:block absolute top-0 -right-1 w-2 h-full cursor-col-resize hover:bg-indigo-500/60 transition-colors z-50 group ${
            isResizing ? 'bg-indigo-500 w-2.5' : ''
          }`}
          title="Drag to resize sidebar width · Double-click to reset (280px)"
        >
          <div className="w-full h-full opacity-0 group-hover:opacity-100 bg-indigo-500/40" />
        </div>
      )}
    </aside>
  );
}
