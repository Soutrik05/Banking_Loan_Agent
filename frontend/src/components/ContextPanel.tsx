import React from 'react';
import type { WorkflowStep, CreditScore } from '../types';
import { WorkflowPanel } from './workflow/WorkflowPanel';
import { CreditScoreCard } from './cards/CreditScoreCard';

interface ContextPanelProps {
  steps: WorkflowStep[];
  creditScore: CreditScore;
}

export const ContextPanel: React.FC<ContextPanelProps> = ({ steps, creditScore }) => (
  <aside className="w-72 flex-shrink-0 bg-[#f8f9fb] border-l border-gray-100 flex flex-col h-full overflow-y-auto p-4 space-y-4">
    <WorkflowPanel steps={steps} />
    <CreditScoreCard score={creditScore} />
  </aside>
);
