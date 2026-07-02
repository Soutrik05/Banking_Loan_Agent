import React, { useState } from 'react';
import type { InterestRate, LoanType, Message } from '../types';
import { InterestRateCard } from './cards/InterestRateCard';
import { useConversations } from '../hooks/useConversations';
import type { ConversationSummary } from '../services/api';

const LoanDecisionBadge: React.FC<{ conv: ConversationSummary }> = ({ conv }) => {
  const d = conv.loan_decision?.decision;
  if (!d) return null;
  if (d === 'approved') return (
    <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-emerald-50 dark:bg-emerald-400/10 text-emerald-600 dark:text-emerald-400 flex-shrink-0 flex items-center gap-0.5">
      ✅ Approved
    </span>
  );
  if (d === 'rejected') return (
    <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-red-50 dark:bg-red-400/10 text-red-600 dark:text-red-400 flex-shrink-0 flex items-center gap-0.5">
      ❌ Declined
    </span>
  );
  return (
    <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-amber-50 dark:bg-amber-400/10 text-amber-600 dark:text-amber-400 flex-shrink-0 flex items-center gap-0.5">
      ⚠️ Review
    </span>
  );
};

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

const SidebarButton: React.FC<{
  open: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
  showArrow: boolean;
  disabled?: boolean;
}> = ({ open, onClick, icon, label, showArrow, disabled }) => {
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const [isHovered, setIsHovered] = useState(false);

  const handleMouseMove = (e: React.MouseEvent<HTMLButtonElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    setMousePos({
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
    });
  };

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      onMouseMove={handleMouseMove}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm font-semibold transition-all text-left relative overflow-hidden group ${
        open
          ? 'bg-blue-500/10 text-blue-600 dark:bg-blue-400/10 dark:text-blue-300 border border-blue-500/10 dark:border-blue-400/10 shadow-sm shadow-blue-500/5'
          : 'text-gray-500 dark:text-gray-400 hover:bg-gray-50/50 dark:hover:bg-gray-800/40 hover:text-gray-950 dark:hover:text-gray-100 border border-transparent'
      }`}
    >
      {/* Spotlight highlight overlay */}
      <div
        className="absolute inset-0 pointer-events-none transition-opacity duration-300"
        style={{
          opacity: isHovered ? 1 : 0,
          background: `radial-gradient(110px circle at ${mousePos.x}px ${mousePos.y}px, rgba(99, 102, 241, 0.12), transparent 80%)`,
        }}
      />

      <span className={`z-10 transition-colors duration-200 ${open ? 'text-[#1e3a6e] dark:text-blue-300' : 'text-gray-400 dark:text-gray-500 group-hover:text-gray-650 dark:group-hover:text-gray-200'}`}>
        {icon}
      </span>
      <span className="z-10 flex-1">{label}</span>
      {showArrow && (
        <svg
          className={`z-10 w-3.5 h-3.5 text-gray-400 dark:text-gray-500 transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      )}
    </button>
  );
};

