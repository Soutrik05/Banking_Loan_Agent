import { useState, useEffect, useRef } from 'react';
import { Sidebar } from './components/Sidebar';
import { ContextPanel } from './components/ContextPanel';
import { ChatWindow } from './components/chat/ChatWindow';
import { ChatInput } from './components/chat/ChatInput';
import { LoginPage } from './pages/LoginPage';
import { FileUploader } from './components/FileUploader';
import { AdvisorPanel } from './components/AdvisorPanel';
import { useChat } from './hooks/useChat';
import { useAuth } from './hooks/useAuth';
import { useTheme } from './hooks/useTheme';
import { loanTypes, interestRates, creditScore } from './store/appState';
import type { CreditScore, CustomerProfile, Message } from './types';

function getTimeBasedGreeting(): string {
  const h = new Date().getHours();
  if (h < 12) return 'Good morning';
  if (h < 17) return 'Good afternoon';
  return 'Good evening';
}

const LOAN_OPTIONS = [
  { label: 'I own a property', value: 'I own a property' },
  { label: 'I want to buy a property', value: 'I want to buy a property' },
  { label: 'Just browsing', value: 'Just browsing' },
];

const API_BASE = import.meta.env.VITE_API_URL as string;

export default function App() {
  // Stateful, not a module-level const — "New Application" rotates this to a
  // brand new id so the backend starts a fresh session/conversation instead
  // of appending to the old one. Loading a past conversation from the
  // sidebar also reassigns this to that conversation's original session_id.
  const [sessionId, setSessionId] = useState<string>(() => crypto.randomUUID());

  const { theme, toggleTheme } = useTheme();
  const {
    auth, loading, error, demoOtp, setStep,
    existingLoginStep1, existingLoginStep2,
    newUserStep1, newUserStep2,
    kycVerifyIdentity, kycRegistrationComplete,
    logout,
  } = useAuth(sessionId);

  const [currentCreditScore, setCurrentCreditScore] = useState<CreditScore>(creditScore);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });

  // Warmup ping — wakes up Render's cold-start container so the user's
  // first real message doesn't bear the full spin-up delay.
  const [isWarmingUp, setIsWarmingUp] = useState(true);
  useEffect(() => {
    fetch(`${API_BASE}/health`, { method: 'GET' })
      .then(() => setIsWarmingUp(false))
      .catch(() => setIsWarmingUp(false)); // silent fail — still mark done
  }, []);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    setMousePos({
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
    });
  };

  // Poll backend session status — only the credit score is still relevant
  // to the UI now that the right panel shows accounts/loans instead of the
  // workflow timeline.
  useEffect(() => {
    if (auth.step !== 'authenticated') return;

    const pollStatus = async () => {
      try {
        const res = await fetch(`http://localhost:8000/session/status?session_id=${sessionId}`);
        if (!res.ok) return;
        const data = await res.json();

        // Map credit score
        if (data.credit_score !== null && data.credit_score !== undefined) {
          setCurrentCreditScore({
            value: data.credit_score,
            max: 900,
            label: data.credit_rating || (data.credit_score >= 750 ? 'Excellent' : data.credit_score >= 700 ? 'Good' : 'Fair')
          });
        }
      } catch (err) {
        console.error('Error polling session status:', err);
      }
    };

    // Poll immediately
    pollStatus();

    // Set interval
    const interval = setInterval(pollStatus, 15000);
    return () => clearInterval(interval);
  }, [auth.step, sessionId]);

  // Financial Advisor panel — separate from the main loan chat
  const [advisorOpen, setAdvisorOpen] = useState(false);

  // Guest browsing: the login screen only shows when explicitly triggered —
  // either the user clicks Sign In, or the orchestrator detects loan intent
  // from a logged-out user (type: "auth_required") and asks us to gate it.
  const [showAuthGate, setShowAuthGate] = useState(false);

  const promptLogin = () => {
    setStep('choose_type');
    setShowAuthGate(true);
  };

  const promptExistingLogin = () => {
    setStep('existing_password');
    setShowAuthGate(true);
  };

  const [initialMessages, setInitialMessages] = useState<Message[] | undefined>(undefined);

  const handleLoadConversation = (
    loadedMessages: Message[],
    _conversationId: string,
    conversationSessionId: string | null
  ) => {
    setInitialMessages(loadedMessages);
    // Continue this conversation under its own original session_id, so any
    // new messages the user types get appended to it instead of bleeding
    // into whatever session_id the tab happened to be on.
    if (conversationSessionId) {
      setSessionId(conversationSessionId);
    }
  };

  const { messages, isTyping, inputValue, setInputValue, sendMessage, injectBotMessage, resetChat } =
    useChat(auth.token, sessionId, promptLogin, initialMessages);

  // Cross-customer session isolation: the moment a NEW customer becomes
  // authenticated during this page's lifetime (a real login, or a
  // re-login-as-someone-else after logout — NOT the initial page-load
  // restore from sessionStorage, which must keep that same customer's
  // in-progress chat intact), wipe every piece of state that could
  // otherwise leak the previous customer's data into the new session.
  // Conversation list (useConversations) and appointment state
  // (ContextPanel) clear themselves via their own customerId/sessionId
  // effects, triggered by the fresh sessionId set here.
  const prevCustomerIdRef = useRef<string | null | undefined>(undefined);
  useEffect(() => {
    const newCustomerId = auth.customerId;
    const isFreshLogin =
      !!newCustomerId &&
      prevCustomerIdRef.current !== undefined &&
      prevCustomerIdRef.current !== newCustomerId;

    if (isFreshLogin) {
      setSessionId(crypto.randomUUID());
      resetChat();
      setInitialMessages(undefined);
      setCurrentCreditScore(creditScore);
      // Inject personalised time-based greeting immediately so the chat
      // viewport opens straight away instead of the landing page.
      const firstName = (auth.fullName || 'there').split(' ')[0];
      const greeting = getTimeBasedGreeting();
      injectBotMessage(
        `${greeting}, ${firstName}! 👋 What can I help you with today?`,
        LOAN_OPTIONS,
      );
    }

    prevCustomerIdRef.current = newCustomerId;
  }, [auth.customerId, auth.fullName, injectBotMessage]);

  const handleNewApplication = () => {
    setSessionId(crypto.randomUUID());
    resetChat();
    setInitialMessages(undefined);

    if (auth.token) {
      setCurrentCreditScore(creditScore);
      const firstName = (auth.fullName || 'there').split(' ')[0];
      injectBotMessage(
        `Let's start fresh! What would you like to do, ${firstName}?`,
        LOAN_OPTIONS,
      );
    } else {
      setCurrentCreditScore(creditScore);
    }
  };

  const showLoginGate = showAuthGate && auth.step !== 'authenticated' && auth.step !== 'financial_docs';

  const handleExistingStep2 = async (otp: string) => {
    // Login completes here; the personalised greeting is injected by the
    // prevCustomerIdRef effect once auth.customerId changes — no need to
    // call injectBotMessage here (it would be wiped by resetChat() anyway).
    await existingLoginStep2(otp);
  };

  const handleNewUserStep2 = async (otp: string) => {
    const nextMessage = await newUserStep2(otp);
    if (nextMessage) injectBotMessage(nextMessage);
  };

  const handleKycVerifyIdentity = async (aadhaar: string, pan: string) => {
    const nextMessage = await kycVerifyIdentity(aadhaar, pan);
    if (nextMessage) injectBotMessage(nextMessage);
  };

  const handleDocumentUploaded = (data: any) => {
    if (data?.registration?.success) {
      kycRegistrationComplete(data.registration);
      injectBotMessage(data.registration.message);
    } else if (data?.success === false && data?.message) {
      injectBotMessage(data.message); // e.g. "looks like a scanned PDF" — let them retry
    }
  };

  const handleWelcomeOption = (opt: string) => {
    if (opt === 'Existing Customer') {
      promptExistingLogin();
    } else {
      sendMessage(opt);
    }
  };

  const handleLogout = () => {
    logout();
    setShowAuthGate(false); // back to guest browsing, not trapped on the login screen
    resetChat();
  };

  if (showLoginGate) {
    return (
      <LoginPage
        step={auth.step}
        loading={loading}
        error={error}
        demoOtp={demoOtp}
        setStep={setStep}
        existingLoginStep1={existingLoginStep1}
        existingLoginStep2={handleExistingStep2}
        newUserStep1={newUserStep1}
        newUserStep2={handleNewUserStep2}
        kycVerifyIdentity={handleKycVerifyIdentity}
        onClose={() => setShowAuthGate(false)}
      />
          );
  }

  return (
    <div onMouseMove={handleMouseMove} className="flex h-screen bg-[#f8f9fb] dark:bg-[#05070d] font-sans overflow-hidden" style={{ '--mouse-x': `${mousePos.x}px`, '--mouse-y': `${mousePos.y}px` } as React.CSSProperties}>
      {/* Left sidebar */}
      <Sidebar
        interestRates={interestRates}
        loanTypes={loanTypes}
        onNewApplication={handleNewApplication}
        isAuthenticated={auth.step === 'authenticated'}
        userName={auth.fullName}
        onLoginClick={promptLogin}
        onLogoutClick={handleLogout}
        accountNumbers={(auth.profile as any)?.account_numbers}
        theme={theme}
        onToggleTheme={toggleTheme}
        token={auth.token}
        customerId={auth.customerId}
        onLoadConversation={handleLoadConversation}
        onAdvisorClick={() => setAdvisorOpen(true)}
      />

      {/* Main chat area */}
      <main className="flex-1 flex flex-col min-w-0">
        <ChatWindow
          messages={messages}
          isTyping={isTyping}
          onWelcomeOption={handleWelcomeOption}
          sessionId={sessionId}
          token={auth.token}
          customerId={auth.customerId}
          customerPhone={(auth.profile as any)?.phone}
          onNewApplication={handleNewApplication}
          onOpenAdvisor={auth.step === 'authenticated' ? () => setAdvisorOpen(true) : undefined}
          userName={auth.fullName}
        />
        {auth.step === 'financial_docs' && (
          <div style={{ display: 'flex', gap: 12, padding: '0 16px 12px', flexWrap: 'wrap' }}>
            <div style={{ flex: '1 1 200px' }}>
              <FileUploader
                label="Last 3 Salary Slips"
                docType="salary_slip"
                token={auth.tempId ?? ''}
                multiple
                onResult={handleDocumentUploaded}
              />
            </div>
            <div style={{ flex: '1 1 200px' }}>
              <FileUploader
                label="Last 6 Months Bank Statements"
                docType="bank_statement"
                token={auth.tempId ?? ''}
                multiple
                onResult={handleDocumentUploaded}
              />
            </div>
            <div style={{ flex: '1 1 200px' }}>
              <FileUploader
                label="Latest ITR (optional)"
                docType="itr"
                token={auth.tempId ?? ''}
                onResult={handleDocumentUploaded}
              />
            </div>
          </div>
        )}
        <ChatInput
          value={inputValue}
          onChange={setInputValue}
          onSend={sendMessage}
          placeholder={isWarmingUp ? 'Connecting...' : 'How can I help you?'}
        />
      </main>

      {/* Right context panel — only meaningful once authenticated */}
      {auth.step === 'authenticated' && (
        <ContextPanel
          profile={auth.profile as unknown as CustomerProfile | null}
          creditScore={currentCreditScore}
          creditRating={currentCreditScore.label}
          sessionId={sessionId}
          token={auth.token}
          customerId={auth.customerId}
        />
      )}

      {/* Financial Advisor panel — slide-in overlay, auth-gated */}
      {advisorOpen && auth.token && (
        <AdvisorPanel
          sessionId={sessionId}
          token={auth.token}
          onClose={() => setAdvisorOpen(false)}
        />
      )}
    </div>
  );
}