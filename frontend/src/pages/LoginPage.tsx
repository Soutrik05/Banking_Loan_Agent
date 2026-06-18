import React, { useState } from 'react';
import type { AuthStep } from '../hooks/useAuth';


interface LoginPageProps {
  step: AuthStep;
  loading: boolean;
  error: string | null;
  demoOtp: string | null;

  setStep: (step: AuthStep) => void;
  existingLoginStep1: (userId: string, password: string) => Promise<void>;
  existingLoginStep2: (otp: string) => Promise<void>;
  newUserStep1: (phone: string) => Promise<void>;
  newUserStep2: (otp: string) => Promise<void>;
  kycVerifyIdentity: (aadhaarNumber: string, panNumber: string) => Promise<void>;
  onClose?: () => void;
}

const card: React.CSSProperties = {
  background: 'white', borderRadius: 20, padding: 40, width: 380,
  boxShadow: '0 4px 24px rgba(0,0,0,.08)',
};
const label: React.CSSProperties = {
  fontSize: 12, fontWeight: 600, color: '#374151', display: 'block', marginBottom: 6,
};
const input: React.CSSProperties = {
  width: '100%', padding: '10px 14px', borderRadius: 10, border: '1px solid #e5e7eb',
  fontSize: 14, outline: 'none', boxSizing: 'border-box',
};
const primaryBtn: React.CSSProperties = {
  width: '100%', padding: '12px', borderRadius: 12, background: '#1e3a6e',
  color: 'white', border: 'none', fontSize: 14, fontWeight: 600, cursor: 'pointer',
};

export const LoginPage: React.FC<LoginPageProps> = ({
  step,
  loading,
  error,
  demoOtp,

  setStep,
  existingLoginStep1,
  existingLoginStep2,
  newUserStep1,
  newUserStep2,
  kycVerifyIdentity,
  onClose,
}) => {
  const [userId, setUserId] = useState('');
  const [password, setPassword] = useState('');
  const [phone, setPhone] = useState('');
  const [otp, setOtp] = useState('');
  const [pan, setPan] = useState('');
  const [aadhaar, setAadhaar] = useState('');
  const [kycError, setKycError] = useState('');

  const Header = ({ title, subtitle }: { title: string; subtitle: string }) => (
    <div style={{ textAlign: 'center', marginBottom: 32 }}>
      <div style={{ width: 52, height: 52, borderRadius: 14, background: '#1e3a6e', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px' }}>
        <span style={{ color: 'white', fontSize: 22, fontWeight: 700 }}>N</span>
      </div>
      <h1 style={{ fontSize: 20, fontWeight: 700, color: '#111827' }}>{title}</h1>
      <p style={{ fontSize: 13, color: '#6b7280', marginTop: 4 }}>{subtitle}</p>
    </div>
  );

  const ErrorBanner = () =>
    error ? (
      <div style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 10, padding: '10px 14px', marginBottom: 16 }}>
        <p style={{ fontSize: 13, color: '#dc2626' }}>{error}</p>
      </div>
    ) : null;

  const DemoOtpBanner = () =>
    demoOtp ? (
      <div style={{ background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: 10, padding: '10px 14px', marginBottom: 16 }}>
        <p style={{ fontSize: 12, color: '#1e40af' }}>🧪 Demo mode — your OTP is <strong>{demoOtp}</strong></p>
      </div>
    ) : null;

  /* ── STEP: choose_type ── */
  if (step === 'choose_type') {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#f8f9fb' }}>
        <div style={card}>
          <Header title="Welcome to National Bank" subtitle="Let's get your loan started" />
          <ErrorBanner />
          <button style={{ ...primaryBtn, marginBottom: 12 }} onClick={() => setStep('existing_password')}>
            I'm an existing customer
          </button>
          <button
            style={{ ...primaryBtn, background: 'white', color: '#1e3a6e', border: '1px solid #1e3a6e' }}
            onClick={() => setStep('new_phone')}
          >
            I'm new here
          </button>
          {onClose && (
            <p style={{ textAlign: 'center', fontSize: 12, color: '#9ca3af', marginTop: 20, cursor: 'pointer' }} onClick={onClose}>
              ← Back to browsing
            </p>
          )}
        </div>
      </div>
    );
  }

  /* ── STEP: existing_password ── */
  if (step === 'existing_password') {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#f8f9fb' }}>
        <div style={card}>
          <Header title="Welcome back" subtitle="Sign in to continue your loan application" />
          <ErrorBanner />
          <div style={{ marginBottom: 16 }}>
            <label style={label}>User ID</label>
            <input style={input} placeholder="e.g. USR001" value={userId} onChange={e => setUserId(e.target.value)} />
          </div>
          <div style={{ marginBottom: 20 }}>
            <label style={label}>Password</label>
            <input style={input} type="password" placeholder="Enter your password" value={password} onChange={e => setPassword(e.target.value)} />
          </div>
          <button
            style={{ ...primaryBtn, opacity: loading || !userId || !password ? 0.5 : 1 }}
            disabled={loading || !userId || !password}
            onClick={() => existingLoginStep1(userId, password)}
          >
            {loading ? 'Signing in…' : 'Continue'}
          </button>
          <p style={{ textAlign: 'center', fontSize: 12, color: '#9ca3af', marginTop: 20 }}>
            New customer?{' '}
            <span style={{ color: '#1e3a6e', fontWeight: 600, cursor: 'pointer' }} onClick={() => setStep('new_phone')}>
              Start fresh application
            </span>
          </p>
        </div>
      </div>
    );
  }

  /* ── STEP: existing_otp ── */
  if (step === 'existing_otp') {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#f8f9fb' }}>
        <div style={card}>
          <Header title="Verify it's you" subtitle="Enter the OTP sent to your registered mobile" />
          <ErrorBanner />
          <DemoOtpBanner />
          <div style={{ marginBottom: 24 }}>
            <label style={label}>Enter OTP</label>
            <input style={{ ...input, letterSpacing: '0.2em' }} placeholder="6-digit OTP" maxLength={6} value={otp} onChange={e => setOtp(e.target.value)} />
          </div>
          <button
            style={{ ...primaryBtn, opacity: loading || otp.length < 6 ? 0.5 : 1 }}
            disabled={loading || otp.length < 6}
            onClick={() => existingLoginStep2(otp)}
          >
            {loading ? 'Verifying…' : 'Sign In'}
          </button>
        </div>
      </div>
    );
  }

  /* ── STEP: new_phone ── */
  if (step === 'new_phone') {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#f8f9fb' }}>
        <div style={card}>
          <Header title="Let's get started" subtitle="Enter your mobile number to begin" />
          <ErrorBanner />
          <div style={{ marginBottom: 20 }}>
            <label style={label}>Mobile Number</label>
            <input style={input} type="tel" placeholder="+91 98765 43210" value={phone} onChange={e => setPhone(e.target.value)} />
          </div>
          <button
            style={{ ...primaryBtn, opacity: loading || phone.length < 10 ? 0.5 : 1 }}
            disabled={loading || phone.length < 10}
            onClick={() => newUserStep1(phone)}
          >
            {loading ? 'Sending OTP…' : 'Send OTP'}
          </button>
          <p style={{ textAlign: 'center', fontSize: 12, color: '#9ca3af', marginTop: 20 }}>
            Already a customer?{' '}
            <span style={{ color: '#1e3a6e', fontWeight: 600, cursor: 'pointer' }} onClick={() => setStep('existing_password')}>
              Sign in instead
            </span>
          </p>
        </div>
      </div>
    );
  }

  /* ── STEP: new_otp ── */
  if (step === 'new_otp') {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#f8f9fb' }}>
        <div style={card}>
          <Header title="Verify your number" subtitle={`OTP sent to ${phone}`} />
          <ErrorBanner />
          <DemoOtpBanner />
          <div style={{ marginBottom: 24 }}>
            <label style={label}>Enter OTP</label>
            <input style={{ ...input, letterSpacing: '0.2em' }} placeholder="6-digit OTP" maxLength={6} value={otp} onChange={e => setOtp(e.target.value)} />
          </div>
          <button
            style={{ ...primaryBtn, opacity: loading || otp.length < 6 ? 0.5 : 1 }}
            disabled={loading || otp.length < 6}
            onClick={() => newUserStep2(otp)}
          >
            {loading ? 'Verifying…' : 'Verify & Continue'}
          </button>
        </div>
      </div>
    );
  }
 /* ── STEP: kyc ── */
