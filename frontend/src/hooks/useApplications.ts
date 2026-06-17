import { useState, useEffect, useCallback } from 'react';
import { getApplications, createApplication, updateApplication } from '../services/api';

export interface Application {
  id: string;
  type: string;
  amount: number;
  status: 'draft' | 'submitted' | 'under_review' | 'approved' | 'rejected';
  createdAt: string;
  propertyAddress?: string;
  workflowStep?: string;
}

export function useApplications(token: string | null) {
  const [applications, setApplications] = useState<Application[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchAll = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const data: any = await getApplications(token); // 🔌 BACKEND: GET /applications
      setApplications(data.applications ?? []);
    } catch (e) {
      console.error('Failed to fetch applications', e);
    } finally { setLoading(false); }
  }, [token]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const create = useCallback(async (payload: object) => {
    if (!token) return;
    const data: any = await createApplication(payload, token); // 🔌 BACKEND: POST /applications
    await fetchAll();
    return data.application;
  }, [token, fetchAll]);

  const saveDraft = useCallback(async (id: string, payload: object) => {
    if (!token) return;
    await updateApplication(id, { ...payload, status: 'draft' }, token); // 🔌 BACKEND: PATCH /applications/:id
    await fetchAll();
  }, [token, fetchAll]);

  return { applications, loading, create, saveDraft, refresh: fetchAll };
}
