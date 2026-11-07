import React, { useState, useMemo } from 'react';
import { 
  Sparkles, 
  Database, 
  FileJson, 
  FileSpreadsheet, 
  ArrowRight, 
  HelpCircle,
  Code2,
  Table as TableIcon,
  RefreshCw
} from 'lucide-react';
import { generateDatasetPrompts } from '../utils/sampleQuerySuggestions';

// Module-level session cache: ensures generated prompts stay rock-solid
// and never re-roll across intermediate async data loading or re-renders
const promptsCache = new Map();

const getDatasetIcon = (type) => {
  const t = (type || 'sql').toLowerCase();
  if (t === 'nosql') return <FileJson className="w-5 h-5 text-amber-400" />;
  if (t === 'excel' || t === 'csv') return <FileSpreadsheet className="w-5 h-5 text-emerald-400" />;
  return <Database className="w-5 h-5 text-indigo-400" />;
};

const getSupportedTools = (type) => {
  const t = (type || 'sql').toLowerCase();
  if (t === 'sql') return ['SQL (SQLite)', 'Python (Pandas)', 'R'];
  if (t === 'nosql') return ['MongoDB MQL', 'Python', 'R'];
  if (t === 'excel') return ['Excel Formula', 'Python (Pandas)', 'R'];
  if (t === 'csv') return ['Python (Pandas)', 'Excel Formula', 'R'];
  return ['Python (Pandas)', 'SQL', 'R'];
};

