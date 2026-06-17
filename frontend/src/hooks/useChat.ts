import { useState, useCallback, useRef } from 'react';
import type { Message } from '../types';
import { sendChatMessage } from '../services/api';

export function useChat(token: string | null, sessionId: string, onAuthRequired?: () => void) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isTyping, setIsTyping] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const sessionRef = useRef(sessionId);

  const sendMessage = useCallback(async (content: string) => {
    if (!content.trim()) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMsg]);
    setInputValue('');
    setIsTyping(true);

    try {
      // 🔌 BACKEND: POST /chat → orchestrator_agent.handle_message()
      const res = await sendChatMessage(content, sessionRef.current, token ?? undefined);

      const botMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: typeof res?.reply === 'string' ? res.reply : "Sorry, I couldn't process that response.",
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, botMsg]);

      // 🔒 Orchestrator detected loan intent from a guest — pop the login screen.
      if (res?.type === 'auth_required') {
        onAuthRequired?.();
      }
    } catch (e) {
      const errMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: "I'm having trouble connecting right now. Please try again in a moment.",
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errMsg]);
    } finally {
      setIsTyping(false);
    }
  }, [token, onAuthRequired]);

  /** Inject a bot message directly without a user turn — used after login/KYC steps */
  const injectBotMessage = useCallback((content: string) => {
    const botMsg: Message = {
      id: Date.now().toString(),
      role: 'assistant',
      content,
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, botMsg]);
  }, []);

  return { messages, isTyping, inputValue, setInputValue, sendMessage, injectBotMessage };
}
