import React from 'react';
import type { CreditScore } from '../../types';

interface CreditScoreCardProps {
  score: CreditScore;
}

export const CreditScoreCard: React.FC<CreditScoreCardProps> = ({ score }) => {
  const pct = (score.value / score.max) * 100;

  // Dynamic status styling
  let colorClass = 'text-emerald-600';
  let barGradient = 'from-emerald-500 to-teal-500';
  if (score.value < 650) {
    colorClass = 'text-rose-600';
    barGradient = 'from-rose-500 to-pink-500';
  } else if (score.value < 750) {
    colorClass = 'text-amber-600';
    barGradient = 'from-amber-500 to-orange-500';
  }

  return (
    <div className="bg-white rounded-2xl border border-gray-100 p-5 shadow-sm mt-4 hover:shadow-md transition-shadow">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-gray-50 flex items-center justify-center border border-gray-100">
            <svg className="w-4 h-4 text-[#1e3a6e]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <rect x="2" y="5" width="20" height="14" rx="2" strokeWidth={2} />
              <path strokeLinecap="round" d="M2 10h20" strokeWidth={2} />
            </svg>
          </div>
          <span className="text-sm font-semibold text-gray-700">Credit Score</span>
        </div>
        <div className="text-right">
          <span className="text-2xl font-extrabold text-gray-900 tracking-tight">{score.value}</span>
          <span className="text-xs font-bold text-gray-400 ml-1">/ {score.max}</span>
        </div>
      </div>
      
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Status</p>
        <p className={`text-xs font-bold ${colorClass}`}>{score.label}</p>
      </div>

      <div className="w-full h-2 bg-gray-100 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full bg-gradient-to-r ${barGradient} transition-all duration-500`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="flex justify-between mt-1.5">
        <span className="text-[10px] font-bold text-gray-300">300</span>
        <span className="text-[10px] font-bold text-gray-300">{score.max}</span>
      </div>
    </div>
  );
};