export default function HomepageWelcome({
  currentDb,
  tables = [],
  relationships = [],
  activeChatId = null,
  isSchemaLoading = false,
  onSelectPrompt,
  onOpenSchemaMap,
  isDark,
  isNewConversation = false
}) {
  const [shuffleKey, setShuffleKey] = useState(0);
  const [isShuffling, setIsShuffling] = useState(false);

  // Context key uniquely identifies the conversation session and database
  const contextKey = `${activeChatId || 'home'}__${currentDb?.id || 'chinook'}`;

  // Stable derivation: generate once per conversation session and dataset, and re-roll on Shuffle
  const activePrompts = useMemo(() => {
    // If schema is still actively loading and tables haven't arrived yet, wait to prevent intermediate flashing
    if (isSchemaLoading && (!tables || tables.length === 0)) {
      return [];
    }

    const cacheKey = `${contextKey}__${shuffleKey}`;
    if (!promptsCache.has(cacheKey)) {
      promptsCache.set(cacheKey, generateDatasetPrompts(tables, relationships, currentDb, 4, shuffleKey));
    }
    return promptsCache.get(cacheKey) || [];
  }, [contextKey, shuffleKey, isSchemaLoading, tables, relationships, currentDb]);

  // Handle manual "Shuffle" click to roll a fresh batch of random suggestions
  const handleShuffle = () => {
    setIsShuffling(true);
    setShuffleKey(prev => prev + 1);
    setTimeout(() => setIsShuffling(false), 350);
  };

  const supportedTools = getSupportedTools(currentDb?.type);

  // Compute metric display
  const isTabular = currentDb?.type === 'excel' || currentDb?.type === 'csv';
  const isNoSql = currentDb?.type === 'nosql';

  let metricText = '';
  if (isTabular) {
    const colCount = currentDb?.column_count;
    const rowCount = (currentDb?.row_count || 0).toLocaleString();
    metricText = colCount ? `${colCount} columns, ${rowCount} rows` : `${rowCount} rows`;
  } else if (isNoSql) {
    metricText = `${tables.length} collections`;
  } else {
    metricText = `${tables.length} tables`;
  }

  const isLoadingPrompts = activePrompts.length === 0 && isSchemaLoading;

  return (
    <div className="max-w-4xl mx-auto py-8 md:py-12 px-2 animate-fadeIn select-none">
      {/* 1. Hero Welcome Header */}
      <div className="text-center mb-8">
        <div className="inline-flex p-3 rounded-2xl bg-indigo-500/10 border border-indigo-500/30 text-indigo-400 mb-3 shadow-xs">
          <Sparkles className="w-7 h-7" />
        </div>
        <h1 className="text-2xl md:text-3xl font-bold tracking-tight mb-2">
          {isNewConversation ? "New Conversation" : "Welcome to Text to Query"}
        </h1>
        <p className="text-xs md:text-sm text-slate-400 max-w-lg mx-auto leading-relaxed">
          {isNewConversation 
            ? `Ready to query ${currentDb?.name || 'your dataset'}. Pick a prompt suggestion below or ask anything to get started.`
            : "Ask questions in plain natural language. Text to Query automatically translates your intent into safe, verified SQL, Python, Excel formulas, or NoSQL queries."}
        </p>
      </div>

      {/* 2. Connected Data Source Card */}
      <div className={`p-4 rounded-2xl border mb-6 transition-all ${
        isDark ? 'bg-slate-900/60 border-slate-800' : 'bg-white border-slate-200 shadow-xs'
      }`}>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className={`p-2.5 rounded-xl border ${
              isDark ? 'bg-slate-800 border-slate-700' : 'bg-slate-100 border-slate-200'
            }`}>
              {getDatasetIcon(currentDb?.type)}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-400 font-medium">Active Data Source:</span>
                <span className="font-semibold text-sm text-indigo-400">{currentDb?.name || 'Chinook'}</span>
              </div>
              <p className="text-[11px] text-slate-500 mt-0.5">
                {metricText} · Engine: <span className="font-medium text-slate-300">{currentDb?.type?.toUpperCase() || 'SQL'}</span>
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-1.5">
            {supportedTools.map((tool) => (
              <span
                key={tool}
                className={`text-[10px] font-medium px-2 py-0.5 rounded-md border ${
                  isDark 
                    ? 'bg-slate-800/80 border-slate-700 text-slate-300' 
                    : 'bg-slate-100 border-slate-200 text-slate-700'
                }`}
              >
                {tool}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* 3. Starter Prompt Cards Grid with Shuffle & Schema Controls */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-3 px-1">
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
            <HelpCircle className="w-3.5 h-3.5 text-indigo-400" />
            Suggested Starter Prompts
          </span>
          
          <div className="flex items-center gap-2">
            {/* 🔄 Interactive Shuffle / Re-Roll Button */}
            <button
              onClick={handleShuffle}
              disabled={isShuffling || isLoadingPrompts}
              className={`text-[11px] font-medium px-2.5 py-1 rounded-lg border transition-all flex items-center gap-1.5 cursor-pointer ${
                isDark 
                  ? 'bg-slate-800/80 hover:bg-slate-700/80 text-slate-300 hover:text-white border-slate-700' 
                  : 'bg-white hover:bg-slate-100 text-slate-600 hover:text-slate-900 border-slate-200 shadow-2xs'
              }`}
              title="Shuffle suggested prompts (roll new random ideas)"
            >
              <RefreshCw className={`w-3 h-3 text-indigo-400 transition-transform ${isShuffling ? 'animate-spin' : ''}`} />
              <span>Shuffle</span>
            </button>

            {!isTabular && onOpenSchemaMap && (
              <button
                onClick={onOpenSchemaMap}
                className="text-[11px] font-medium text-indigo-400 hover:text-indigo-300 hover:underline flex items-center gap-1 cursor-pointer"
              >
                <TableIcon className="w-3 h-3" />
                <span>Explore Schema</span>
              </button>
            )}
          </div>
        </div>

        {/* Loading Skeleton Cards while initial schema is fetching */}
        {isLoadingPrompts ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {[0, 1, 2, 3].map(i => (
              <div
                key={i}
                className={`p-3.5 rounded-xl border animate-pulse ${
                  isDark ? 'bg-slate-900/30 border-slate-800' : 'bg-white border-slate-200 shadow-2xs'
                }`}
              >
                <div className="flex items-center justify-between mb-2.5">
                  <div className={`h-3 w-28 rounded ${isDark ? 'bg-slate-800' : 'bg-slate-200'}`} />
                  <div className={`h-3 w-16 rounded ${isDark ? 'bg-slate-800' : 'bg-slate-200'}`} />
                </div>
                <div className={`h-3 w-full rounded mb-2 ${isDark ? 'bg-slate-800/60' : 'bg-slate-100'}`} />
                <div className={`h-3 w-3/4 rounded ${isDark ? 'bg-slate-800/60' : 'bg-slate-100'}`} />
              </div>
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {activePrompts.map((item, idx) => (
              <button
                key={`${item.title}-${idx}`}
                onClick={() => onSelectPrompt(item.prompt)}
                className={`p-3.5 rounded-xl border text-left transition-all group cursor-pointer ${
                  isDark 
                    ? 'bg-slate-900/40 hover:bg-slate-800/80 border-slate-800 hover:border-indigo-500/50 hover:shadow-xs' 
                    : 'bg-white hover:bg-slate-50 border-slate-200 hover:border-indigo-400 hover:shadow-xs'
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-xs font-semibold text-slate-200 group-hover:text-indigo-400 transition-colors">
                    {item.title}
                  </span>
                  <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${
                    isDark ? 'bg-slate-800 text-slate-400' : 'bg-slate-100 text-slate-600'
                  }`}>
                    {item.tag}
                  </span>
                </div>
                <p className="text-xs text-slate-400 group-hover:text-slate-300 line-clamp-2 leading-relaxed">
                  "{item.prompt}"
                </p>
                <div className="mt-2 flex items-center gap-1 text-[11px] font-medium text-indigo-400 opacity-0 group-hover:opacity-100 transition-opacity">
                  <span>Use prompt</span>
                  <ArrowRight className="w-3 h-3 transition-transform group-hover:translate-x-0.5" />
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* 4. Instructions Footer Note */}
      <div className="text-center text-[11px] text-slate-500 flex items-center justify-center gap-1.5">
        <Code2 className="w-3.5 h-3.5 text-indigo-400/80" />
        <span>
          {isNewConversation
            ? `Type your question below or click a prompt suggestion above to start querying ${currentDb?.name || 'your dataset'}.`
            : "Type your question in the prompt box below or click a starter suggestion to begin."}
        </span>
      </div>
    </div>
  );
}
