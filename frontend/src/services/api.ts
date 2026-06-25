/**
 * ╔══════════════════════════════════════════════════════════╗
 * ║           BACKEND CONNECTION FILE — api.ts               ║
 * ║  Connects to the FastAPI bridge at backend_api/main.py   ║
 * ╚══════════════════════════════════════════════════════════╝
 */

const BASE_URL = import.meta.env.VITE_API_URL; // 🔌 FastAPI backend (uvicorn)

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  token?: string
): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => null);
    const detail = err?.detail;
    const msg = Array.isArray(detail)
      ? detail.map((d: { msg?: string }) => d.msg).join(', ')
      : detail || `API ${method} ${path} → ${res.status}`;
    throw new Error(msg);
  }
  return res.json();
}

/* ─── AUTH: EXISTING CUSTOMER (password + OTP) ─── */

// POST /auth/existing/login — Step 1: user_id + password → sends OTP
export const existingLogin = (sessionId: string, userId: string, password: string) =>
  request<{
    success: boolean;
    user_id: string;
    full_name: string;
    phone: string;
    otp?: string; // demo mode only
    message: string;
    next_step: string;
  }>('POST', '/auth/existing/login', { session_id: sessionId, user_id: userId, password });

// POST /auth/existing/verify-otp — Step 2: OTP → JWT + full profile
export const existingVerifyOTP = (sessionId: string, userId: string, otp: string) =>
  request<{
    success: boolean;
    jwt_token: string;
    user_id: string;
    full_name: string;
    customer_id: string;
    is_existing: true;
    profile: Record<string, unknown>;
    next_message: string;
  }>('POST', '/auth/existing/verify-otp', { session_id: sessionId, user_id: userId, otp });

/* ─── AUTH: NEW USER (phone + OTP only, no password) ─── */

// POST /auth/new/request-otp — Step 1: phone number → sends OTP
export const newUserRequestOTP = (sessionId: string, phone: string) =>
  request<{
    success: boolean;
    phone: string;
    already_exists: boolean;
    temp_id?: string;
    otp?: string; // demo mode only
    message: string;
    next_step: string;
  }>('POST', '/auth/new/request-otp', { session_id: sessionId, phone });

// POST /auth/new/verify-otp — Step 2: OTP → routes to KYC (no JWT yet)
export const newUserVerifyOTP = (sessionId: string, tempId: string, phone: string, otp: string) =>
  request<{
    success: boolean;
    phone: string;
    temp_id: string;
    is_existing: false;
    message: string;
    next_step: string;
  }>('POST', '/auth/new/verify-otp', { session_id: sessionId, temp_id: tempId, phone, otp });

/* ─── SESSION ─── */

// GET /auth/session?token=... — validate token on app reload
export const checkSession = (token: string) =>
  request<{ valid: boolean; profile: Record<string, unknown> }>(
    'GET',
    `/auth/session?token=${encodeURIComponent(token)}`
  );

/* ─── CHAT — routes through orchestrator_agent ─── */

export const sendChatMessage = (message: string, sessionId: string, token?: string) =>
  request<{ reply: string; type: string; [key: string]: unknown }>(
    'POST',
    '/chat',
    { message, session_id: sessionId, token }
  );

/* ─── INTEREST RATES (public, no auth) ─── */

export const getRates = () => request('GET', '/rates');

/* ─── KYC (to be built next) ─── */
 
 export const verifyIdentity = (
  sessionId: string,
  tempId: string,
  phone: string,
  aadhaarNumber: string,
  panNumber: string
) =>
  request<{
    success: boolean;
    verified_name: string;
    verified_dob: string;
    verified_address: string;
    financial_data: Record<string, unknown>;
    message: string;
    next_step: string;
  }>(
    'POST',
    '/kyc/verify-identity',
    {
      session_id: sessionId,
      temp_id: tempId,
      phone,
      aadhaar_number: aadhaarNumber,
      pan_number: panNumber
    }
  );

