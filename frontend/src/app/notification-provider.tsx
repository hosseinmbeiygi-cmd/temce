'use client';

import { useEffect } from 'react';
import { useNotifications } from '@/hooks/useNotifications';

export function NotificationProvider({ children }: { children: React.ReactNode }) {
  const { requestPermission, permission } = useNotifications();

  useEffect(() => {
    // Auto-request permission on first interaction
    const handleInteraction = () => {
      if (permission === 'default') {
        requestPermission();
      }
    };

    document.addEventListener('click', handleInteraction, { once: true });
    return () => document.removeEventListener('click', handleInteraction);
  }, [permission, requestPermission]);

  return <>{children}</>;
}