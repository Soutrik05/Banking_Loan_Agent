import { useState, useEffect, useRef } from 'react';
import { Sidebar } from './components/Sidebar';
import { ContextPanel } from './components/ContextPanel';
import { ChatWindow } from './components/chat/ChatWindow';
import { ChatInput } from './components/chat/ChatInput';
import { LoginPage } from './pages/LoginPage';
import { FileUploader } from './components/FileUploader';
import { useChat } from './hooks/useChat';
import { useAuth } from './hooks/useAuth';
import { useTheme } from './hooks/useTheme';
import { loanTypes, interestRates, creditScore } from './store/appState';
import type { CreditScore, CustomerProfile, Message } from './types';

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
    }

    prevCustomerIdRef.current = newCustomerId;
  }, [auth.customerId]);

  const handleNewApplication = () => {
    setSessionId(crypto.randomUUID());
    resetChat();
    setInitialMessages(undefined);

    if (auth.token) {
      setCurrentCreditScore(creditScore);
      // Already authenticated — stay in the chat instead of dropping back to
      // the guest "Existing Customer / Just Browsing" landing screen, and
      // jump straight back into the property-choice step.
      injectBotMessage(
        "Great! Let's start a new application. Are you looking to take a loan against a property you already own, or are you looking to buy a new property using our loan?",
        [
          { label: 'I own a property', value: 'I own a property' },
          { label: 'I want to buy a property', value: 'I want to buy a property' },
        ]
      );
    } else {
      setCurrentCreditScore(creditScore);
    }
  };

  const showLoginGate = showAuthGate && auth.step !== 'authenticated' && auth.step !== 'financial_docs';

  const handleExistingStep2 = async (otp: string) => {
    const nextMessage = await existingLoginStep2(otp);
    if (nextMessage) {
      injectBotMessage(nextMessage, [
        { id: 'lap', label: 'I own a property' },
        { id: 'home_loan', label: 'I want to buy a property' },
      ]);
    }
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
    <div className="flex h-screen bg-[#f8f9fb] dark:bg-[#05070d] font-sans overflow-hidden">
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
    </div>
  );
}