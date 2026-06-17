import React, { useState } from 'react';
import { Sidebar } from './components/Sidebar';
import { ContextPanel } from './components/ContextPanel';
import { ChatWindow } from './components/chat/ChatWindow';
import { ChatInput } from './components/chat/ChatInput';
import { LoginPage } from './pages/LoginPage';
import { useChat } from './hooks/useChat';
import { useAuth } from './hooks/useAuth';
import { workflowSteps, loanTypes, interestRates, creditScore } from './store/appState';

// Generates a fresh session id each time the tab opens — dies with the tab
const SESSION_ID = Math.random().toString(36).slice(2);

export default function App() {
  const {
    auth, loading, error, demoOtp, setStep,
    existingLoginStep1, existingLoginStep2,
    newUserStep1, newUserStep2,
    logout,
  } = useAuth(SESSION_ID);

  // Guest browsing: the login screen only shows when explicitly triggered —
  // either the user clicks Sign In, or the orchestrator detects loan intent
  // from a logged-out user (type: "auth_required") and asks us to gate it.
  const [showAuthGate, setShowAuthGate] = useState(false);

  const promptLogin = () => {
    setStep('choose_type');
    setShowAuthGate(true);
  };

  const { messages, isTyping, inputValue, setInputValue, sendMessage, injectBotMessage } =
    useChat(auth.token, SESSION_ID, promptLogin);

  const showLoginGate = showAuthGate && auth.step !== 'authenticated';

  const handleExistingStep2 = async (otp: string) => {
    const nextMessage = await existingLoginStep2(otp);
    if (nextMessage) injectBotMessage(nextMessage);
  };

  const handleNewUserStep2 = async (otp: string) => {
    const nextMessage = await newUserStep2(otp);
    if (nextMessage) injectBotMessage(nextMessage);
  };

  const handleWelcomeOption = (opt: string) => {
    sendMessage(opt);
  };

  const handleLogout = () => {
    logout();
    setShowAuthGate(false); // back to guest browsing, not trapped on the login screen
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
      />

      {/* Main chat area */}
      <main className="flex-1 flex flex-col bg-white min-w-0">
        <ChatWindow
          messages={messages}
          isTyping={isTyping}
          onWelcomeOption={handleWelcomeOption}
        />
        <ChatInput
          value={inputValue}
          onChange={setInputValue}
          onSend={sendMessage}
        />
      </main>

      {/* Right context panel — only meaningful once authenticated */}
      {auth.step === 'authenticated' && (
        <ContextPanel steps={workflowSteps} creditScore={creditScore} />
      )}
    </div>
  );
}