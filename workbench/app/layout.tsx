import type { Metadata } from "next";
import "./globals.css";
import { HydrationBoundary } from "@/components/HydrationBoundary";
import { Nav } from "@/components/Nav";

export const metadata: Metadata = {
  title: "SOVEREIGN Workbench",
  description:
    "On-Premise Agentic AI Workbench for Confidential Industrial Work",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body className="antialiased">
        <HydrationBoundary>
          <div className="flex min-h-screen">
            <Nav />
            <div className="flex-1 min-w-0 flex flex-col">
              <main className="flex-1 min-w-0">{children}</main>
            </div>
          </div>
        </HydrationBoundary>
      </body>
    </html>
  );
}
