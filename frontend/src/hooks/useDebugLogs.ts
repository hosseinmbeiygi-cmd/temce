import { useState, useCallback, useEffect, useMemo } from 'react';

export interface DebugLog {
  id: string;
  endpoint: string;
  status: 'loading' | 'success' | 'error' | 'info';
  data?: unknown;
  error?: string;
  timestamp: string;
  duration?: number;
  method?: string;
}

export interface DebugStats {
  total: number;
  loading: number;
  success: number;
  error: number;
  info: number;
  averageDuration: number;
}

const STORAGE_KEY = 'debug_logs';
const MAX_LOGS = 100;

export function useDebugLogs(maxLogs: number = MAX_LOGS) {
  // بارگذاری لاگ‌های ذخیره‌شده از localStorage (فقط در کلاینت)
  const loadSavedLogs = useCallback((): DebugLog[] => {
    // فقط در سمت کلاینت اجرا شود
    if (typeof window === 'undefined') return [];
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed)) return parsed;
      }
    } catch (e) {
      console.warn('Failed to load saved logs:', e);
    }
    return [];
  }, []);

  const [logs, setLogs] = useState<DebugLog[]>(() => loadSavedLogs());
  const [isEnabled, setIsEnabled] = useState(true);

  // ذخیره‌سازی خودکار در localStorage (فقط در کلاینت)
  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(logs.slice(0, maxLogs)));
    } catch (e) {
      console.warn('Failed to save logs:', e);
    }
  }, [logs, maxLogs]);

  const addLog = useCallback(
    (endpoint: string, status: DebugLog['status'], data?: unknown, error?: string, method: string = 'GET') => {
      if (!isEnabled) return;

      const newLog: DebugLog = {
        id: `${Date.now()}-${Math.random().toString(36).substr(2, 8)}`,
        endpoint,
        status,
        data,
        error,
        method,
        timestamp: new Date().toLocaleTimeString('fa-IR'),
        duration: (data as Record<string, any> | undefined)?.__duration as number | undefined,
      };

      setLogs((prev) => {
        const updated = [newLog, ...prev];
        return updated.slice(0, maxLogs);
      });

      const emoji = status === 'success' ? '✅' : status === 'error' ? '❌' : status === 'loading' ? '⏳' : 'ℹ️';
      console.log(`${emoji} [${status.toUpperCase()}] ${endpoint}`, data || error || '');
    },
    [isEnabled, maxLogs]
  );

  const clearLogs = useCallback(() => {
    setLogs([]);
  }, []);

  const toggleEnabled = useCallback(() => {
    setIsEnabled((prev) => !prev);
  }, []);

  const stats = useMemo<DebugStats>(() => {
    const total = logs.length;
    const loading = logs.filter(l => l.status === 'loading').length;
    const success = logs.filter(l => l.status === 'success').length;
    const error = logs.filter(l => l.status === 'error').length;
    const info = logs.filter(l => l.status === 'info').length;

    const successfulLogs = logs.filter(l => l.status === 'success' && l.duration);
    const avgDuration = successfulLogs.length > 0
      ? successfulLogs.reduce((acc, l) => acc + (l.duration || 0), 0) / successfulLogs.length
      : 0;

    return { total, loading, success, error, info, averageDuration: avgDuration };
  }, [logs]);

  const getLogsByEndpoint = useCallback((endpoint: string) => {
    return logs.filter(l => l.endpoint === endpoint);
  }, [logs]);

  const getErrors = useCallback(() => {
    return logs.filter(l => l.status === 'error');
  }, [logs]);

  return {
    logs,
    stats,
    addLog,
    clearLogs,
    isEnabled,
    toggleEnabled,
    getLogsByEndpoint,
    getErrors,
  };
}