import React, { useState } from 'react';
import type { InterestRate, LoanType } from '../../types';

interface InterestRateCardProps {
  rates: InterestRate[];
  loanTypes: LoanType[];
}

const TrendIcon: React.FC<{ trend: 'down' | 'flat' | 'up' }> = ({ trend }) => {
  if (trend === 'down')
    return <svg className="w-4 h-4 text-emerald-500 dark:text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}><path strokeLinecap="round" strokeLinejoin="round" d="M17 7l-10 10M7 7v10h10" /></svg>;
  if (trend === 'up')
    return <svg className="w-4 h-4 text-rose-500 dark:text-rose-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}><path strokeLinecap="round" strokeLinejoin="round" d="M7 17L17 7M7 7h10v10" /></svg>;
  return <span className="text-gray-300 dark:text-gray-600 text-sm font-extrabold">—</span>;
};

export const InterestRateCard: React.FC<InterestRateCardProps> = ({ rates, loanTypes }) => {
  const [activeLoan, setActiveLoan] = useState(loanTypes[0]?.id);
  const [open, setOpen] = useState(true);

  return (
    <div className="bg-white dark:bg-[#10141f] rounded-2xl border border-gray-100 dark:border-gray-800 shadow-sm overflow-hidden hover:shadow-md transition-shadow">
      <button
        className="w-full flex items-center justify-between px-5 py-4 hover:bg-gray-50/50 dark:hover:bg-gray-800/40 transition-colors"
        onClick={() => setOpen(o => !o)}
      >
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-gray-50 dark:bg-gray-800 flex items-center justify-center border border-gray-100 dark:border-gray-700">
            <span className="text-[#1e3a6e] dark:text-blue-300 font-extrabold text-base">%</span>
          </div>
          <span className="text-sm font-semibold text-gray-700 dark:text-gray-200">Interest Rates</span>
        </div>
        <svg
          className={`w-4 h-4 text-gray-400 dark:text-gray-500 transition-transform duration-350 ${open ? 'rotate-180' : ''}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div className="px-5 pb-5 animate-fade-in">
          {/* Loan type tabs */}
          <div className="flex gap-1.5 mb-4 bg-gray-50 dark:bg-gray-800/60 p-1 rounded-xl border border-gray-100 dark:border-gray-700">
            {loanTypes.map(lt => (
              <button
                key={lt.id}
                onClick={() => setActiveLoan(lt.id)}
                className={`flex-1 py-1.5 rounded-lg text-xs font-bold transition-all ${
                  activeLoan === lt.id
                    ? 'bg-white dark:bg-gray-900 text-[#1e3a6e] dark:text-blue-300 shadow-sm border border-gray-100/50 dark:border-gray-700'
                    : 'text-gray-400 dark:text-gray-500 hover:text-gray-750 dark:hover:text-gray-300'
                }`}
              >
                {lt.label}
              </button>
            ))}
          </div>

          {/* Rates list */}
          <div className="space-y-3.5">
            {rates.map((rate, i) => (
              <div key={i} className="flex items-center justify-between py-2 border-b border-gray-50 dark:border-gray-800 last:border-0">
                <div>
                  <p className="text-sm font-bold text-gray-800 dark:text-gray-200 tracking-tight">{rate.range}</p>
                  <p className="text-[11px] font-semibold text-gray-400 dark:text-gray-500">{rate.tenure}</p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-base font-extrabold text-[#1e3a6e] dark:text-blue-300 tracking-tight">{rate.rate}</span>
                  <TrendIcon trend={rate.trend} />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
