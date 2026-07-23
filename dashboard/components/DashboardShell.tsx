"use client";

import { Toaster } from "sonner";
import Sidebar from "@/components/Sidebar";
import DemoHeader from "@/components/DemoHeader";
import { useDemoPersona } from "@/hooks/useDemoPersona";

export function DashboardShell({ children }: { children: React.ReactNode }) {
  const { personaId, persona, setPersonaId } = useDemoPersona();

  return (
    <div className="flex min-h-screen">
      <Sidebar persona={persona} />
      <div className="flex flex-1 flex-col">
        <DemoHeader personaId={personaId} onPersonaChange={setPersonaId} />
        <main
          id="main-content"
          className="flex-1 mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-8"
        >
          {children}
        </main>
      </div>
      <Toaster position="bottom-right" />
    </div>
  );
}
