"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

type NavEntry = {
  href: string;
  label: string;
  icon: React.ReactNode;
  group: "workspace" | "intelligence" | "system";
  description: string;
};

const I = {
  dashboard: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="9" rx="1.5" />
      <rect x="14" y="3" width="7" height="5" rx="1.5" />
      <rect x="14" y="12" width="7" height="9" rx="1.5" />
      <rect x="3" y="16" width="7" height="5" rx="1.5" />
    </svg>
  ),
  documents: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 3v4a1 1 0 0 0 1 1h4" />
      <path d="M17 21H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h7l5 5v11a2 2 0 0 1-2 2z" />
      <path d="M9 13h6M9 17h4" />
    </svg>
  ),
  search: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="7" />
      <path d="m21 21-4.3-4.3" />
    </svg>
  ),
  rag: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
      <path d="M8 10h.01M12 10h.01M16 10h.01" />
    </svg>
  ),
  agents: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="4" y="6" width="16" height="12" rx="2" />
      <path d="M12 2v2M9 2h6" />
      <circle cx="9" cy="12" r="1.2" fill="currentColor" stroke="none" />
      <circle cx="15" cy="12" r="1.2" fill="currentColor" stroke="none" />
      <path d="M2 12h2M20 12h2" />
    </svg>
  ),
  deliverables: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6" />
      <path d="M9 14l2 2 4-4" />
    </svg>
  ),
  audit: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2 4 5v6c0 5 3.5 9 8 11 4.5-2 8-6 8-11V5l-8-3z" />
      <path d="m9 12 2 2 4-4" />
    </svg>
  ),
};

const NAV: NavEntry[] = [
  {
    href: "/",
    label: "Dashboard",
    icon: I.dashboard,
    group: "workspace",
    description: "System overview",
  },
  {
    href: "/documents",
    label: "Documents",
    icon: I.documents,
    group: "workspace",
    description: "Upload & manage",
  },
  {
    href: "/search",
    label: "Search",
    icon: I.search,
    group: "intelligence",
    description: "Vector search the KB",
  },
  {
    href: "/rag",
    label: "Ask",
    icon: I.rag,
    group: "intelligence",
    description: "Grounded Q&A with citations",
  },
  {
    href: "/agents",
    label: "Agents",
    icon: I.agents,
    group: "intelligence",
    description: "Multi-step investigations",
  },
  {
    href: "/deliverables",
    label: "Deliverables",
    icon: I.deliverables,
    group: "intelligence",
    description: "Generate & export reports",
  },
  {
    href: "/audit",
    label: "Audit",
    icon: I.audit,
    group: "system",
    description: "Tamper-evident chain",
  },
];

const GROUP_LABELS: Record<NavEntry["group"], string> = {
  workspace: "Workspace",
  intelligence: "Intelligence",
  system: "System",
};

function isActive(pathname: string, href: string) {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(href + "/");
}

export function Nav() {
  const pathname = usePathname();
  const groups: NavEntry["group"][] = ["workspace", "intelligence", "system"];

  return (
    <aside
      className="sticky top-0 h-screen w-[260px] shrink-0 flex flex-col border-r"
      style={{
        background:
          "linear-gradient(180deg, #0d0d10 0%, #0a0a0b 100%)",
        borderColor: "var(--color-border)",
      }}
    >
      {/* Brand */}
      <div className="px-5 pt-5 pb-4 border-b" style={{ borderColor: "var(--color-border)" }}>
        <Link href="/" className="flex items-center gap-2.5 group">
          <div
            className="relative w-8 h-8 rounded-lg flex items-center justify-center"
            style={{
              background:
                "linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)",
              boxShadow: "0 4px 12px -4px rgba(99,102,241,0.6)",
            }}
          >
            <svg viewBox="0 0 24 24" className="w-4.5 h-4.5" fill="none" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2 4 5v6c0 5 3.5 9 8 11 4.5-2 8-6 8-11V5l-8-3z" />
              <path d="m9 12 2 2 4-4" />
            </svg>
          </div>
          <div className="flex flex-col leading-none">
            <span className="text-[15px] font-semibold tracking-tight text-white">
              SOVEREIGN
            </span>
            <span className="text-[10.5px] text-zinc-500 mt-0.5 tracking-wide uppercase">
              Workbench
            </span>
          </div>
        </Link>
      </div>

      {/* Nav groups */}
      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-5">
        {groups.map((g) => {
          const items = NAV.filter((n) => n.group === g);
          return (
            <div key={g} className="space-y-1">
              <div
                className="px-3 mb-1.5 text-[10.5px] font-semibold tracking-[0.08em] uppercase"
                style={{ color: "var(--color-text-subtle)" }}
              >
                {GROUP_LABELS[g]}
              </div>
              {items.map((item) => {
                const active = isActive(pathname, item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`sov-nav-item ${active ? "sov-nav-item-active" : ""}`}
                    title={item.description}
                  >
                    {item.icon}
                    <span className="flex-1 truncate">{item.label}</span>
                    {active && (
                      <span
                        className="w-1.5 h-1.5 rounded-full"
                        style={{ background: "var(--color-primary)" }}
                      />
                    )}
                  </Link>
                );
              })}
            </div>
          );
        })}
      </nav>

      {/* Footer status */}
      <div
        className="px-4 py-3 border-t flex items-center gap-2.5"
        style={{ borderColor: "var(--color-border)" }}
      >
        <span className="status-dot status-dot-ok" />
        <div className="flex-1 min-w-0">
          <div className="text-[12px] font-medium text-zinc-300 leading-none">
            On-Premise
          </div>
          <div className="text-[10.5px] text-zinc-500 mt-0.5 leading-none">
            Confidential · Air-gapped ready
          </div>
        </div>
        <span className="sov-badge badge-neutral">v1.0</span>
      </div>
    </aside>
  );
}
