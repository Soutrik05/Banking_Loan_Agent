import React from 'react';
import type { InterestRate, LoanType } from '../types';
import { InterestRateCard } from './cards/InterestRateCard';

interface SidebarProps {
  interestRates: InterestRate[];
  loanTypes: LoanType[];
  onNewApplication: () => void;
  isAuthenticated: boolean;
  userName: string | null;
  onLoginClick: () => void;
  onLogoutClick: () => void;
  accountNumbers?: string[];
}

const NavItem: React.FC<{ icon: React.ReactNode; label: string; badge?: number; active?: boolean }> = ({
  icon, label, badge, active
}) => (
  <button className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm font-semibold transition-all text-left group ${
    active ? 'bg-[#1e3a6e]/10 text-[#1e3a6e]' : 'text-gray-500 hover:bg-gray-50 hover:text-gray-950'
  }`}>
    <span className={`transition-colors duration-200 ${active ? 'text-[#1e3a6e]' : 'text-gray-400 group-hover:text-gray-650'}`}>{icon}</span>
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
}) => (
  <aside className="w-72 flex-shrink-0 bg-[#fbfcfd] border-r border-gray-150/70 flex flex-col h-full">
    {/* Logo */}
    <div className="flex items-center gap-3 px-6 py-6 border-b border-gray-100">
      <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-[#1e3a6e] to-[#3b82f6] flex items-center justify-center shadow-md shadow-blue-500/10">
        <span className="text-white font-black text-base">N</span>
      </div>
      <div>
        <p className="text-sm font-extrabold text-gray-900 tracking-tight leading-none mb-1">National Bank</p>
        <p className="text-xs font-semibold text-gray-400">Loan Assistant</p>
      </div>
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

      <NavItem
        icon={<svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>}
        label="Application History"
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
        <div className="pt-4 border-t border-gray-100 mt-4">
          <p className="text-[10px] font-extrabold text-[#1e3a6e] uppercase tracking-wider mb-2.5 px-2">
            Linked Accounts
          </p>
          <div className="space-y-2">
            {accountNumbers.map((acc) => {
              const isFD = acc.startsWith('FD');
              const label = isFD ? 'Fixed Deposit' : 'Savings Account';
              const bg = isFD ? 'from-purple-500/5 to-indigo-500/5 border-purple-100/50' : 'from-blue-500/5 to-teal-500/5 border-blue-100/50';
              const text = isFD ? 'text-purple-700' : 'text-blue-700';
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
                  <p className="text-xs font-mono font-bold text-gray-800 mt-1">
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
    <div className="p-4 border-t border-gray-100 bg-gray-50/50">
      {isAuthenticated ? (
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-[#1e3a6e] to-[#3b82f6] flex items-center justify-center text-white text-xs font-bold flex-shrink-0 shadow-sm">
            {userName?.charAt(0) ?? '?'}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-gray-900 truncate">{userName}</p>
            <p className="text-[10px] font-bold text-emerald-600 flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              Signed in
            </p>
          </div>
          <button
            onClick={onLogoutClick}
            className="text-xs text-gray-400 hover:text-gray-600 font-bold transition-colors"
          >
            Sign out
          </button>
        </div>
      ) : (
        <button
          onClick={onLoginClick}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl border border-gray-200 text-sm font-bold text-gray-650 hover:bg-gray-50 active:scale-[0.98] transition-all bg-white shadow-sm"
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
