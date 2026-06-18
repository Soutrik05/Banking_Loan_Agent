import { useState, useCallback, useEffect } from 'react';
import {
  existingLogin,
  existingVerifyOTP,
  newUserRequestOTP,
  newUserVerifyOTP,
  checkSession,
  verifyIdentity,
} from '../services/api';

/**
 * Session lives in sessionStorage — NOT localStorage.
 * Closing the tab clears it. User must log in again.
 */

export type AuthStep =
  | 'choose_type'      // existing vs new
  | 'existing_password' // user_id + password
  | 'existing_otp'      // OTP after password
  | 'new_phone'          // phone number
  | 'new_otp'            // OTP after phone
  | 'kyc'                // new user → proceed to KYC
  | 'financial_docs'     // KYC identity verified → uploading income docs, chat visible
  | 'authenticated';     // fully logged in

export interface AuthState {
  step: AuthStep;
  token: string | null;
  userId: string | null;
  fullName: string | null;
  customerId: string | null;
  isExisting: boolean | null;
  profile: Record<string, unknown> | null;
  // new user intermediate state
  tempId: string | null;
  phone: string | null;
  documentsRequired: Array<{ doc_type: string; label: string; required: boolean }> | null;
}

const SESSION_KEY = 'bw_session';

function loadSession(): { token: string; userId: string; fullName: string; customerId: string } | null {
  const raw = sessionStorage.getItem(SESSION_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function saveSession(data: { token: string; userId: string; fullName: string; customerId: string }) {
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(data));
}

function clearSession() {
  sessionStorage.removeItem(SESSION_KEY);
}

export function useAuth(sessionId: string) {
  const existing = loadSession();

  const [auth, setAuth] = useState<AuthState>({
    step: existing ? 'authenticated' : 'choose_type',
    token: existing?.token ?? null,
    userId: existing?.userId ?? null,
    fullName: existing?.fullName ?? null,
    customerId: existing?.customerId ?? null,
    isExisting: existing ? true : null,
    profile: null,
    tempId: null,
    phone: null,
    documentsRequired: null,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [demoOtp, setDemoOtp] = useState<string | null>(null); // shown on screen in demo mode

  // Re-validate session on mount (tab refresh, not tab close)
  useEffect(() => {
    if (existing?.token) {
      checkSession(existing.token)
        .then(res => {
          if (res.valid) {
            setAuth(prev => ({ ...prev, step: 'authenticated', profile: res.profile }));
          } else {
            clearSession();
            setAuth(prev => ({ ...prev, step: 'choose_type', token: null }));
          }
        })
        .catch(() => {
          clearSession();
          setAuth(prev => ({ ...prev, step: 'choose_type', token: null }));
        });
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  /* ───────────── EXISTING CUSTOMER FLOW ───────────── */

  const existingLoginStep1 = useCallback(async (userId: string, password: string) => {
    setLoading(true); setError(null);
    try {
      const res = await existingLogin(sessionId, userId, password);
      setDemoOtp(res.otp ?? null);
      setAuth(prev => ({ ...prev, step: 'existing_otp', userId: res.user_id, fullName: res.full_name }));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Login failed');
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  const existingLoginStep2 = useCallback(async (otp: string) => {
    if (!auth.userId) return;
    setLoading(true); setError(null);
    try {
      const res = await existingVerifyOTP(sessionId, auth.userId, otp);
      saveSession({
        token: res.jwt_token,
        userId: res.user_id,
        fullName: res.full_name,
        customerId: res.customer_id,
      });
      setAuth(prev => ({
        ...prev,
        step: 'authenticated',
        token: res.jwt_token,
        customerId: res.customer_id,
        isExisting: true,
        profile: res.profile,
      }));
      setDemoOtp(null);
      return res.next_message; // bot's next message — caller injects into chat
    } catch (e) {
      setError(e instanceof Error ? e.message : 'OTP verification failed');
    } finally {
      setLoading(false);
    }
  }, [sessionId, auth.userId]);

  /* ───────────── NEW USER FLOW ───────────── */

  const newUserStep1 = useCallback(async (phone: string) => {
    setLoading(true); setError(null);
    try {
      const res = await newUserRequestOTP(sessionId, phone);
      if (res.already_exists) {
        setAuth(prev => ({ ...prev, step: 'existing_password' }));
        setError(res.message);
        return;
      }
      setDemoOtp(res.otp ?? null);
      setAuth(prev => ({ ...prev, step: 'new_otp', phone, tempId: res.temp_id ?? null }));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to send OTP');
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  const newUserStep2 = useCallback(async (otp: string) => {
    if (!auth.tempId || !auth.phone) return;
    setLoading(true); setError(null);
    try {
      const res = await newUserVerifyOTP(sessionId, auth.tempId, auth.phone, otp);
      setAuth(prev => ({ ...prev, step: 'kyc', isExisting: false }));
      setDemoOtp(null);
      return res.message;
    } catch (e) {
      setError(e instanceof Error ? e.message : 'OTP verification failed');
    } finally {
      setLoading(false);
    }
  }, [sessionId, auth.tempId, auth.phone]);

  /* ───────────── NEW USER: KYC + FINANCIAL DOCUMENTS ───────────── */

  const kycVerifyIdentity = useCallback(async (aadhaarNumber: string, panNumber: string) => {
    if (!auth.tempId || !auth.phone) return;
    setLoading(true); setError(null);
    try {
      const res = await verifyIdentity(sessionId, auth.tempId, auth.phone, aadhaarNumber, panNumber);
      setAuth(prev => ({
        ...prev,
        step: 'financial_docs',
        documentsRequired: (res as unknown as { documents_required?: AuthState['documentsRequired'] }).documents_required ?? null,
      }));
      return res.message; // bot's next message — caller injects into chat
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Identity verification failed');
    } finally {
      setLoading(false);
    }
  }, [sessionId, auth.tempId, auth.phone]);

  const kycRegistrationComplete = useCallback((registration: {
    jwt_token: string; user_id: string; full_name: string; customer_id: string;
  }) => {
    saveSession({
      token: registration.jwt_token,
      userId: registration.user_id,
      fullName: registration.full_name,
      customerId: registration.customer_id,
    });
    setAuth(prev => ({
      ...prev,
      step: 'authenticated',
      token: registration.jwt_token,
      userId: registration.user_id,
      fullName: registration.full_name,
      customerId: registration.customer_id,
      isExisting: false,
      documentsRequired: null,
    }));
  }, []);

  /* ───────────── LOGOUT ───────────── */

  const logout = useCallback(() => {
    clearSession();
    setAuth({
      step: 'choose_type', token: null, userId: null, fullName: null,
      customerId: null, isExisting: null, profile: null, tempId: null, phone: null,
      documentsRequired: null,
    });
  }, []);

  const setStep = useCallback((step: AuthStep) => {
    setAuth(prev => ({ ...prev, step }));
    setError(null);
  }, []);

  return {
    auth, loading, error, demoOtp, setStep,
    existingLoginStep1, existingLoginStep2,
    newUserStep1, newUserStep2,
    kycVerifyIdentity, kycRegistrationComplete,
    logout,
  };
}
