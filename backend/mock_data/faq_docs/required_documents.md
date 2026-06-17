# Required Documents — Frequently Asked Questions

## What documents do I need to apply?

Documents fall into three categories: Identity, Income, and Property.

---

## Salaried — New Customer

**Identity (KYC)**
- Aadhaar Card (mandatory)
- PAN Card (mandatory)
- Passport or Voter ID (any one as address proof)

**Income**
- Last 3 months salary slips
- Last 6 months bank statements (salary account)
- Form 16 or latest ITR

**Property**
- Sale Deed / Title Deed
- Property Tax Receipt (latest year)
- Encumbrance Certificate (last 15 years)
- Registry Document / Index II

---

## Salaried — Existing Customer

Since your KYC is already on file, you only need:

**Income (updated)**
- Last 3 months salary slips
- Last 3 months bank statements

**Property**
- Sale Deed
- Encumbrance Certificate
- Property Tax Receipt (optional but helpful)

You will NOT be asked to resubmit Aadhaar, PAN, or any identity document unless there has been a name change or address update.

---

## Self-Employed — New Customer

**Identity (KYC)**
- Aadhaar Card
- PAN Card
- Passport or Voter ID

**Income**
- ITR for last 2 years (with computation of income)
- Last 12 months bank statements (business + personal)
- Audited financial statements (P&L and Balance Sheet)
- GST returns (if registered)

**Business**
- Business registration certificate
- GST Certificate
- Partnership deed / MOA / AOA (if applicable)

**Property**
- Sale Deed, Property Tax Receipt, Encumbrance Certificate, Registry Document

---

## Self-Employed — Existing Customer

**Income**
- Latest ITR
- Last 6 months bank statements

**Property**
- Sale Deed
- Encumbrance Certificate

---

## What information is extracted from each document?

| Document | Extracted Fields | Used By |
|---|---|---|
| Aadhaar | Name, DOB, Address, UID (masked) | KYC Agent |
| PAN | PAN number, Name, DOB | KYC Agent, Credit Agent |
| Salary Slip | Employer name, gross salary, deductions, month | Eligibility Agent |
| Bank Statement | Avg credit, avg debit, EMI payments, bounces | Risk Agent |
| ITR / Form 16 | Annual income, employer, tax paid | Eligibility Agent |
| Sale Deed | Owner name, property address, area, reg. date | Property Agent |
| Encumbrance Cert | Charge history, existing mortgages, clear/unclear | Property Agent |
| Property Tax Receipt | Property ID, owner, tax paid up to year | Property Agent |
| Registry Document | Registration number, stamp duty, parties | Property Agent |

---

## What happens if I cannot provide a document?

The system will tell you exactly which document is missing and why it is needed. You have two attempts to upload the missing document before the case is escalated to a human officer who can assess alternatives on a case-by-case basis.

Common alternatives accepted at officer discretion:
- **No Form 16:** Latest ITR accepted instead
- **No Encumbrance Certificate:** Bank may order one directly from registry (adds 3–5 days)
- **Property Tax arrears:** Clearance receipt accepted if paid before disbursement

---

## Are physical documents required or can I upload scans?

Clear scans or photos are accepted for initial processing. However, originals must be produced at the time of loan agreement signing for physical verification. All uploaded documents are processed through automated extraction and verified against government databases (mock verification in demo mode).

---

## How is my Aadhaar data protected?

Only the last 4 digits of your Aadhaar number are stored. The full number is hashed immediately after verification and is never stored in plain text. This complies with UIDAI guidelines on Aadhaar data storage.
