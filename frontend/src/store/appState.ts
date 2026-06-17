import type { WorkflowStep, Message, CreditScore, InterestRate, LoanType } from '../types';

export const workflowSteps: WorkflowStep[] = [
  { id: 'auth', label: 'Authentication', status: 'completed' },
  { id: 'account', label: 'Account Discovery', status: 'completed' },
  { id: 'kyc', label: 'KYC', status: 'completed' },
  { id: 'property', label: 'Property Verification', status: 'completed' },
  { id: 'risk', label: 'Risk Assessment', status: 'active', subLabel: 'Processing...' },
  { id: 'credit', label: 'Credit Assessment', status: 'pending' },
  { id: 'decision', label: 'Loan Decision', status: 'pending' },
];

export const loanTypes: LoanType[] = [
  { id: 'home', label: 'Home Loan' },
  { id: 'property', label: 'Property Type' },
];

export const interestRates: InterestRate[] = [
  { range: 'Up to ₹30 Lakhs', tenure: 'Up to 20 years', rate: '8.35%', trend: 'down' },
  { range: '₹30L – ₹75 Lakhs', tenure: 'Up to 25 years', rate: '8.50%', trend: 'flat' },
  { range: '₹75L & Above', tenure: 'Up to 30 years', rate: '8.75%', trend: 'up' },
];

export const creditScore: CreditScore = {
  value: 745,
  max: 900,
  label: 'Good',
};

export const initialMessages: Message[] = [];
