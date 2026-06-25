import React, { useState } from 'react';
import type { InterestRate, LoanType, Message } from '../types';
import { InterestRateCard } from './cards/InterestRateCard';
import { useConversations } from '../hooks/useConversations';

interface SidebarProps {
  interestRates: InterestRate[];
  loanTypes: LoanType[];
  onNewApplication: () => void;
  isAuthenticated: boolean;
  userName: string | null;
  onLoginClick: () => void;
  onLogoutClick: () => void;
  accountNumbers?: string[];
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
  token: string | null;
  customerId: string | null;
  onLoadConversation: (messages: Message[], conversationId: string, sessionId: string | null) => void;
}

function formatConversationDate(iso: string): string {
  const date = new Date(iso);
  const now = new Date();
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  const sameDay = (a: Date, b: Date) => a.toDateString() === b.toDateString();
  if (sameDay(date, now)) return 'Today';
  if (sameDay(date, yesterday)) return 'Yesterday';
  return date.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' });
}

const ApplicationHistorySection: React.FC<{
  isAuthenticated: boolean;
  token: string | null;
  customerId: string | null;
  onLoadConversation: (messages: Message[], conversationId: string, sessionId: string | null) => void;
}> = ({ isAuthenticated, token, customerId, onLoadConversation }) => {
  const [open, setOpen] = useState(false);
  const { conversations, activeConversationId, loadConversation } = useConversations(token, customerId);

  const handleSelect = async (id: string) => {
    const { messages, sessionId } = await loadConversation(id);
    onLoadConversation(messages, id, sessionId);
  };

  return (
    <div>
      <button
        onClick={() => setOpen(o => !o)}
        className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm font-semibold transition-all text-left group ${
          open ? 'bg-[#1e3a6e]/10 text-[#1e3a6e] dark:bg-blue-400/10 dark:text-blue-300' : 'text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800/50 hover:text-gray-950 dark:hover:text-gray-100'
        }`}
      >
        <span className={`transition-colors duration-200 ${open ? 'text-[#1e3a6e] dark:text-blue-300' : 'text-gray-400 dark:text-gray-500 group-hover:text-gray-650 dark:group-hover:text-gray-200'}`}>
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
        </span>
        <span className="flex-1">Application History</span>
        {isAuthenticated && (
          <svg
            className={`w-3.5 h-3.5 text-gray-400 dark:text-gray-500 transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
            fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        )}
      </button>

      {open && isAuthenticated && (
        <div className="mt-1 ml-4 pl-3 border-l border-gray-100 dark:border-gray-800 space-y-0.5 animate-fade-in">
          {conversations.length === 0 && (
            <p className="text-xs text-gray-400 dark:text-gray-500 px-3 py-2">No past applications yet.</p>
          )}
          {conversations.map(conv => (
            <button
              key={conv.id}
              onClick={() => handleSelect(conv.id)}
              className={`w-full text-left px-3 py-2 rounded-lg transition-colors ${
                activeConversationId === conv.id
                  ? 'bg-[#1e3a6e]/10 text-[#1e3a6e] dark:bg-blue-400/10 dark:text-blue-300'
                  : 'text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800/50'
              }`}
            >
              <span className="block text-xs font-semibold truncate">{conv.title}</span>
              <span className="block text-[10px] font-medium text-gray-400 dark:text-gray-500 mt-0.5">
                {formatConversationDate(conv.updated_at)}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

const NavItem: React.FC<{ icon: React.ReactNode; label: string; badge?: number; active?: boolean }> = ({
  icon, label, badge, active
}) => (
  <button className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm font-semibold transition-all text-left group ${
    active ? 'bg-[#1e3a6e]/10 text-[#1e3a6e] dark:bg-blue-400/10 dark:text-blue-300' : 'text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800/50 hover:text-gray-950 dark:hover:text-gray-100'
  }`}>
    <span className={`transition-colors duration-200 ${active ? 'text-[#1e3a6e] dark:text-blue-300' : 'text-gray-400 dark:text-gray-500 group-hover:text-gray-650 dark:group-hover:text-gray-200'}`}>{icon}</span>
    <span className="flex-1">{label}</span>
    {badge !== undefined && (
      <span className="bg-[#1e3a6e]/10 text-[#1e3a6e] text-xs font-bold rounded-full w-5 h-5 flex items-center justify-center">
        {badge}
      </span>
    )}
  </button>
);

export const Sidebar: React.FC<SidebarProps> = ({
  interestRates, loanTypes, onNewApplication,
  isAuthenticated, userName, onLoginClick, onLogoutClick, accountNumbers,
  theme, onToggleTheme, token, customerId, onLoadConversation,
}) => (
  <aside className="w-72 flex-shrink-0 bg-[#fbfcfd] dark:bg-[#0b0f1a] border-r border-gray-150/70 dark:border-gray-800/70 flex flex-col h-full">
    {/* Logo */}
    <div className="flex items-center gap-3 px-6 py-6 border-b border-gray-100 dark:border-gray-800">
      <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-[#1e3a6e] to-[#3b82f6] flex items-center justify-center shadow-md shadow-blue-500/10">
        <span className="text-white font-black text-base">N</span>
      </div>
      <div className="flex-1">
        <p className="text-sm font-extrabold text-gray-900 dark:text-gray-50 tracking-tight leading-none mb-1">National Bank</p>
        <p className="text-xs font-semibold text-gray-400 dark:text-gray-500">Loan Assistant</p>
      </div>
      <button
        onClick={onToggleTheme}
        title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
        className="w-9 h-9 flex-shrink-0 rounded-xl flex items-center justify-center border border-gray-200 dark:border-gray-700 text-gray-500 dark:text-amber-300 hover:bg-gray-50 dark:hover:bg-gray-800/60 transition-colors"
      >
        {theme === 'dark' ? (
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.36 6.36l-.7-.7M6.34 6.34l-.7-.7m12.02 0l-.7.7M6.34 17.66l-.7.7M12 7a5 5 0 100 10 5 5 0 000-10z" />
          </svg>
        ) : (
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z" />
          </svg>
        )}
      </button>
    </div>

    {/* Nav */}
    <div className="flex-1 overflow-y-auto px-4 py-6 space-y-1">
      {/* New Application CTA */}
      <button
        onClick={onNewApplication}
        className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-gradient-to-tr from-[#1e3a6e] to-[#254f96] hover:shadow-lg hover:shadow-blue-500/10 hover:brightness-110 active:scale-[0.98] text-sm font-bold text-white transition-all mb-4"
      >
        <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
        </svg>
        New Application
      </button>

      <ApplicationHistorySection
        isAuthenticated={isAuthenticated}
        token={token}
        customerId={customerId}
        onLoadConversation={onLoadConversation}
      />
      <NavItem
        icon={<svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><circle cx="12" cy="12" r="10" /><path strokeLinecap="round" d="M12 16v-4M12 8h.01" /></svg>}
        label="FAQ Section"
      />
      <NavItem
        icon={<svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>}
        label="Saved Drafts"
      />

      {/* Interest Rates */}
      <div className="pt-5">
        <InterestRateCard rates={interestRates} loanTypes={loanTypes} />
      </div>

      {/* Linked Accounts */}
      {isAuthenticated && accountNumbers && accountNumbers.length > 0 && (
        <div className="pt-4 border-t border-gray-100 dark:border-gray-800 mt-4">
          <p className="text-[10px] font-extrabold text-[#1e3a6e] dark:text-blue-300 uppercase tracking-wider mb-2.5 px-2">
            Linked Accounts
          </p>
          <div className="space-y-2">
            {accountNumbers.map((acc) => {
              const isFD = acc.startsWith('FD');
              const label = isFD ? 'Fixed Deposit' : 'Savings Account';
              const bg = isFD ? 'from-purple-500/5 to-indigo-500/5 border-purple-100/50 dark:from-purple-400/10 dark:to-indigo-400/10 dark:border-purple-400/20' : 'from-blue-500/5 to-teal-500/5 border-blue-100/50 dark:from-blue-400/10 dark:to-teal-400/10 dark:border-blue-400/20';
              const text = isFD ? 'text-purple-700 dark:text-purple-300' : 'text-blue-700 dark:text-blue-300';
              return (
                <div
                  key={acc}
                  className={`bg-gradient-to-tr ${bg} border p-3 rounded-xl shadow-sm hover:scale-[1.02] transition-transform duration-200`}
                >
                  <div className="flex items-center justify-between">
                    <span className={`text-[10px] font-bold ${text} uppercase tracking-wide`}>
                      {label}
                    </span>
                    <span className="text-[9px] text-[#00b894] font-bold flex items-center gap-1">
                      <span className="w-1 h-1 rounded-full bg-[#00b894] animate-ping" />
                      Active
                    </span>
                  </div>
                  <p className="text-xs font-mono font-bold text-gray-800 dark:text-gray-200 mt-1">
                    {acc}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>

    {/* Sign In / Sign Out — reflects real auth state */}
    <div className="p-4 border-t border-gray-100 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-900/40">
      {isAuthenticated ? (
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-[#1e3a6e] to-[#3b82f6] flex items-center justify-center text-white text-xs font-bold flex-shrink-0 shadow-sm">
            {userName?.charAt(0) ?? '?'}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-gray-900 dark:text-gray-100 truncate">{userName}</p>
            <p className="text-[10px] font-bold text-emerald-600 dark:text-emerald-400 flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              Signed in
            </p>
          </div>
          <button
            onClick={onLogoutClick}
            className="text-xs text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 font-bold transition-colors"
          >
            Sign out
          </button>
        </div>
      ) : (
        <button
          onClick={onLoginClick}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl border border-gray-200 dark:border-gray-700 text-sm font-bold text-gray-650 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-800 active:scale-[0.98] transition-all bg-white dark:bg-gray-900 shadow-sm"
        >
          <svg className="w-4 h-4 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
          </svg>
          Sign In
        </button>
      )}
    </div>
  </aside>
);
