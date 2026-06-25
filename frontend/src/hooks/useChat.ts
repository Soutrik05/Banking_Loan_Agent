import { useState, useCallback, useRef, useEffect } from 'react';
import type { Message } from '../types';
import { sendChatMessage } from '../services/api';

export function useChat(
  token: string | null,
  sessionId: string,
  onAuthRequired?: () => void,
  initialMessages?: Message[]
) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isTyping, setIsTyping] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const sessionRef = useRef(sessionId);

  // sessionId can change after mount — a new "New Application" id, or a past
  // conversation's original session_id once it's loaded. Keep the ref (read
  // by sendMessage) in sync, otherwise every message keeps going to whatever
  // session was active on the very first render.
  useEffect(() => {
    sessionRef.current = sessionId;
  }, [sessionId]);

  useEffect(() => {
    if (initialMessages && initialMessages.length > 0) {
      setMessages(initialMessages);
    }
  }, [initialMessages]);

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
        type: res?.type,
        options: res?.options as any[],
        properties: res?.properties as any[],
      };
      setMessages(prev => [...prev, botMsg]);

      // 🔒 Orchestrator detected loan intent from a guest — pop the login screen after a 2-second delay.
      if (res?.type === 'auth_required') {
        setTimeout(() => {
          onAuthRequired?.();
        }, 2000);
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
  const injectBotMessage = useCallback((content: string, options?: any[]) => {
    const botMsg: Message = {
      id: Date.now().toString(),
      role: 'assistant',
      content,
      timestamp: new Date(),
      options,
    };
    setMessages(prev => [...prev, botMsg]);
  }, []);

  const resetChat = useCallback(() => {
    setMessages([]);
  }, []);

  return { messages, isTyping, inputValue, setInputValue, sendMessage, injectBotMessage, resetChat };
}
