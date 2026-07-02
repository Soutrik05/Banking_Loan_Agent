import React, { useRef, useEffect, useState } from 'react';
import type { Message } from '../../types';
import { uploadPropertyDoc, getPropertyDocuments, bookAppointment } from '../../services/api';

interface MessageBubbleProps {
  message: Message;
}

const LOAN_DECISION_PREFIX = 'LOAN_DECISION_CARD:';

const MessageBubble: React.FC<MessageBubbleProps> = ({ message }) => {
  // The final loan decision is rendered as a card (see LoanDecisionCard
  // below), not as a plain text bubble — hide the raw JSON payload.
  if (message.content.startsWith(LOAN_DECISION_PREFIX)) return null;

  return (
    <div className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'} animate-fade-in`}>
      {message.role === 'assistant' && (
        <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-[#1e3a6e] to-[#3b82f6] shadow-md shadow-blue-500/10 flex items-center justify-center mr-3 flex-shrink-0 mt-0.5 hover:rotate-6 transition-transform duration-200">
          <svg className="w-4 h-4 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7s0 6 8 10z" />
            <path d="M8 17h8" />
            <path d="M9 17v-4" />
            <path d="M12 17v-4" />
            <path d="M15 17v-4" />
            <path d="M9 11h6" />
            <path d="M12 8l4 3H8l4-3z" />
          </svg>
        </div>
      )}
      <div
        className={`max-w-[72%] px-4 py-3 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap transition-all ${
          message.role === 'user'
            ? 'bg-gradient-to-tr from-blue-600 to-indigo-600 dark:from-blue-500 dark:to-indigo-500 text-white rounded-tr-none shadow-md shadow-indigo-500/10'
            : 'bg-white/95 dark:bg-[#111625]/90 border border-gray-150/60 dark:border-gray-800/80 border-l-[3px] border-l-blue-500/80 dark:border-l-blue-400/80 text-gray-800 dark:text-gray-100 rounded-tl-none shadow-sm shadow-blue-900/5'
        }`}
      >
        {message.content}
      </div>
    </div>
  );
};

interface LoanDecisionCardData {
  decision: 'approved' | 'rejected' | 'conditional';
  customer_name: string;
  flow_type?: 'lap' | 'own_choice' | 'tie_ups' | null;
  loan_amount?: number | null;
  interest_rate?: number | null;
  tenure_years?: number | null;
  monthly_emi?: number | null;
  cibil_score?: number | null;
  cibil_rating?: string | null;
  property_value?: number | null;
  purchase_price?: number | null;
  conditions?: string[];
  rejection_reasons?: string[];
}

function formatINR(n?: number | null): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '—';
  return `₹${Math.round(n).toLocaleString('en-IN')}`;
}

const StatTile: React.FC<{ label: string; value: React.ReactNode }> = ({ label, value }) => (
  <div className="bg-white/70 dark:bg-black/20 rounded-xl p-3">
    <p className="text-[10px] font-bold text-gray-400 dark:text-gray-500 uppercase tracking-wide">{label}</p>
    <p className="text-sm font-extrabold text-gray-800 dark:text-gray-100 mt-0.5">{value}</p>
  </div>
);

const LoanDecisionCard: React.FC<{ data: LoanDecisionCardData }> = ({ data }) => {
  const handleComingSoon = () => alert('Coming soon');

  if (data.decision === 'rejected') {
    return (
      <div className="rounded-2xl border border-red-200 dark:border-red-500/30 bg-red-50/70 dark:bg-red-500/10 p-5 shadow-sm max-w-md animate-fade-in">
        <h3 className="text-base font-extrabold text-red-700 dark:text-red-400 mb-1">❌ LOAN DECLINED</h3>
        <p className="text-xs text-gray-500 dark:text-gray-400 mb-4">
          We're unable to approve this application at this time.
        </p>
        {data.rejection_reasons && data.rejection_reasons.length > 0 && (
          <ul className="space-y-1.5 mb-4">
            {data.rejection_reasons.map((reason, i) => (
              <li key={i} className="text-xs text-red-700 dark:text-red-300 flex items-start gap-2">
                <span className="mt-0.5">•</span>
                <span>{reason}</span>
              </li>
            ))}
          </ul>
        )}
        <button
          onClick={handleComingSoon}
          className="w-full bg-red-600 hover:bg-red-700 active:scale-[0.98] text-white text-xs font-bold py-2.5 rounded-xl transition-all shadow-sm"
        >
          Speak to an Advisor
        </button>
      </div>
    );
  }

  if (data.decision === 'conditional') {
    return (
      <div className="rounded-2xl border border-amber-200 dark:border-amber-500/30 bg-amber-50/70 dark:bg-amber-500/10 p-5 shadow-sm max-w-md animate-fade-in">
        <h3 className="text-base font-extrabold text-amber-700 dark:text-amber-400 mb-1">⚠️ CONDITIONALLY APPROVED</h3>
        <p className="text-xs text-gray-600 dark:text-gray-300 mb-4">
          Loan Amount: <span className="font-bold text-gray-800 dark:text-gray-100">{formatINR(data.loan_amount)}</span>
        </p>
        {data.conditions && data.conditions.length > 0 && (
          <ul className="space-y-1.5 mb-4">
            {data.conditions.map((cond, i) => (
              <li key={i} className="text-xs text-amber-700 dark:text-amber-300 flex items-start gap-2">
                <span className="mt-0.5">•</span>
                <span>{cond}</span>
              </li>
            ))}
          </ul>
        )}
        <button
          onClick={handleComingSoon}
          className="w-full bg-amber-500 hover:bg-amber-600 active:scale-[0.98] text-white text-xs font-bold py-2.5 rounded-xl transition-all shadow-sm"
        >
          Submit Additional Documents
        </button>
      </div>
    );
  }

  // approved
  return (
    <div className="rounded-2xl border border-emerald-200 dark:border-emerald-500/30 bg-gradient-to-br from-emerald-50 to-teal-50 dark:from-emerald-500/10 dark:to-teal-500/5 p-5 shadow-sm max-w-md animate-fade-in">
      <h3 className="text-base font-extrabold text-emerald-700 dark:text-emerald-400 mb-1">✅ LOAN APPROVED</h3>
      <p className="text-xs text-gray-600 dark:text-gray-300 mb-4">Congratulations, {data.customer_name}!</p>
      <div className="grid grid-cols-2 gap-3 mb-4">
        <StatTile label="Loan Amount" value={formatINR(data.loan_amount)} />
        <StatTile label="Interest Rate" value={data.interest_rate != null ? `${data.interest_rate}%` : '—'} />
        <StatTile label="Tenure" value={data.tenure_years != null ? `${data.tenure_years} years` : '—'} />
        <StatTile label="Monthly EMI" value={formatINR(data.monthly_emi)} />
        <StatTile
          label="CIBIL Score"
          value={data.cibil_score != null ? `${data.cibil_score}${data.cibil_rating ? ` (${data.cibil_rating})` : ''}` : '—'}
        />
        {data.flow_type === 'own_choice' ? (
          <>
            <StatTile label="Purchase Price" value={formatINR(data.purchase_price)} />
            <StatTile label="Bank Valuation" value={formatINR(data.property_value)} />
          </>
        ) : data.flow_type === 'tie_ups' ? (
          <StatTile label="Property Price" value={formatINR(data.property_value)} />
        ) : (
          <StatTile label="Property Value" value={formatINR(data.property_value)} />
        )}
      </div>
      <div className="flex gap-2">
        <button
          onClick={handleComingSoon}
          className="flex-1 bg-gradient-to-tr from-[#1e3a6e] to-[#3b82f6] hover:brightness-110 active:scale-[0.98] text-white text-xs font-bold py-2.5 rounded-xl transition-all shadow-sm"
        >
          Download Sanction Letter
        </button>
        <button
          onClick={handleComingSoon}
          className="flex-1 border border-emerald-300 dark:border-emerald-500/40 text-emerald-700 dark:text-emerald-400 hover:bg-emerald-50 dark:hover:bg-emerald-500/10 active:scale-[0.98] text-xs font-bold py-2.5 rounded-xl transition-all"
        >
          Talk to RM
        </button>
      </div>
    </div>
  );
};

