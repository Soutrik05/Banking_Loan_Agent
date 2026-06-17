import React, { useState } from 'react';
import type { InterestRate, LoanType } from '../../types';

interface InterestRateCardProps {
  rates: InterestRate[];
  loanTypes: LoanType[];
}

const TrendIcon: React.FC<{ trend: 'down' | 'flat' | 'up' }> = ({ trend }) => {
  if (trend === 'down')
    return <svg className="w-4 h-4 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M17 7l-10 10M7 7v10h10" /></svg>;
  if (trend === 'up')
    return <svg className="w-4 h-4 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M7 17L17 7M7 7h10v10" /></svg>;
  return <span className="text-gray-400 text-sm font-bold">—</span>;
};

export const InterestRateCard: React.FC<InterestRateCardProps> = ({ rates, loanTypes }) => {
  const [activeLoan, setActiveLoan] = useState(loanTypes[0]?.id);
  const [open, setOpen] = useState(true);

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
      <button
        className="w-full flex items-center justify-between px-5 py-4 hover:bg-gray-50 transition-colors"
        onClick={() => setOpen(o => !o)}
      >
        <div className="flex items-center gap-2">
          <span className="text-[#1e3a6e] font-bold text-base">%</span>
          <span className="text-sm font-semibold text-gray-700">Interest Rates</span>
        </div>
        <svg
          className={`w-4 h-4 text-gray-400 transition-transform ${open ? 'rotate-180' : ''}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div className="px-5 pb-5">
          {/* Loan type tabs */}
          <div className="flex gap-2 mb-4">
            {loanTypes.map(lt => (
              <button
                key={lt.id}
                onClick={() => setActiveLoan(lt.id)}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                  activeLoan === lt.id
                    ? 'bg-[#1e3a6e] text-white'
                    : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
                }`}
              >
                {lt.label}
              </button>
            ))}
          </div>

          {/* Rates list */}
          <div className="space-y-3">
            {rates.map((rate, i) => (
              <div key={i} className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
                <div>
                  <p className="text-sm font-medium text-gray-800">{rate.range}</p>
                  <p className="text-xs text-gray-400">{rate.tenure}</p>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="text-base font-bold text-[#1e3a6e]">{rate.rate}</span>
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
