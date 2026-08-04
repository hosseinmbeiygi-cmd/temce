import { useEffect, useState } from "react";

interface ApiHealth {
  backend: "online" | "offline" | "checking";
  latency: number | null;
  lastCheck: string | null;
  endpoints: Record<string, "working" | "failed" | "untested">;
}

export function useApiMonitor(baseUrl: string = "http://localhost:8000") {
  const [health, setHealth] = useState<ApiHealth>({
    backend: "checking",
    latency: null,
    lastCheck: null,
    endpoints: {},
  });
  const [isChecking, setIsChecking] = useState(false);

  const checkBackend = async () => {
    if (isChecking) return;
    setIsChecking(true);
    setHealth((prev) => ({ ...prev, backend: "checking" }));

    try {
      const startTime = performance.now();
      const response = await fetch(`${baseUrl}/health`, {
        signal: AbortSignal.timeout(5000),
      });
      const endTime = performance.now();
      const latency = Math.round(endTime - startTime);

      if (response.ok) {
        setHealth((prev) => ({
          ...prev,
          backend: "online",
          latency,
          lastCheck: new Date().toLocaleTimeString("fa-IR"),
        }));
      } else {
        setHealth((prev) => ({
          ...prev,
          backend: "offline",
          latency,
          lastCheck: new Date().toLocaleTimeString("fa-IR"),
        }));
      }
    } catch {
      setHealth((prev) => ({
        ...prev,
        backend: "offline",
        latency: null,
        lastCheck: new Date().toLocaleTimeString("fa-IR"),
      }));
    } finally {
      setIsChecking(false);
    }
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional synchronous state reset on mount/filter change
    checkBackend();
    const interval = setInterval(checkBackend, 30000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- mount-only init
  }, []);

  return { health, checkBackend, isChecking };
}