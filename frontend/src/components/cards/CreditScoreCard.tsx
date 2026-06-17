import React from 'react';
import type { CreditScore } from '../../types';

interface CreditScoreCardProps {
  score: CreditScore;
}

export const CreditScoreCard: React.FC<CreditScoreCardProps> = ({ score }) => {
  const pct = (score.value / score.max) * 100;

  return (
    <div className="bg-white rounded-2xl border border-gray-100 p-5 shadow-sm mt-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="w-8 h-6 rounded bg-gray-100 flex items-center justify-center">
            <svg className="w-4 h-4 text-[#1e3a6e]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <rect x="2" y="5" width="20" height="14" rx="2" strokeWidth={2} />
              <path strokeLinecap="round" d="M2 10h20" strokeWidth={2} />
            </svg>
          </div>
          <span className="text-sm font-semibold text-gray-700">Credit Score</span>
        </div>
        <div className="text-right">
          <span className="text-2xl font-bold text-gray-900">{score.value}</span>
          <span className="text-xs text-gray-400 ml-1">/ {score.max}</span>
        </div>
      </div>
      <p className="text-xs text-gray-500 mb-2">{score.label}</p>
      <div className="w-full h-2 bg-gray-100 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full bg-[#1e3a6e] transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="flex justify-between mt-1">
        <span className="text-xs text-gray-400">300</span>
        <span className="text-xs text-gray-400">{score.max}</span>
      </div>
    </div>
  );
};