export const uploadDocument = async (file: File, docType: string, tempId: string) => {
  const fd = new FormData();
  fd.append('file', file);
  fd.append('doc_type', docType);
  fd.append('temp_id', tempId);
  const res = await fetch(`${BASE_URL}/kyc/upload`, { method: 'POST', body: fd });
  if (!res.ok) throw new Error('Document upload failed');
  return res.json();
};

/* ─── PROPERTY (to be built next) ─── */

export const getBankInventory = (token: string) =>
  request('GET', '/property/inventory', undefined, token);

export const submitOwnProperty = (data: object, token: string) =>
  request('POST', '/property/submit', data, token);

/* ─── APPLICATIONS ─── */

export const getApplications = (token: string) =>
  request('GET', '/applications', undefined, token);

export const createApplication = (data: object, token: string) =>
  request('POST', '/applications', data, token);

export const updateApplication = (id: string, data: object, token: string) =>
  request('PATCH', `/applications/${id}`, data, token);

/* ─── ELIGIBILITY ─── */

export const checkEligibility = (data: object, token: string) =>
  request('POST', '/eligibility/check', data, token);

/* ─── CONVERSATIONS (persistent chat history sidebar) ─── */

export interface ConversationSummary {
  id: string;
  customer_id: string;
  session_id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ConversationMessageRow {
  id: string;
  conversation_id: string;
  role: 'user' | 'assistant';
  content: string;
  message_type?: string | null;
  metadata?: Record<string, unknown> | null;
  created_at: string;
}

export const getConversations = (customerId: string) =>
  request<ConversationSummary[]>('GET', `/conversations?customer_id=${encodeURIComponent(customerId)}`);

export const getConversationMessages = (conversationId: string) =>
  request<ConversationMessageRow[]>('GET', `/conversations/${conversationId}/messages`);

export const updateConversationTitle = (conversationId: string, title: string) =>
  request<{ success: boolean }>('PATCH', `/conversations/${conversationId}/title`, { title });

/* ─── PROPERTY DOCUMENT UPLOAD (Supabase Storage) ─── */

export const uploadPropertyDocument = async (
  file: File, docType: string, sessionId: string, token: string
) => {
  const fd = new FormData();
  fd.append('file', file);
  fd.append('doc_type', docType);
  fd.append('session_id', sessionId);
  fd.append('token', token);
  const res = await fetch(`${BASE_URL}/property/upload-document`, { method: 'POST', body: fd });
  if (!res.ok) throw new Error('Property document upload failed');
  return res.json();
};

export const getPropertyDocuments = (sessionId: string, token: string) =>
  request('GET', `/property/documents?session_id=${sessionId}&token=${encodeURIComponent(token)}`, undefined);

/* ─── SALE DEED UPLOAD (Gemini OCR → LAP property verification) ─── */

export const uploadSaleDeed = async (file: File, sessionId: string, token: string, customerId: string) => {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("session_id", sessionId);
  fd.append("token", token);
  fd.append("customer_id", customerId);
  const res = await fetch(`${BASE_URL}/property/upload-sale-deed`, {
    method: "POST", body: fd
  });
  if (!res.ok) throw new Error("Sale deed upload failed");
  return res.json();
};

/* ─── MULTI-DOCUMENT UPLOAD (acquisition-type-aware checklist) ─── */

export const uploadPropertyDoc = async (
  file: File,
  docType: string,
  sessionId: string,
  token: string,
  customerId: string
) => {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("doc_type", docType);
  fd.append("session_id", sessionId);
  fd.append("token", token);
  fd.append("customer_id", customerId);
  const res = await fetch(`${BASE_URL}/property/upload-sale-deed`, {
    method: "POST", body: fd
  });
  if (!res.ok) throw new Error("Upload failed");
  return res.json();
};

/* ─── APPOINTMENTS (manual-review follow-up) ─── */

export const bookAppointment = async (data: {
  customer_id: string;
  session_id: string;
  appointment_date: string;
  appointment_time: string;
  branch: string;
  reason: string;
  contact_phone: string;
  token: string;
}) => {
  const res = await fetch(`${BASE_URL}/appointments/book`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Booking failed');
  return res.json();
};

export const getAppointment = (sessionId: string, token: string) =>
  request('GET', `/appointments/${sessionId}?token=${encodeURIComponent(token)}`);
