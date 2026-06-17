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
    <div className="border-t border-gray-100 px-4 py-3 bg-white">
      <div className="flex items-center gap-2 bg-gray-50 rounded-xl px-3 py-2 border border-gray-200 focus-within:border-[#1e3a6e] transition-colors">
        {/* Attachment */}
        <button className="text-gray-400 hover:text-gray-600 p-1 flex-shrink-0">
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
          placeholder="Type your message..."
          className="flex-1 bg-transparent text-sm text-gray-700 placeholder-gray-400 outline-none"
        />

        {/* Mic */}
        <button className="text-gray-400 hover:text-gray-600 p-1 flex-shrink-0">
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
          </svg>
        </button>

        {/* Send */}
        <button
          onClick={() => onSend(value)}
          disabled={!value.trim()}
          className="w-8 h-8 rounded-lg bg-[#1e3a6e] flex items-center justify-center hover:bg-[#162d56] transition-colors disabled:opacity-40 disabled:cursor-not-allowed flex-shrink-0"
        >
          <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
          </svg>
        </button>
      </div>
      <p className="text-center text-xs text-gray-400 mt-2">
        ✦ BankWise AI can make suggestions. Verify important information.
      </p>
    </div>
  );
};
