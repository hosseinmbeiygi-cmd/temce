'use client';
import { toast } from 'sonner';
import { useEffect, useCallback, useRef } from 'react';

export interface NotificationData {
  id: string;
  title: string;
  body: string;
  type?: 'success' | 'error' | 'warning' | 'info';
  timestamp?: number;
}

interface NotificationToastProps {
  websocketUrl?: string;
}

export function useNotificationToast() {
  const showToast = useCallback((notification: NotificationData) => {
    const { title, body, type = 'info' } = notification;

    switch (type) {
      case 'success':
        toast.success(title, { description: body });
        break;
      case 'error':
        toast.error(title, { description: body });
        break;
      case 'warning':
        toast.warning(title, { description: body });
        break;
      default:
        toast.info(title, { description: body });
    }
  }, []);

  return { showToast };
}

export function NotificationToast({ websocketUrl }: NotificationToastProps) {
  const wsRef = useRef<WebSocket | null>(null);
  const { showToast } = useNotificationToast();

  useEffect(() => {
    if (!websocketUrl) return;

    const connect = () => {
      try {
        const ws = new WebSocket(websocketUrl);
        wsRef.current = ws;

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.type === 'notification') {
              showToast({
                id: data.id || Date.now().toString(),
                title: data.title,
                body: data.body,
                type: data.level || 'info',
                timestamp: data.timestamp,
              });
            }
          } catch {
            // Ignore malformed messages
          }
        };

        ws.onclose = () => {
          setTimeout(connect, 3000);
        };
      } catch {
        setTimeout(connect, 3000);
      }
    };

    connect();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [websocketUrl, showToast]);

  return null;
}