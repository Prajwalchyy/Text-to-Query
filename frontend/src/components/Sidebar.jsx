import React, { useState } from 'react';
import { 
  Plus, 
  MessageSquare, 
  Trash2, 
  Pencil, 
  Check, 
  X, 
  Database, 
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
  FolderPlus
} from 'lucide-react';

export default function Sidebar({
  chats,
  activeChatId,
  onSelectChat,
  onNewChat,
  onDeleteChat,
  onRenameChat,
  tables = [],
  onSelectPrompt,
  onOpenUpload,
  isDark,
  onToggleTheme,
  isOpen,
  onClose
}) {
  const [activeTab, setActiveTab] = useState('chats'); // 'chats' | 'schema'
  // Multi-table expansion state (Set of table names currently expanded)
  const [expandedTables, setExpandedTables] = useState(() => new Set(tables.length > 0 ? [tables[0].name] : []));
  const [editingChatId, setEditingChatId] = useState(null);
  const [editTitle, setEditTitle] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

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
      className={`fixed inset-y-0 left-0 z-40 w-72 flex flex-col transition-all duration-300 md:static md:translate-x-0 ${
        isOpen ? 'translate-x-0' : '-translate-x-full'
      } ${
        isDark ? 'bg-slate-900 border-r border-slate-800 text-slate-200' : 'bg-slate-50 border-r border-slate-200 text-slate-800'
      }`}
    >
      {/* Top Header & App Branding */}
      <div className="p-4 border-b border-slate-700/40">
        <div className="flex items-center gap-2.5 mb-3 px-1">
          <div className="p-1.5 bg-indigo-500/10 border border-indigo-500/30 rounded-lg text-indigo-400">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-sm font-bold tracking-tight">SQL Assistant</h1>
            <p className="text-[10px] text-slate-400">Enterprise Database AI</p>
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
            className={`flex-1 py-1.5 rounded-lg flex items-center justify-center gap-1.5 transition-all cursor-pointer ${
              activeTab === 'schema'
                ? isDark ? 'bg-slate-800 text-white shadow-xs' : 'bg-white text-indigo-600 shadow-xs'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            <span>Tables ({tables.length})</span>
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

        {/* Upload Database Action (Only visible on Tables tab) */}
        {activeTab === 'schema' && onOpenUpload && (
          <button
            onClick={onOpenUpload}
            className="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs transition-all shadow-sm shadow-indigo-600/30 cursor-pointer"
          >
            <FolderPlus className="w-4 h-4" />
            <span>+ Upload Custom Database</span>
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
                No chats yet. Start a new conversation!
              </div>
            ) : (
              chats.map((chat) => {
                const isActive = chat.id === activeChatId;
                const isEditing = editingChatId === chat.id;

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
                      /* Standard View Mode */
                      <>
                        <div className="flex items-center gap-2.5 truncate pr-2 flex-1">
                          <MessageSquare className={`w-3.5 h-3.5 shrink-0 ${isActive ? 'text-indigo-400' : 'text-slate-500'}`} />
                          <span className="truncate">{chat.title || 'Untitled Conversation'}</span>
                        </div>

                        <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
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
                      </>
                    )}
                  </div>
                );
              })
            )}
          </div>
        )}

        {/* TAB 2: DATABASE SCHEMA EXPLORER (With Multi-Table Expansion & Search) */}
        {activeTab === 'schema' && (
          <div className="space-y-2.5">
            {/* Instant Search Bar */}
            <div className="relative px-0.5">
              <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search tables or columns..."
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

            {/* Quick Actions Header: Table Count + Expand/Collapse All */}
            <div className="flex items-center justify-between px-1 text-[10px]">
              <span className="font-semibold text-slate-400 uppercase tracking-wider">
                {searchQuery ? `Matches (${filteredTables.length})` : `Tables (${tables.length})`}
              </span>
              
              <div className="flex items-center gap-2">
                <button
                  onClick={expandAll}
                  className="text-slate-400 hover:text-indigo-400 flex items-center gap-0.5 cursor-pointer"
                  title="Expand all tables"
                >
                  <Maximize2 className="w-2.5 h-2.5" /> Expand All
                </button>
                <span className="text-slate-600">|</span>
                <button
                  onClick={collapseAll}
                  className="text-slate-400 hover:text-indigo-400 flex items-center gap-0.5 cursor-pointer"
                  title="Collapse all tables"
                >
                  <Minimize2 className="w-2.5 h-2.5" /> Collapse
                </button>
              </div>
            </div>

            {filteredTables.length === 0 ? (
              <div className="text-xs text-slate-500 text-center py-6">
                {searchQuery ? `No tables or columns match "${searchQuery}"` : "Connecting to database..."}
              </div>
            ) : (
              filteredTables.map((t) => {
                // Check if this specific table is expanded
                const isExpanded = expandedTables.has(t.name) || Boolean(searchQuery.trim());
                return (
                  <div
                    key={t.name}
                    className={`border rounded-xl transition-all overflow-hidden ${
                      isDark ? 'border-slate-800 bg-slate-950/40' : 'border-slate-200 bg-white'
                    }`}
                  >
                    {/* Table Title Bar (Toggles only this table independently) */}
                    <div
                      onClick={() => toggleTable(t.name)}
                      className={`flex items-center justify-between px-3 py-2 cursor-pointer select-none transition-colors ${
                        isExpanded
                          ? isDark ? 'bg-slate-800/60' : 'bg-slate-100'
                          : isDark ? 'hover:bg-slate-800/30' : 'hover:bg-slate-50'
                      }`}
                    >
                      <div className="flex items-center gap-2 text-xs font-semibold truncate">
                        <TableIcon className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                        <span className="truncate">{t.name}</span>
                      </div>

                      <div className="flex items-center gap-1.5 shrink-0">
                        <span className="text-[10px] text-slate-400 font-mono">
                          {t.cols.length} cols
                        </span>
                        {isExpanded ? <ChevronDown className="w-3.5 h-3.5 text-slate-400" /> : <ChevronRight className="w-3.5 h-3.5 text-slate-400" />}
                      </div>
                    </div>

                    {/* Columns List */}
                    {isExpanded && (
                      <div className="p-2.5 border-t border-slate-800/40 space-y-1.5">
                        <ul className="space-y-1 text-xs">
                          {t.cols.map((col, idx) => {
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
                          })}
                        </ul>

                        <button
                          onClick={() => {
                            if (onSelectPrompt) {
                              onSelectPrompt(`Show me the top 5 records from the ${t.name} table.`);
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
            <Database className="w-3.5 h-3.5 text-indigo-400" /> System Status
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
    </aside>
  );
}
