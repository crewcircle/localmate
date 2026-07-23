"use client";

import PersonaSwitcher from "@/components/PersonaSwitcher";
import type { PersonaId } from "@/lib/demo-personas";

interface DemoHeaderProps {
  personaId: PersonaId;
  onPersonaChange: (id: PersonaId) => void;
}

/** Single central "Demo" ribbon indicator — replaces scattered DemoBadges. */
export default function DemoHeader({
  personaId,
  onPersonaChange,
}: DemoHeaderProps) {
  return (
    <div className="sticky top-0 z-50 border-b border-border bg-accent/5 px-4 py-2">
      <div className="mx-auto flex max-w-7xl items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="-rotate-3 select-none rounded bg-accent px-2 py-0.5 text-xs font-bold uppercase tracking-wider text-accent-foreground">
            Demo
          </span>
          <span className="text-xs text-muted-foreground">
            Preview mode — data is illustrative
          </span>
        </div>
        <PersonaSwitcher
          currentId={personaId}
          onChange={onPersonaChange}
        />
      </div>
    </div>
  );
}
