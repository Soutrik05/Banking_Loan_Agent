import { useState, useEffect } from 'react';
import { Sidebar } from './components/Sidebar';
import { ContextPanel } from './components/ContextPanel';
import { ChatWindow } from './components/chat/ChatWindow';
import { ChatInput } from './components/chat/ChatInput';
import { LoginPage } from './pages/LoginPage';
import { FileUploader } from './components/FileUploader';
import { useChat } from './hooks/useChat';
import { useAuth } from './hooks/useAuth';
import { workflowSteps, loanTypes, interestRates, creditScore } from './store/appState';
import type { WorkflowStep, CreditScore } from './types';

// Generates a fresh session id each time the tab opens — dies with the tab
const SESSION_ID = Math.random().toString(36).slice(2);

export default function App() {
  const {
    auth, loading, error, demoOtp, setStep,
    existingLoginStep1, existingLoginStep2,
    newUserStep1, newUserStep2,
    kycVerifyIdentity, kycRegistrationComplete,
    logout,
  } = useAuth(SESSION_ID);

  const [currentSteps, setCurrentSteps] = useState<WorkflowStep[]>(workflowSteps);
  const [currentCreditScore, setCurrentCreditScore] = useState<CreditScore>(creditScore);

  // Poll backend session status
  useEffect(() => {
    fetch(`${import.meta.env.VITE_API_URL}/health`).catch(() => {});
  }, []);

  // Poll backend session status  ← your existing useEffect stays below
  useEffect(() => {
    if (auth.step !== 'authenticated') return;

    const pollStatus = async () => {
      try {
        const res = await fetch(`${import.meta.env.VITE_API_URL}/session/status?session_id=${SESSION_ID}`);
        if (!res.ok) return;
        const data = await res.json();

        // Map steps
        if (data.steps) {
          setCurrentSteps(prevSteps => {
            return prevSteps.map(step => {
              if (data.active_step === step.id) {
                return {
                  ...step,
                  status: 'active',
                  subLabel: step.id === 'risk' ? 'Processing...' : undefined
                };
              }
              const backendStatus = data.steps[step.id] || 'pending';
              return {
                ...step,
                status: backendStatus as 'completed' | 'active' | 'pending',
                subLabel: undefined
              };
            });
          });
        }

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
    const interval = setInterval(pollStatus, 3000);
    return () => clearInterval(interval);
  }, [auth.step]);

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

  const { messages, isTyping, inputValue, setInputValue, sendMessage, injectBotMessage, resetChat } =
    useChat(auth.token, SESSION_ID, promptLogin);

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
    <div className="flex h-screen bg-[#f8f9fb] font-sans overflow-hidden">
      {/* Left sidebar */}
      <Sidebar
        interestRates={interestRates}
        loanTypes={loanTypes}
        onNewApplication={() => {}}
        isAuthenticated={auth.step === 'authenticated'}
        userName={auth.fullName}
        onLoginClick={promptLogin}
        onLogoutClick={handleLogout}
        accountNumbers={(auth.profile as any)?.account_numbers}
      />

      {/* Main chat area */}
      <main className="flex-1 flex flex-col bg-white min-w-0">
        <ChatWindow
          messages={messages}
          isTyping={isTyping}
          onWelcomeOption={handleWelcomeOption}
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
        <ContextPanel steps={currentSteps} creditScore={currentCreditScore} />
      )}
    </div>
  );
}