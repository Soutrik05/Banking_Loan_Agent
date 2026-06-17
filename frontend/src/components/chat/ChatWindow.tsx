import React, { useRef, useEffect } from 'react';
import type { Message } from '../../types';

interface WelcomeScreenProps {
  onOption: (opt: string) => void;
}

const WelcomeScreen: React.FC<WelcomeScreenProps> = ({ onOption }) => (
  <div className="flex flex-col items-center justify-center h-full text-center px-6 gap-6">
    <div className="w-16 h-16 rounded-2xl bg-[#1e3a6e] flex items-center justify-center shadow-lg">
      <span className="text-white text-2xl font-bold">B</span>
    </div>
    <div>
      <h2 className="text-2xl font-bold text-gray-900 mb-2">Welcome to BankWise AI</h2>
      <p className="text-gray-500 text-sm max-w-sm leading-relaxed">
        Your intelligent loan assistant. I can help you with loan applications, property verification, eligibility checks, and more.
      </p>
    </div>
    <div className="grid grid-cols-3 gap-3 w-full max-w-lg">
      {[
        { label: 'New Customer', desc: 'Start fresh application' },
        { label: 'Existing Customer', desc: 'Login and continue' },
        { label: 'Just Browsing', desc: 'Explore our services' },
      ].map(opt => (
        <button
          key={opt.label}
          onClick={() => onOption(opt.label)}
          className="bg-white border border-gray-200 rounded-xl p-4 text-left hover:border-[#1e3a6e] hover:shadow-md transition-all group"
        >
          <p className="text-sm font-semibold text-gray-800 group-hover:text-[#1e3a6e] mb-1">{opt.label}</p>
          <p className="text-xs text-gray-400">{opt.desc}</p>
        </button>
      ))}
    </div>
  </div>
);

interface MessageBubbleProps {
  message: Message;
}

const MessageBubble: React.FC<MessageBubbleProps> = ({ message }) => (
  <div className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
    {message.role === 'assistant' && (
      <div className="w-7 h-7 rounded-lg bg-[#1e3a6e] flex items-center justify-center mr-2 flex-shrink-0 mt-0.5">
        <span className="text-white text-xs font-bold">B</span>
      </div>
    )}
    <div
      className={`max-w-[75%] px-4 py-2.5 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap ${
        message.role === 'user'
          ? 'bg-[#1e3a6e] text-white rounded-tr-sm'
          : 'bg-gray-100 text-gray-800 rounded-tl-sm'
      }`}
    >
      {message.content}
    </div>
  </div>
);

interface ChatWindowProps {
  messages: Message[];
  isTyping: boolean;
  onWelcomeOption: (opt: string) => void;
}

export const ChatWindow: React.FC<ChatWindowProps> = ({ messages, isTyping, onWelcomeOption }) => {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  if (messages.length === 0 && !isTyping) {
    return <WelcomeScreen onOption={onWelcomeOption} />;
  }

  return (
    <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
      {messages.map(msg => <MessageBubble key={msg.id} message={msg} />)}
      {isTyping && (
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-[#1e3a6e] flex items-center justify-center flex-shrink-0">
            <span className="text-white text-xs font-bold">B</span>
          </div>
          <div className="bg-gray-100 rounded-2xl rounded-tl-sm px-4 py-2.5 flex gap-1 items-center">
            {[0, 1, 2].map(i => (
              <span
                key={i}
                className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce"
                style={{ animationDelay: `${i * 150}ms` }}
              />
            ))}
          </div>
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  );
};
