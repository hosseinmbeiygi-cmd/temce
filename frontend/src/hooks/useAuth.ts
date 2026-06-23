import { useState, useEffect } from 'react';
import { getStoredAuth } from '@/lib/api';

export function useAuth() {
  const [auth, setAuth] = useState<{ token: string; refreshToken: string; user: any } | null>(null);

  useEffect(() => {
    setAuth(getStoredAuth());
  }, []);

  return {
    auth,
    isAuthenticated: !!auth,
    user: auth?.user,
  };
}
