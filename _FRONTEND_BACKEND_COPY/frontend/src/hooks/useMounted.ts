import { useState, useEffect } from "react";

/**
 * Returns true after the component has mounted on the client.
 *
 * This is useful for avoiding hydration mismatches in SSR. The state update
 * is intentionally done once on mount, so the strict `set-state-in-effect`
 * rule is suppressed.
 */
export function useMounted(): boolean {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    // Intentional mount-only flag; suppress strict lint rule.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMounted(true);
  }, []);

  return mounted;
}
