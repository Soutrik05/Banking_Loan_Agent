import React, { useState } from 'react';
import { checkEligibility } from '../services/api';

interface EligibilityPageProps {
  token: string | null;
}

export const EligibilityPage: React.FC<EligibilityPageProps> = ({ token }) => {
  const [form, setForm] = useState({ income: '', obligations: '', tenure: '20', rate: '8.35' });
  const [result, setResult] = useState<{ eligible: number; emi: number } | null>(null);
  const [loading, setLoading] = useState(false);

  const set = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }));

  const calculate = async () => {
    // Local fallback calculation (used when no token/backend)
    const monthly = +form.income - +form.obligations;
    const maxEMI = monthly * 0.5;
    const r = +form.rate / 100 / 12;
    const n = +form.tenure * 12;
    const eligible = Math.round(maxEMI * (1 - Math.pow(1 + r, -n)) / r);
    const emi = Math.round(eligible * r / (1 - Math.pow(1 + r, -n)));
    setResult({ eligible, emi });

    // 🔌 BACKEND call (when token available)
    if (token) {
      setLoading(true);
      try {
        const data: any = await checkEligibility(form, token); // 🔌 BACKEND: POST /eligibility/check
        setResult({ eligible: data.eligible_amount, emi: data.estimated_emi });
      } catch { /* use local result */ }
      finally { setLoading(false); }
    }
  };

  const inp = (label: string, key: string, placeholder: string, prefix?: string) => (
    <div style={{ marginBottom: 16 }}>
      <label style={{ fontSize: 12, fontWeight: 600, color: '#374151', display: 'block', marginBottom: 6 }}>{label}</label>
      <div style={{ display: 'flex', alignItems: 'center', border: '1px solid #e5e7eb', borderRadius: 10, overflow: 'hidden' }}>
        {prefix && <span style={{ padding: '10px 12px', background: '#f9fafb', fontSize: 13, color: '#6b7280', borderRight: '1px solid #e5e7eb' }}>{prefix}</span>}
        <input type="number" value={(form as any)[key]} placeholder={placeholder}
          onChange={e => set(key, e.target.value)}
          style={{ flex: 1, padding: '10px 14px', border: 'none', fontSize: 14, outline: 'none' }} />
      </div>
    </div>
  );

  return (
    <div style={{ maxWidth: 560, margin: '0 auto', padding: '32px 24px' }}>
      <h2 style={{ fontSize: 20, fontWeight: 700, color: '#111827', marginBottom: 6 }}>Eligibility Check</h2>
      <p style={{ fontSize: 13, color: '#6b7280', marginBottom: 28 }}>Find out how much loan you qualify for.</p>

      {inp('Monthly Income', 'income', '80000', '₹')}
      {inp('Existing EMI / Obligations', 'obligations', '0', '₹')}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
        <div>
          <label style={{ fontSize: 12, fontWeight: 600, color: '#374151', display: 'block', marginBottom: 6 }}>Tenure (years)</label>
          <select value={form.tenure} onChange={e => set('tenure', e.target.value)}
            style={{ width: '100%', padding: '10px 14px', borderRadius: 10, border: '1px solid #e5e7eb', fontSize: 14, background: 'white', outline: 'none' }}>
            {['10','15','20','25','30'].map(t => <option key={t} value={t}>{t} years</option>)}
          </select>
        </div>
        <div>
          <label style={{ fontSize: 12, fontWeight: 600, color: '#374151', display: 'block', marginBottom: 6 }}>Interest Rate</label>
          <select value={form.rate} onChange={e => set('rate', e.target.value)}
            style={{ width: '100%', padding: '10px 14px', borderRadius: 10, border: '1px solid #e5e7eb', fontSize: 14, background: 'white', outline: 'none' }}>
            {['8.35','8.50','8.75','9.00'].map(r => <option key={r} value={r}>{r}%</option>)}
          </select>
        </div>
      </div>

      <button onClick={calculate} disabled={!form.income || loading}
        style={{ width: '100%', padding: '12px', borderRadius: 12, background: '#1e3a6e', color: 'white', border: 'none', fontSize: 14, fontWeight: 600, cursor: 'pointer', opacity: !form.income ? 0.5 : 1 }}>
        {loading ? 'Checking…' : 'Check Eligibility'}
      </button>

      {result && (
        <div style={{ marginTop: 24, background: 'linear-gradient(135deg,#1e3a6e,#2d5be3)', borderRadius: 16, padding: 24, color: 'white' }}>
          <p style={{ fontSize: 13, opacity: 0.8, marginBottom: 8 }}>Maximum Loan Eligible</p>
          <p style={{ fontSize: 36, fontWeight: 800 }}>₹{(result.eligible/100000).toFixed(1)}<span style={{ fontSize: 18, fontWeight: 500 }}> Lakhs</span></p>
          <div style={{ marginTop: 16, paddingTop: 16, borderTop: '1px solid rgba(255,255,255,.2)', display: 'flex', justifyContent: 'space-between' }}>
            <div>
              <p style={{ fontSize: 11, opacity: 0.7 }}>Estimated EMI</p>
              <p style={{ fontSize: 18, fontWeight: 700 }}>₹{result.emi.toLocaleString('en-IN')}/mo</p>
            </div>
            <div>
              <p style={{ fontSize: 11, opacity: 0.7 }}>Tenure</p>
              <p style={{ fontSize: 18, fontWeight: 700 }}>{form.tenure} years</p>
            </div>
            <div>
              <p style={{ fontSize: 11, opacity: 0.7 }}>Rate</p>
              <p style={{ fontSize: 18, fontWeight: 700 }}>{form.rate}% p.a.</p>
            </div>
          </div>
          <p style={{ fontSize: 11, opacity: 0.6, marginTop: 12 }}>* Based on 50% FOIR. Actual eligibility may vary.</p>
        </div>
      )}
    </div>
  );
};
