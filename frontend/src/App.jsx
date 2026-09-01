import React, { useState, useEffect, useRef } from 'react';
import { Menu, WifiOff, AlertTriangle, RefreshCw, Sparkles, Shield, Database } from 'lucide-react';
import Sidebar from './components/Sidebar';
import ChatMessage from './components/ChatMessage';
import ChatInput from './components/ChatInput';
import SchemaDrawer from './components/SchemaDrawer';

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
  const [tables, setTables] = useState([]);
  const [schemaDrawerOpen, setSchemaDrawerOpen] = useState(false);
  const [prefilledPrompt, setPrefilledPrompt] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [apiOnline, setApiOnline] = useState(true);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const messagesEndRef = useRef(null);

  // 1. Initial Load: Fetch chats and live database schema from Backend
  useEffect(() => {
    loadChatsFromBackend();
    loadSchemaFromBackend();
  }, []);

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

  const loadSchemaFromBackend = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/tables`);
      if (res.ok) {
        const data = await res.json();
        setTables(data.tables || []);
      }
    } catch (e) {
      console.error("Failed to load schema:", e);
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

  // Auto-scroll to bottom of messages
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [activeChat?.messages, isLoading]);

  // 2. Create a new conversation on Backend
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

  // 3. Delete a conversation on Backend
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

  // 4. Send message: Saves to Backend Database & runs Text-to-SQL Pipeline
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
        body: JSON.stringify({ question: text }),
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
      {/* ChatGPT-style Left Sidebar (With Chats and Schema Tabs) */}
      <Sidebar
        chats={chats}
        activeChatId={activeChatId}
        onSelectChat={setActiveChatId}
        onNewChat={handleNewChat}
        onDeleteChat={handleDeleteChat}
        tables={tables}
        onSelectPrompt={handleSelectPrompt}
        isDark={isDark}
        onToggleTheme={() => setIsDark(!isDark)}
        isOpen={mobileMenuOpen}
        onClose={() => setMobileMenuOpen(false)}
      />

      {/* Slide-over Schema Drawer */}
      <SchemaDrawer
        isOpen={schemaDrawerOpen}
        onClose={() => setSchemaDrawerOpen(false)}
        tables={tables}
        onSelectPrompt={handleSelectPrompt}
        isDark={isDark}
      />

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col h-full min-w-0">
        {/* Top Navbar */}
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
            {/* Database Schema Explorer Trigger Button */}
            <button
              onClick={() => setSchemaDrawerOpen(true)}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border text-xs font-medium transition-all cursor-pointer ${
                isDark
                  ? 'bg-indigo-500/10 text-indigo-300 border-indigo-500/30 hover:bg-indigo-500/20'
                  : 'bg-indigo-50 text-indigo-600 border-indigo-200 hover:bg-indigo-100 shadow-xs'
              }`}
            >
              <Database className="w-3.5 h-3.5" />
              <span>Explore Schema ({tables.length})</span>
            </button>

            {!apiOnline && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
                <WifiOff className="w-3.5 h-3.5" /> Offline
              </span>
            )}

            <span className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <Shield className="w-3.5 h-3.5" /> AST Guardrails
            </span>
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
              onClick={() => { loadChatsFromBackend(); loadSchemaFromBackend(); }}
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
              <div className="py-16 text-center animate-fadeIn">
                <div className="inline-flex p-4 rounded-2xl bg-indigo-500/10 border border-indigo-500/30 text-indigo-400 mb-4 shadow-sm">
                  <Sparkles className="w-8 h-8" />
                </div>
                <h2 className="text-xl font-bold mb-2">What can I query for you today?</h2>
                <p className="text-xs text-slate-400 max-w-md mx-auto leading-relaxed mb-6">
                  Ask database questions in plain English. Check the <strong>Explore Schema</strong> button above or the <strong>Tables</strong> tab on the left to browse available tables and columns.
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
                <span>Analyzing schema, applying guardrails & generating SQL...</span>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Bottom Sticky Prompt Bar */}
        <ChatInput
          onSendMessage={handleSendMessage}
          isLoading={isLoading}
          isDark={isDark}
          showSuggestions={!activeChat?.messages || activeChat.messages.length === 0}
          prefilledText={prefilledPrompt}
        />
      </div>
    </div>
  );
}
