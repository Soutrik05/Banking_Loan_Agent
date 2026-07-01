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

// Define sub-components outside the LoginPage component function to prevent unmounting & focus loss on re-render.
const Header: React.FC<{ title: string; subtitle: string }> = ({ title, subtitle }) => (
  <div className="text-center mb-8 animate-fade-in">
    <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-[#1e3a6e] to-[#3b82f6] flex items-center justify-center shadow-xl shadow-blue-500/20 mx-auto mb-4 hover:rotate-6 hover:scale-105 transition-transform duration-300">
      <svg className="w-7 h-7 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
        <path d="M3 22h18M6 18V9M10 18V9M14 18V9M18 18V9M12 2L2 7h20L12 2z" />
      </svg>
    </div>
    <h1 className="text-xl font-bold text-gray-900 dark:text-gray-50 tracking-tight">{title}</h1>
    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1.5 font-medium">{subtitle}</p>
  </div>
);

const ErrorBanner: React.FC<{ error: string | null }> = ({ error }) =>
  error ? (
    <div className="bg-red-500/10 dark:bg-red-500/5 border border-red-500/20 dark:border-red-500/10 text-red-600 dark:text-red-400 text-xs rounded-xl p-3.5 mb-4 flex items-start gap-2 animate-fade-in">
      <span className="mt-0.5">⚠️</span>
      <p className="font-semibold leading-normal">{error}</p>
    </div>
  ) : null;

const DemoOtpBanner: React.FC<{ demoOtp: string | null }> = ({ demoOtp }) =>
  demoOtp ? (
    <div className="bg-blue-500/10 dark:bg-blue-500/5 border border-blue-500/20 dark:border-blue-500/10 text-blue-600 dark:text-blue-300 text-xs rounded-xl p-3.5 mb-4 flex items-start gap-2 animate-fade-in">
      <span className="mt-0.5">🧪</span>
      <p className="font-semibold leading-normal">
        Demo mode — your OTP is <strong className="font-black underline tracking-wider">{demoOtp}</strong>
      </p>
    </div>
  ) : null;

const CardWrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div className="bg-gradient-to-br from-[#eef2ff] via-[#f5f3ff] to-[#e0f2fe] dark:from-[#0a0e1f] dark:via-[#111530] dark:to-[#0a1422] min-h-screen flex items-center justify-center p-4">
    <div className="bg-white/90 dark:bg-[#0c101d]/85 backdrop-blur-xl border border-gray-200/50 dark:border-gray-800/80 shadow-2xl rounded-3xl p-8 w-full max-w-[390px] transition-all duration-300 animate-slide-up">
      {children}
    </div>
  </div>
);

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

  /* ── STEP: choose_type ── */
  if (step === 'choose_type') {
    return (
      <CardWrapper>
        <Header title="Welcome to National Bank" subtitle="Let's get your loan started" />
        <ErrorBanner error={error} />
        
        <div className="space-y-3">
          <button 
            className="w-full py-3.5 px-4 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:brightness-110 active:scale-[0.98] text-white font-semibold text-sm shadow-md shadow-blue-500/10 transition-all duration-200"
            onClick={() => setStep('existing_password')}
          >
            I'm an existing customer
          </button>
          
          <button
            className="w-full py-3.5 px-4 rounded-xl border border-gray-200 dark:border-gray-800 text-gray-800 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-900/50 font-semibold text-sm active:scale-[0.98] transition-all duration-200"
            onClick={() => setStep('new_phone')}
          >
            I'm new here
          </button>
        </div>

        {onClose && (
          <p 
            className="text-center text-xs font-semibold text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 mt-6 cursor-pointer transition-colors" 
            onClick={onClose}
          >
            ← Back to browsing
          </p>
        )}
      </CardWrapper>
    );
  }

  /* ── STEP: existing_password ── */
  if (step === 'existing_password') {
    return (
      <CardWrapper>
        <Header title="Welcome back" subtitle="Sign in to continue your loan application" />
        <ErrorBanner error={error} />
        
        <div className="space-y-4 mb-6">
          <div>
            <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1.5">User ID</label>
            <input 
              className="w-full px-4 py-3 rounded-xl border border-gray-200/80 dark:border-gray-800 bg-white/50 dark:bg-gray-950/50 text-gray-900 dark:text-gray-100 text-sm outline-none transition-all duration-200 focus:border-blue-500 dark:focus:border-blue-400 focus:ring-2 focus:ring-blue-500/20 dark:focus:ring-blue-400/20 placeholder-gray-400 dark:placeholder-gray-600"
              placeholder="e.g. USR001" 
              value={userId} 
              onChange={e => setUserId(e.target.value)} 
            />
          </div>
          
          <div>
            <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1.5">Password</label>
            <input 
              className="w-full px-4 py-3 rounded-xl border border-gray-200/80 dark:border-gray-800 bg-white/50 dark:bg-gray-950/50 text-gray-900 dark:text-gray-100 text-sm outline-none transition-all duration-200 focus:border-blue-500 dark:focus:border-blue-400 focus:ring-2 focus:ring-blue-500/20 dark:focus:ring-blue-400/20 placeholder-gray-400 dark:placeholder-gray-600"
              type="password" 
              placeholder="Enter your password" 
              value={password} 
              onChange={e => setPassword(e.target.value)} 
              onKeyDown={e => {
                if (e.key === 'Enter' && !loading && userId && password) {
                  existingLoginStep1(userId, password);
                }
              }}
            />
          </div>
        </div>

        <button
          className="w-full py-3.5 px-4 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:brightness-110 active:scale-[0.98] text-white font-semibold text-sm shadow-md shadow-blue-500/10 transition-all duration-200 disabled:opacity-45 disabled:pointer-events-none disabled:active:scale-100"
          disabled={loading || !userId || !password}
          onClick={() => existingLoginStep1(userId, password)}
        >
          {loading ? 'Signing in…' : 'Continue'}
        </button>

        <p className="text-center text-xs text-gray-400 dark:text-gray-500 mt-6 font-medium">
          New customer?{' '}
          <span 
            className="text-blue-600 dark:text-blue-400 font-bold cursor-pointer hover:underline" 
            onClick={() => setStep('new_phone')}
          >
            Start fresh application
          </span>
        </p>
      </CardWrapper>
    );
  }

  /* ── STEP: existing_otp ── */
  if (step === 'existing_otp') {
    return (
      <CardWrapper>
        <Header title="Verify it's you" subtitle="Enter the OTP sent to your registered mobile" />
        <ErrorBanner error={error} />
        <DemoOtpBanner demoOtp={demoOtp} />
        
        <div className="mb-6">
          <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1.5">Enter OTP</label>
          <input 
            className="w-full px-4 py-3 rounded-xl border border-gray-200/80 dark:border-gray-800 bg-white/50 dark:bg-gray-950/50 text-gray-900 dark:text-gray-100 text-sm outline-none transition-all duration-200 focus:border-blue-500 dark:focus:border-blue-400 focus:ring-2 focus:ring-blue-500/20 dark:focus:ring-blue-400/20 placeholder-gray-400 dark:placeholder-gray-600 text-center tracking-[0.2em] font-bold"
            placeholder="6-digit OTP" 
            maxLength={6} 
            value={otp} 
            onChange={e => setOtp(e.target.value)} 
            onKeyDown={e => {
              if (e.key === 'Enter' && !loading && otp.length >= 6) {
                existingLoginStep2(otp);
              }
            }}
          />
        </div>

        <button
          className="w-full py-3.5 px-4 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:brightness-110 active:scale-[0.98] text-white font-semibold text-sm shadow-md shadow-blue-500/10 transition-all duration-200 disabled:opacity-45 disabled:pointer-events-none disabled:active:scale-100"
          disabled={loading || otp.length < 6}
          onClick={() => existingLoginStep2(otp)}
        >
          {loading ? 'Verifying…' : 'Sign In'}
        </button>
      </CardWrapper>
    );
  }

  /* ── STEP: new_phone ── */
  if (step === 'new_phone') {
    return (
      <CardWrapper>
        <Header title="Let's get started" subtitle="Enter your mobile number to begin" />
        <ErrorBanner error={error} />
        
        <div className="mb-6">
          <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1.5">Mobile Number</label>
          <input 
            className="w-full px-4 py-3 rounded-xl border border-gray-200/80 dark:border-gray-800 bg-white/50 dark:bg-gray-950/50 text-gray-900 dark:text-gray-100 text-sm outline-none transition-all duration-200 focus:border-blue-500 dark:focus:border-blue-400 focus:ring-2 focus:ring-blue-500/20 dark:focus:ring-blue-400/20 placeholder-gray-400 dark:placeholder-gray-600"
            type="tel" 
            placeholder="+91 98765 43210" 
            value={phone} 
            onChange={e => setPhone(e.target.value)} 
            onKeyDown={e => {
              if (e.key === 'Enter' && !loading && phone.length >= 10) {
                newUserStep1(phone);
              }
            }}
          />
        </div>

        <button
          className="w-full py-3.5 px-4 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:brightness-110 active:scale-[0.98] text-white font-semibold text-sm shadow-md shadow-blue-500/10 transition-all duration-200 disabled:opacity-45 disabled:pointer-events-none disabled:active:scale-100"
          disabled={loading || phone.length < 10}
          onClick={() => newUserStep1(phone)}
        >
          {loading ? 'Sending OTP…' : 'Send OTP'}
        </button>

        <p className="text-center text-xs text-gray-400 dark:text-gray-500 mt-6 font-medium">
          Already a customer?{' '}
          <span 
            className="text-blue-600 dark:text-blue-400 font-bold cursor-pointer hover:underline" 
            onClick={() => setStep('existing_password')}
          >
            Sign in instead
          </span>
        </p>
      </CardWrapper>
    );
  }

  /* ── STEP: new_otp ── */
  if (step === 'new_otp') {
    return (
      <CardWrapper>
        <Header title="Verify your number" subtitle={`OTP sent to ${phone}`} />
        <ErrorBanner error={error} />
        <DemoOtpBanner demoOtp={demoOtp} />
        
        <div className="mb-6">
          <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1.5">Enter OTP</label>
          <input 
            className="w-full px-4 py-3 rounded-xl border border-gray-200/80 dark:border-gray-800 bg-white/50 dark:bg-gray-950/50 text-gray-900 dark:text-gray-100 text-sm outline-none transition-all duration-200 focus:border-blue-500 dark:focus:border-blue-400 focus:ring-2 focus:ring-blue-500/20 dark:focus:ring-blue-400/20 placeholder-gray-400 dark:placeholder-gray-600 text-center tracking-[0.2em] font-bold"
            placeholder="6-digit OTP" 
            maxLength={6} 
            value={otp} 
            onChange={e => setOtp(e.target.value)} 
            onKeyDown={e => {
              if (e.key === 'Enter' && !loading && otp.length >= 6) {
                newUserStep2(otp);
              }
            }}
          />
        </div>

        <button
          className="w-full py-3.5 px-4 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:brightness-110 active:scale-[0.98] text-white font-semibold text-sm shadow-md shadow-blue-500/10 transition-all duration-200 disabled:opacity-45 disabled:pointer-events-none disabled:active:scale-100"
          disabled={loading || otp.length < 6}
          onClick={() => newUserStep2(otp)}
        >
          {loading ? 'Verifying…' : 'Verify & Continue'}
        </button>
      </CardWrapper>
    );
  }

  /* ── STEP: kyc ── */
  if (step === 'kyc') {
    return (
      <CardWrapper>
        <Header title="KYC Verification" subtitle="Identity verification required" />

        <div className="space-y-4 mb-6">
          <div>
            <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1.5">PAN Number</label>
            <input
              className={`w-full px-4 py-3 rounded-xl border bg-white/50 dark:bg-gray-950/50 text-gray-900 dark:text-gray-100 text-sm outline-none transition-all duration-200 focus:ring-2 focus:ring-blue-500/20 dark:focus:ring-blue-400/20 placeholder-gray-400 dark:placeholder-gray-600 ${
                kycError && !pan.trim() 
                  ? 'border-red-500 focus:border-red-500' 
                  : 'border-gray-200/80 dark:border-gray-800 focus:border-blue-500 dark:focus:border-blue-400'
              }`}
              placeholder="ABCDE1234F"
              value={pan}
              onChange={(e) => {
                setPan(e.target.value);
                setKycError('');
              }}
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1.5">Aadhaar Number</label>
            <input
              className={`w-full px-4 py-3 rounded-xl border bg-white/50 dark:bg-gray-950/50 text-gray-900 dark:text-gray-100 text-sm outline-none transition-all duration-200 focus:ring-2 focus:ring-blue-500/20 dark:focus:ring-blue-400/20 placeholder-gray-400 dark:placeholder-gray-600 ${
                kycError && !aadhaar.trim() 
                  ? 'border-red-500 focus:border-red-500' 
                  : 'border-gray-200/80 dark:border-gray-800 focus:border-blue-500 dark:focus:border-blue-400'
              }`}
              placeholder="123456789012"
              value={aadhaar}
              onChange={(e) => {
                setAadhaar(e.target.value);
                setKycError('');
              }}
              onKeyDown={async (e) => {
                if (e.key === 'Enter' && !loading) {
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
                }
              }}
            />
          </div>
        </div>

        {kycError && (
          <p className="text-xs font-bold text-red-500 dark:text-red-400 mb-4 animate-fade-in">
            {kycError}
          </p>
        )}

        <button
          className="w-full py-3.5 px-4 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:brightness-110 active:scale-[0.98] text-white font-semibold text-sm shadow-md shadow-blue-500/10 transition-all duration-200 disabled:opacity-45 disabled:pointer-events-none disabled:active:scale-100"
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
          {loading ? 'Verifying…' : 'Continue'}
        </button>
      </CardWrapper>
    );
  }

  return null;
};
