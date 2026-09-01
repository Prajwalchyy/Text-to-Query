import React, { useState, useEffect } from 'react';
import { 
  Database, 
  ShieldCheck, 
  CheckCircle2, 
  AlertTriangle, 
  Copy, 
  Check, 
  Send, 
  RefreshCw, 
  Terminal, 
  Table as TableIcon,
  Sparkles,
  Layers,
  WifiOff,
  Server,
  Sun,
  Moon
} from 'lucide-react';

const API_BASE_URL = "/api";

const QUICK_QUESTIONS = [
  { label: "Top 3 Artists", question: "Which 3 artists have the most albums in the catalog?" },
  { label: "Top 5 Customers", question: "List the top 5 customers by total invoice spending." },
  { label: "Total Tracks", question: "How many total tracks are in the database?" },
  { label: "Attack Test (DROP)", question: "DROP TABLE Customer;" }
];

export default function App() {
  const [isDark, setIsDark] = useState(() => {
    const savedTheme = localStorage.getItem("theme");
    return savedTheme !== null ? savedTheme === "dark" : true;
  });

  useEffect(() => {
    localStorage.setItem("theme", isDark ? "dark" : "light");
  }, [isDark]);

  const [inputQuestion, setInputQuestion] = useState(QUICK_QUESTIONS[0].question);
  const [activeTab, setActiveTab] = useState('summary');
  const [copied, setCopied] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [apiOnline, setApiOnline] = useState(false);
  const [tables, setTables] = useState([]);
  const [selectedTable, setSelectedTable] = useState(null);
  const [errorMsg, setErrorMsg] = useState(null);

  // Live Query Result State
  const [result, setResult] = useState({
    status: "READY",
    confidence_score: 0,
    latency_ms: 0,
    attempts: 0,
    final_sql: "-- Run a query to generate SQL --",
    summary: "Enter a question above or click one of the quick test queries to query Chinook SQLite live.",
    data: []
  });

  // 1. Check API Health & Fetch Live Database Schema
  useEffect(() => {
    checkHealthAndFetchSchema();
  }, []);

  const checkHealthAndFetchSchema = async () => {
    try {
      const healthRes = await fetch(`${API_BASE_URL}/health`);
      if (healthRes.ok) {
        setApiOnline(true);
        setErrorMsg(null);

        // Fetch Live Tables from SQLite
        const tablesRes = await fetch(`${API_BASE_URL}/tables`);
        if (tablesRes.ok) {
          const data = await tablesRes.json();
          setTables(data.tables || []);
          if (data.tables && data.tables.length > 0) {
            setSelectedTable(data.tables[0]);
          }
        }
      } else {
        setApiOnline(false);
      }
    } catch (err) {
      setApiOnline(false);
    }
  };

  // 2. Execute Live Query through FastAPI Backend
  const handleRunQuery = async (queryText = inputQuestion) => {
    if (!queryText.trim()) return;

    setIsLoading(true);
    setErrorMsg(null);

    try {
      const response = await fetch(`${API_BASE_URL}/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: queryText }),
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || "Query execution failed.");
      }

      const data = await response.json();
      setResult(data);
      setApiOnline(true);
    } catch (err) {
      setErrorMsg(err.message || "Failed to reach backend API. Make sure FastAPI is running.");
      setApiOnline(false);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCopy = (text) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={`min-h-screen flex flex-col font-sans transition-colors duration-200 ${
      isDark ? 'bg-slate-950 text-slate-100' : 'bg-slate-50 text-slate-900'
    }`}>
      {/* Top Navbar */}
      <header className={`border-b px-6 py-4 flex items-center justify-between sticky top-0 z-50 transition-colors backdrop-blur-md ${
        isDark ? 'border-slate-800 bg-slate-900/70' : 'border-slate-200 bg-white/80 shadow-xs'
      }`}>
        <div className="flex items-center gap-3">
          <div className="p-2 bg-indigo-500/10 border border-indigo-500/30 rounded-xl text-indigo-400">
            <Database className="w-6 h-6" />
          </div>
          <div>
            <h1 className={`text-xl font-bold bg-clip-text text-transparent ${
              isDark 
                ? 'bg-gradient-to-r from-white via-slate-200 to-indigo-300' 
                : 'bg-gradient-to-r from-slate-900 via-slate-800 to-indigo-600'
            }`}>
              Enterprise Text-to-SQL
            </h1>
            <p className={`text-xs ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
              React Frontend + FastAPI Live Connection
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Server Connection Indicator */}
          <div className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium border ${
            apiOnline 
              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' 
              : 'bg-amber-500/10 text-amber-500 border-amber-500/30'
          }`}>
            {apiOnline ? <Server className="w-3.5 h-3.5" /> : <WifiOff className="w-3.5 h-3.5" />}
            {apiOnline ? "FastAPI: Connected" : "FastAPI: Offline"}
          </div>

          <span className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
            <ShieldCheck className="w-3.5 h-3.5" /> 4-Layer Guardrails
          </span>

          {/* ☀️ / 🌙 Light & Dark Mode Toggle Button */}
          <button
            onClick={() => setIsDark(!isDark)}
            aria-label="Toggle Light and Dark Mode"
            className={`p-2 rounded-xl border transition-all cursor-pointer flex items-center gap-1.5 text-xs font-medium ${
              isDark
                ? 'bg-slate-800/80 border-slate-700 text-amber-300 hover:bg-slate-700 hover:text-amber-200'
                : 'bg-white border-slate-300 text-indigo-600 hover:bg-slate-100 hover:border-slate-400 shadow-xs'
            }`}
          >
            {isDark ? (
              <>
                <Sun className="w-4 h-4 text-amber-400" />
                <span className="hidden md:inline">Light</span>
              </>
            ) : (
              <>
                <Moon className="w-4 h-4 text-indigo-600" />
                <span className="hidden md:inline">Dark</span>
              </>
            )}
          </button>
        </div>
      </header>

      {/* Backend Offline Warning Banner */}
      {!apiOnline && (
        <div className="bg-amber-500/10 border-b border-amber-500/20 px-6 py-2.5 text-xs text-amber-500 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-500" />
            <span>
              Backend is offline. Run: <code className={`${isDark ? 'bg-amber-950/60 text-amber-200' : 'bg-amber-100 text-amber-900'} px-2 py-0.5 rounded font-mono`}>python backend/main.py</code>
            </span>
          </div>
          <button 
            onClick={checkHealthAndFetchSchema}
            className="text-xs font-medium hover:underline flex items-center gap-1 cursor-pointer"
          >
            <RefreshCw className="w-3 h-3" /> Retry Connection
          </button>
        </div>
      )}

      {/* Main Grid Layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Sidebar: Live Schema Explorer */}
        <aside className={`w-80 border-r p-5 flex flex-col gap-6 overflow-y-auto hidden md:flex transition-colors ${
          isDark ? 'border-slate-800 bg-slate-900/20' : 'border-slate-200 bg-slate-100/40'
        }`}>
          <div>
            <h2 className={`text-sm font-semibold uppercase tracking-wider flex items-center gap-2 mb-3 ${
              isDark ? 'text-slate-300' : 'text-slate-700'
            }`}>
              <Layers className="w-4 h-4 text-indigo-500" /> Live Database Schema
            </h2>
            <p className={`text-xs mb-4 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
              SQLite Tables ({tables.length})
            </p>

            {tables.length > 0 ? (
              <div className="space-y-1.5 max-h-64 overflow-y-auto pr-1">
                {tables.map(table => (
                  <button
                    key={table.name}
                    onClick={() => setSelectedTable(table)}
                    className={`w-full text-left px-3 py-2 rounded-lg text-xs font-medium transition-all flex items-center justify-between cursor-pointer ${
                      selectedTable?.name === table.name
                        ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30'
                        : isDark
                          ? 'bg-slate-800/40 text-slate-300 hover:bg-slate-800 hover:text-white'
                          : 'bg-white text-slate-700 hover:bg-slate-200/70 border border-slate-200/80 shadow-xs'
                    }`}
                  >
                    <span className="flex items-center gap-2">
                      <TableIcon className="w-3.5 h-3.5 opacity-70" />
                      {table.name}
                    </span>
                    <span className="text-[10px] opacity-70">{table.cols.length} cols</span>
                  </button>
                ))}
              </div>
            ) : (
              <div className={`text-xs py-3 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                {apiOnline ? "Loading tables..." : "Connect backend to inspect tables."}
              </div>
            )}
          </div>

          {/* Selected Table Columns */}
          {selectedTable && (
            <div className={`border rounded-xl p-4 flex-1 overflow-y-auto transition-colors ${
              isDark ? 'border-slate-800 bg-slate-900/40' : 'border-slate-200 bg-white shadow-xs'
            }`}>
              <h3 className={`text-xs font-bold mb-2.5 flex items-center gap-1.5 ${
                isDark ? 'text-slate-200' : 'text-slate-800'
              }`}>
                <Sparkles className="w-3.5 h-3.5 text-indigo-500" /> Columns in `{selectedTable.name}`:
              </h3>
              <ul className="space-y-1 text-xs">
                {selectedTable.cols.map((col, idx) => (
                  <li key={idx} className="flex items-center gap-2 py-0.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-indigo-500"></span>
                    <code className={isDark ? 'text-slate-300' : 'text-slate-600 font-mono'}>{col}</code>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </aside>

        {/* Center/Right Content Area */}
        <main className="flex-1 flex flex-col p-6 max-w-5xl mx-auto w-full gap-6 overflow-y-auto">
          {/* Query Bar */}
          <div className={`border rounded-2xl p-4 shadow-sm transition-colors ${
            isDark ? 'bg-slate-900/60 border-slate-800' : 'bg-white border-slate-200'
          }`}>
            <div className="flex flex-wrap gap-2 mb-3">
              <span className={`text-xs font-medium self-center mr-1 ${
                isDark ? 'text-slate-400' : 'text-slate-500'
              }`}>
                Sample Questions:
              </span>
              {QUICK_QUESTIONS.map((sq, i) => (
                <button
                  key={i}
                  onClick={() => {
                    setInputQuestion(sq.question);
                    handleRunQuery(sq.question);
                  }}
                  className={`text-xs px-3 py-1 rounded-full border transition-all cursor-pointer ${
                    inputQuestion === sq.question
                      ? isDark
                        ? 'border-indigo-500 bg-indigo-500/20 text-indigo-300 font-medium'
                        : 'border-indigo-600 bg-indigo-50 text-indigo-700 font-medium'
                      : isDark
                        ? 'border-slate-800 bg-slate-900 hover:border-slate-700 text-slate-400'
                        : 'border-slate-200 bg-slate-100 hover:border-slate-300 text-slate-600'
                  }`}
                >
                  {sq.label}
                </button>
              ))}
            </div>

            <div className="flex items-center gap-3">
              <input
                type="text"
                value={inputQuestion}
                onChange={(e) => setInputQuestion(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleRunQuery()}
                placeholder="Ask a question about your database in natural English..."
                className={`flex-1 border rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-indigo-500 transition-colors ${
                  isDark
                    ? 'bg-slate-950 border-slate-700/80 text-white placeholder-slate-500'
                    : 'bg-slate-50 border-slate-300 text-slate-900 placeholder-slate-400 focus:bg-white'
                }`}
              />
              <button
                onClick={() => handleRunQuery()}
                disabled={isLoading}
                className="px-5 py-3 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-xl font-medium text-sm flex items-center gap-2 transition-all shadow-md shadow-indigo-600/20 cursor-pointer"
              >
                {isLoading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                Run Pipeline
              </button>
            </div>

            {errorMsg && (
              <div className="mt-3 text-xs text-rose-500 bg-rose-500/10 border border-rose-500/20 p-2.5 rounded-lg flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 shrink-0" />
                <span>{errorMsg}</span>
              </div>
            )}
          </div>

          {/* Telemetry Metrics Bar */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className={`border rounded-xl p-4 transition-colors ${
              isDark ? 'bg-slate-900/40 border-slate-800/80' : 'bg-white border-slate-200 shadow-xs'
            }`}>
              <span className={`text-xs font-medium ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                Pipeline Status
              </span>
              <div className="flex items-center gap-2 mt-1">
                {result.status === 'SUCCESS' ? (
                  <>
                    <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                    <span className="text-sm font-bold text-emerald-500">SUCCESS</span>
                  </>
                ) : result.status === 'FAILED' ? (
                  <>
                    <AlertTriangle className="w-4 h-4 text-rose-500" />
                    <span className="text-sm font-bold text-rose-500">BLOCKED / FAILED</span>
                  </>
                ) : (
                  <span className={`text-sm font-bold ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                    IDLE
                  </span>
                )}
              </div>
            </div>

            <div className={`border rounded-xl p-4 transition-colors ${
              isDark ? 'bg-slate-900/40 border-slate-800/80' : 'bg-white border-slate-200 shadow-xs'
            }`}>
              <span className={`text-xs font-medium ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                Confidence Score
              </span>
              <div className={`text-sm font-bold mt-1 ${isDark ? 'text-white' : 'text-slate-900'}`}>
                {Math.round((result.confidence_score || 0) * 100)}%
              </div>
            </div>

            <div className={`border rounded-xl p-4 transition-colors ${
              isDark ? 'bg-slate-900/40 border-slate-800/80' : 'bg-white border-slate-200 shadow-xs'
            }`}>
              <span className={`text-xs font-medium ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                Latency
              </span>
              <div className={`text-sm font-bold mt-1 ${isDark ? 'text-white' : 'text-slate-900'}`}>
                {result.latency_ms || 0} ms
              </div>
            </div>

            <div className={`border rounded-xl p-4 transition-colors ${
              isDark ? 'bg-slate-900/40 border-slate-800/80' : 'bg-white border-slate-200 shadow-xs'
            }`}>
              <span className={`text-xs font-medium ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                Attempts Needed
              </span>
              <div className={`text-sm font-bold mt-1 ${isDark ? 'text-white' : 'text-slate-900'}`}>
                {result.attempts || 0} / 3
              </div>
            </div>
          </div>

          {/* Inspection Tabs */}
          <div className={`border rounded-2xl flex-1 flex flex-col overflow-hidden transition-colors ${
            isDark ? 'bg-slate-900/40 border-slate-800' : 'bg-white border-slate-200 shadow-xs'
          }`}>
            <div className={`flex border-b px-4 pt-2 gap-2 ${
              isDark ? 'border-slate-800' : 'border-slate-200'
            }`}>
              <button
                onClick={() => setActiveTab('summary')}
                className={`px-4 py-2.5 text-xs font-semibold border-b-2 transition-all flex items-center gap-2 cursor-pointer ${
                  activeTab === 'summary'
                    ? isDark ? 'border-indigo-500 text-indigo-400' : 'border-indigo-600 text-indigo-600'
                    : isDark ? 'border-transparent text-slate-400 hover:text-slate-200' : 'border-transparent text-slate-500 hover:text-slate-800'
                }`}
              >
                <Sparkles className="w-3.5 h-3.5" /> Plain-English Answer
              </button>
              <button
                onClick={() => setActiveTab('data')}
                className={`px-4 py-2.5 text-xs font-semibold border-b-2 transition-all flex items-center gap-2 cursor-pointer ${
                  activeTab === 'data'
                    ? isDark ? 'border-indigo-500 text-indigo-400' : 'border-indigo-600 text-indigo-600'
                    : isDark ? 'border-transparent text-slate-400 hover:text-slate-200' : 'border-transparent text-slate-500 hover:text-slate-800'
                }`}
              >
                <TableIcon className="w-3.5 h-3.5" /> Data Table ({result.data?.length || 0})
              </button>
              <button
                onClick={() => setActiveTab('sql')}
                className={`px-4 py-2.5 text-xs font-semibold border-b-2 transition-all flex items-center gap-2 cursor-pointer ${
                  activeTab === 'sql'
                    ? isDark ? 'border-indigo-500 text-indigo-400' : 'border-indigo-600 text-indigo-600'
                    : isDark ? 'border-transparent text-slate-400 hover:text-slate-200' : 'border-transparent text-slate-500 hover:text-slate-800'
                }`}
              >
                <Terminal className="w-3.5 h-3.5" /> Generated SQL
              </button>
            </div>

            <div className="p-5 flex-1 overflow-auto">
              {/* Tab 1: Summary */}
              {activeTab === 'summary' && (
                <div className={`p-4 rounded-xl border text-sm leading-relaxed ${
                  isDark 
                    ? 'bg-slate-950/60 border-slate-800/80 text-slate-300' 
                    : 'bg-slate-50 border-slate-200 text-slate-700'
                }`}>
                  <p>{result.summary || "No response generated."}</p>
                </div>
              )}

              {/* Tab 2: Data Table */}
              {activeTab === 'data' && (
                <div>
                  {result.data && result.data.length > 0 ? (
                    <div className={`border rounded-xl overflow-hidden ${
                      isDark ? 'border-slate-800' : 'border-slate-200'
                    }`}>
                      <table className="w-full text-left text-xs border-collapse">
                        <thead className={`uppercase tracking-wider font-semibold border-b ${
                          isDark 
                            ? 'bg-slate-800/60 text-slate-300 border-slate-700/60' 
                            : 'bg-slate-100 text-slate-700 border-slate-200'
                        }`}>
                          <tr>
                            {Object.keys(result.data[0]).map((key) => (
                              <th key={key} className="px-4 py-3">{key}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody className={`divide-y ${isDark ? 'divide-slate-800' : 'divide-slate-200'}`}>
                          {result.data.map((row, idx) => (
                            <tr key={idx} className={isDark ? 'hover:bg-slate-800/30 transition-colors' : 'hover:bg-slate-50 transition-colors'}>
                              {Object.values(row).map((val, cIdx) => (
                                <td key={cIdx} className={`px-4 py-3 font-mono ${
                                  isDark ? 'text-slate-300' : 'text-slate-700'
                                }`}>
                                  {String(val)}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className={`text-center py-8 text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                      No data rows returned for this query.
                    </div>
                  )}
                </div>
              )}

              {/* Tab 3: SQL Code */}
              {activeTab === 'sql' && (
                <div className={`rounded-xl border transition-all h-auto w-full ${
                  isDark ? 'bg-slate-950 border-slate-800' : 'bg-slate-900 border-slate-800'
                }`}>
                  {/* Top Bar with Query Info & Copy Button */}
                  <div className="flex items-center justify-between px-4 py-2.5 bg-slate-900/90 border-b border-slate-800 text-xs text-slate-400 font-mono">
                    <span className="flex items-center gap-1.5 font-semibold text-slate-300">
                      <Terminal className="w-3.5 h-3.5 text-indigo-400" /> SQLite Dialect
                    </span>
                    <button
                      onClick={() => handleCopy(result.final_sql)}
                      className="px-2.5 py-1 rounded-md bg-slate-800 hover:bg-slate-700 text-slate-200 transition-colors flex items-center gap-1.5 cursor-pointer text-[11px]"
                    >
                      {copied ? (
                        <>
                          <Check className="w-3 h-3 text-emerald-400" />
                          <span className="text-emerald-400">Copied!</span>
                        </>
                      ) : (
                        <>
                          <Copy className="w-3 h-3 text-slate-400" />
                          <span>Copy SQL</span>
                        </>
                      )}
                    </button>
                  </div>

                  {/* Auto-expanding Code Container */}
                  <div className="p-4 overflow-x-auto w-full">
                    <pre className="font-mono text-xs text-emerald-400 whitespace-pre-wrap break-words leading-relaxed m-0 selection:bg-emerald-950 selection:text-emerald-200">
                      {result.final_sql || "-- No SQL generated"}
                    </pre>
                  </div>
                </div>
              )}
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
