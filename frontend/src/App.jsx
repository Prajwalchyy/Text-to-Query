import React, { useState, useEffect, useRef } from 'react';
import { Menu, WifiOff, AlertTriangle, RefreshCw, Sparkles, Database, Plus, ChevronDown } from 'lucide-react';
import Sidebar from './components/Sidebar';
import ChatMessage from './components/ChatMessage';
import ChatInput from './components/ChatInput';
import UploadDbModal from './components/UploadDbModal';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api";

export default function App() {
  // Theme state with localStorage persistence
  const [isDark, setIsDark] = useState(() => {
    const savedTheme = localStorage.getItem("theme");
    return savedTheme !== null ? savedTheme === "dark" : true;
  });

  useEffect(() => {
    localStorage.setItem("theme", isDark ? "dark" : "light");
  }, [isDark]);

  // Chat sessions state (Loaded and saved directly via FastAPI Backend)
  const [chats, setChats] = useState([]);
  const [activeChatId, setActiveChatId] = useState(null);

  // Multi-Database states
  const [databases, setDatabases] = useState([]);
  const [selectedDbId, setSelectedDbId] = useState("chinook");
  const [uploadModalOpen, setUploadModalOpen] = useState(false);

  // Schema states
  const [tables, setTables] = useState([]);
  const [prefilledPrompt, setPrefilledPrompt] = useState('');

  // Execution states
  const [isLoading, setIsLoading] = useState(false);
  const [apiOnline, setApiOnline] = useState(true);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const messagesEndRef = useRef(null);

  // 1. Initial Load: Fetch chats, databases, and schema
  useEffect(() => {
    loadChatsFromBackend();
    loadDatabases();
  }, []);

  // When selected database changes, reload schema for that database
  useEffect(() => {
    if (selectedDbId) {
      loadSchemaForDb(selectedDbId);
    }
  }, [selectedDbId]);

  const loadChatsFromBackend = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/chats`);
      if (res.ok) {
        const data = await res.json();
        setApiOnline(true);
        if (data.chats && data.chats.length > 0) {
          setChats(data.chats);
          setActiveChatId(data.chats[0].id);
        } else {
          await createInitialChat();
        }
      } else {
        setApiOnline(false);
      }
    } catch {
      setApiOnline(false);
    }
  };

  const loadDatabases = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/databases`);
      if (res.ok) {
        const data = await res.json();
        setDatabases(data.databases || []);
        if (data.databases && data.databases.length > 0) {
          if (!data.databases.some(d => d.id === selectedDbId)) {
            setSelectedDbId(data.databases[0].id);
          }
        }
      }
    } catch (e) {
      console.error("Failed to load databases:", e);
    }
  };

  const loadSchemaForDb = async (dbId) => {
    try {
      const res = await fetch(`${API_BASE_URL}/tables?db_id=${encodeURIComponent(dbId)}`);
      if (res.ok) {
        const data = await res.json();
        setTables(data.tables || []);
      }
    } catch (e) {
      console.error("Failed to load schema for db:", dbId, e);
    }
  };

  const createInitialChat = async () => {
    const initialId = Date.now().toString();
    try {
      const res = await fetch(`${API_BASE_URL}/chats`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: initialId, title: "New Conversation" }),
      });
      if (res.ok) {
        const newChat = await res.json();
        setChats([newChat]);
        setActiveChatId(newChat.id);
      }
    } catch (e) {
      console.error("Failed to create initial chat on backend:", e);
    }
  };

  // Active chat session object
  const activeChat = chats.find(c => c.id === activeChatId) || chats[0] || { messages: [] };
  const currentDb = databases.find(d => d.id === selectedDbId) || { name: "Chinook (Music)", id: "chinook" };

  // Auto-scroll to bottom of messages
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [activeChat?.messages, isLoading]);

  // Create a new conversation on Backend
  const handleNewChat = async () => {
    const newId = Date.now().toString();
    const newChatObj = { id: newId, title: "New Conversation", messages: [] };

    setChats(prev => [newChatObj, ...prev]);
    setActiveChatId(newId);

    try {
      await fetch(`${API_BASE_URL}/chats`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: newId, title: "New Conversation" }),
      });
    } catch (err) {
      console.error("Backend error creating chat:", err);
    }
  };

  // Delete a conversation on Backend
  const handleDeleteChat = async (chatId) => {
    setChats(prev => {
      const filtered = prev.filter(c => c.id !== chatId);
      if (filtered.length === 0) return [];
      return filtered;
    });

    if (activeChatId === chatId) {
      const remaining = chats.filter(c => c.id !== chatId);
      if (remaining.length > 0) {
        setActiveChatId(remaining[0].id);
      } else {
        createInitialChat();
      }
    }

    try {
      await fetch(`${API_BASE_URL}/chats/${chatId}`, {
        method: "DELETE",
      });
    } catch (err) {
      console.error("Backend error deleting chat:", err);
    }
  };

  // Rename a conversation on Backend
  const handleRenameChat = async (chatId, newTitle) => {
    setChats(prev => prev.map(c => c.id === chatId ? { ...c, title: newTitle } : c));

    try {
      await fetch(`${API_BASE_URL}/chats/${chatId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: newTitle }),
      });
    } catch (err) {
      console.error("Backend error renaming chat:", err);
    }
  };

  // Callback when a new database is uploaded
  const handleUploadSuccess = (newDb) => {
    setDatabases(prev => [...prev, newDb]);
    setSelectedDbId(newDb.id);
  };

  // Callback when a database is deleted
  const handleDeleteDatabase = (deletedDbId) => {
    setDatabases(prev => prev.filter(d => d.id !== deletedDbId));
    if (selectedDbId === deletedDbId) {
      setSelectedDbId("chinook");
    }
  };

  // Send message: Runs Text-to-SQL Pipeline against the selected database
  const handleSendMessage = async (text) => {
    if (!text.trim() || isLoading) return;

    const currentChatId = activeChatId || Date.now().toString();
    const isFirstMessage = !activeChat || !activeChat.messages || activeChat.messages.length === 0;
    const newTitle = isFirstMessage ? (text.length > 32 ? text.slice(0, 32) + '...' : text) : (activeChat?.title || "Conversation");

    // Clear any prefilled text
    setPrefilledPrompt('');

    // Optimistic User Message
    const userMsg = {
      id: Date.now().toString(),
      role: 'user',
      content: text,
      timestamp: new Date().toISOString()
    };

    setChats(prev => prev.map(chat => {
      if (chat.id === currentChatId) {
        return {
          ...chat,
          title: newTitle,
          messages: [...(chat.messages || []), userMsg]
        };
      }
      return chat;
    }));

    setIsLoading(true);

    try {
      const response = await fetch(`${API_BASE_URL}/chats/${currentChatId}/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          question: text,
          db_id: selectedDbId 
        }),
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || "Query execution failed.");
      }

      const assistantMsg = await response.json();

      setChats(prev => prev.map(chat => {
        if (chat.id === currentChatId) {
          return {
            ...chat,
            title: newTitle,
            messages: [...(chat.messages || []), assistantMsg]
          };
        }
        return chat;
      }));
      setApiOnline(true);
    } catch (err) {
      const errorMsg = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `Error: ${err.message || "Failed to reach backend pipeline. Please check if FastAPI is running."}`,
        status: 'FAILED',
        timestamp: new Date().toISOString()
      };

      setChats(prev => prev.map(chat => {
        if (chat.id === currentChatId) {
          return {
            ...chat,
            messages: [...(chat.messages || []), errorMsg]
          };
        }
        return chat;
      }));
      setApiOnline(false);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectPrompt = (prompt) => {
    setPrefilledPrompt(prompt);
  };

  return (
    <div className={`flex h-screen overflow-hidden font-sans transition-colors duration-200 ${
      isDark ? 'bg-slate-950 text-slate-100' : 'bg-slate-50 text-slate-900'
    }`}>
      {/* ChatGPT-style Left Sidebar (with integrated Chats & Searchable Tables) */}
      <Sidebar
        chats={chats}
        activeChatId={activeChatId}
        onSelectChat={setActiveChatId}
        onNewChat={handleNewChat}
        onDeleteChat={handleDeleteChat}
        onRenameChat={handleRenameChat}
        tables={tables}
        onSelectPrompt={handleSelectPrompt}
        onOpenUpload={() => setUploadModalOpen(true)}
        isDark={isDark}
        onToggleTheme={() => setIsDark(!isDark)}
        isOpen={mobileMenuOpen}
        onClose={() => setMobileMenuOpen(false)}
      />

      {/* Manage & Upload Databases Modal */}
      <UploadDbModal
        isOpen={uploadModalOpen}
        onClose={() => setUploadModalOpen(false)}
        databases={databases}
        onUploadSuccess={handleUploadSuccess}
        onDeleteDatabase={handleDeleteDatabase}
        isDark={isDark}
        apiBaseUrl={API_BASE_URL}
      />

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col h-full min-w-0">
        {/* Top Navbar with Dynamic Database Selector */}
        <header className={`h-14 px-4 flex items-center justify-between border-b shrink-0 backdrop-blur-md ${
          isDark ? 'bg-slate-900/60 border-slate-800' : 'bg-white/70 border-slate-200'
        }`}>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="p-1.5 rounded-lg md:hidden text-slate-400 hover:text-slate-200 cursor-pointer"
            >
              <Menu className="w-5 h-5" />
            </button>

            <span className="font-semibold text-xs tracking-wide">
              {activeChat?.title || "New Conversation"}
            </span>
          </div>

          <div className="flex items-center gap-2.5">
            {/* 🗄️ PROMINENT DATABASE SELECTOR & UPLOAD CONTROLS */}
            <div className="flex items-center gap-2">
              <div className={`relative flex items-center rounded-xl border text-xs ${
                isDark ? 'bg-slate-900 border-slate-700/80 text-slate-200' : 'bg-white border-slate-300 text-slate-800 shadow-xs'
              }`}>
                <Database className="w-3.5 h-3.5 ml-2.5 text-indigo-400 shrink-0" />
                <select
                  value={selectedDbId}
                  onChange={(e) => {
                    if (e.target.value === '__upload_new__') {
                      setUploadModalOpen(true);
                    } else {
                      setSelectedDbId(e.target.value);
                    }
                  }}
                  className="bg-transparent py-1.5 pl-2 pr-7 text-xs font-medium focus:outline-none appearance-none cursor-pointer"
                  title="Switch data source for this chat"
                >
                  {databases.map((db) => {
                    const isNoSql = db.type === 'nosql';
                    return (
                      <option 
                        key={db.id} 
                        value={db.id}
                        className={isDark ? 'bg-slate-900 text-slate-200' : 'bg-white text-slate-800'}
                      >
                        {isNoSql ? `📄 ${db.name} (${db.doc_count || 0} docs)` : `🗄️ ${db.name} (${db.table_count || 0} tables)`}
                      </option>
                    );
                  })}
                  <option value="__upload_new__" className="text-indigo-400 font-semibold">
                    + Upload New Data Source...
                  </option>
                </select>
                <ChevronDown className="w-3.5 h-3.5 absolute right-2 text-slate-400 pointer-events-none" />
              </div>

              {/* ➕ CLEAR, PROMINENT "UPLOAD DATA" BUTTON */}
              <button
                onClick={() => setUploadModalOpen(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-xs shadow-indigo-600/30 transition-all cursor-pointer"
                title="Manage or upload SQLite (.db) or NoSQL (.json) datasets"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Upload DB</span>
              </button>
            </div>

            {!apiOnline && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
                <WifiOff className="w-3.5 h-3.5" /> Offline
              </span>
            )}
          </div>
        </header>

        {/* Offline Warning Banner */}
        {!apiOnline && (
          <div className="bg-amber-500/10 border-b border-amber-500/20 px-4 py-2 text-xs text-amber-400 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4" />
              <span>Backend API is not responding. Ensure <code>python backend/main.py</code> is running.</span>
            </div>
            <button
              onClick={() => { loadChatsFromBackend(); loadDatabases(); }}
              className="text-xs underline flex items-center gap-1 cursor-pointer"
            >
              <RefreshCw className="w-3 h-3" /> Retry
            </button>
          </div>
        )}

        {/* Messages Stream Container */}
        <div className="flex-1 overflow-y-auto p-4 md:p-6">
          <div className="max-w-3xl mx-auto w-full">
            {/* Empty State Welcome Screen */}
            {(!activeChat?.messages || activeChat.messages.length === 0) && (
              <div className="py-14 text-center animate-fadeIn">
                <div className="inline-flex p-4 rounded-2xl bg-indigo-500/10 border border-indigo-500/30 text-indigo-400 mb-4 shadow-sm">
                  <Sparkles className="w-8 h-8" />
                </div>
                <h2 className="text-xl font-bold mb-1.5">What can I query for you today?</h2>
                <p className="text-xs text-slate-400 max-w-md mx-auto leading-relaxed mb-4">
                  Currently querying: <strong className="text-indigo-400">{currentDb.name}</strong> ({tables.length} tables).
                  You can inspect tables in the left sidebar or upload your own SQLite file.
                </p>
              </div>
            )}

            {/* Conversation Messages */}
            {activeChat?.messages?.map((msg) => (
              <ChatMessage key={msg.id} message={msg} isDark={isDark} />
            ))}

            {/* AI Thinking Animation */}
            {isLoading && (
              <div className="flex items-center gap-3 text-xs text-slate-400 animate-pulse my-4">
                <div className="p-2 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
                  <Sparkles className="w-4 h-4 animate-spin" />
                </div>
                <span>Analyzing {currentDb.name} schema, applying guardrails & generating SQL...</span>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Bottom Sticky Prompt Bar (Clean without suggestions) */}
        <ChatInput
          onSendMessage={handleSendMessage}
          isLoading={isLoading}
          isDark={isDark}
          prefilledText={prefilledPrompt}
        />
      </div>
    </div>
  );
}
