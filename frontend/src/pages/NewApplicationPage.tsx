import React, { useState } from 'react';
import { FileUploader } from '../components/FileUploader';

interface NewApplicationPageProps {
  token: string;
  onSubmit: (data: object) => Promise<void>;
  onSaveDraft: (data: object) => void;
}

const STEPS = ['Loan Details', 'Personal Info', 'KYC & Documents', 'Review'];

export const NewApplicationPage: React.FC<NewApplicationPageProps> = ({ token, onSubmit, onSaveDraft }) => {
  const [step, setStep] = useState(0);
  const [form, setForm] = useState({
    loanType: 'home', amount: '', tenure: '20',
    fullName: '', dob: '', pan: '', aadhaar: '',
    employment: 'salaried', monthlyIncome: '', employer: '',
    propertyAddress: '', propertyValue: '',
    panDocUrl: '', aadhaarDocUrl: '', incomeDocUrl: '',
  });

  const set = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }));
  const next = () => setStep(s => Math.min(s + 1, STEPS.length - 1));
  const prev = () => setStep(s => Math.max(s - 1, 0));

  const inp = (label: string, key: string, type = 'text', placeholder = '') => (
    <div style={{ marginBottom: 16 }}>
      <label style={{ fontSize: 12, fontWeight: 600, color: '#374151', display: 'block', marginBottom: 6 }}>{label}</label>
      <input
        type={type} value={(form as any)[key]} placeholder={placeholder}
        onChange={e => set(key, e.target.value)}
        style={{ width: '100%', padding: '10px 14px', borderRadius: 10, border: '1px solid #e5e7eb', fontSize: 14, outline: 'none' }}
      />
    </div>
  );

  const sel = (label: string, key: string, options: {v:string,l:string}[]) => (
    <div style={{ marginBottom: 16 }}>
      <label style={{ fontSize: 12, fontWeight: 600, color: '#374151', display: 'block', marginBottom: 6 }}>{label}</label>
      <select value={(form as any)[key]} onChange={e => set(key, e.target.value)}
        style={{ width: '100%', padding: '10px 14px', borderRadius: 10, border: '1px solid #e5e7eb', fontSize: 14, outline: 'none', background: 'white' }}>
        {options.map(o => <option key={o.v} value={o.v}>{o.l}</option>)}
      </select>
    </div>
  );

  return (
    <div style={{ maxWidth: 640, margin: '0 auto', padding: '32px 24px' }}>
      {/* Progress */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 0, marginBottom: 40 }}>
        {STEPS.map((s, i) => (
          <React.Fragment key={s}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flex: 1 }}>
              <div style={{
                width: 32, height: 32, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 13, fontWeight: 600,
                background: i < step ? '#00b894' : i === step ? '#1e3a6e' : '#e5e7eb',
                color: i <= step ? 'white' : '#9ca3af',
              }}>
                {i < step ? '✓' : i + 1}
              </div>
              <p style={{ fontSize: 11, color: i === step ? '#1e3a6e' : '#9ca3af', fontWeight: i === step ? 600 : 400, marginTop: 6, textAlign: 'center' }}>{s}</p>
            </div>
            {i < STEPS.length - 1 && (
              <div style={{ flex: 1, height: 2, background: i < step ? '#00b894' : '#e5e7eb', marginBottom: 24 }} />
            )}
          </React.Fragment>
        ))}
      </div>

      {/* Step 0: Loan Details */}
      {step === 0 && (
        <div>
          <h2 style={{ fontSize: 18, fontWeight: 700, color: '#111827', marginBottom: 24 }}>Loan Details</h2>
          {sel('Loan Type', 'loanType', [
            { v:'home', l:'Home Loan' }, { v:'lap', l:'Loan Against Property' }, { v:'construction', l:'Construction Loan' }
          ])}
          {inp('Loan Amount (₹)', 'amount', 'number', '3000000')}
          {inp('Property Address', 'propertyAddress', 'text', '123 MG Road, Bangalore 560001')}
          {inp('Property Value (₹)', 'propertyValue', 'number', '5000000')}
          {sel('Loan Tenure', 'tenure', [
            { v:'10', l:'10 years' }, { v:'15', l:'15 years' }, { v:'20', l:'20 years' }, { v:'25', l:'25 years' }, { v:'30', l:'30 years' }
          ])}

          {/* EMI preview */}
          {form.amount && (
            <div style={{ background: '#eff6ff', borderRadius: 12, padding: 16, marginTop: 8 }}>
              <p style={{ fontSize: 12, color: '#1e3a6e', fontWeight: 600 }}>Estimated EMI</p>
              <p style={{ fontSize: 22, fontWeight: 700, color: '#1e3a6e', marginTop: 4 }}>
                ₹{Math.round((+form.amount * 0.0835/12) / (1 - Math.pow(1 + 0.0835/12, -+form.tenure*12))).toLocaleString('en-IN')}
                <span style={{ fontSize: 13, fontWeight: 400, color: '#3b82f6' }}>/month</span>
              </p>
              <p style={{ fontSize: 11, color: '#6b7280', marginTop: 2 }}>At 8.35% p.a. for {form.tenure} years</p>
            </div>
          )}
        </div>
      )}

      {/* Step 1: Personal Info */}
      {step === 1 && (
        <div>
          <h2 style={{ fontSize: 18, fontWeight: 700, color: '#111827', marginBottom: 24 }}>Personal Information</h2>
          {inp('Full Name (as per PAN)', 'fullName', 'text', 'Arjun Sharma')}
          {inp('Date of Birth', 'dob', 'date')}
          {inp('PAN Number', 'pan', 'text', 'ABCDE1234F')}
          {inp('Aadhaar Number', 'aadhaar', 'text', '1234 5678 9012')}
          {sel('Employment Type', 'employment', [
            { v:'salaried', l:'Salaried' }, { v:'self', l:'Self-Employed' }, { v:'business', l:'Business Owner' }
          ])}
          {inp('Monthly Income (₹)', 'monthlyIncome', 'number', '80000')}
          {inp('Employer / Business Name', 'employer', 'text', 'Infosys Ltd.')}
        </div>
      )}

      {/* Step 2: KYC & Documents */}
      {step === 2 && (
        <div>
          <h2 style={{ fontSize: 18, fontWeight: 700, color: '#111827', marginBottom: 24 }}>KYC & Documents</h2>
          <p style={{ fontSize: 13, color: '#6b7280', marginBottom: 20 }}>
            Upload clear scanned copies. Supported formats: PDF, JPG, PNG (max 5MB each).
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: '#374151', display: 'block', marginBottom: 8 }}>PAN Card</label>
              {/* 🔌 BACKEND: POST /documents/upload (type=pan) */}
              <FileUploader label="PAN Card (front)" docType="pan" token={token} onUploaded={url => set('panDocUrl', url)} />
            </div>
            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: '#374151', display: 'block', marginBottom: 8 }}>Aadhaar Card</label>
              {/* 🔌 BACKEND: POST /documents/upload (type=aadhaar) */}
              <FileUploader label="Aadhaar (front & back)" docType="aadhaar" token={token} onUploaded={url => set('aadhaarDocUrl', url)} />
            </div>
            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: '#374151', display: 'block', marginBottom: 8 }}>Income Proof</label>
              {/* 🔌 BACKEND: POST /documents/upload (type=income) */}
              <FileUploader label="Last 3 months salary slips / ITR" docType="income" token={token} onUploaded={url => set('incomeDocUrl', url)} />
            </div>
          </div>
        </div>
      )}

      {/* Step 3: Review */}
      {step === 3 && (
        <div>
          <h2 style={{ fontSize: 18, fontWeight: 700, color: '#111827', marginBottom: 24 }}>Review & Submit</h2>
          {[
            ['Loan Type', form.loanType === 'home' ? 'Home Loan' : form.loanType],
            ['Amount', `₹${Number(form.amount).toLocaleString('en-IN')}`],
            ['Tenure', `${form.tenure} years`],
            ['Applicant', form.fullName],
            ['PAN', form.pan],
            ['Monthly Income', `₹${Number(form.monthlyIncome).toLocaleString('en-IN')}`],
            ['Property', form.propertyAddress],
          ].map(([k, v]) => (
            <div key={k} style={{ display: 'flex', justifyContent: 'space-between', padding: '12px 0', borderBottom: '1px solid #f3f4f6' }}>
              <span style={{ fontSize: 13, color: '#6b7280' }}>{k}</span>
              <span style={{ fontSize: 13, fontWeight: 600, color: '#111827' }}>{v}</span>
            </div>
          ))}
          <div style={{ background: '#f0fdf4', borderRadius: 12, padding: 16, marginTop: 20 }}>
            <p style={{ fontSize: 13, color: '#16a34a', fontWeight: 600 }}>✓ Documents uploaded</p>
            <p style={{ fontSize: 12, color: '#6b7280', marginTop: 4 }}>Your application will be reviewed within 2 business days.</p>
          </div>
        </div>
      )}

      {/* Navigation */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 32 }}>
        <button onClick={() => { onSaveDraft(form); }}
          style={{ padding: '10px 20px', borderRadius: 10, border: '1px solid #e5e7eb', fontSize: 13, fontWeight: 600, color: '#6b7280', background: 'none', cursor: 'pointer' }}>
          Save Draft
        </button>
        <div style={{ display: 'flex', gap: 10 }}>
          {step > 0 && (
            <button onClick={prev}
              style={{ padding: '10px 20px', borderRadius: 10, border: '1px solid #e5e7eb', fontSize: 13, fontWeight: 600, color: '#374151', background: 'white', cursor: 'pointer' }}>
              ← Back
            </button>
          )}
          {step < STEPS.length - 1 ? (
            <button onClick={next}
              style={{ padding: '10px 24px', borderRadius: 10, background: '#1e3a6e', color: 'white', border: 'none', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>
              Next →
            </button>
          ) : (
            <button onClick={() => onSubmit(form)} // 🔌 BACKEND: POST /applications
              style={{ padding: '10px 24px', borderRadius: 10, background: '#00b894', color: 'white', border: 'none', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>
              Submit Application
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
