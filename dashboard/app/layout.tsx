import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import { Analytics } from "@vercel/analytics/react";
import { SpeedInsights } from "@vercel/speed-insights/next";
import "./globals.css";
import Sidebar from "@/components/Sidebar";
import TrialBanner from "@/components/TrialBanner";

export const metadata: Metadata = {
  title: "LocalMate | Local Business Automation by CrewCircle",
  description:
    "AI-powered automation for Australian small businesses. Review responses, SEO reports, competitor tracking, patient rebooking, and menu sync.",
  metadataBase: new URL("https://localmate.crewcircle.com.au"),
  openGraph: {
    title: "LocalMate | Local Business Automation by CrewCircle",
    description:
      "AI-powered automation for Australian small businesses.",
    type: "website",
    locale: "en_AU",
    siteName: "LocalMate",
  },
  twitter: {
    card: "summary_large_image",
    title: "LocalMate | Local Business Automation by CrewCircle",
    description:
      "AI-powered automation for Australian small businesses.",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <body className="min-h-full bg-background text-foreground antialiased flex flex-col">
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-[100] focus:rounded-lg focus:bg-accent focus:px-4 focus:py-2 focus:text-accent-foreground focus:shadow-lg"
        >
          Skip to main content
        </a>
        <div className="flex min-h-screen">
          <Sidebar />
          <div className="flex flex-1 flex-col">
            <TrialBanner />
            <main id="main-content" className="flex-1 mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
              {children}
            </main>
          </div>
        </div>
        <Analytics />
        <SpeedInsights />
      </body>
    </html>
  );
}
