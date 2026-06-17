# BankWise AI — Project Structure

```
bankwise/
│
├── index.html                          ← Single deployable file (open in browser)
├── App.tsx                             ← Root component, page router
│
├── types/
│   └── index.ts                        ← All TypeScript interfaces & types
│
├── store/
│   └── appState.ts                     ← Static/demo data (rates, steps, scores)
│
├── services/
│   └── api.ts                          ← 🔌 ALL backend API calls live here
│                                          Change BASE_URL to your server
│
├── hooks/
│   ├── useAuth.ts                      ← 🔌 Login / OTP / logout → /auth/*
│   ├── useChat.ts                      ← Chat state + bot reply logic
│   └── useApplications.ts             ← 🔌 CRUD for loan applications → /applications
│
├── pages/
│   ├── LoginPage.tsx                   ← 🔌 OTP sign-in form
│   ├── NewApplicationPage.tsx          ← 🔌 4-step application form + doc upload
│   ├── ApplicationHistoryPage.tsx      ← 🔌 List + detail view of applications
│   ├── EligibilityPage.tsx             ← 🔌 Eligibility calculator → /eligibility/check
│   └── FAQPage.tsx                     ← Static FAQ accordion (no backend needed)
│
└── components/
    ├── Sidebar.tsx                     ← Left nav (links to all pages)
    ├── ContextPanel.tsx                ← Right panel (workflow + credit score)
    ├── FileUploader.tsx                ← 🔌 Drag & drop → POST /documents/upload
    │
    ├── cards/
    │   ├── CreditScoreCard.tsx         ← 🔌 Shows score from GET /credit-score
    │   └── InterestRateCard.tsx        ← 🔌 Shows rates from GET /rates
    │
    ├── chat/
    │   ├── ChatWindow.tsx              ← Message bubbles + welcome screen
    │   └── ChatInput.tsx               ← Text input with attachment + mic buttons
    │
    ├── workflow/
    │   └── WorkflowPanel.tsx           ← Vertical step tracker (right panel)
    │
    └── ui/
        ├── Button.tsx                  ← Reusable button (primary/secondary/ghost)
        └── Badge.tsx                   ← Status badge pill
```

---

## 🔌 Backend Connection Map

| File | Endpoint(s) | Notes |
|------|-------------|-------|
| `services/api.ts` | ALL endpoints | Change `BASE_URL` here |
| `hooks/useAuth.ts` | `POST /auth/send-otp` `POST /auth/login` `POST /auth/logout` | Stores JWT in localStorage |
| `hooks/useApplications.ts` | `GET /applications` `POST /applications` `PATCH /applications/:id` | Full CRUD |
| `pages/NewApplicationPage.tsx` | `POST /applications` `POST /kyc/verify` | Step 4 submit |
| `pages/ApplicationHistoryPage.tsx` | `GET /applications` `GET /applications/:id` | List + detail |
| `pages/EligibilityPage.tsx` | `POST /eligibility/check` | Falls back to local calc if no token |
| `pages/LoginPage.tsx` | `POST /auth/send-otp` `POST /auth/login` | OTP flow |
| `components/FileUploader.tsx` | `POST /documents/upload` | Multipart FormData |
| `components/cards/CreditScoreCard.tsx` | `GET /credit-score` | Bureau score |
| `components/cards/InterestRateCard.tsx` | `GET /rates` | Public endpoint, no auth |

---

## 🚀 How to Run

### Option A — Just open the file
```
open index.html
```
Works entirely in the browser. No build step needed.

### Option B — React project (Vite)
```bash
npm create vite@latest bankwise -- --template react-ts
cd bankwise
# Copy all .tsx/.ts files into src/
npm install
npm run dev
```

### Option C — Next.js
```bash
npx create-next-app@latest bankwise --typescript
# Copy pages/ into app/ (or pages/ for pages router)
# Copy components/, hooks/, services/, store/, types/ into src/
npm run dev
```

---

## ⚙️ Environment Variables (React/Next)
```env
VITE_API_URL=https://api.bankwise.com/v1
# or for Next.js:
NEXT_PUBLIC_API_URL=https://api.bankwise.com/v1
```

Then in `services/api.ts`:
```ts
const BASE_URL = import.meta.env.VITE_API_URL;
```
