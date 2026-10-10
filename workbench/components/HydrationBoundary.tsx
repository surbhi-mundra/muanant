"use client";

import { useEffect, useState } from "react";

export function HydrationBoundary({ children }: { children: React.ReactNode }) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) return null;
  return children;
}
