import React from 'react';
import type { WorkflowStep, WorkflowStatus } from '../../types';

interface WorkflowStepItemProps {
  step: WorkflowStep;
  isLast: boolean;
}

const StatusIcon: React.FC<{ status: WorkflowStatus }> = ({ status }) => {
  if (status === 'completed') {
    return (
      <div className="w-7 h-7 rounded-full bg-[#00b894] flex items-center justify-center flex-shrink-0">
        <svg className="w-3.5 h-3.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
        </svg>
      </div>
    );
  }
  if (status === 'active') {
    return (
      <div className="w-7 h-7 rounded-full border-2 border-[#1e3a6e] dark:border-blue-400 flex items-center justify-center flex-shrink-0">
        <div className="w-2.5 h-2.5 rounded-full bg-[#1e3a6e] dark:bg-blue-400 animate-pulse" />
      </div>
    );
  }
  return (
    <div className="w-7 h-7 rounded-full border-2 border-gray-300 dark:border-gray-700 flex-shrink-0" />
  );
};

const WorkflowStepItem: React.FC<WorkflowStepItemProps> = ({ step, isLast }) => (
  <div className="flex gap-3">
    <div className="flex flex-col items-center">
      <StatusIcon status={step.status} />
      {!isLast && (
        <div className={`w-0.5 flex-1 mt-1 ${step.status === 'completed' ? 'bg-[#00b894]' : 'bg-gray-200 dark:bg-gray-700'}`} style={{ minHeight: 28 }} />
      )}
    </div>
    <div className="pb-5">
      <p className={`text-sm font-medium leading-7 ${step.status === 'pending' ? 'text-gray-400 dark:text-gray-500' : 'text-gray-800 dark:text-gray-200'}`}>
        {step.label}
      </p>
      {step.subLabel && (
        <p className="text-xs text-[#1e3a6e] dark:text-blue-300 font-medium -mt-1">{step.subLabel}</p>
      )}
    </div>
  </div>
);

interface WorkflowPanelProps {
  steps: WorkflowStep[];
}

export const WorkflowPanel: React.FC<WorkflowPanelProps> = ({ steps }) => (
  <div className="bg-white dark:bg-[#10141f] rounded-2xl border border-gray-100 dark:border-gray-800 p-5 shadow-sm">
    <p className="text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-widest mb-5">
      Loan Application Workflow
    </p>
    {steps.map((step, i) => (
      <WorkflowStepItem key={step.id} step={step} isLast={i === steps.length - 1} />
    ))}
  </div>
);
