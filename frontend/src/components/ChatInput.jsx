import React, { useState, useRef, useEffect } from 'react';
import { Send, Loader2 } from 'lucide-react';

export default function ChatInput({ 
  onSendMessage, 
  isLoading, 
  isDark, 
  prefilledText = '' 
}) {
  const [text, setText] = useState('');
  const textareaRef = useRef(null);

  // Sync prefilled text from schema explorer
  useEffect(() => {
    if (prefilledText) {
      setText(prefilledText);
      textareaRef.current?.focus();
    }
  }, [prefilledText]);

  const handleSubmit = (e) => {
    if (e) e.preventDefault();
    if (!text.trim() || isLoading) return;
    onSendMessage(text);
    setText('');
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="w-full max-w-3xl mx-auto px-4 pb-4">
      {/* Floating Prompt Bar */}
      <form onSubmit={handleSubmit} className="relative">
        <div className={`flex items-center rounded-2xl border transition-all p-2 shadow-lg ${
          isDark 
            ? 'bg-slate-900 border-slate-700/80 focus-within:border-indigo-500 shadow-black/30' 
            : 'bg-white border-slate-300 focus-within:border-indigo-500 shadow-slate-200/50'
        }`}>
          <textarea
            ref={textareaRef}
            rows={1}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask anything about your database (e.g. Total sales by country, Top 5 products)..."
            className={`w-full px-3 py-1.5 text-sm resize-none bg-transparent focus:outline-none max-h-32 ${
              isDark ? 'text-slate-100 placeholder-slate-500' : 'text-slate-900 placeholder-slate-400'
            }`}
          />

          <button
            type="submit"
            disabled={!text.trim() || isLoading}
            className="p-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-30 disabled:hover:bg-indigo-600 text-white transition-all shrink-0 cursor-pointer"
            aria-label="Send message"
          >
            {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          </button>
        </div>
        <p className="text-[10px] text-center text-slate-400 mt-2">
          Natural Language to SQL • AST & Keyword Guardrails • SQLite Local Execution
        </p>
      </form>
    </div>
  );
}
