import React, { useRef, useEffect, useState } from 'react';
import type { Message } from '../../types';
import { uploadSaleDeed } from '../../services/api';

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
          : 'bg-white/80 dark:bg-[#161b29]/90 border border-gray-100 dark:border-gray-800 text-gray-800 dark:text-gray-100 rounded-tl-none shadow-sm'
      }`}
    >
      {message.content}
    </div>
  </div>
);

interface ExtractedSaleDeedFields {
  registration_number?: string | null;
  owner_name?: string | null;
  owner_pan?: string | null;
  address?: string | null;
  area_sqft?: number | string | null;
  property_type?: string | null;
}

const SaleDeedUploadCard: React.FC<{
  sessionId: string;
  token: string | null;
  customerId: string | null;
  onConfirm: (propertyDataMessage: string) => void;
}> = ({ sessionId, token, customerId, onConfirm }) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<'idle' | 'uploading' | 'extracted' | 'error'>('idle');
  const [fields, setFields] = useState<ExtractedSaleDeedFields | null>(null);
  const [errorMsg, setErrorMsg] = useState('');

  const canConfirm = !!fields?.registration_number && !!fields?.owner_name;

  const handleUpload = async () => {
    if (!file || !token) return;
    setStatus('uploading');
    setErrorMsg('');
    try {
      const data: any = await uploadSaleDeed(file, sessionId, token, customerId ?? '');
      if (data?.success) {
        setFields(data.extracted_fields);
        setStatus('extracted');
      } else {
        setErrorMsg(data?.message || 'Could not extract details from this document.');
        setStatus('error');
      }
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : 'Upload failed.');
      setStatus('error');
    }
  };

  const handleConfirm = () => {
    if (!fields || !canConfirm) return;
    const payload = {
      registration_number: fields.registration_number,
      owner_name: fields.owner_name,
      owner_pan: fields.owner_pan,
      address: fields.address,
      area_sqft: fields.area_sqft,
    };
    onConfirm(`PROPERTY_DATA: ${JSON.stringify(payload)}`);
  };

  return (
    <div className="bg-white dark:bg-[#10141f] border border-gray-150 dark:border-gray-800 rounded-2xl p-5 shadow-sm max-w-md animate-fade-in">
      <h3 className="text-sm font-bold text-gray-800 dark:text-gray-100 mb-1">Upload Your Sale Deed</h3>
      <p className="text-xs text-gray-400 dark:text-gray-500 mb-4">AI will extract details automatically</p>

      {status !== 'extracted' && (
        <div
          onClick={() => status !== 'uploading' && inputRef.current?.click()}
          className={`border-2 border-dashed rounded-xl p-5 text-center cursor-pointer transition-colors ${
            status === 'error'
              ? 'border-red-300 dark:border-red-500/50'
              : 'border-gray-200 dark:border-gray-700 hover:border-[#1e3a6e] dark:hover:border-blue-400'
          }`}
        >
          <input
            ref={inputRef}
            type="file"
            hidden
            accept=".pdf,.jpg,.jpeg,.png"
            onChange={e => e.target.files?.[0] && setFile(e.target.files[0])}
          />
          {status === 'uploading' ? (
            <p className="text-xs font-semibold text-[#1e3a6e] dark:text-blue-300">Extracting details with AI...</p>
          ) : file ? (
            <p className="text-xs font-semibold text-gray-700 dark:text-gray-200">{file.name}</p>
          ) : (
            <p className="text-xs font-medium text-gray-400 dark:text-gray-500">Click to upload (PDF, JPG, PNG)</p>
          )}
        </div>
      )}

      {status === 'error' && (
        <p className="text-xs text-red-500 dark:text-red-400 mt-2">{errorMsg}</p>
      )}

      {status !== 'extracted' && status !== 'uploading' && file && (
        <button
          onClick={handleUpload}
          className="w-full mt-3 bg-gradient-to-tr from-[#1e3a6e] to-[#3b82f6] hover:brightness-110 active:scale-[0.98] text-white text-xs font-bold py-2.5 rounded-xl transition-all shadow-sm shadow-blue-500/10"
        >
          Upload &amp; Extract
        </button>
      )}

      {status === 'extracted' && fields && (
        <div className="space-y-3 animate-fade-in">
          <div className="space-y-2 text-xs">
            <div className="flex justify-between gap-3 border-b border-gray-100 dark:border-gray-800 pb-1.5">
              <span className="text-gray-400 dark:text-gray-500 flex-shrink-0">Registration Number</span>
              <span className="font-semibold text-gray-800 dark:text-gray-100 text-right">{fields.registration_number || '—'}</span>
            </div>
            <div className="flex justify-between gap-3 border-b border-gray-100 dark:border-gray-800 pb-1.5">
              <span className="text-gray-400 dark:text-gray-500 flex-shrink-0">Owner Name</span>
              <span className="font-semibold text-gray-800 dark:text-gray-100 text-right">{fields.owner_name || '—'}</span>
            </div>
            <div className="flex justify-between gap-3 border-b border-gray-100 dark:border-gray-800 pb-1.5">
              <span className="text-gray-400 dark:text-gray-500 flex-shrink-0">Address</span>
              <span className="font-semibold text-gray-800 dark:text-gray-100 text-right">{fields.address || '—'}</span>
            </div>
            <div className="flex justify-between gap-3">
              <span className="text-gray-400 dark:text-gray-500 flex-shrink-0">Area (sqft)</span>
              <span className="font-semibold text-gray-800 dark:text-gray-100 text-right">{fields.area_sqft || '—'}</span>
            </div>
          </div>
          {!canConfirm && (
            <p className="text-xs text-red-500 dark:text-red-400">
              Could not extract required fields. Please upload a clearer document.
            </p>
          )}
          <button
            onClick={handleConfirm}
            disabled={!canConfirm}
            className="w-full bg-gradient-to-tr from-[#1e3a6e] to-[#3b82f6] hover:brightness-110 active:scale-[0.98] text-white text-xs font-bold py-2.5 rounded-xl transition-all shadow-sm shadow-blue-500/10 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:brightness-100 disabled:active:scale-100"
          >
            Confirm &amp; Proceed
          </button>
        </div>
      )}
    </div>
  );
};

interface ChatWindowProps {
  messages: Message[];
  isTyping: boolean;
  onWelcomeOption: (opt: string) => void;
  sessionId: string;
  token: string | null;
  customerId: string | null;
}

export const ChatWindow: React.FC<ChatWindowProps> = ({ messages, isTyping, onWelcomeOption, sessionId, token, customerId }) => {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  if (messages.length === 0 && !isTyping) {
    return (
      <div className="flex-1 flex flex-col justify-center items-center overflow-hidden px-6 relative bg-gradient-to-br from-[#eef2ff] via-[#f5f3ff] to-[#e0f2fe] dark:from-[#0a0e1f] dark:via-[#111530] dark:to-[#0a1422]">
        {/* Ambient glow decorative blobs */}
        <div className="absolute top-1/4 left-1/4 w-72 h-72 bg-blue-200/40 dark:bg-blue-500/10 rounded-full blur-3xl -z-10 pointer-events-none" />
        <div className="absolute bottom-1/4 right-1/4 w-80 h-80 bg-indigo-200/40 dark:bg-indigo-500/10 rounded-full blur-3xl -z-10 pointer-events-none" />

        <div className="w-full max-w-xl flex flex-col items-center text-center animate-slide-up">
          {/* Logo B container */}
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-[#1e3a6e] to-[#3b82f6] flex items-center justify-center shadow-xl shadow-blue-500/20 mb-6 hover:rotate-6 hover:scale-105 transition-transform duration-300">
            <span className="text-white text-3xl font-black">B</span>
          </div>

          <h1 className="text-4xl font-extrabold text-gray-900 dark:text-gray-50 tracking-tight mb-3">
            Welcome to BankWise AI
          </h1>

          <p className="text-sm text-gray-500 dark:text-gray-400 max-w-md leading-relaxed mb-10 font-medium">
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
                className="bg-white/80 dark:bg-[#10141f]/90 border border-gray-200/80 dark:border-gray-800 rounded-2xl p-6 text-left hover:border-[#1e3a6e] dark:hover:border-blue-400 hover:shadow-lg hover:-translate-y-1 active:scale-[0.98] transition-all duration-300 group shadow-sm flex flex-col justify-between"
              >
                <div>
                  <p className="text-base font-bold text-gray-800 dark:text-gray-100 group-hover:text-[#1e3a6e] dark:group-hover:text-blue-300 transition-colors mb-1">
                    {opt.label}
                  </p>
                  <p className="text-xs text-gray-400 dark:text-gray-500 font-medium leading-normal">
                    {opt.desc}
                  </p>
                </div>
                <div className="mt-5 flex items-center gap-1.5 text-xs font-semibold text-[#1e3a6e] dark:text-blue-300 opacity-0 group-hover:opacity-100 transition-opacity">
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
    <div className="flex-1 overflow-y-auto px-6 py-6 space-y-4 bg-gradient-to-br from-[#eef2ff] via-[#f5f3ff] to-[#e0f2fe] dark:from-[#0a0e1f] dark:via-[#111530] dark:to-[#0a1422]">
      {messages.map((msg) => {
        // The Sale Deed confirm-and-proceed payload is an internal signal
        // to the backend, not something the user should see as a chat bubble.
        if (msg.role === 'user' && msg.content.startsWith('PROPERTY_DATA:')) {
          return null;
        }
        return (
        <div key={msg.id} className="space-y-2">
          <MessageBubble message={msg} />
          
          {/* Render options if this is an assistant message and has options */}
          {msg.role === 'assistant' && msg.options && msg.options.length > 0 && (
            <div className="pl-11 flex flex-wrap gap-2 animate-fade-in">
              {msg.options.map((opt: any) => (
                <button
                  key={opt.id || opt.label}
                  onClick={() => onWelcomeOption(opt.label)}
                  className="bg-white/90 dark:bg-[#10141f] border border-gray-200 dark:border-gray-700 text-xs font-bold text-[#1e3a6e] dark:text-blue-300 px-4 py-2 rounded-xl hover:border-[#1e3a6e] dark:hover:border-blue-400 hover:bg-[#1e3a6e]/5 dark:hover:bg-blue-400/10 hover:shadow-sm active:scale-95 transition-all duration-200 shadow-sm"
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
                  className="bg-white dark:bg-[#10141f] border border-gray-150 dark:border-gray-800 rounded-2xl p-5 hover:shadow-lg transition-all duration-300 transform hover:-translate-y-0.5 flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-[10px] font-extrabold text-[#1e3a6e] dark:text-blue-300 bg-[#1e3a6e]/10 dark:bg-blue-400/10 px-2 py-0.5 rounded-md uppercase tracking-wider">
                        {prop.property_id}
                      </span>
                      <span className="text-xs font-semibold text-gray-400 dark:text-gray-500">
                        {prop.city}
                      </span>
                    </div>
                    <h3 className="text-sm font-bold text-gray-800 dark:text-gray-100 line-clamp-2 mb-2">
                      {prop.address}
                    </h3>
                    <div className="flex items-center gap-4 text-xs text-gray-500 dark:text-gray-400 font-medium mb-3">
                      <span className="flex items-center gap-1">
                        🏠 {prop.area_sqft} sqft
                      </span>
                      <span className="flex items-center gap-1">
                        🛏️ {prop.bedrooms} BHK
                      </span>
                    </div>
                    {(prop.crime_rate || prop.transit || (prop.nearby_schools && prop.nearby_schools.length > 0) || (prop.hospitals && prop.hospitals.length > 0)) && (
                      <div className="mt-3 pt-3 border-t border-gray-100/70 dark:border-gray-800 space-y-1.5 text-xs text-gray-600 dark:text-gray-400 font-medium">
                        {prop.crime_rate && (
                          <div className="flex items-start gap-1.5">
                            <span className="text-gray-400 dark:text-gray-500 flex-shrink-0" title="Crime Rate">🛡️</span>
                            <span className="text-[11px] leading-snug"><strong className="text-gray-700 dark:text-gray-200 font-semibold font-bold">Crime:</strong> {prop.crime_rate}</span>
                          </div>
                        )}
                        {prop.transit && (
                          <div className="flex items-start gap-1.5">
                            <span className="text-gray-400 dark:text-gray-500 flex-shrink-0" title="Transit (Metro/Bus/Train)">🚇</span>
                            <span className="text-[11px] leading-snug">
                              <strong className="text-gray-700 dark:text-gray-200 font-semibold font-bold">Transit:</strong> Metro ({prop.transit.metro}) | Bus ({prop.transit.bus}) | Train ({prop.transit.train})
                            </span>
                          </div>
                        )}
                        {prop.nearby_schools && prop.nearby_schools.length > 0 && (
                          <div className="flex items-start gap-1.5">
                            <span className="text-gray-400 dark:text-gray-500 flex-shrink-0" title="Nearby Schools">🏫</span>
                            <span className="text-[11px] leading-snug">
                              <strong className="text-gray-700 dark:text-gray-200 font-semibold font-bold">Schools:</strong> {prop.nearby_schools.join(', ')}
                            </span>
                          </div>
                        )}
                        {prop.hospitals && prop.hospitals.length > 0 && (
                          <div className="flex items-start gap-1.5">
                            <span className="text-gray-400 dark:text-gray-500 flex-shrink-0" title="Hospitals">🏥</span>
                            <span className="text-[11px] leading-snug">
                              <strong className="text-gray-700 dark:text-gray-200 font-semibold font-bold">Hospitals:</strong> {prop.hospitals.join(', ')}
                            </span>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                  <div className="border-t border-gray-100 dark:border-gray-800 pt-3 flex items-center justify-between mt-3">
                    <div>
                      <p className="text-[10px] font-bold text-gray-400 dark:text-gray-500 uppercase leading-none">Price</p>
                      <p className="text-sm font-black text-gray-900 dark:text-gray-50 mt-1">
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

          {/* Sale Deed upload card — OCR extracts fields, user confirms to trigger property verification */}
          {msg.role === 'assistant' && msg.type === 'property_document_upload' && (
            <div className="pl-11 animate-fade-in">
              <SaleDeedUploadCard
                sessionId={sessionId}
                token={token}
                customerId={customerId}
                onConfirm={onWelcomeOption}
              />
            </div>
          )}
        </div>
        );
      })}
      {isTyping && (
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-[#1e3a6e] to-[#3b82f6] flex items-center justify-center flex-shrink-0 shadow-sm">
            <span className="text-white text-xs font-black">B</span>
          </div>
          <div className="bg-white/80 dark:bg-[#161b29]/90 rounded-2xl rounded-tl-none px-4 py-3 border border-gray-100 dark:border-gray-800 flex gap-1.5 items-center shadow-sm">
            {[0, 1, 2].map(i => (
              <span
                key={i}
                className="w-1.5 h-1.5 bg-gray-400 dark:bg-gray-500 rounded-full animate-bounce"
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
