"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { readStoredSession } from "@/lib/authClient";

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    router.replace(readStoredSession() ? "/dashboard/health" : "/login");
  }, [router]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-cabin-bg text-slate-400">
      Loading…
    </div>
  );
}
