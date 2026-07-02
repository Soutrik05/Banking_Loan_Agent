import React, { useState, useRef, useEffect } from 'react';
import { askAdvisor } from '../services/api';

interface AdvisorMessage {
  role: 'user' | 'assistant';
  content: string;
}

interface AdvisorPanelProps {
  sessionId: string;
  token: string;
  onClose: () => void;
}

const EXAMPLE_PROMPTS = [
  'Should I break my FD?',
  'How can I improve my CIBIL?',
  'Can I reduce my EMI?',
  'What if I lose my job?',
];

const AdvisorAvatar: React.FC = () => (
  <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-violet-600 to-purple-500 shadow-md shadow-purple-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
    <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
      <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
    </svg>
  </div>
);

export const AdvisorPanel: React.FC<AdvisorPanelProps> = ({ sessionId, token, onClose }) => {
  const [history, setHistory] = useState<AdvisorMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [history, isLoading]);

  useEffect(() => {
    // Auto-focus input when panel opens
    setTimeout(() => inputRef.current?.focus(), 100);
  }, []);

  const send = async (message: string) => {
    if (!message.trim() || isLoading) return;
    setError(null);
    const userMsg: AdvisorMessage = { role: 'user', content: message.trim() };
    setHistory(prev => [...prev, userMsg]);
    setInput('');
    setIsLoading(true);

    try {
      const data = await askAdvisor(message.trim(), sessionId, token, [...history, userMsg]);
      setHistory(prev => [...prev, { role: 'assistant', content: data.reply }]);
    } catch (e) {
      setError("I'm having trouble connecting right now. Please try again.");
      // Remove the optimistically added user message on failure
      setHistory(prev => prev.slice(0, -1));
    } finally {
      setIsLoading(false);
    }
  };

  const handleKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-end pointer-events-none">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/30 backdrop-blur-[2px] pointer-events-auto animate-fade-in"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="relative pointer-events-auto w-full max-w-md h-[85vh] max-h-[700px] mr-4 mb-4 flex flex-col rounded-3xl shadow-2xl shadow-purple-900/20 bg-white dark:bg-[#0d1020] border border-purple-100 dark:border-purple-900/40 overflow-hidden animate-slide-up">

        {/* Header */}
        <div className="flex items-center gap-3 px-5 py-4 border-b border-purple-100/60 dark:border-purple-900/40 bg-gradient-to-r from-violet-50/80 to-purple-50/50 dark:from-violet-950/40 dark:to-purple-950/20 flex-shrink-0">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-violet-600 to-purple-500 shadow-md shadow-purple-500/25 flex items-center justify-center flex-shrink-0">
            <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
              <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-extrabold text-gray-900 dark:text-gray-50 leading-none">Financial Advisor</p>
            <p className="text-[11px] font-medium text-purple-600 dark:text-purple-400 mt-0.5 flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse flex-shrink-0" />
              Personalised advice based on your real data
            </p>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-xl flex items-center justify-center text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors flex-shrink-0"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
          {history.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-center px-4 space-y-5">
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-violet-100 to-purple-100 dark:from-violet-900/30 dark:to-purple-900/30 flex items-center justify-center">
                <svg className="w-7 h-7 text-violet-500 dark:text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
                  <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
              </div>
              <div>
                <p className="text-sm font-bold text-gray-700 dark:text-gray-200 mb-1">Ask me anything about your finances</p>
                <p className="text-xs text-gray-400 dark:text-gray-500">I have access to your income, accounts, loans, and CIBIL data to give you personalised advice.</p>
              </div>
              <div className="w-full space-y-2">
                <p className="text-[10px] font-bold text-gray-400 dark:text-gray-500 uppercase tracking-wider">Try asking</p>
                <div className="flex flex-wrap gap-2 justify-center">
                  {EXAMPLE_PROMPTS.map(prompt => (
                    <button
                      key={prompt}
                      onClick={() => send(prompt)}
                      className="text-[11px] font-semibold text-violet-600 dark:text-violet-400 bg-violet-50 dark:bg-violet-900/20 border border-violet-100 dark:border-violet-800/40 px-3 py-1.5 rounded-xl hover:bg-violet-100 dark:hover:bg-violet-900/40 transition-colors"
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {history.map((msg, i) => (
            <div key={i} className={`flex gap-2.5 ${msg.role === 'user' ? 'justify-end' : 'justify-start'} animate-fade-in`}>
              {msg.role === 'assistant' && <AdvisorAvatar />}
              <div
                className={`max-w-[80%] px-4 py-3 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap ${
                  msg.role === 'user'
                    ? 'bg-gradient-to-tr from-violet-600 to-purple-500 text-white rounded-tr-none shadow-md shadow-purple-500/15'
                    : 'bg-violet-50/80 dark:bg-violet-950/40 border border-violet-100 dark:border-violet-900/40 border-l-[3px] border-l-violet-400 text-gray-800 dark:text-gray-100 rounded-tl-none shadow-sm'
                }`}
              >
                {msg.content}
              </div>
            </div>
          ))}

          {isLoading && (
            <div className="flex items-center gap-2.5">
              <AdvisorAvatar />
              <div className="bg-violet-50/80 dark:bg-violet-950/40 border border-violet-100 dark:border-violet-900/40 rounded-2xl rounded-tl-none px-4 py-3 flex gap-1.5 items-center shadow-sm">
                {[0, 1, 2].map(i => (
                  <span key={i} className="w-1.5 h-1.5 bg-violet-400 dark:bg-violet-500 rounded-full animate-bounce" style={{ animationDelay: `${i * 150}ms` }} />
                ))}
              </div>
            </div>
          )}

          {error && (
            <p className="text-xs text-red-500 dark:text-red-400 text-center px-4">{error}</p>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="px-4 py-3 border-t border-purple-100/60 dark:border-purple-900/40 bg-white/80 dark:bg-[#0d1020]/90 flex-shrink-0">
          <div className="flex items-end gap-2">
            <textarea
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKey}
              placeholder="Ask me anything about your finances…"
              rows={1}
              className="flex-1 resize-none text-sm bg-violet-50/60 dark:bg-violet-950/30 border border-violet-100 dark:border-violet-900/40 rounded-xl px-3.5 py-2.5 text-gray-800 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-600 outline-none focus:border-violet-400 dark:focus:border-violet-500 transition-colors leading-relaxed"
              style={{ maxHeight: 96 }}
              onInput={e => {
                const el = e.currentTarget;
                el.style.height = 'auto';
                el.style.height = `${Math.min(el.scrollHeight, 96)}px`;
              }}
            />
            <button
              onClick={() => send(input)}
              disabled={!input.trim() || isLoading}
              className="w-10 h-10 rounded-xl bg-gradient-to-tr from-violet-600 to-purple-500 hover:brightness-110 active:scale-95 text-white flex items-center justify-center flex-shrink-0 transition-all shadow-sm shadow-purple-500/20 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
            </button>
          </div>
          <p className="text-[10px] text-gray-400 dark:text-gray-600 mt-2 text-center">
            Advice is based on your live account data · Not financial regulation
          </p>
        </div>
      </div>
    </div>
  );
};
