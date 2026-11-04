"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  DEFAULT_PERSONA,
  PERSONAS,
  PERSONA_STORAGE_KEY,
  isPersonaId,
  type PersonaDefinition,
  type PersonaId,
} from "./personas";

interface PersonaContextValue {
  persona: PersonaId;
  definition: PersonaDefinition;
  setPersona: (id: PersonaId) => void;
  /** False until the persisted choice has been adopted after mount. */
  ready: boolean;
}

const PersonaContext = createContext<PersonaContextValue | null>(null);

function readStoredPersona(): PersonaId {
  if (typeof window === "undefined") return DEFAULT_PERSONA;
  try {
    const stored = window.localStorage.getItem(PERSONA_STORAGE_KEY);
    return isPersonaId(stored) ? stored : DEFAULT_PERSONA;
  } catch {
    // Private mode / blocked storage: keep the deterministic default.
    return DEFAULT_PERSONA;
  }
}

export function PersonaProvider({ children }: { children: ReactNode }) {
  // SSR-safe: server and first client render agree on the default; the stored
  // preference is adopted after mount so hydration never mismatches.
  const [persona, setPersonaState] = useState<PersonaId>(DEFAULT_PERSONA);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setPersonaState(readStoredPersona());
    setReady(true);
  }, []);

  const setPersona = useCallback((id: PersonaId) => {
    setPersonaState(id);
    try {
      window.localStorage.setItem(PERSONA_STORAGE_KEY, id);
    } catch {
      // Storage is a convenience, not a requirement.
    }
  }, []);

  const value = useMemo<PersonaContextValue>(
    () => ({ persona, definition: PERSONAS[persona], setPersona, ready }),
    [persona, setPersona, ready],
  );

  return <PersonaContext.Provider value={value}>{children}</PersonaContext.Provider>;
}

/**
 * Persona selection for UI adaptation. Falls back to the default persona when
 * rendered outside a provider (e.g. an isolated component test), because this
 * is a presentation preference and must never break rendering.
 */
export function usePersona(): PersonaContextValue {
  const ctx = useContext(PersonaContext);
  if (ctx) return ctx;
  return {
    persona: DEFAULT_PERSONA,
    definition: PERSONAS[DEFAULT_PERSONA],
    setPersona: () => undefined,
    ready: false,
  };
}
