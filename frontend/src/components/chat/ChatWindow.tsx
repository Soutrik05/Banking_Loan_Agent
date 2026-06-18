import React, { useRef, useEffect } from 'react';
import type { Message } from '../../types';

interface MessageBubbleProps {
  message: Message;
}

const MessageBubble: React.FC<MessageBubbleProps> = ({ message }) => (
  <div className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'} animate-fade-in`}>
    {message.role === 'assistant' && (
      <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-[#1e3a6e] to-[#3b82f6] shadow-md shadow-blue-500/10 flex items-center justify-center mr-3 flex-shrink-0 mt-0.5">
        <span className="text-white text-xs font-black">B</span>
      </div>
    )}
    <div
      className={`max-w-[72%] px-4 py-3 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap transition-all ${
        message.role === 'user'
          ? 'bg-gradient-to-tr from-[#1e3a6e] to-[#254f96] text-white rounded-tr-none shadow-md shadow-blue-900/10'
          : 'bg-[#f3f4f6]/90 border border-gray-100 text-gray-800 rounded-tl-none shadow-sm'
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
    return (
      <div className="flex-1 flex flex-col justify-center items-center overflow-hidden px-6 relative bg-gradient-to-b from-[#f8f9fb] to-white">
        {/* Ambient glow decorative blobs */}
        <div className="absolute top-1/4 left-1/4 w-72 h-72 bg-blue-100/30 rounded-full blur-3xl -z-10 pointer-events-none" />
        <div className="absolute bottom-1/4 right-1/4 w-80 h-80 bg-indigo-100/30 rounded-full blur-3xl -z-10 pointer-events-none" />

        <div className="w-full max-w-xl flex flex-col items-center text-center animate-slide-up">
          {/* Logo B container */}
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-[#1e3a6e] to-[#3b82f6] flex items-center justify-center shadow-xl shadow-blue-500/20 mb-6 hover:rotate-6 hover:scale-105 transition-transform duration-300">
            <span className="text-white text-3xl font-black">B</span>
          </div>

          <h1 className="text-4xl font-extrabold text-gray-900 tracking-tight mb-3">
            Welcome to BankWise AI
          </h1>
          
          <p className="text-sm text-gray-500 max-w-md leading-relaxed mb-10 font-medium">
            Your intelligent loan assistant. I can help you with loan applications, property verification, eligibility checks, and more.
          </p>

          <div className="grid grid-cols-2 gap-4 w-full">
            {[
              { label: 'Existing Customer', desc: 'Login and continue application' },
              { label: 'Just Browsing', desc: 'Explore rates & services' },
            ].map(opt => (
              <button
                key={opt.label}
                onClick={() => onWelcomeOption(opt.label)}
                className="bg-white border border-gray-200/80 rounded-2xl p-6 text-left hover:border-[#1e3a6e] hover:shadow-lg hover:-translate-y-1 active:scale-[0.98] transition-all duration-300 group shadow-sm flex flex-col justify-between"
              >
                <div>
                  <p className="text-base font-bold text-gray-800 group-hover:text-[#1e3a6e] transition-colors mb-1">
                    {opt.label}
                  </p>
                  <p className="text-xs text-gray-400 font-medium leading-normal">
                    {opt.desc}
                  </p>
                </div>
                <div className="mt-5 flex items-center gap-1.5 text-xs font-semibold text-[#1e3a6e] opacity-0 group-hover:opacity-100 transition-opacity">
                  <span>Get Started</span>
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                  </svg>
                </div>
              </button>
            ))}
          </div>
        </div>
        <div ref={bottomRef} />
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-6 py-6 space-y-4 bg-gradient-to-b from-[#fafbfc] to-white">
      {messages.map((msg) => (
        <div key={msg.id} className="space-y-2">
          <MessageBubble message={msg} />
          
          {/* Render options if this is an assistant message and has options */}
          {msg.role === 'assistant' && msg.options && msg.options.length > 0 && (
            <div className="pl-11 flex flex-wrap gap-2 animate-fade-in">
              {msg.options.map((opt: any) => (
                <button
                  key={opt.id || opt.label}
                  onClick={() => onWelcomeOption(opt.label)}
                  className="bg-white border border-gray-200 text-xs font-bold text-[#1e3a6e] px-4 py-2 rounded-xl hover:border-[#1e3a6e] hover:bg-[#1e3a6e]/5 hover:shadow-sm active:scale-95 transition-all duration-200 shadow-sm"
                >
                  {opt.label}
                </button>
              ))}
            </div>
          )}

          {/* Render property list if this is an assistant message and has properties */}
          {msg.role === 'assistant' && msg.properties && msg.properties.length > 0 && (
            <div className="pl-11 grid grid-cols-1 sm:grid-cols-2 gap-4 w-full animate-fade-in max-w-2xl">
              {msg.properties.map((prop: any) => (
                <div
                  key={prop.property_id}
                  className="bg-white border border-gray-150 rounded-2xl p-5 hover:shadow-lg transition-all duration-300 transform hover:-translate-y-0.5 flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-[10px] font-extrabold text-[#1e3a6e] bg-[#1e3a6e]/10 px-2 py-0.5 rounded-md uppercase tracking-wider">
                        {prop.property_id}
                      </span>
                      <span className="text-xs font-semibold text-gray-400">
                        {prop.city}
                      </span>
                    </div>
                    <h3 className="text-sm font-bold text-gray-800 line-clamp-2 mb-2">
                      {prop.address}
                    </h3>
                    <div className="flex items-center gap-4 text-xs text-gray-500 font-medium mb-3">
                      <span className="flex items-center gap-1">
                        🏠 {prop.area_sqft} sqft
                      </span>
                      <span className="flex items-center gap-1">
                        🛏️ {prop.bedrooms} BHK
                      </span>
                    </div>
                    {(prop.crime_rate || prop.transit || (prop.nearby_schools && prop.nearby_schools.length > 0) || (prop.hospitals && prop.hospitals.length > 0)) && (
                      <div className="mt-3 pt-3 border-t border-gray-100/70 space-y-1.5 text-xs text-gray-600 font-medium">
                        {prop.crime_rate && (
                          <div className="flex items-start gap-1.5">
                            <span className="text-gray-400 flex-shrink-0" title="Crime Rate">🛡️</span>
                            <span className="text-[11px] leading-snug"><strong className="text-gray-700 font-semibold font-bold">Crime:</strong> {prop.crime_rate}</span>
                          </div>
                        )}
                        {prop.transit && (
                          <div className="flex items-start gap-1.5">
                            <span className="text-gray-400 flex-shrink-0" title="Transit (Metro/Bus/Train)">🚇</span>
                            <span className="text-[11px] leading-snug">
                              <strong className="text-gray-700 font-semibold font-bold">Transit:</strong> Metro ({prop.transit.metro}) | Bus ({prop.transit.bus}) | Train ({prop.transit.train})
                            </span>
                          </div>
                        )}
                        {prop.nearby_schools && prop.nearby_schools.length > 0 && (
                          <div className="flex items-start gap-1.5">
                            <span className="text-gray-400 flex-shrink-0" title="Nearby Schools">🏫</span>
                            <span className="text-[11px] leading-snug">
                              <strong className="text-gray-700 font-semibold font-bold">Schools:</strong> {prop.nearby_schools.join(', ')}
                            </span>
                          </div>
                        )}
                        {prop.hospitals && prop.hospitals.length > 0 && (
                          <div className="flex items-start gap-1.5">
                            <span className="text-gray-400 flex-shrink-0" title="Hospitals">🏥</span>
                            <span className="text-[11px] leading-snug">
                              <strong className="text-gray-700 font-semibold font-bold">Hospitals:</strong> {prop.hospitals.join(', ')}
                            </span>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                  <div className="border-t border-gray-100 pt-3 flex items-center justify-between mt-3">
                    <div>
                      <p className="text-[10px] font-bold text-gray-400 uppercase leading-none">Price</p>
                      <p className="text-sm font-black text-gray-900 mt-1">
                        ₹{(prop.listed_price / 100000).toFixed(1)} Lakh
                      </p>
                    </div>
                    <button
                      onClick={() => onWelcomeOption(prop.property_id)}
                      className="bg-gradient-to-tr from-[#1e3a6e] to-[#3b82f6] hover:brightness-110 active:scale-95 text-[11px] font-bold text-white px-3.5 py-2 rounded-xl transition-all shadow-sm shadow-blue-500/10"
                    >
                      Select
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
      {isTyping && (
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-[#1e3a6e] to-[#3b82f6] flex items-center justify-center flex-shrink-0 shadow-sm">
            <span className="text-white text-xs font-black">B</span>
          </div>
          <div className="bg-[#f3f4f6]/90 rounded-2xl rounded-tl-none px-4 py-3 border border-gray-100 flex gap-1.5 items-center shadow-sm">
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
