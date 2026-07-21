'use client';
import { useState, useCallback, useEffect } from 'react';

type Permission = 'default' | 'granted' | 'denied';

interface UseNotificationsReturn {
  permission: Permission;
  notify: (title: string, body: string, icon?: string) => void;
  requestPermission: () => Promise<Permission>;
}

export function useNotifications(): UseNotificationsReturn {
  const [permission, setPermission] = useState<Permission>('default');

  useEffect(() => {
    if (typeof window !== 'undefined' && 'Notification' in window) {
      setPermission(Notification.permission as Permission);
    }
  }, []);

  const requestPermission = useCallback(async (): Promise<Permission> => {
    if (typeof window === 'undefined' || !('Notification' in window)) {
      return 'denied';
    }

    if (Notification.permission === 'granted') {
      setPermission('granted');
      return 'granted';
    }

    if (Notification.permission === 'denied') {
      setPermission('denied');
      return 'denied';
    }

    const result = await Notification.requestPermission();
    setPermission(result as Permission);
    return result as Permission;
  }, []);

  const notify = useCallback((title: string, body: string, icon?: string) => {
    if (typeof window === 'undefined' || !('Notification' in window)) {
      return;
    }

    if (Notification.permission !== 'granted') {
      return;
    }

    new Notification(title, {
      body,
      icon: icon || '/icons/icon-192.png',
    });
  }, []);

  return { permission, notify, requestPermission };
}