import type { Metadata } from "next";
import "./globals.css";
import { Nav } from "@/components/Nav";

export const metadata: Metadata = {
  title: "SOVEREIGN Workbench",
  description: "On-Premise Agentic AI Workbench for Confidential Industrial Work",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <Nav />
        <main className="sovereign-container">{children}</main>
      </body>
    </html>
  );
}
