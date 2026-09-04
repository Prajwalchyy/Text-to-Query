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

  // Dynamic Auto-Expand Textarea (up to 220px height)
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      const scrollHeight = textareaRef.current.scrollHeight;
      const targetHeight = Math.min(Math.max(scrollHeight, 38), 220);
      textareaRef.current.style.height = `${targetHeight}px`;
    }
  }, [text]);

  const handleSubmit = (e) => {
    if (e) e.preventDefault();
    if (!text.trim() || isLoading) return;
    onSendMessage(text);
    setText('');
    if (textareaRef.current) {
      textareaRef.current.style.height = '38px';
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const isMultiLine = text.includes('\n') || text.length > 80;

  return (
    <div className="w-full max-w-5xl xl:max-w-6xl mx-auto px-4 pb-4">
      {/* Floating Prompt Bar */}
      <form onSubmit={handleSubmit} className="relative">
        <div className={`flex items-end rounded-2xl border transition-all p-2 shadow-lg ${
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
            placeholder="Ask anything about your data (SQL queries, NoSQL aggregations, Pandas filters, Excel formulas)..."
            style={{ minHeight: '38px', maxHeight: '220px' }}
            className={`w-full px-3 py-2 text-sm resize-none bg-transparent focus:outline-none custom-scrollbar leading-relaxed ${
              isDark ? 'text-slate-100 placeholder-slate-500' : 'text-slate-900 placeholder-slate-400'
            }`}
          />

          <button
            type="submit"
            disabled={!text.trim() || isLoading}
            className="p-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-30 disabled:hover:bg-indigo-600 text-white transition-all shrink-0 cursor-pointer mb-0.5"
            aria-label="Send message"
            title="Send message (Enter)"
          >
            {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          </button>
        </div>
        <div className="flex items-center justify-between px-1 text-[10px] text-slate-400 mt-2">
          <span>Multi-Engine Data Intelligence • SQL, NoSQL & Spreadsheets • AST Sandboxed Guardrails</span>
          {isMultiLine && (
            <span className="font-mono text-indigo-400/90 font-medium">
              Shift + Enter for new line • Enter to send
            </span>
          )}
        </div>
      </form>
    </div>
  );
}
