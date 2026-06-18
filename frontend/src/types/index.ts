export type WorkflowStatus = 'completed' | 'active' | 'pending';

export interface WorkflowStep {
  id: string;
  label: string;
  status: WorkflowStatus;
  subLabel?: string;
}

export interface InterestRate {
  range: string;
  tenure: string;
  rate: string;
  trend: 'down' | 'flat' | 'up';
}

export interface LoanType {
  id: string;
  label: string;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  type?: string;
  options?: any[];
  properties?: any[];
}

export interface ApplicationHistoryItem {
  id: string;
  title: string;
  status: string;
  date: string;
}

export interface CreditScore {
  value: number;
  max: number;
  label: string;
}

/* ─── AUTH ─── */

export type AuthStep =
  | 'choose_type'
  | 'existing_password'
  | 'existing_otp'
  | 'new_phone'
  | 'new_otp'
  | 'kyc'
  | 'financial_docs'
  | 'authenticated';

export interface CustomerProfile {
  customer_id: string;
  full_name: string;
  email: string;
  phone: string;
  pan_number: string;
  aadhaar_number: string;
  kyc_status: string;
  monthly_income: number;
  employment_type: string;
  employer_name: string;
  existing_loans: LoanRecord[];
  total_emi: number;
  customer_segment: string;
}

export interface LoanRecord {
  loan_id: string;
  loan_type: string;
  outstanding_amount: number;
  emi: number;
  status: string;
}

/* ─── KYC ─── */

export type KYCDocType = 'aadhaar' | 'pan' | 'salary_slip' | 'bank_statement' | 'itr';

export interface KYCDocument {
  doc_type: KYCDocType;
  file_name: string;
  uploaded: boolean;
  verified: boolean;
}

/* ─── PROPERTY ─── */

export type PropertyChoice = 'lap' | 'home_loan';

export interface BankProperty {
  property_id: string;
  address: string;
  city: string;
  area_sqft: number;
  bedrooms: number;
  listed_price: number;
  max_loan_available: number;
  property_score: number;
  nearby_schools?: string[];
  hospitals?: string[];
  transit?: {
    metro: string;
    bus: string;
    train: string;
  };
  crime_rate?: string;
}

export interface OwnPropertySubmission {
  registration_number: string;
  owner_name: string;
  address: string;
  pincode: string;
  area_sqft: number;
  property_type: string;
}
