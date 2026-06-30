import React, { useState, useEffect } from 'react';
import type { CreditScore, CustomerProfile, Appointment } from '../types';
import { CreditScoreCard } from './cards/CreditScoreCard';
import { getAppointment, cancelAppointment } from '../services/api';

interface ContextPanelProps {
  profile: CustomerProfile | null;
  creditScore: CreditScore;
  creditRating?: string;
  sessionId: string;
  token: string | null;
  customerId?: string | null;
}

const LOAN_TYPE_LABELS: Record<string, string> = {
  personal_loan: 'Personal Loan',
  home_loan: 'Home Loan',
  lap: 'Loan Against Property',
  loan_against_property: 'Loan Against Property',
  car_loan: 'Car Loan',
  education_loan: 'Education Loan',
  gold_loan: 'Gold Loan',
  business_loan: 'Business Loan',
};

function formatLoanType(type: string): string {
  return LOAN_TYPE_LABELS[type] ?? type
    .split('_')
    .map(w => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

function formatINR(n: number): string {
  return `₹${Math.round(n).toLocaleString('en-IN')}`;
}

type AccountKind = 'savings' | 'fd' | 'cc';

function accountKind(acc: string): AccountKind {
  if (acc.startsWith('FD-')) return 'fd';
  if (acc.startsWith('CC-')) return 'cc';
  return 'savings';
}

const ACCOUNT_LABELS: Record<AccountKind, string> = {
  savings: 'Savings Account',
  fd: 'Fixed Deposit',
  cc: 'Credit Card',
};

const AccountIcon: React.FC<{ kind: AccountKind; className?: string }> = ({ kind, className }) => {
  if (kind === 'fd') {
    // Piggy bank
    return (
      <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 11c0-3.5 3.5-6 7-6 1 0 2 .2 2.8.6L14 4l1 2.2c2.2.9 4 2.8 4 4.8v1h1v3h-1.5c-.4 1.2-1.3 2.2-2.5 2.8V20h-2v-1.5a8 8 0 01-3 0V20H9v-2.2A6 6 0 015.5 15H3v-4z" />
        <circle cx="8" cy="11" r="0.6" fill="currentColor" stroke="none" />
      </svg>
    );
  }
  if (kind === 'cc') {
    // Credit card
    return (
      <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <rect x="2.5" y="5" width="19" height="14" rx="2" />
        <path strokeLinecap="round" d="M2.5 9.5h19" />
        <path strokeLinecap="round" d="M6 15h4" />
      </svg>
    );
  }
  // Bank / savings
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 10l9-6 9 6M4 10v9m4-9v9m4-9v9m4-9v9m4-9v9M2 21h20" />
    </svg>
  );
};

const SectionCard: React.FC<{ title: string; children: React.ReactNode }> = ({ title, children }) => (
  <div className="bg-white dark:bg-[#10141f] rounded-2xl border border-gray-100 dark:border-gray-800 p-5 shadow-sm">
    <p className="text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-widest mb-4">
      {title}
    </p>
    {children}
  </div>
);

const SkeletonRow: React.FC<{ className?: string }> = ({ className = 'h-12' }) => (
  <div className={`animate-pulse bg-gray-100 dark:bg-gray-800 rounded-xl ${className}`} />
);

const AppointmentBox: React.FC<{
  appointment: Appointment;
  token: string | null;
  onCancelled: () => void;
}> = ({ appointment, token, onCancelled }) => {
  const [cancelling, setCancelling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCancel = async () => {
    if (!token || cancelling) return;
    setCancelling(true);
    setError(null);
    try {
      const res = await cancelAppointment(appointment.id, token);
      if (res?.success) {
        // Clear immediately, right here — don't wait for the next poll.
        onCancelled();
      } else {
        setError(res?.message || 'Could not cancel the appointment.');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not cancel the appointment.');
    } finally {
      setCancelling(false);
    }
  };

  return (
    <div
      className="rounded-2xl border-l-[3px] border-emerald-500 bg-[#f0fdf4] dark:bg-emerald-500/10 p-5 shadow-sm"
    >
      <div className="flex items-center gap-2 mb-3">
        <span className="text-sm">📅</span>
        <p className="text-xs font-bold text-emerald-700 dark:text-emerald-400 uppercase tracking-widest">
          Upcoming Appointment
        </p>
      </div>
      <div className="space-y-2 text-xs">
        <div className="flex justify-between gap-3">
          <span className="text-gray-500 dark:text-gray-400 flex-shrink-0">Date</span>
          <span className="font-semibold text-gray-800 dark:text-gray-100 text-right">
            {new Date(appointment.appointment_date).toLocaleDateString('en-GB', {
              day: 'numeric', month: 'long', year: 'numeric',
            })}
          </span>
        </div>
        <div className="flex justify-between gap-3">
          <span className="text-gray-500 dark:text-gray-400 flex-shrink-0">Time</span>
          <span className="font-semibold text-gray-800 dark:text-gray-100">{appointment.appointment_time}</span>
        </div>
        <div className="flex justify-between gap-3">
          <span className="text-gray-500 dark:text-gray-400 flex-shrink-0">Branch</span>
          <span className="font-semibold text-gray-800 dark:text-gray-100 text-right truncate">{appointment.branch}</span>
        </div>
        <div className="flex justify-between gap-3">
          <span className="text-gray-500 dark:text-gray-400 flex-shrink-0">Status</span>
          <span className="font-bold text-emerald-600 dark:text-emerald-400 flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" /> Confirmed
          </span>
        </div>
        <div className="flex justify-between gap-3">
          <span className="text-gray-500 dark:text-gray-400 flex-shrink-0">Reason</span>
          <span
            className="font-semibold text-gray-800 dark:text-gray-100 text-right truncate max-w-[150px]"
            title={appointment.reason}
          >
            {appointment.reason}
          </span>
        </div>
      </div>
      {error && <p className="text-[11px] text-red-500 dark:text-red-400 mt-2">{error}</p>}
      <button
        onClick={handleCancel}
        disabled={cancelling}
        className="w-full mt-3 text-[11px] font-bold text-rose-600 dark:text-rose-400 border border-rose-200 dark:border-rose-500/30 hover:bg-rose-50 dark:hover:bg-rose-500/10 rounded-xl py-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {cancelling ? 'Cancelling…' : 'Cancel Appointment'}
      </button>
    </div>
  );
};

export const ContextPanel: React.FC<ContextPanelProps> = ({ profile, creditScore, creditRating, sessionId, token, customerId }) => {
  const [selectedAccount, setSelectedAccount] = useState<string | null>(null);
  const [selectedLoan, setSelectedLoan] = useState<any | null>(null);
  const [width, setWidth] = useState(288);
  const [appointment, setAppointment] = useState<Appointment | null>(null);

  useEffect(() => {
    // Clear FIRST, synchronously, before fetching — a new sessionId (fresh
    // login, or "New Application") must never keep showing the PREVIOUS
    // session's appointment box while the new fetch is in flight, and if
    // this session simply has no appointment, the box must stay hidden
    // rather than showing whatever was here before.
    setAppointment(null);

    if (!sessionId || !token) {
      return;
    }
    let isMounted = true;
    const fetchAppointment = () => {
      getAppointment(sessionId, token)
        .then((res: any) => {
          if (!isMounted) return;
          // get_appointment() returns the most recent row for this session
          // regardless of status — a cancelled appointment (e.g. cancelled
          // via the chat flow) must not be displayed as if still upcoming.
          const fetched = res?.appointment ?? null;
          setAppointment(fetched && fetched.status !== 'cancelled' ? fetched : null);
        })
        .catch(() => {});
    };
    fetchAppointment();
    // Booking happens inline in the chat (AppointmentFormCard), with no
    // direct callback into this sibling panel — poll so a freshly booked
    // appointment shows up here without requiring a page reload, same
    // pattern as the credit-score poll in App.tsx.
    const interval = setInterval(fetchAppointment, 8000);
    return () => { isMounted = false; clearInterval(interval); };
  }, [sessionId, token, customerId]);

  const startResizing = React.useCallback((mouseDownEvent: React.MouseEvent) => {
    mouseDownEvent.preventDefault();
    const handleMouseMove = (e: MouseEvent) => {
      setWidth(Math.max(250, Math.min(600, window.innerWidth - e.clientX - 16)));
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

  const loading = !profile;
  const accountNumbers = profile?.account_numbers ?? [];
  const loans = profile?.existing_loans ?? [];
  const totalEmi = profile?.total_emi ?? loans.reduce((sum, l) => sum + (l.status === 'active' ? l.emi : 0), 0);

  const scoreForCard = creditRating ? { ...creditScore, label: creditRating } : creditScore;

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setSelectedAccount(null);
        setSelectedLoan(null);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  function getNextEmiDate(): string {
    const d = new Date();
    let nextMonth = d.getMonth() + 1;
    let year = d.getFullYear();
    if (nextMonth > 11) {
      nextMonth = 0;
      year += 1;
    }
    const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    return `05-${monthNames[nextMonth]}-${year}`;
  }

  return (
    <aside style={{ width }} className="relative my-4 mr-4 flex-shrink-0 z-10 bg-[#fbfcfd] dark:bg-[#0b0f1a] rounded-2xl border border-gray-200 dark:border-gray-800 shadow-2xl flex flex-col overflow-y-auto p-4 space-y-4">
      {/* Resizer */}
      <div
        onMouseDown={startResizing}
        className="absolute top-0 left-0 w-1.5 h-full cursor-col-resize hover:bg-blue-500/50 active:bg-blue-500 z-50 rounded-l-2xl"
      />

      {/* Styles for smooth animations */}
      <style>{`
        @keyframes modalFadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes modalScaleUp {
          from { transform: scale(0.95); opacity: 0; }
          to { transform: scale(1); opacity: 1; }
        }
        .animate-modalFadeIn {
          animation: modalFadeIn 0.2s ease-out forwards;
        }
        .animate-modalScaleUp {
          animation: modalScaleUp 0.25s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }
      `}</style>

      {/* Linked Accounts */}
      <SectionCard title="Linked Accounts">
        {loading ? (
          <div className="space-y-2">
            <SkeletonRow />
            <SkeletonRow />
          </div>
        ) : accountNumbers.length === 0 ? (
          <p className="text-xs text-gray-400 dark:text-gray-500">No linked accounts</p>
        ) : (
          <div className="space-y-2">
            {accountNumbers.map(acc => {
              const kind = accountKind(acc);
              return (
                <div
                  key={acc}
                  onClick={() => setSelectedAccount(acc)}
                  className="bg-gray-50 dark:bg-gray-800/40 border border-gray-100 dark:border-gray-700 rounded-xl p-3 hover:scale-[1.02] cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-800/80 transition-all duration-200"
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="flex items-center gap-1.5 text-[10px] font-bold text-[#1e3a6e] dark:text-blue-300 uppercase tracking-wide truncate">
                      <AccountIcon kind={kind} className="w-3.5 h-3.5 flex-shrink-0" />
                      <span className="truncate pr-2">{ACCOUNT_LABELS[kind]}</span>
                    </span>
                    <span className="text-[9px] text-[#00b894] font-bold flex items-center gap-1 flex-shrink-0">
                      <span className="w-1.5 h-1.5 rounded-full bg-[#00b894] animate-ping" />
                      Active
                    </span>
                  </div>
                  <p className="text-xs font-mono font-bold text-gray-800 dark:text-gray-200 truncate">{acc}</p>
                </div>
              );
            })}
          </div>
        )}
      </SectionCard>

      {/* Upcoming Appointment — only shown once one has been booked */}
      {appointment && (
        <AppointmentBox
          appointment={appointment}
          token={token}
          onCancelled={() => setAppointment(null)}
        />
      )}

      {/* Active Loans & EMI */}
      <SectionCard title="Active Loans & EMI">
        {loading ? (
          <SkeletonRow className="h-20" />
        ) : loans.length === 0 ? (
          <p className="text-xs font-bold text-emerald-600 dark:text-emerald-400">No active loans ✓</p>
        ) : (
          <>
            <div className="space-y-3">
              {loans.map(loan => (
                <div
                  key={loan.loan_id}
                  onClick={() => setSelectedLoan(loan)}
                  className="border-b border-gray-100 dark:border-gray-800 pb-3 last:border-0 last:pb-0 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800/30 p-2 -mx-2 rounded-xl transition-all duration-200"
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-bold text-gray-800 dark:text-gray-100 truncate pr-2">
                      {formatLoanType(loan.loan_type)}
                    </span>
                    <span
                      className={`text-[9px] font-bold uppercase px-1.5 py-0.5 rounded flex-shrink-0 ${
                        loan.status === 'active'
                          ? 'bg-emerald-50 dark:bg-emerald-400/10 text-emerald-600 dark:text-emerald-400'
                          : 'bg-gray-100 dark:bg-gray-800 text-gray-400 dark:text-gray-500'
                      }`}
                    >
                      {loan.status}
                    </span>
                  </div>
                  <p className="text-[10px] font-mono text-gray-400 dark:text-gray-500 mb-1.5 truncate">{loan.loan_id}</p>
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-bold text-rose-600 dark:text-rose-400">
                      {formatINR(loan.emi)}/month
                    </span>
                    <span className="text-gray-500 dark:text-gray-400">
                      Out: {formatINR(loan.outstanding_amount)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-3 pt-3 border-t border-gray-100 dark:border-gray-800 flex items-center justify-between">
              <span className="text-[10px] font-bold text-gray-400 dark:text-gray-500 uppercase tracking-wide">
                Total EMI
              </span>
              <span className="text-sm font-extrabold text-rose-600 dark:text-rose-400 truncate pl-2">
                {formatINR(totalEmi)}/month
              </span>
            </div>
          </>
        )}
      </SectionCard>

      {/* Credit Score — kept at the bottom of this panel */}
      {loading ? <SkeletonRow className="h-32" /> : (
        <div className="flex-shrink-0 opacity-90">
          <CreditScoreCard score={scoreForCard} />
        </div>
      )}

      {/* Account Details Popup Modal */}
      {selectedAccount && (
        <div
          onClick={() => setSelectedAccount(null)}
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-modalFadeIn"
        >
          <div
            onClick={e => e.stopPropagation()}
            className="bg-white dark:bg-[#151926] border border-gray-100 dark:border-gray-800 rounded-3xl p-6 shadow-2xl w-full max-w-sm relative animate-modalScaleUp text-gray-800 dark:text-gray-100"
          >
            <button
              onClick={() => setSelectedAccount(null)}
              className="absolute top-4 right-4 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>

            <div className="flex items-center gap-2 mb-4">
              <div className="w-8 h-8 rounded-xl bg-blue-50 dark:bg-blue-900/30 flex items-center justify-center text-blue-600 dark:text-blue-400">
                <AccountIcon kind={accountKind(selectedAccount)} className="w-5 h-5" />
              </div>
              <div className="overflow-hidden">
                <h3 className="font-bold text-[10px] text-gray-400 dark:text-gray-500 uppercase tracking-wider truncate">Account Details</h3>
                <p className="text-sm font-extrabold text-gray-900 dark:text-white truncate">
                  {ACCOUNT_LABELS[accountKind(selectedAccount)]}
                </p>
              </div>
            </div>

            <div className="space-y-3.5 border-t border-gray-100 dark:border-gray-800 pt-4">
              <div className="flex justify-between items-center text-xs">
                <span className="text-gray-500 dark:text-gray-400">Account Number</span>
                <span className="font-mono font-bold text-gray-900 dark:text-white truncate pl-2">{selectedAccount}</span>
              </div>

              <div className="flex justify-between items-center text-xs">
                <span className="text-gray-500 dark:text-gray-400">Status</span>
                <span className="text-[10px] bg-emerald-50 dark:bg-emerald-400/10 text-emerald-600 dark:text-emerald-400 font-bold px-2 py-0.5 rounded flex items-center gap-1.5 flex-shrink-0">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                  Active
                </span>
              </div>

              <div className="flex justify-between items-center text-xs">
                <span className="text-gray-500 dark:text-gray-400">Account Open Date</span>
                <span className="font-semibold text-gray-900 dark:text-white pl-2 text-right">
                  {profile?.account_open_date ? new Date(profile.account_open_date).toLocaleDateString('en-IN', {
                    day: 'numeric',
                    month: 'short',
                    year: 'numeric'
                  }) : 'N/A'}
                </span>
              </div>

              <div className="flex justify-between items-center text-xs">
                <span className="text-gray-500 dark:text-gray-400">Average Monthly Balance</span>
                <span className="font-bold text-gray-900 dark:text-white truncate pl-2">
                  {profile?.avg_monthly_balance ? formatINR(profile.avg_monthly_balance) : 'N/A'}
                </span>
              </div>

              <div className="flex justify-between items-center text-xs">
                <span className="text-gray-500 dark:text-gray-400">Monthly Income</span>
                <span className="font-bold text-gray-900 dark:text-white truncate pl-2">
                  {profile?.monthly_income ? formatINR(profile.monthly_income) : 'N/A'}
                </span>
              </div>

              <div className="flex justify-between items-center text-xs">
                <span className="text-gray-500 dark:text-gray-400">Employer</span>
                <span className="font-semibold text-gray-900 dark:text-white truncate max-w-[200px]" title={profile?.employer_name ?? undefined}>
                  {profile?.employer_name ?? 'N/A'}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Loan Details Popup Modal */}
      {selectedLoan && (
        <div
          onClick={() => setSelectedLoan(null)}
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-modalFadeIn"
        >
          <div
            onClick={e => e.stopPropagation()}
            className="bg-white dark:bg-[#151926] border border-gray-100 dark:border-gray-800 rounded-3xl p-6 shadow-2xl w-full max-w-sm relative animate-modalScaleUp text-gray-800 dark:text-gray-100"
          >
            <button
              onClick={() => setSelectedLoan(null)}
              className="absolute top-4 right-4 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>

            <div className="flex items-center gap-2 mb-4">
              <div className="w-8 h-8 rounded-xl bg-rose-50 dark:bg-rose-900/30 flex items-center justify-center text-rose-600 dark:text-rose-400 flex-shrink-0">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <div className="overflow-hidden">
                <h3 className="font-bold text-[10px] text-gray-400 dark:text-gray-500 uppercase tracking-wider truncate">Loan Details</h3>
                <p className="text-sm font-extrabold text-gray-900 dark:text-white truncate">
                  {formatLoanType(selectedLoan.loan_type)}
                </p>
              </div>
            </div>

            <div className="space-y-3.5 border-t border-gray-100 dark:border-gray-800 pt-4">
              <div className="flex justify-between items-center text-xs">
                <span className="text-gray-500 dark:text-gray-400">Loan ID</span>
                <span className="font-mono font-bold text-gray-900 dark:text-white truncate pl-2">{selectedLoan.loan_id}</span>
              </div>

              <div className="flex justify-between items-center text-xs">
                <span className="text-gray-500 dark:text-gray-400">Status</span>
                <span className={`text-[10px] font-bold px-2 py-0.5 rounded flex items-center gap-1.5 uppercase flex-shrink-0 ${
                  selectedLoan.status === 'active'
                    ? 'bg-emerald-50 dark:bg-emerald-400/10 text-emerald-600 dark:text-emerald-400'
                    : 'bg-gray-100 dark:bg-gray-800 text-gray-400 dark:text-gray-500'
                }`}>
                  {selectedLoan.status === 'active' && <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />}
                  {selectedLoan.status}
                </span>
              </div>

              <div className="flex justify-between items-center text-xs">
                <span className="text-gray-500 dark:text-gray-400">Outstanding Amount</span>
                <span className="font-bold text-gray-900 dark:text-white truncate pl-2">
                  {formatINR(selectedLoan.outstanding_amount)}
                </span>
              </div>

              <div className="flex justify-between items-center text-xs">
                <span className="text-gray-500 dark:text-gray-400">Monthly EMI</span>
                <span className="font-bold text-rose-600 dark:text-rose-400 truncate pl-2">
                  {formatINR(selectedLoan.emi)}/month
                </span>
              </div>

              <div className="flex justify-between items-center text-xs">
                <span className="text-gray-500 dark:text-gray-400">Next EMI Date</span>
                <span className="font-semibold text-gray-900 dark:text-white pl-2 text-right">
                  {selectedLoan.next_emi_date ? new Date(selectedLoan.next_emi_date).toLocaleDateString('en-IN', {
                    day: 'numeric',
                    month: 'short',
                    year: 'numeric'
                  }) : getNextEmiDate()}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}
    </aside>
  );
};
