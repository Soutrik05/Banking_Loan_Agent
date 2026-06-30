import { useState, useEffect, useCallback, useRef } from 'react';
import type { Message } from '../types';
import { getConversations, getConversationMessages, type ConversationSummary } from '../services/api';

export function useConversations(token: string | null, customerId: string | null) {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const lastFetchRef = useRef<number>(0);
  const fetchPromiseRef = useRef<Promise<ConversationSummary[]> | null>(null);

  // Tracks the CURRENT customerId synchronously (refs update immediately,
  // unlike state) so an in-flight fetch started for a previous customer
  // can detect, the instant it resolves, that it's now stale and must not
  // paint its data into the new customer's sidebar.
  const customerIdRef = useRef(customerId);
  useEffect(() => {
    customerIdRef.current = customerId;
  }, [customerId]);

  const fetchConversations = useCallback(async (force = false) => {
    if (!token || !customerId) {
      setConversations([]);
      return;
    }

    const now = Date.now();
    if (!force && now - lastFetchRef.current < 30000) {
      return;
    }

    const requestedCustomerId = customerId;

    if (fetchPromiseRef.current) {
      try {
        const data = await fetchPromiseRef.current;
        if (customerIdRef.current === requestedCustomerId) setConversations(data);
      } catch (err) {
        // Ignored
      }
      return;
    }

    setIsLoading(true);
    fetchPromiseRef.current = getConversations(customerId, token);

    try {
      const data = await fetchPromiseRef.current;
      // The customer may have changed (or logged out) while this request
      // was in flight — a stale response for someone else must never land.
      if (customerIdRef.current === requestedCustomerId) {
        setConversations(data);
        lastFetchRef.current = Date.now();
      }
    } catch (err) {
      if (customerIdRef.current === requestedCustomerId) setConversations([]);
    } finally {
      setIsLoading(false);
      fetchPromiseRef.current = null;
    }
  }, [token, customerId]);

  // Clear immediately on any customerId change (including logout -> null,
  // or login as a different customer in the same tab) so the previous
  // customer's list never lingers on screen while the new fetch (below) is
  // in flight — the race against a still-resolving OLD fetch is closed by
  // the customerIdRef check above, not by this synchronous clear alone.
  useEffect(() => {
    setConversations([]);
    lastFetchRef.current = 0;
    fetchPromiseRef.current = null;
  }, [customerId]);

  useEffect(() => {
    fetchConversations();
  }, [fetchConversations]);

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
        metadata: row.metadata ?? undefined,
      }));
      const conversation = conversations.find(c => c.id === conversationId);

      // The backend auto-generates a real title after this conversation's
      // next exchange (replacing the generic "New Application" placeholder)
      // — refresh shortly after so it shows up in the sidebar on its own.
      if (customerId) {
        setTimeout(() => {
          fetchConversations(true);
        }, 3000);
      }

      return { messages, sessionId: conversation?.session_id ?? null };
    } finally {
      setIsLoading(false);
    }
  }, [conversations, customerId, fetchConversations]);

  return { conversations, activeConversationId, loadConversation, isLoading };
}
