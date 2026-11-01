import { useCallback, useEffect, useRef } from "react";

/**
 * Invalidates in-flight async work when a newer request starts or the
 * component unmounts, so a late response cannot overwrite fresher state.
 *
 * Call the returned function when a request starts; it returns a predicate
 * that is `true` only while that request is still the latest one.
 */
export function useStaleGuard(): () => () => boolean {
  const latest = useRef(0);

  useEffect(
    () => () => {
      latest.current += 1;
    },
    [],
  );

  return useCallback(() => {
    const id = ++latest.current;
    return () => id === latest.current;
  }, []);
}
