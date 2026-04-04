"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";

export function AuthGate({ children }: { children: React.ReactNode }) {
  const { ready, session } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!ready) return;
    if (!session) router.replace("/login");
  }, [ready, session, router]);

  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-cabin-bg text-slate-400">
        Loading…
      </div>
    );
  }

  if (!session) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-cabin-bg text-slate-400">
        Redirecting…
      </div>
    );
  }

  return <>{children}</>;
}
