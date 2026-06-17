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
}

const NavItem: React.FC<{ icon: React.ReactNode; label: string; badge?: number; active?: boolean }> = ({
  icon, label, badge, active
}) => (
  <button className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm font-medium transition-colors text-left ${
    active ? 'bg-gray-100 text-gray-900' : 'text-gray-500 hover:bg-gray-50 hover:text-gray-700'
  }`}>
    <span className="text-gray-400">{icon}</span>
    <span className="flex-1">{label}</span>
    {badge !== undefined && (
      <span className="bg-gray-200 text-gray-600 text-xs font-semibold rounded-full w-5 h-5 flex items-center justify-center">
        {badge}
      </span>
    )}
  </button>
);

export const Sidebar: React.FC<SidebarProps> = ({
  interestRates, loanTypes, onNewApplication,
  isAuthenticated, userName, onLoginClick, onLogoutClick,
}) => (
  <aside className="w-72 flex-shrink-0 bg-white border-r border-gray-100 flex flex-col h-full">
    {/* Logo */}
    <div className="flex items-center gap-3 px-5 py-5 border-b border-gray-100">
      <div className="w-9 h-9 rounded-xl bg-[#1e3a6e] flex items-center justify-center">
        <span className="text-white font-bold text-sm">N</span>
      </div>
      <div>
        <p className="text-sm font-bold text-gray-900">National Bank</p>
        <p className="text-xs text-gray-400">Loan Assistant</p>
      </div>
    </div>

    {/* Nav */}
    <div className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
      {/* New Application CTA */}
      <button
        onClick={onNewApplication}
        className="w-full flex items-center gap-2 px-4 py-3 rounded-xl bg-gray-100 hover:bg-gray-200 text-sm font-semibold text-gray-700 transition-colors mb-3"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
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
      <div className="pt-3">
        <InterestRateCard rates={interestRates} loanTypes={loanTypes} />
      </div>
    </div>

    {/* Sign In / Sign Out — reflects real auth state */}
    <div className="p-4 border-t border-gray-100">
      {isAuthenticated ? (
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-[#1e3a6e] flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
            {userName?.charAt(0) ?? '?'}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-gray-900 truncate">{userName}</p>
            <p className="text-xs text-green-600">● Signed in</p>
          </div>
          <button
            onClick={onLogoutClick}
            className="text-xs text-gray-400 hover:text-gray-600 font-medium"
          >
            Sign out
          </button>
        </div>
      ) : (
        <button
          onClick={onLoginClick}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl border border-gray-200 text-sm font-medium text-gray-600 hover:bg-gray-50 transition-colors"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
          </svg>
          Sign In
        </button>
      )}
    </div>
  </aside>
);
