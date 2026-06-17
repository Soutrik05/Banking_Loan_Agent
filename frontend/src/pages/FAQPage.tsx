import React, { useState } from 'react';

const FAQS = [
  { q: 'What documents are required for a home loan?', a: 'You need: PAN card, Aadhaar card, last 3 months salary slips (or 2 years ITR for self-employed), bank statements for 6 months, and property documents.' },
  { q: 'How long does the loan approval process take?', a: 'Typically 3–7 business days after all documents are submitted. Property verification may take an additional 2–3 days.' },
  { q: 'What is the minimum credit score required?', a: 'We recommend a CIBIL score of 700+. Scores above 750 qualify for the best interest rates. Scores between 650–699 may attract higher rates.' },
  { q: 'Can I prepay my loan without penalty?', a: 'For floating-rate loans, RBI guidelines prohibit prepayment penalties. Fixed-rate loans may have a 2% charge on the prepaid amount.' },
  { q: 'What is FOIR and how does it affect my eligibility?', a: 'FOIR (Fixed Obligations to Income Ratio) is the share of your income going to existing EMIs and obligations. We allow up to 50% FOIR, so available income above that determines your eligible loan amount.' },
  { q: 'Is there a processing fee?', a: 'Yes, 0.5% of the loan amount (minimum ₹5,000, maximum ₹25,000) plus applicable GST. This is non-refundable.' },
  { q: 'Can I apply jointly with a co-applicant?', a: 'Yes. Adding a co-applicant (spouse, parent, or sibling) increases your combined income and therefore your loan eligibility.' },
  { q: 'How do I track my application status?', a: 'Use the Application History section in the sidebar. You\'ll also receive SMS and email updates at every workflow stage.' },
];

export const FAQPage: React.FC = () => {
  const [open, setOpen] = useState<number | null>(null);
  const [search, setSearch] = useState('');

  const filtered = FAQS.filter(f => f.q.toLowerCase().includes(search.toLowerCase()) || f.a.toLowerCase().includes(search.toLowerCase()));

  return (
    <div style={{ maxWidth: 680, margin: '0 auto', padding: '32px 24px' }}>
      <h2 style={{ fontSize: 20, fontWeight: 700, color: '#111827', marginBottom: 6 }}>Frequently Asked Questions</h2>
      <p style={{ fontSize: 13, color: '#6b7280', marginBottom: 24 }}>Quick answers to common loan questions.</p>

      {/* Search */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, background: '#f9fafb', border: '1px solid #e5e7eb', borderRadius: 12, padding: '10px 14px', marginBottom: 24 }}>
        <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="#9ca3af" strokeWidth={2}>
          <circle cx="11" cy="11" r="8"/><path strokeLinecap="round" d="M21 21l-4.35-4.35"/>
        </svg>
        <input type="text" value={search} onChange={e => setSearch(e.target.value)} placeholder="Search questions…"
          style={{ flex: 1, background: 'transparent', border: 'none', outline: 'none', fontSize: 14, color: '#374151' }} />
      </div>

      {/* Accordion */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {filtered.map((faq, i) => (
          <div key={i} style={{ background: 'white', borderRadius: 14, border: '1px solid #f3f4f6', overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,.04)' }}>
            <button onClick={() => setOpen(open === i ? null : i)}
              style={{ width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 20px', background: 'none', border: 'none', cursor: 'pointer', textAlign: 'left' }}>
              <span style={{ fontSize: 14, fontWeight: 600, color: '#1f2937', lineHeight: 1.4 }}>{faq.q}</span>
              <svg style={{ flexShrink: 0, marginLeft: 12, transform: open === i ? 'rotate(180deg)' : 'none', transition: 'transform .2s' }}
                width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="#9ca3af" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7"/>
              </svg>
            </button>
            {open === i && (
              <div style={{ padding: '0 20px 16px' }}>
                <p style={{ fontSize: 13, color: '#6b7280', lineHeight: 1.7 }}>{faq.a}</p>
              </div>
            )}
          </div>
        ))}
        {filtered.length === 0 && (
          <p style={{ textAlign: 'center', color: '#9ca3af', fontSize: 14, padding: 32 }}>No results for "{search}"</p>
        )}
      </div>
    </div>
  );
};