const LoanDecisionCardFromMessage: React.FC<{ content: string }> = ({ content }) => {
  try {
    const data = JSON.parse(content.slice(LOAN_DECISION_PREFIX.length));
    return <LoanDecisionCard data={data} />;
  } catch {
    return null;
  }
};

const APPOINTMENT_BOOKED_PREFIX = 'APPOINTMENT_BOOKED:';

interface AppointmentBookedData {
  appointment_date: string;
  appointment_time: string;
  branch: string;
  contact_phone?: string;
  appointment_id?: string;
}

const AppointmentConfirmedCard: React.FC<{ content: string }> = ({ content }) => {
  let data: AppointmentBookedData | null = null;
  try {
    data = JSON.parse(content.slice(APPOINTMENT_BOOKED_PREFIX.length));
  } catch {
    data = null;
  }
  if (!data) return null;

  return (
    <div className="flex justify-start animate-fade-in">
      <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-[#1e3a6e] to-[#3b82f6] shadow-md shadow-blue-500/10 flex items-center justify-center mr-3 flex-shrink-0 mt-0.5">
        <span className="text-white text-xs font-black">B</span>
      </div>
      <div className="max-w-[72%] rounded-2xl rounded-tl-none border-l-[3px] border-emerald-500 bg-emerald-50/80 dark:bg-emerald-500/10 px-4 py-3 shadow-sm">
        <p className="text-sm font-bold text-emerald-700 dark:text-emerald-400 mb-2">✅ Appointment Confirmed!</p>
        <div className="space-y-1 text-xs text-gray-700 dark:text-gray-200">
          <p>📅 Date: <span className="font-semibold">{data.appointment_date}</span></p>
          <p>🕐 Time: <span className="font-semibold">{data.appointment_time}</span></p>
          <p>🏦 Branch: <span className="font-semibold">{data.branch}</span></p>
          {data.contact_phone && (
            <p>📞 We'll call you at: <span className="font-semibold">{data.contact_phone}</span></p>
          )}
        </div>
        <p className="text-[11px] text-gray-500 dark:text-gray-400 mt-2 leading-relaxed">
          Our property verification team will review your case and contact you before the appointment.
        </p>
      </div>
    </div>
  );
};

const APPOINTMENT_TIME_SLOTS = ['10:00 AM', '11:00 AM', '12:00 PM', '2:00 PM', '3:00 PM', '4:00 PM'];
const APPOINTMENT_BRANCHES = [
  'Ballygunge Branch',
  'Salt Lake Branch',
  'New Town Branch',
  'Dum Dum Branch',
  'Tollygunge Branch',
  'Park Street Branch',
];

function isoDateOffset(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

const AppointmentFormCard: React.FC<{
  sessionId: string;
  token: string | null;
  customerId: string | null;
  customerPhone?: string;
  onConfirm: (message: string) => void;
}> = ({ sessionId, token, customerId, customerPhone, onConfirm }) => {
  const [date, setDate] = useState('');
  const [time, setTime] = useState('');
  const [branch, setBranch] = useState('');
  const [phone, setPhone] = useState(customerPhone ?? '');
  const [status, setStatus] = useState<'idle' | 'booking' | 'error'>('idle');
  const [errorMsg, setErrorMsg] = useState('');
  const [booked, setBooked] = useState(false);

  const reason = 'Property verification — manual review required';
  const canSubmit = !!date && !!time && !!branch && !!phone.trim();

  const handleSubmit = async () => {
    if (!canSubmit || !token || !customerId) return;
    setStatus('booking');
    setErrorMsg('');
    try {
      const data: any = await bookAppointment({
        customer_id: customerId,
        session_id: sessionId,
        appointment_date: date,
        appointment_time: time,
        branch,
        reason,
        contact_phone: phone,
        token,
      });
      if (data?.success) {
        setBooked(true);
        onConfirm(`${APPOINTMENT_BOOKED_PREFIX} ${JSON.stringify({
          appointment_date: date,
          appointment_time: time,
          branch,
          contact_phone: phone,
          appointment_id: data.appointment_id,
        })}`);
      } else {
        setErrorMsg(data?.message || 'Booking failed. Please try again.');
        setStatus('error');
      }
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : 'Booking failed. Please try again.');
      setStatus('error');
    }
  };

  if (booked) return null; // the APPOINTMENT_BOOKED bubble takes over from here

  return (
    <div className="bg-white dark:bg-[#10141f] border border-gray-150 dark:border-gray-800 rounded-2xl shadow-sm max-w-md animate-fade-in overflow-hidden">
      <div className="bg-gradient-to-tr from-[#1e3a6e] to-[#3b82f6] px-5 py-3 flex items-center gap-2">
        <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
          <rect x="3" y="4" width="18" height="18" rx="2" />
          <path strokeLinecap="round" d="M16 2v4M8 2v4M3 10h18" />
        </svg>
        <h3 className="text-sm font-bold text-white">Book an Appointment</h3>
      </div>
      <div className="p-5 space-y-3">
        <div>
          <label className="block text-[11px] font-semibold text-gray-500 dark:text-gray-400 mb-1">Preferred Date</label>
          <input
            type="date"
            value={date}
            min={isoDateOffset(1)}
            max={isoDateOffset(30)}
            onChange={e => setDate(e.target.value)}
            className="w-full text-xs px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 text-gray-800 dark:text-gray-100 outline-none focus:border-[#1e3a6e] dark:focus:border-blue-400"
          />
        </div>
        <div>
          <label className="block text-[11px] font-semibold text-gray-500 dark:text-gray-400 mb-1">Preferred Time</label>
          <select
            value={time}
            onChange={e => setTime(e.target.value)}
            className="w-full text-xs px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 text-gray-800 dark:text-gray-100 outline-none focus:border-[#1e3a6e] dark:focus:border-blue-400"
          >
            <option value="">Select a time</option>
            {APPOINTMENT_TIME_SLOTS.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-[11px] font-semibold text-gray-500 dark:text-gray-400 mb-1">Branch</label>
          <select
            value={branch}
            onChange={e => setBranch(e.target.value)}
            className="w-full text-xs px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 text-gray-800 dark:text-gray-100 outline-none focus:border-[#1e3a6e] dark:focus:border-blue-400"
          >
            <option value="">Select a branch</option>
            {APPOINTMENT_BRANCHES.map(b => <option key={b} value={b}>{b}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-[11px] font-semibold text-gray-500 dark:text-gray-400 mb-1">Contact Phone</label>
          <input
            type="text"
            value={phone}
            onChange={e => setPhone(e.target.value)}
            className="w-full text-xs px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 text-gray-800 dark:text-gray-100 outline-none focus:border-[#1e3a6e] dark:focus:border-blue-400"
          />
        </div>
        <div>
          <label className="block text-[11px] font-semibold text-gray-500 dark:text-gray-400 mb-1">Reason</label>
          <input
            type="text"
            value={reason}
            readOnly
            className="w-full text-xs px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-gray-500 dark:text-gray-400 outline-none cursor-not-allowed"
          />
        </div>

        {status === 'error' && (
          <p className="text-xs text-red-500 dark:text-red-400">{errorMsg}</p>
        )}

        <button
          onClick={handleSubmit}
          disabled={!canSubmit || status === 'booking'}
          className="w-full bg-gradient-to-tr from-[#1e3a6e] to-[#3b82f6] hover:brightness-110 active:scale-[0.98] text-white text-xs font-bold py-2.5 rounded-xl transition-all shadow-sm shadow-blue-500/10 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {status === 'booking' ? 'Booking your appointment...' : 'Confirm Appointment'}
        </button>
      </div>
    </div>
  );
};

interface ExtractedSaleDeedFields {
  registration_number?: string | null;
  owner_name?: string | null;
  owner_pan?: string | null;
  address?: string | null;
  area_sqft?: number | string | null;
  property_type?: string | null;
  document_type?: string | null;
}

const DOCUMENT_DISPLAY_NAMES: Record<string, string> = {
  sale_deed: 'Sale Deed',
  succession_certificate: 'Succession / Will Certificate',
  mutation_certificate: 'Mutation Certificate',
  gift_deed: 'Gift Deed',
  encumbrance_certificate: 'Encumbrance Certificate',
  noc_builder: 'NOC from Builder / Society',
};

interface DocUploadState {
  status: 'idle' | 'uploading' | 'done' | 'error';
  fileName?: string;
  errorMsg?: string;
  extractedFields?: ExtractedSaleDeedFields;
}

const DocumentUploadRow: React.FC<{
  docType: string;
  state: DocUploadState;
  onUpload: (file: File) => void;
}> = ({ docType, state, onUpload }) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const label = DOCUMENT_DISPLAY_NAMES[docType] ?? docType;
  const clickable = state.status !== 'uploading' && state.status !== 'done';

  return (
    <div
      onClick={() => clickable && inputRef.current?.click()}
      className={`border-2 border-dashed rounded-xl p-3.5 flex items-center justify-between gap-3 transition-colors ${
        state.status === 'done'
          ? 'border-emerald-300 dark:border-emerald-500/40 bg-emerald-50/50 dark:bg-emerald-400/5'
          : state.status === 'error'
            ? 'border-red-300 dark:border-red-500/50 cursor-pointer'
            : 'border-gray-200 dark:border-gray-700 hover:border-[#1e3a6e] dark:hover:border-blue-400 cursor-pointer'
      }`}
    >
      <input
        ref={inputRef}
        type="file"
        hidden
        accept=".pdf,.jpg,.jpeg,.png"
        onChange={e => e.target.files?.[0] && onUpload(e.target.files[0])}
      />
      <div className="min-w-0 flex-1">
        <p className="text-xs font-semibold text-gray-700 dark:text-gray-200">{label}</p>
        {state.status === 'idle' && (
          <p className="text-[11px] text-gray-400 dark:text-gray-500 mt-0.5">Click to upload (PDF, JPG, PNG)</p>
        )}
        {state.status === 'uploading' && (
          <p className="text-[11px] text-[#1e3a6e] dark:text-blue-300 mt-0.5">Extracting details with AI...</p>
        )}
        {state.status === 'done' && (
          <p className="text-[11px] text-emerald-600 dark:text-emerald-400 font-medium mt-0.5 truncate">{state.fileName}</p>
        )}
        {state.status === 'error' && (
          <>
            <p className="text-[11px] text-red-500 dark:text-red-400 mt-0.5">{state.errorMsg || 'Upload failed. Try again.'}</p>
            {state.extractedFields && Object.values(state.extractedFields).some(v => v !== null && v !== undefined && v !== '') && (
              <div className="mt-1.5 space-y-0.5 opacity-50">
                <p className="text-[10px] font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wide">Partially extracted</p>
                {Object.entries(state.extractedFields)
                  .filter(([, v]) => v !== null && v !== undefined && v !== '')
                  .map(([key, value]) => (
                    <p key={key} className="text-[10px] text-gray-400 dark:text-gray-500">
                      <span className="font-medium">{key.replace(/_/g, ' ')}:</span> {String(value)}
                    </p>
                  ))}
              </div>
            )}
            <button
              type="button"
              onClick={e => { e.stopPropagation(); inputRef.current?.click(); }}
              className="mt-1.5 text-[11px] font-bold text-[#1e3a6e] dark:text-blue-300 underline"
            >
              Try Again
            </button>
          </>
        )}
      </div>
      {state.status === 'uploading' ? (
        <svg className="w-5 h-5 animate-spin text-[#1e3a6e] dark:text-blue-300 flex-shrink-0" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth={4} />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
      ) : state.status === 'done' ? (
        <svg className="w-5 h-5 text-emerald-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
        </svg>
      ) : (
        <svg className="w-5 h-5 text-gray-400 dark:text-gray-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
        </svg>
      )}
    </div>
  );
};

const SaleDeedUploadCard: React.FC<{
  sessionId: string;
  token: string | null;
  customerId: string | null;
  requiredDocuments?: string[];
  onConfirm: (propertyDataMessage: string) => void;
}> = ({ sessionId, token, customerId, requiredDocuments, onConfirm }) => {
  const docTypes = requiredDocuments && requiredDocuments.length > 0 ? requiredDocuments : ['sale_deed'];
  const [docs, setDocs] = useState<Record<string, DocUploadState>>(() =>
    Object.fromEntries(docTypes.map(d => [d, { status: 'idle' as const }]))
  );
  // Gates the whole checklist: uploads must stay disabled until the
  // pre-populate fetch below has fully resolved. Without this gate, a
  // slow/late-arriving "no documents yet" response (likely on a real
  // network, e.g. Render + Supabase) can land AFTER a fast upload and
  // stomp its freshly-extracted fields back to a bare "done, no fields"
  // state — silently re-disabling Confirm & Proceed after it had already
  // become enabled.
  const [checklistLoading, setChecklistLoading] = useState(true);

  // Pre-populate from documents already uploaded for this session, so
  // coming back to a conversation mid-flow shows the correct state. Must
  // finish (success or error) before any upload is allowed to start.
  useEffect(() => {
    let isMounted = true;

    if (!token) {
      setChecklistLoading(false);
      return () => { isMounted = false; };
    }

    getPropertyDocuments(sessionId, token)
      .then((existing: any) => {
        if (!isMounted || !Array.isArray(existing)) return;
        setDocs(prev => {
          const next = { ...prev };
          for (const row of existing) {
            if (row?.doc_type && next[row.doc_type]) {
              next[row.doc_type] = { status: 'done', fileName: row.file_name };
            }
          }
          return next;
        });
      })
      .catch(() => {})
      .finally(() => {
        if (isMounted) setChecklistLoading(false);
      });

    return () => { isMounted = false; };
  }, [sessionId, token]);

  const handleUpload = async (docType: string, file: File) => {
    if (!token || checklistLoading) return;
    setDocs(prev => ({ ...prev, [docType]: { status: 'uploading', fileName: file.name } }));
    try {
      const data: any = await uploadPropertyDoc(file, docType, sessionId, token, customerId ?? '');
      if (data?.success) {
        setDocs(prev => ({
          ...prev,
          [docType]: { status: 'done', fileName: file.name, extractedFields: data.extracted_fields },
        }));
      } else {
        setDocs(prev => ({
          ...prev,
          [docType]: {
            status: 'error',
            errorMsg: data?.message || 'Could not extract details from this document.',
            extractedFields: data?.extracted_fields,
          },
        }));
      }
    } catch (e) {
      setDocs(prev => ({
        ...prev,
        [docType]: { status: 'error', errorMsg: e instanceof Error ? e.message : 'Upload failed.' },
      }));
    }
  };

  const allUploaded = docTypes.every(d => docs[d]?.status === 'done');

  const mergedFields = docTypes.reduce<ExtractedSaleDeedFields>((merged, d) => {
    const fields = docs[d]?.extractedFields;
    if (!fields) return merged;
    return {
      registration_number: merged.registration_number ?? fields.registration_number,
      owner_name: merged.owner_name ?? fields.owner_name,
      owner_pan: merged.owner_pan ?? fields.owner_pan,
      address: merged.address ?? fields.address,
      area_sqft: merged.area_sqft ?? fields.area_sqft,
    };
  }, {});

  const canConfirm = allUploaded && !!mergedFields.registration_number && !!mergedFields.owner_name;

  // Per-document fields, keyed by doc type — lets the backend cross-check
  // for discrepancies (e.g. mismatched registration numbers) across
  // multi-document acquisition types instead of trusting the client-side
  // merge above blindly.
  const perDocumentFields = docTypes.reduce<Record<string, ExtractedSaleDeedFields>>((acc, d) => {
    if (docs[d]?.extractedFields) acc[d] = docs[d].extractedFields as ExtractedSaleDeedFields;
    return acc;
  }, {});

  const handleConfirm = () => {
    if (!canConfirm) return;
    onConfirm(`PROPERTY_DATA: ${JSON.stringify({ ...mergedFields, _documents: perDocumentFields })}`);
  };

  const title = docTypes.length === 1 && docTypes[0] === 'sale_deed' ? 'Upload Your Sale Deed' : 'Upload Required Documents';

  return (
    <div className="bg-white dark:bg-[#10141f] border border-gray-150 dark:border-gray-800 rounded-2xl p-5 shadow-sm max-w-md animate-fade-in">
      <h3 className="text-sm font-bold text-gray-800 dark:text-gray-100 mb-1">{title}</h3>
      <p className="text-xs text-gray-400 dark:text-gray-500 mb-4">AI will extract details automatically</p>

      {checklistLoading ? (
        <div className="space-y-2.5">
          {docTypes.map(docType => (
            <div
              key={docType}
              className="animate-pulse h-[58px] rounded-xl bg-gray-100 dark:bg-gray-800/60 border-2 border-dashed border-gray-100 dark:border-gray-800"
            />
          ))}
          <p className="text-[11px] text-gray-400 dark:text-gray-500 text-center pt-1">Checking for existing uploads...</p>
        </div>
      ) : (
        <>
          <div className="space-y-2.5">
            {docTypes.map(docType => (
              <DocumentUploadRow
                key={docType}
                docType={docType}
                state={docs[docType] ?? { status: 'idle' }}
                onUpload={file => handleUpload(docType, file)}
              />
            ))}
          </div>

          {allUploaded && !canConfirm && (
            <p className="text-xs text-red-500 dark:text-red-400 mt-3">
              Could not extract required fields. Please upload a clearer document.
            </p>
          )}

          <button
            onClick={handleConfirm}
            disabled={!canConfirm}
            className="w-full mt-3 bg-gradient-to-tr from-[#1e3a6e] to-[#3b82f6] hover:brightness-110 active:scale-[0.98] text-white text-xs font-bold py-2.5 rounded-xl transition-all shadow-sm shadow-blue-500/10 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:brightness-100 disabled:active:scale-100"
          >
            Confirm &amp; Proceed
          </button>
        </>
      )}
    </div>
  );
};

interface ValuationResultData {
  fair_market_value: number;
  distress_value: number;
  max_loan_lap: number;
  max_loan_home: number;
  locality: string;
  locality_rate_per_sqft: number;
  area_sqft: number;
  valuation_grade: 'A' | 'B' | 'C';
  valuation_grade_desc: string;
}

function formatINRFull(n?: number | null): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '—';
  return `₹${Math.round(n).toLocaleString('en-IN')}`;
}

const VALUATION_GRADE_BADGE_STYLES: Record<string, string> = {
  A: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-400/10 dark:text-emerald-400',
  B: 'bg-blue-100 text-blue-700 dark:bg-blue-400/10 dark:text-blue-300',
  C: 'bg-amber-100 text-amber-700 dark:bg-amber-400/10 dark:text-amber-400',
};

const ValuationCard: React.FC<{ data: ValuationResultData }> = ({ data }) => {
  const gradeStyle = VALUATION_GRADE_BADGE_STYLES[data.valuation_grade] ?? VALUATION_GRADE_BADGE_STYLES.C;

  return (
    <div className="rounded-2xl border border-gray-150 dark:border-gray-800 bg-white dark:bg-[#10141f] shadow-sm max-w-md animate-fade-in overflow-hidden">
      <div className="bg-gradient-to-tr from-[#1e3a6e] to-[#3b82f6] px-5 py-3 flex items-center gap-2">
        <span className="text-base">🏠</span>
        <h3 className="text-sm font-bold text-white uppercase tracking-wide">Property Valuation Report</h3>
      </div>
      <div className="p-5 space-y-3">
        <div className="space-y-1.5 text-xs pb-3 border-b border-gray-100 dark:border-gray-800">
          <div className="flex justify-between gap-3">
            <span className="text-gray-500 dark:text-gray-400">Locality</span>
            <span className="font-semibold text-gray-800 dark:text-gray-100 text-right">{data.locality}</span>
          </div>
          <div className="flex justify-between gap-3">
            <span className="text-gray-500 dark:text-gray-400">Area</span>
            <span className="font-semibold text-gray-800 dark:text-gray-100">
              {data.area_sqft?.toLocaleString('en-IN')} sq.ft.
            </span>
          </div>
          <div className="flex justify-between gap-3">
            <span className="text-gray-500 dark:text-gray-400">Circle Rate</span>
            <span className="font-semibold text-gray-800 dark:text-gray-100">
              {formatINRFull(data.locality_rate_per_sqft)}/sq.ft.
            </span>
          </div>
        </div>

        <div className="space-y-1.5 text-xs pb-3 border-b border-gray-100 dark:border-gray-800">
          <div className="flex justify-between gap-3">
            <span className="text-gray-500 dark:text-gray-400">Fair Market Value</span>
            <span className="font-bold text-gray-900 dark:text-gray-50">{formatINRFull(data.fair_market_value)}</span>
          </div>
          <div className="flex justify-between gap-3">
            <span className="text-gray-500 dark:text-gray-400">Distress Value</span>
            <span className="font-semibold text-gray-700 dark:text-gray-300">{formatINRFull(data.distress_value)}</span>
          </div>
          <div className="flex justify-between gap-3 items-center">
            <span className="text-gray-500 dark:text-gray-400">Max Loan (LAP)</span>
            <span className="font-bold text-emerald-600 dark:text-emerald-400">{formatINRFull(data.max_loan_lap)}</span>
          </div>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-500 dark:text-gray-400">Valuation Grade</span>
          <span className={`text-[11px] font-bold px-2 py-1 rounded-lg ${gradeStyle}`}>
            [{data.valuation_grade}] {data.valuation_grade_desc}
          </span>
        </div>
      </div>
    </div>
  );
};

interface ChatWindowProps {
  messages: Message[];
  isTyping: boolean;
  onWelcomeOption: (opt: string) => void;
  sessionId: string;
  token: string | null;
  customerId: string | null;
  customerPhone?: string;
  onNewApplication?: () => void;
  userName?: string | null;
}

const CardSpotlight: React.FC<{
  label: string;
  desc: string;
  bgClass: string;
  spotlightColor: string;
  textAccentClass: string;
  onClick: () => void;
}> = ({ label, desc, bgClass, spotlightColor, textAccentClass, onClick }) => {
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const [tilt, setTilt] = useState({ rx: 0, ry: 0 });
  const [isHovered, setIsHovered] = useState(false);

  const handleMouseMove = (e: React.MouseEvent<HTMLButtonElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    setMousePos({ x, y });

    // 3D tilt calculation
    const xc = rect.width / 2;
    const yc = rect.height / 2;
    const rx = -((y - yc) / yc) * 4; // max 4 degrees
    const ry = ((x - xc) / xc) * 4;  // max 4 degrees
    setTilt({ rx, ry });
  };

  const handleMouseLeave = () => {
    setIsHovered(false);
    setTilt({ rx: 0, ry: 0 });
  };

  return (
    <button
      onClick={onClick}
      onMouseMove={handleMouseMove}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={handleMouseLeave}
      style={{
        transform: `perspective(800px) rotateX(${tilt.rx}deg) rotateY(${tilt.ry}deg)`,
        transition: isHovered ? 'none' : 'transform 0.5s cubic-bezier(0.16, 1, 0.3, 1)',
      }}
      className={`relative overflow-hidden border border-gray-200/80 dark:border-gray-800/80 rounded-2xl p-4 text-left hover:shadow-xl active:scale-[0.98] transition-all duration-300 group shadow-sm flex flex-col justify-between min-h-[96px] w-full bg-gradient-to-br ${bgClass}`}
    >
      {/* Spotlight layer */}
      <div
        className="absolute inset-0 pointer-events-none transition-opacity duration-300"
        style={{
          opacity: isHovered ? 1 : 0,
          background: `radial-gradient(130px circle at ${mousePos.x}px ${mousePos.y}px, ${spotlightColor}, transparent 80%)`,
        }}
      />
      
      <div className="z-10">
        <p className={`text-[15px] font-bold transition-colors mb-1 ${textAccentClass}`}>
          {label}
        </p>
        <p className="text-xs text-gray-400 dark:text-gray-500 font-medium leading-relaxed">
          {desc}
        </p>
      </div>

      <div className={`z-10 mt-2 flex items-center gap-1.5 text-[11px] font-semibold opacity-0 group-hover:opacity-100 group-hover:translate-x-1 transition-all duration-300 ${textAccentClass}`}>
        <span>Get Started</span>
        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
        </svg>
      </div>
    </button>
  );
};

const InteractiveBotLogo: React.FC = () => {
  return (
    <div className="relative w-16 h-16 mb-6 group cursor-pointer z-10">
      {/* Glowing ring */}
      <div className="absolute inset-0 rounded-2xl bg-blue-500/25 dark:bg-blue-400/15 blur-xl group-hover:scale-125 transition-transform duration-500 animate-pulse" />
      
      {/* Main logo frame */}
      <div className="relative w-full h-full rounded-2xl bg-gradient-to-tr from-[#1e3a6e] to-[#3b82f6] flex items-center justify-center shadow-xl shadow-blue-500/20 group-hover:scale-105 group-hover:rotate-6 transition-all duration-300">
        <svg className="w-8 h-8 text-white group-hover:scale-110 transition-transform" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
          {/* Shield frame */}
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7s0 6 8 10z" />
          {/* Bank pillars */}
          <path d="M8 17h8" />
          <path d="M9 17v-4" />
          <path d="M12 17v-4" />
          <path d="M15 17v-4" />
          <path d="M9 11h6" />
          <path d="M12 8l4 3H8l4-3z" />
        </svg>
        
        {/* Animated AI node indicator */}
        <span className="absolute -top-1 -right-1 w-3 h-3 bg-emerald-400 dark:bg-emerald-300 rounded-full border-2 border-[#1e3a6e] shadow-sm animate-ping" />
        <span className="absolute -top-1 -right-1 w-3 h-3 bg-emerald-500 dark:bg-emerald-400 rounded-full border-2 border-[#1e3a6e] shadow-sm" />
      </div>
    </div>
  );
};

function getGreetingTimeWord(): string {
  const h = new Date().getHours();
  if (h < 12) return 'Morning';
  if (h < 17) return 'Afternoon';
  return 'Evening';
}

function isGreetingMessage(msg: Message): boolean {
  return (
    msg.role === 'assistant' &&
    /^(Good (morning|afternoon|evening)|Let's start fresh)/i.test(msg.content)
  );
}

export const ChatWindow: React.FC<ChatWindowProps> = ({ messages, isTyping, onWelcomeOption, sessionId, token, customerId, customerPhone, onNewApplication, userName }) => {
  const bottomRef = useRef<HTMLDivElement>(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  // Tracks whether the user has dismissed the post-decision advisor prompt
  const [advisorPromptDismissed, setAdvisorPromptDismissed] = useState(false);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    setMousePos({
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
    });
  };

  // Once a LOAN_DECISION_CARD has been rendered, the application is
  // complete — disable older MCQ buttons so they can't re-trigger a flow
  // that no longer makes sense. Derived from `messages` rather than
  // imperatively tracked, so "New Application" clearing the message list
  // (see App.tsx's handleNewApplication -> resetChat) naturally resets it.
  const [loanDecisionMade, setLoanDecisionMade] = useState(false);
  useEffect(() => {
    setLoanDecisionMade(messages.some(m => m.content.startsWith(LOAN_DECISION_PREFIX)));
  }, [messages]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  // Guest landing cards — only shown when no messages (unauthenticated).
  const guestCards = [
    { label: 'Existing Customer', desc: 'Login and continue application', bgClass: 'from-blue-50/60 to-indigo-50/60 dark:from-[#11172a]/70 dark:to-[#0f172a]/70 hover:border-blue-500/50', spotlightColor: 'rgba(59, 130, 246, 0.15)', textAccentClass: 'text-blue-600 dark:text-blue-300' },
    { label: 'Just Browsing', desc: 'Explore rates & services', bgClass: 'from-emerald-50/60 to-teal-50/60 dark:from-[#0b1b19]/70 dark:to-[#061413]/70 hover:border-emerald-500/50', spotlightColor: 'rgba(16, 185, 129, 0.15)', textAccentClass: 'text-emerald-600 dark:text-emerald-300' },
  ];

  // Three display states:
  //  showWelcome  — no messages at all (unauthenticated landing)
  //  showGreeting — exactly one greeting message, no typing yet (just logged in)
  //  showChat     — normal conversation view
  const showWelcome = messages.length === 0 && !isTyping;
  const showGreeting = messages.length === 1 && !isTyping && isGreetingMessage(messages[0]);
  const showChat = !showWelcome && !showGreeting;
  const firstName = (userName || 'there').split(' ')[0];

  return (
    <div 
      onMouseMove={handleMouseMove}
      className="flex-1 flex flex-col overflow-hidden relative bg-gradient-to-br from-[#eef2ff] via-[#f5f3ff] to-[#e0f2fe] dark:from-[#0a0e1f] dark:via-[#111530] dark:to-[#0a1422]"
    >
      {/* Ambient interactive mouse glow */}
      <div 
        className="absolute inset-0 pointer-events-none transition-opacity duration-300 opacity-70 dark:opacity-50"
        style={{
          background: `radial-gradient(700px circle at ${mousePos.x}px ${mousePos.y}px, rgba(99, 102, 241, 0.1), transparent 85%)`
        }}
      />

      {/* Ambient glow decorative blobs */}
      <div className="absolute top-1/4 left-1/4 w-72 h-72 bg-blue-200/40 dark:bg-blue-500/10 rounded-full blur-3xl -z-10 pointer-events-none" />
      <div className="absolute bottom-1/4 right-1/4 w-80 h-80 bg-indigo-200/40 dark:bg-indigo-500/10 rounded-full blur-3xl -z-10 pointer-events-none" />

      {/* Message timeline viewport */}
      <div className={`overflow-y-auto px-6 py-6 space-y-4 transition-all duration-500 ${
        showChat ? 'flex-1 opacity-100 h-full' : 'opacity-0 pointer-events-none h-0 py-0'
      }`}>
        {messages.map((msg) => {
          // The Sale Deed confirm-and-proceed payload is an internal signal
          // to the backend, not something the user should see as a chat bubble.
          if (msg.role === 'user' && msg.content.startsWith('PROPERTY_DATA:')) {
            return null;
          }
          // The appointment-booked notification is internal too (sent right
          // after a successful /appointments/book call) — render the
          // confirmation card in its place instead of the raw JSON, for
          // either role since the frontend sends it as a "user" message.
          if (msg.content.startsWith(APPOINTMENT_BOOKED_PREFIX)) {
            return (
              <div key={msg.id} className="space-y-2">
                <AppointmentConfirmedCard content={msg.content} />
              </div>
            );
          }
          return (
          <div key={msg.id} className="space-y-2">
            <MessageBubble message={msg} />

            {/* Loan already approved this session — hard stop from the backend.
                Rendered as plain styled text (not a card), with a prominent
                button that does exactly what the sidebar's New Application
                button does. */}
            {msg.role === 'assistant' && msg.type === 'loan_already_approved' && onNewApplication && (
              <div className="pl-11 animate-fade-in">
                <button
                  onClick={onNewApplication}
                  className="bg-gradient-to-tr from-[#1e3a6e] to-[#3b82f6] hover:brightness-110 active:scale-[0.98] text-white text-xs font-bold px-4 py-2.5 rounded-xl transition-all shadow-sm shadow-blue-500/10"
                >
                  Start New Application
                </button>
              </div>
            )}

            {/* Render options if this is an assistant message and has options */}
            {msg.role === 'assistant' && msg.options && msg.options.length > 0 && (
              <div className="pl-11 flex flex-wrap gap-2 animate-fade-in">
                {msg.options.map((opt: any) => (
                  <button
                    key={opt.id || opt.label}
                    onClick={() => !loanDecisionMade && onWelcomeOption(opt.label)}
                    disabled={loanDecisionMade}
                    title={loanDecisionMade ? 'Application complete. Click New Application to start fresh.' : undefined}
                    className={`bg-white/90 dark:bg-[#111625]/90 border border-blue-500/25 dark:border-blue-400/20 text-xs font-bold text-blue-600 dark:text-blue-300 px-4 py-2.5 rounded-xl hover:border-blue-500 dark:hover:border-blue-400 hover:bg-blue-500/5 dark:hover:bg-blue-400/10 hover:shadow-md hover:shadow-blue-500/5 active:scale-[0.97] transition-all duration-200 shadow-sm ${loanDecisionMade ? 'opacity-50 cursor-not-allowed' : ''}`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            )}

            {/* Render property list if this is an assistant message and has properties */}
            {msg.role === 'assistant' && msg.properties && msg.properties.length > 0 && (
              <div className="pl-11 grid grid-cols-1 sm:grid-cols-2 gap-4 w-full animate-fade-in max-w-2xl">
                {msg.properties.map((prop: any) => (
                  <div
                    key={prop.property_id}
                    className="bg-white dark:bg-[#10141f] border border-gray-150 dark:border-gray-800 rounded-2xl p-5 hover:shadow-lg transition-all duration-300 transform hover:-translate-y-0.5 flex flex-col justify-between"
                  >
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-[10px] font-extrabold text-[#1e3a6e] dark:text-blue-300 bg-[#1e3a6e]/10 dark:bg-blue-400/10 px-2 py-0.5 rounded-md uppercase tracking-wider">
                          {prop.property_id}
                        </span>
                        <span className="text-xs font-semibold text-gray-400 dark:text-gray-500">
                          {prop.city}
                        </span>
                      </div>
                      <h3 className="text-sm font-bold text-gray-800 dark:text-gray-100 line-clamp-2 mb-2">
                        {prop.address}
                      </h3>
                      <div className="flex items-center gap-4 text-xs text-gray-500 dark:text-gray-400 font-medium mb-3">
                        <span className="flex items-center gap-1">
                          🏠 {prop.area_sqft} sqft
                        </span>
                        <span className="flex items-center gap-1">
                          🛏️ {prop.bedrooms} BHK
                        </span>
                      </div>
                      {(prop.crime_rate || prop.transit || (prop.nearby_schools && prop.nearby_schools.length > 0) || (prop.hospitals && prop.hospitals.length > 0)) && (
                        <div className="mt-3 pt-3 border-t border-gray-100/70 dark:border-gray-800 space-y-1.5 text-xs text-gray-600 dark:text-gray-400 font-medium">
                          {prop.crime_rate && (
                            <div className="flex items-start gap-1.5">
                              <span className="text-gray-400 dark:text-gray-500 flex-shrink-0" title="Crime Rate">🛡️</span>
                              <span className="text-[11px] leading-snug"><strong className="text-gray-700 dark:text-gray-200 font-semibold font-bold">Crime:</strong> {prop.crime_rate}</span>
                            </div>
                          )}
                          {prop.transit && (
                            <div className="flex items-start gap-1.5">
                              <span className="text-gray-400 dark:text-gray-500 flex-shrink-0" title="Transit (Metro/Bus/Train)">🚇</span>
                              <span className="text-[11px] leading-snug">
                                <strong className="text-gray-700 dark:text-gray-200 font-semibold font-bold">Transit:</strong> Metro ({prop.transit.metro}) | Bus ({prop.transit.bus}) | Train ({prop.transit.train})
                              </span>
                            </div>
                          )}
                          {prop.nearby_schools && prop.nearby_schools.length > 0 && (
                            <div className="flex items-start gap-1.5">
                              <span className="text-gray-400 dark:text-gray-500 flex-shrink-0" title="Nearby Schools">🏫</span>
                              <span className="text-[11px] leading-snug">
                                <strong className="text-gray-700 dark:text-gray-200 font-semibold font-bold">Schools:</strong> {prop.nearby_schools.join(', ')}
                              </span>
                            </div>
                          )}
                          {prop.hospitals && prop.hospitals.length > 0 && (
                            <div className="flex items-start gap-1.5">
                              <span className="text-gray-400 dark:text-gray-500 flex-shrink-0" title="Hospitals">🏥</span>
                              <span className="text-[11px] leading-snug">
                                <strong className="text-gray-700 dark:text-gray-200 font-semibold font-bold">Hospitals:</strong> {prop.hospitals.join(', ')}
                              </span>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                    <div className="border-t border-gray-100 dark:border-gray-800 pt-3 flex items-center justify-between mt-3">
                      <div>
                        <p className="text-[10px] font-bold text-gray-400 dark:text-gray-500 uppercase leading-none">Price</p>
                        <p className="text-sm font-black text-gray-900 dark:text-gray-50 mt-1">
                          ₹{(prop.listed_price / 100000).toFixed(1)} Lakh
                        </p>
                      </div>
                      <button
                        onClick={() => onWelcomeOption(prop.property_id)}
                        className="bg-gradient-to-tr from-[#1e3a6e] to-[#3b82f6] hover:brightness-110 active:scale-95 text-[11px] font-bold text-white px-3.5 py-2 rounded-xl transition-all shadow-sm shadow-blue-500/10"
                      >
                        Select
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Property document checklist — OCR extracts fields per document, user confirms to trigger verification */}
            {msg.role === 'assistant' && msg.type === 'property_document_upload' && (
              <div className="pl-11 animate-fade-in">
                <SaleDeedUploadCard
                  sessionId={sessionId}
                  token={token}
                  customerId={customerId}
                  requiredDocuments={msg.metadata?.required_documents as string[] | undefined}
                  onConfirm={onWelcomeOption}
                />
              </div>
            )}

            {/* Manual-review appointment booking form */}
            {msg.role === 'assistant' && msg.type === 'appointment_form' && (
              <div className="pl-11 animate-fade-in">
                <AppointmentFormCard
                  sessionId={sessionId}
                  token={token}
                  customerId={customerId}
                  customerPhone={customerPhone}
                  onConfirm={onWelcomeOption}
                />
              </div>
            )}

            {/* Property valuation report — shown below the text summary whenever this
                turn ran the valuation step, regardless of which node ended up terminal
                for it (the auto-chain means valuation never stops there itself). */}
            {msg.role === 'assistant' && !!msg.metadata?.valuation_result && (
              <div className="pl-11 animate-fade-in">
                <ValuationCard data={msg.metadata.valuation_result as ValuationResultData} />
              </div>
            )}

            {/* Final loan decision — rendered as a card, raw JSON hidden by MessageBubble */}
            {msg.role === 'assistant' && msg.content.startsWith(LOAN_DECISION_PREFIX) && (
              <>
                <div className="pl-11 animate-fade-in">
                  <LoanDecisionCardFromMessage content={msg.content} />
                </div>
                {/* Advisor prompt — answers are sent as chat messages so the
                    financial advisor continues IN the main chat (the graph's
                    financial_advisor node handles "Yes, help me"/"No, thanks") */}
                {!advisorPromptDismissed && (
                  <div className="pl-11 mt-3 animate-fade-in">
                    <div className="bg-violet-50/80 dark:bg-violet-950/30 border border-violet-100 dark:border-violet-900/40 rounded-2xl px-4 py-3 max-w-sm">
                      <p className="text-xs font-semibold text-violet-700 dark:text-violet-300 mb-2.5 flex items-center gap-1.5">
                        <svg className="w-3.5 h-3.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
                          <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                        </svg>
                        Would you like personalised financial recommendations?
                      </p>
                      <div className="flex gap-2">
                        <button
                          onClick={() => { setAdvisorPromptDismissed(true); onWelcomeOption('Yes, help me'); }}
                          className="flex-1 text-[11px] font-bold text-white bg-gradient-to-tr from-violet-600 to-purple-500 hover:brightness-110 active:scale-[0.97] py-2 rounded-xl transition-all shadow-sm shadow-purple-500/15"
                        >
                          Yes, help me
                        </button>
                        <button
                          onClick={() => { setAdvisorPromptDismissed(true); onWelcomeOption('No, thanks'); }}
                          className="flex-1 text-[11px] font-bold text-violet-600 dark:text-violet-400 border border-violet-200 dark:border-violet-800/60 hover:bg-violet-50 dark:hover:bg-violet-900/20 py-2 rounded-xl transition-all"
                        >
                          No, thanks
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
          );
        })}
        {isTyping && (
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-[#1e3a6e] to-[#3b82f6] flex items-center justify-center flex-shrink-0 shadow-sm">
              <span className="text-white text-xs font-black">B</span>
            </div>
            <div className="bg-white/80 dark:bg-[#161b29]/90 rounded-2xl rounded-tl-none px-4 py-3 border border-gray-100 dark:border-gray-800 flex gap-1.5 items-center shadow-sm">
              {[0, 1, 2].map(i => (
                <span
                  key={i}
                  className="w-1.5 h-1.5 bg-gray-400 dark:bg-gray-500 rounded-full animate-bounce"
                  style={{ animationDelay: `${i * 150}ms` }}
                />
              ))}
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Claude-style authenticated greeting (just logged in / new application) */}
      <div className={`w-full transition-all duration-500 ease-in-out flex flex-col items-center justify-center px-8 text-center z-10 ${
        showGreeting
          ? 'flex-1 opacity-100 translate-y-0'
          : 'h-0 opacity-0 overflow-hidden pointer-events-none'
      }`}>
        <h1 className="text-5xl sm:text-6xl font-light text-gray-800 dark:text-gray-100 tracking-tight mb-3">
          {getGreetingTimeWord()}, {firstName}
        </h1>
        <p className="text-base text-gray-500 dark:text-gray-400 font-medium mb-10">
          How can I help you today?
        </p>
        <div className="flex flex-wrap gap-2.5 justify-center">
          {(messages[0]?.options || []).map((opt: any) => (
            <button
              key={opt.id || opt.label}
              onClick={() => onWelcomeOption(opt.label)}
              className="bg-white/90 dark:bg-[#111625]/90 border border-blue-500/25 dark:border-blue-400/20 text-sm font-semibold text-blue-600 dark:text-blue-300 px-5 py-2.5 rounded-xl hover:border-blue-500 dark:hover:border-blue-400 hover:bg-blue-500/5 dark:hover:bg-blue-400/10 hover:shadow-md active:scale-[0.97] transition-all duration-200 shadow-sm"
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Unauthenticated landing — "Welcome to BankWise AI" with cards */}
      <div className={`w-full transition-all duration-700 ease-in-out flex flex-col items-center justify-center px-6 text-center z-10 ${
        showWelcome
          ? 'flex-1 opacity-100 scale-100 translate-y-0'
          : 'h-0 opacity-0 scale-95 -translate-y-12 overflow-hidden pointer-events-none py-0'
      }`}>
        <div className="w-full max-w-xl flex flex-col items-center text-center">
          <InteractiveBotLogo />

          <h1 className="text-4xl sm:text-5xl font-extrabold text-gray-900 dark:text-gray-50 tracking-tight mb-4 flex flex-col sm:flex-row items-center justify-center gap-2">
            <span>Welcome to</span>
            <span className="relative pb-2 text-transparent bg-clip-text bg-gradient-to-r from-blue-600 via-indigo-500 to-purple-600 dark:from-blue-400 dark:via-indigo-300 dark:to-purple-400 font-black">
              BankWise AI
              <svg className="absolute left-0 bottom-0 w-full h-2.5 text-blue-500/80 dark:text-blue-400/80" viewBox="0 0 100 10" preserveAspectRatio="none">
                <path d="M2 7 C 20 2, 80 2, 98 7" stroke="currentColor" strokeWidth="3.5" fill="none" strokeLinecap="round" className="animate-draw-line" />
              </svg>
            </span>
          </h1>

          <p className="text-sm text-gray-500 dark:text-gray-400 max-w-md leading-relaxed mb-6 font-medium">
            Your intelligent loan assistant. I can help you with loan applications, property verification, eligibility checks, and more.
          </p>

          <div className="grid grid-cols-2 gap-3 w-full">
            {guestCards.map(opt => (
              <CardSpotlight
                key={opt.label}
                label={opt.label}
                desc={opt.desc}
                bgClass={opt.bgClass}
                spotlightColor={opt.spotlightColor}
                textAccentClass={opt.textAccentClass}
                onClick={() => onWelcomeOption(opt.label)}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
