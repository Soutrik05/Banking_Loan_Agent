import { useState, useEffect, useCallback } from 'react';
import type { Message } from '../types';
import { getConversations, getConversationMessages, type ConversationSummary } from '../services/api';

export function useConversations(token: string | null, customerId: string | null) {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!token || !customerId) {
      setConversations([]);
      return;
    }
    setIsLoading(true);
    getConversations(customerId)
      .then(setConversations)
      .catch(() => setConversations([]))
      .finally(() => setIsLoading(false));
  }, [token, customerId]);

  const loadConversation = useCallback(async (
    conversationId: string
  ): Promise<{ messages: Message[]; sessionId: string | null }> => {
    setIsLoading(true);
    try {
      const rows = await getConversationMessages(conversationId);
      setActiveConversationId(conversationId);
      const messages: Message[] = rows.map((row, idx) => ({
        id: row.id ?? `${conversationId}-${idx}`,
        role: row.role === 'user' ? 'user' : 'assistant' as const,
        content: row.content,
        timestamp: row.created_at ? new Date(row.created_at) : new Date(),
        type: row.message_type ?? undefined,
      }));
      const conversation = conversations.find(c => c.id === conversationId);
      return { messages, sessionId: conversation?.session_id ?? null };
    } finally {
      setIsLoading(false);
    }
  }, [conversations]);

  return { conversations, activeConversationId, loadConversation, isLoading };
}
