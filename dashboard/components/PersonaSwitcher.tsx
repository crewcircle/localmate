"use client";

import { useState, useRef, useEffect } from "react";
import { ChevronDown, Users } from "lucide-react";
import type { PersonaId } from "@/lib/demo-personas";
import { PERSONA_LIST } from "@/lib/demo-personas";

interface PersonaSwitcherProps {
  currentId: PersonaId;
  onChange: (id: PersonaId) => void;
}

export default function PersonaSwitcher({ currentId, onChange }: PersonaSwitcherProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const current = PERSONA_LIST.find((p) => p.id === currentId)!;

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="inline-flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-1.5 text-sm font-medium text-foreground hover:bg-muted transition-colors"
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <Users className="h-4 w-4 text-muted-foreground" />
        <span>{current.name}</span>
        <span className="hidden sm:inline text-xs text-muted-foreground">
          · {current.businessName}
        </span>
        <ChevronDown className={`h-3.5 w-3.5 text-muted-foreground transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <ul
          role="listbox"
          className="absolute right-0 z-50 mt-1 w-72 overflow-hidden rounded-lg border border-border bg-background shadow-lg"
        >
          <div className="border-b border-border px-3 py-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Switch demo persona
          </div>
          {PERSONA_LIST.map((p) => {
            const isActive = p.id === currentId;
            return (
              <li key={p.id}>
                <button
                  role="option"
                  aria-selected={isActive}
                  onClick={() => {
                    onChange(p.id);
                    setOpen(false);
                  }}
                  className={`flex w-full items-center justify-between px-3 py-2.5 text-sm transition-colors hover:bg-muted ${
                    isActive ? "bg-accent/5 text-accent" : "text-foreground"
                  }`}
                >
                  <div className="text-left">
                    <p className="font-medium">{p.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {p.businessName}
                    </p>
                  </div>
                  <span className="rounded bg-muted px-1.5 py-0.5 text-xs font-medium text-muted-foreground">
                    {p.plan}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
