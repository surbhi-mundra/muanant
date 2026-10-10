"use client";

import Link from "next/link";

export function Nav() {
  return (
    <nav className="sovereign-nav">
      <strong>SOVEREIGN</strong>
      <Link href="/">Dashboard</Link>
      <Link href="/documents">Documents</Link>
      <Link href="/search">Search</Link>
      <Link href="/rag">Ask</Link>
      <Link href="/agents">Agents</Link>
      <Link href="/deliverables">Deliverables</Link>
      <Link href="/audit">Audit</Link>
    </nav>
  );
}