const NewApplicationButton: React.FC<{ onClick: () => void }> = ({ onClick }) => {
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const [isHovered, setIsHovered] = useState(false);

  const handleMouseMove = (e: React.MouseEvent<HTMLButtonElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    setMousePos({ x: e.clientX - rect.left, y: e.clientY - rect.top });
  };

  return (
    <button
      onClick={onClick}
      onMouseMove={handleMouseMove}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-gradient-to-tr from-[#1e3a6e] to-[#254f96] hover:shadow-lg hover:shadow-blue-500/15 active:scale-[0.98] text-sm font-bold text-white transition-all mb-4 relative overflow-hidden group"
    >
      <div
        className="absolute inset-0 pointer-events-none transition-opacity duration-300"
        style={{
          opacity: isHovered ? 1 : 0,
          background: `radial-gradient(110px circle at ${mousePos.x}px ${mousePos.y}px, rgba(255, 255, 255, 0.15), transparent 80%)`,
        }}
      />
      <svg className="w-4 h-4 text-white flex-shrink-0 z-10" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
      </svg>
      <span className="truncate z-10">New Application</span>
    </button>
  );
};

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
      <SidebarButton
        open={open}
        onClick={() => setOpen(o => !o)}
        label="Application History"
        showArrow={isAuthenticated}
        icon={<svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>}
      />

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
              <div className="flex items-center justify-between gap-1 mt-0.5">
                <span className="text-[10px] font-medium text-gray-400 dark:text-gray-500 truncate">
                  {formatConversationDate(conv.updated_at)}
                </span>
                <LoanDecisionBadge conv={conv} />
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

// Condensed key points lifted from backend/mock_data/faq_docs/*.md — kept in
// sync manually since the sidebar has no backend call for this (purely
// informational, same for every customer).
const FAQ_CATEGORIES: { id: string; label: string; points: string[] }[] = [
  {
    id: 'loan_products',
    label: 'Loan Products',
    points: [
      'Home Loan: ₹5L–₹5Cr, 5–25 yr tenure, 0.50% processing fee, no prepayment penalty.',
      'Loan Against Property (LAP): ₹10L–₹10Cr, 1–15 yr tenure, 1.00% processing fee, 2% prepayment penalty within 12 months.',
      'Top-Up Loan: ₹2L–₹1Cr, 1–10 yr tenure, existing home loan customers only.',
      'Max amount depends on income (up to 60× annual for salaried), property LTV (75–90%), and EMI affordability (≤50% of income).',
      'Standard approval: 7–10 working days. Fast-track (tied property): 3 working days.',
    ],
  },
  {
    id: 'interest_rates',
    label: 'Interest Rates',
    points: [
      'Base rate: 8.75% p.a., floating, linked to the RBI repo rate.',
      'Rate = Base + Credit Score Modifier + DTI Modifier + Risk Modifier − Fast-Track Discount.',
      'Excellent credit (800+): −0.50% · Fair (650–699): +0.75% · Poor (600–649): +1.50%.',
      'Rate range: 7.50% minimum to 14.00% maximum.',
      'No prepayment penalty on Home/Top-Up loans. LAP: 2% if prepaid within 12 months.',
    ],
  },
  {
    id: 'eligibility',
    label: 'Eligibility Criteria',
    points: [
      'Age: 21–65 years (loan must be fully repaid by age 65).',
      'Min income: ₹25,000/month salaried (12 months at employer) or ₹35,000/month self-employed (24 months vintage).',
      'Min credit score: 650 standard, 600 for fast-track (bank-tied property). Below 600 not eligible.',
      'DTI (EMIs ÷ income) must stay under 55% (60% for fast-track).',
      'LTV caps: 90% up to ₹30L value, 80% up to ₹75L, 75% above ₹75L.',
    ],
  },
  {
    id: 'documents',
    label: 'Required Documents',
    points: [
      'Identity: Aadhaar, PAN, and Passport/Voter ID — new customers only.',
      'Income (salaried): 3 months salary slips, 6 months bank statements, Form 16/ITR.',
      'Income (self-employed): 2 years ITR, 12 months bank statements, audited financials, GST returns.',
      'Property: Sale Deed, Property Tax Receipt, Encumbrance Certificate, Registry Document.',
      'Existing customers skip identity documents unless name/address has changed.',
    ],
  },
];

const FAQSection: React.FC<{ isAuthenticated: boolean }> = ({ isAuthenticated }) => {
  const [open, setOpen] = useState(false);
  const [activeCategory, setActiveCategory] = useState<string | null>(null);

  return (
    <div>
      <SidebarButton
        open={open}
        onClick={() => setOpen(o => !o)}
        label="FAQ Section"
        showArrow={isAuthenticated}
        icon={<svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><circle cx="12" cy="12" r="10" /><path strokeLinecap="round" d="M12 16v-4M12 8h.01" /></svg>}
      />

      {open && isAuthenticated && (
        <div className="mt-1 ml-4 pl-3 border-l border-gray-100 dark:border-gray-800 space-y-1 animate-fade-in">
          {FAQ_CATEGORIES.map(cat => (
            <div key={cat.id}>
              <button
                onClick={() => setActiveCategory(prev => (prev === cat.id ? null : cat.id))}
                className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-semibold transition-colors ${
                  activeCategory === cat.id
                    ? 'bg-[#1e3a6e]/10 text-[#1e3a6e] dark:bg-blue-400/10 dark:text-blue-300'
                    : 'text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800/50'
                }`}
              >
                <span>{cat.label}</span>
                <svg
                  className={`w-3 h-3 transition-transform duration-200 ${activeCategory === cat.id ? 'rotate-180' : ''}`}
                  fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {activeCategory === cat.id && (
                <ul className="px-3 pt-1.5 pb-2 space-y-1.5 animate-fade-in">
                  {cat.points.map((point, i) => (
                    <li
                      key={i}
                      className="text-[11px] text-gray-500 dark:text-gray-400 leading-relaxed pl-2 border-l-2 border-gray-200 dark:border-gray-700"
                    >
                      {point}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

function conversationStatus(updatedAtIso: string): 'Active' | 'Completed' {
  const hoursSince = (Date.now() - new Date(updatedAtIso).getTime()) / 36e5;
  return hoursSince < 24 ? 'Active' : 'Completed';
}

const SavedApplicationsSection: React.FC<{
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
      <SidebarButton
        open={open}
        onClick={() => setOpen(o => !o)}
        label="Saved Applications"
        showArrow={isAuthenticated}
        icon={<svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>}
      />

      {open && isAuthenticated && (
        <div className="mt-1 ml-4 pl-3 border-l border-gray-100 dark:border-gray-800 space-y-0.5 animate-fade-in">
          {conversations.length === 0 && (
            <p className="text-xs text-gray-400 dark:text-gray-500 px-3 py-2">No saved applications yet.</p>
          )}
          {conversations.map(conv => {
            const status = conversationStatus(conv.updated_at);
            return (
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
                <div className="flex items-center justify-between gap-1 mt-0.5">
                  <span className="text-[10px] font-medium text-gray-400 dark:text-gray-500 truncate">
                    {formatConversationDate(conv.updated_at)}
                  </span>
                  {conv.loan_decision?.decision ? (
                    <LoanDecisionBadge conv={conv} />
                  ) : (
                    <span
                      className={`text-[9px] font-bold uppercase px-1.5 py-0.5 rounded flex-shrink-0 ${
                        status === 'Active'
                          ? 'bg-emerald-50 dark:bg-emerald-400/10 text-emerald-600 dark:text-emerald-400'
                          : 'bg-gray-100 dark:bg-gray-800 text-gray-400 dark:text-gray-500'
                      }`}
                    >
                      {status}
                    </span>
                  )}
                </div>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
};

const EMICalculatorSection: React.FC = () => {
  const [open, setOpen] = useState(false);
  const [amount, setAmount] = useState(5000000); // 50 Lakhs default
  const [rate, setRate] = useState(8.5); // 8.5% default
  const [tenure, setTenure] = useState(20); // 20 years default

  // Calculate EMI
  const monthlyRate = (rate / 12) / 100;
  const totalMonths = tenure * 12;
  const emi = amount * monthlyRate * Math.pow(1 + monthlyRate, totalMonths) / (Math.pow(1 + monthlyRate, totalMonths) - 1);
  const totalPayment = emi * totalMonths;
  const totalInterest = totalPayment - amount;

  const formattedEMI = Math.round(emi).toLocaleString('en-IN');
  const formattedInterest = Math.round(totalInterest).toLocaleString('en-IN');

  const formatLakhs = (val: number) => {
    if (val >= 10000000) return `₹${(val / 10000000).toFixed(2)} Cr`;
    return `₹${(val / 100000).toFixed(0)} Lakh`;
  };

  const interestPercentage = (totalInterest / totalPayment) * 100;

  return (
    <div className="pt-2 border-t border-gray-150/40 dark:border-gray-800/80 mt-2">
      <SidebarButton
        open={open}
        onClick={() => setOpen(o => !o)}
        label="EMI Calculator"
        showArrow={true}
        icon={<svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
          <rect x="3" y="3" width="18" height="18" rx="2" />
          <path strokeLinecap="round" d="M7 8h10M7 12h10M7 16h6" />
        </svg>}
      />

      {open && (
        <div className="mt-3 px-3 py-4 bg-white/60 dark:bg-gray-950/40 border border-gray-150/40 dark:border-gray-850/80 rounded-2xl space-y-4 animate-slide-up">
          {/* EMI Display */}
          <div className="text-center bg-gradient-to-tr from-blue-500/5 to-indigo-500/5 dark:from-blue-400/10 dark:to-indigo-400/10 border border-blue-100/50 dark:border-blue-400/10 rounded-2xl p-4">
            <p className="text-[10px] font-bold text-gray-400 dark:text-gray-500 uppercase tracking-wider">Monthly EMI</p>
            <p className="text-2xl font-black text-blue-600 dark:text-blue-300 mt-1">₹{formattedEMI}</p>
            <p className="text-[10px] text-gray-500 dark:text-gray-400 mt-1.5 font-medium">Total Interest: <span className="font-bold text-gray-700 dark:text-gray-200">₹{formattedInterest}</span></p>
            
            {/* Visual ratio bar */}
            <div className="mt-3.5 h-1.5 w-full bg-blue-100/50 dark:bg-blue-950/50 rounded-full overflow-hidden flex">
              <div className="bg-blue-600 dark:bg-blue-400 h-full" style={{ width: `${100 - interestPercentage}%` }} title="Principal" />
              <div className="bg-amber-400 dark:bg-amber-500 h-full" style={{ width: `${interestPercentage}%` }} title="Interest" />
            </div>
          </div>

          {/* Amount Slider */}
          <div className="space-y-1">
            <div className="flex justify-between text-[11px] font-semibold text-gray-500 dark:text-gray-400 px-0.5">
              <span>Loan Amount</span>
              <span className="text-blue-600 dark:text-blue-300 font-bold">{formatLakhs(amount)}</span>
            </div>
            <input
              type="range"
              min={100000}
              max={20000000}
              step={100000}
              value={amount}
              onChange={e => setAmount(Number(e.target.value))}
              className="w-full h-1 bg-gray-200 dark:bg-gray-800 rounded-lg appearance-none cursor-pointer accent-blue-600 dark:accent-blue-400"
            />
          </div>

          {/* Rate Slider */}
          <div className="space-y-1">
            <div className="flex justify-between text-[11px] font-semibold text-gray-500 dark:text-gray-400 px-0.5">
              <span>Interest Rate</span>
              <span className="text-blue-600 dark:text-blue-300 font-bold">{rate}% p.a.</span>
            </div>
            <input
              type="range"
              min={5}
              max={15}
              step={0.1}
              value={rate}
              onChange={e => setRate(Number(e.target.value))}
              className="w-full h-1 bg-gray-200 dark:bg-gray-800 rounded-lg appearance-none cursor-pointer accent-blue-600 dark:accent-blue-400"
            />
          </div>

          {/* Tenure Slider */}
          <div className="space-y-1">
            <div className="flex justify-between text-[11px] font-semibold text-gray-500 dark:text-gray-400 px-0.5">
              <span>Tenure</span>
              <span className="text-blue-600 dark:text-blue-300 font-bold">{tenure} Years</span>
            </div>
            <input
              type="range"
              min={1}
              max={30}
              step={1}
              value={tenure}
              onChange={e => setTenure(Number(e.target.value))}
              className="w-full h-1 bg-gray-200 dark:bg-gray-800 rounded-lg appearance-none cursor-pointer accent-blue-600 dark:accent-blue-400"
            />
          </div>
        </div>
      )}
    </div>
  );
};

export const Sidebar: React.FC<SidebarProps> = ({
  interestRates, loanTypes, onNewApplication,
  isAuthenticated, userName, onLoginClick, onLogoutClick, accountNumbers,
  theme, onToggleTheme, token, customerId, onLoadConversation,
}) => {
  const [width, setWidth] = useState(288); // 72 tailwind = 288px
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });

  const handleMouseMove = (e: React.MouseEvent<HTMLElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    setMousePos({
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
    });
  };

  const startResizing = React.useCallback((mouseDownEvent: React.MouseEvent) => {
    mouseDownEvent.preventDefault();
    const handleMouseMove = (e: MouseEvent) => {
      setWidth(Math.max(200, Math.min(600, e.clientX)));
    };
    const handleMouseUp = () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = 'default';
    };
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    document.body.style.cursor = 'col-resize';
  }, []);

  return (
  <aside 
    style={{ width }} 
    onMouseMove={handleMouseMove}
    className="relative flex-shrink-0 bg-gradient-to-b from-blue-50/45 via-indigo-50/15 to-white dark:from-[#080c18] dark:via-[#0b0f1d] dark:to-[#060914] border-r border-gray-150/70 dark:border-gray-800/70 flex flex-col h-full overflow-hidden"
  >
    {/* Ambient interactive mouse glow */}
    <div 
      className="absolute inset-0 pointer-events-none transition-opacity duration-300 opacity-60 dark:opacity-40"
      style={{
        background: `radial-gradient(320px circle at ${mousePos.x}px ${mousePos.y}px, rgba(99, 102, 241, 0.07), transparent 85%)`
      }}
    />
    {/* Resizer */}
    <div
      onMouseDown={startResizing}
      className="absolute top-0 right-0 w-1.5 h-full cursor-col-resize hover:bg-blue-500/50 active:bg-blue-500 z-50"
    />
    
    {/* Logo */}
    <div className="flex items-center gap-3 px-6 py-6 border-b border-gray-100 dark:border-gray-800">
      <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-[#1e3a6e] to-[#3b82f6] flex items-center justify-center shadow-md shadow-blue-500/10 hover:scale-105 transition-transform duration-200">
        <svg className="w-5 h-5 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
          <path d="M3 22h18M6 18V9M10 18V9M14 18V9M18 18V9M12 2L2 7h20L12 2z" />
        </svg>
      </div>
      <div className="flex-1 overflow-hidden">
        <p className="text-sm font-extrabold text-gray-900 dark:text-gray-50 tracking-tight leading-none mb-0.5 truncate">National Bank</p>
        <p className="text-xs font-semibold text-gray-400 dark:text-gray-500 truncate">Loan Assistant</p>
        <p className="text-[10px] font-normal text-gray-400 dark:text-gray-600 truncate">BankWise AI</p>
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
      <NewApplicationButton onClick={onNewApplication} />

      <ApplicationHistorySection
        isAuthenticated={isAuthenticated}
        token={token}
        customerId={customerId}
        onLoadConversation={onLoadConversation}
      />
      <FAQSection isAuthenticated={isAuthenticated} />
      <SavedApplicationsSection
        isAuthenticated={isAuthenticated}
        token={token}
        customerId={customerId}
        onLoadConversation={onLoadConversation}
      />
      <EMICalculatorSection />

      {/* Interest Rates */}
      <div className="pt-5 overflow-hidden">
        <InterestRateCard rates={interestRates} loanTypes={loanTypes} />
      </div>

      {/* Linked Accounts */}
      {isAuthenticated && accountNumbers && accountNumbers.length > 0 && (
        <div className="pt-4 border-t border-gray-100 dark:border-gray-800 mt-4 overflow-hidden">
          <p className="text-[10px] font-extrabold text-[#1e3a6e] dark:text-blue-300 uppercase tracking-wider mb-2.5 px-2 truncate">
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
                    <span className={`text-[10px] font-bold ${text} uppercase tracking-wide truncate pr-2`}>
                      {label}
                    </span>
                    <span className="text-[9px] text-[#00b894] font-bold flex items-center gap-1 flex-shrink-0">
                      <span className="w-1 h-1 rounded-full bg-[#00b894] animate-ping" />
                      Active
                    </span>
                  </div>
                  <p className="text-xs font-mono font-bold text-gray-800 dark:text-gray-200 mt-1 truncate">
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
    <div className={`p-4 border-t transition-all duration-300 ${
      isAuthenticated 
        ? 'bg-emerald-500/5 dark:bg-emerald-400/5 border-emerald-500/10 dark:border-emerald-400/10' 
        : 'border-gray-100 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-900/40'
    }`}>
      {isAuthenticated ? (
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-emerald-600 to-teal-500 text-white text-xs font-bold flex-shrink-0 shadow-md shadow-emerald-500/20 ring-2 ring-emerald-400/20 flex items-center justify-center">
            {userName?.charAt(0) ?? '?'}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-bold text-gray-900 dark:text-gray-100 truncate">{userName}</p>
            <p className="text-[9px] font-extrabold text-emerald-600 dark:text-emerald-400 flex items-center gap-1.5 uppercase tracking-wider">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse flex-shrink-0" />
              Secure Session
            </p>
          </div>
          <button
            onClick={onLogoutClick}
            className="text-xs flex-shrink-0 text-gray-400 dark:text-gray-500 hover:text-red-500 dark:hover:text-red-400 font-bold transition-colors"
          >
            Sign out
          </button>
        </div>
      ) : (
        <button
          onClick={onLoginClick}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl border border-gray-200 dark:border-gray-700 text-sm font-bold text-gray-650 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-800 active:scale-[0.98] transition-all bg-white dark:bg-gray-900 shadow-sm"
        >
          <svg className="w-4 h-4 text-gray-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
          </svg>
          <span className="truncate">Sign In</span>
        </button>
      )}
    </div>
  </aside>
  );
};
