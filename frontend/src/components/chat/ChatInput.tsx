import React, { useRef } from 'react';

interface ChatInputProps {
  value: string;
  onChange: (val: string) => void;
  onSend: (val: string) => void;
}

export const ChatInput: React.FC<ChatInputProps> = ({ value, onChange, onSend }) => {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSend(value);
    }
  };

  return (
    <div className="border-t border-gray-150/50 dark:border-gray-800 px-6 py-4 bg-white/95 dark:bg-[#0b0f1a]/95 backdrop-blur-md">
      <div className="flex items-center gap-3 bg-gray-50/70 dark:bg-gray-900/60 hover:bg-gray-50 dark:hover:bg-gray-900 focus-within:bg-white dark:focus-within:bg-gray-900 rounded-2xl px-4 py-2.5 border border-gray-200 dark:border-gray-700 focus-within:border-[#1e3a6e] dark:focus-within:border-blue-400 focus-within:ring-4 focus-within:ring-[#1e3a6e]/10 dark:focus-within:ring-blue-400/10 transition-all duration-200 shadow-sm">
        {/* Attachment */}
        <button className="text-gray-400 dark:text-gray-500 hover:text-[#1e3a6e] dark:hover:text-blue-300 p-1 flex-shrink-0 transition-colors">
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
          </svg>
        </button>

        <input
          ref={inputRef}
          type="text"
          value={value}
          onChange={e => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="How can I help you?"
          className="flex-1 bg-transparent text-sm text-gray-700 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 outline-none font-medium"
        />

        {/* Mic */}
        <button className="text-gray-400 dark:text-gray-500 hover:text-[#1e3a6e] dark:hover:text-blue-300 p-1 flex-shrink-0 transition-colors">
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
          </svg>
        </button>

        {/* Send */}
        <button
          onClick={() => onSend(value)}
          disabled={!value.trim()}
          className="w-9 h-9 rounded-xl bg-gradient-to-tr from-[#1e3a6e] to-[#3b82f6] flex items-center justify-center hover:shadow-lg hover:shadow-blue-500/10 active:scale-95 transition-all duration-200 disabled:opacity-30 disabled:cursor-not-allowed disabled:shadow-none flex-shrink-0"
        >
          <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
          </svg>
        </button>
      </div>
      <p className="text-center text-[10px] tracking-wide font-medium text-gray-400 dark:text-gray-600 uppercase mt-2.5">
        ✦ BankWise AI can make suggestions. Verify important information.
      </p>
    </div>
  );
};