if (step === 'kyc') {
  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#f8f9fb'
      }}
    >
      <div style={card}>
        <Header
          title="KYC Verification"
          subtitle="Identity verification required"
        />

        <div style={{ marginBottom: 16 }}>
          <label style={label}>PAN Number</label>
          <input
            style={{
              ...input,
              border:
                kycError && !pan.trim()
                  ? '1px solid red'
                  : '1px solid #e5e7eb'
            }}
            placeholder="ABCDE1234F"
            value={pan}
            onChange={(e) => {
              setPan(e.target.value);
              setKycError('');
            }}
          />
        </div>

        <div style={{ marginBottom: 16 }}>
          <label style={label}>Aadhaar Number</label>
          <input
            style={{
              ...input,
              border:
                kycError && !aadhaar.trim()
                  ? '1px solid red'
                  : '1px solid #e5e7eb'
            }}
            placeholder="123456789012"
            value={aadhaar}
            onChange={(e) => {
              setAadhaar(e.target.value);
              setKycError('');
            }}
          />
        </div>

        {kycError && (
          <p
            style={{
              color: 'red',
              fontSize: '12px',
              marginBottom: '12px'
            }}
          >
            {kycError}
          </p>
        )}

        <button
          style={{
            ...primaryBtn,
            opacity: loading ? 0.7 : 1
          }}
          disabled={loading}
          onClick={async () => {
            if (!pan.trim() || !aadhaar.trim()) {
              setKycError('* Empty fields');
              return;
            }

            try {
              await kycVerifyIdentity(aadhaar, pan);
            } catch (err) {
              console.error(err);
              setKycError('KYC Verification Failed');
            }
          }}
        >
          Continue
        </button>
      </div>
    </div>
  );
}

    return null;
  };
