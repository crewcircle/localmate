"use client";

import { useCallback, useEffect, useState } from "react";
import type { PersonaId, Persona } from "@/lib/demo-personas";
import { PERSONAS, DEFAULT_PERSONA_ID } from "@/lib/demo-personas";

const STORAGE_KEY = "localmate_demo_persona";

/** Reactive hook for demo persona state, persisted to sessionStorage. */
export function useDemoPersona() {
  const [personaId, setPersonaIdState] = useState<PersonaId>(DEFAULT_PERSONA_ID);

  // Hydrate from sessionStorage on mount.
  useEffect(() => {
    const stored = sessionStorage.getItem(STORAGE_KEY);
    if (stored && stored in PERSONAS) {
      setPersonaIdState(stored as PersonaId);
    } else {
      setPersonaIdState(DEFAULT_PERSONA_ID);
    }
  }, []);

  const setPersonaId = useCallback((id: PersonaId) => {
    sessionStorage.setItem(STORAGE_KEY, id);
    setPersonaIdState(id);
  }, []);

  const persona: Persona = PERSONAS[personaId];

  return { personaId, persona, setPersonaId };
}
