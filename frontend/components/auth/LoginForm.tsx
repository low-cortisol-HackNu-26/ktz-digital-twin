"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { getApiBase } from "@/lib/authClient";

export function LoginForm() {
  const router = useRouter();
  const { ready, session, signIn } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const usernameRef = useRef<HTMLInputElement>(null);
  const passwordRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!ready) return;
    if (session) router.replace("/dashboard/health");
  }, [ready, session, router]);

  useEffect(() => {
    if (ready && !session) usernameRef.current?.focus();
  }, [ready, session]);

  async function submit() {
    setError(null);
    const u = username.trim();
    if (!u || !password) {
      setError("Enter username and password, then press Enter.");
      return;
    }
    setBusy(true);
    try {
      await signIn(u, password);
      router.replace("/dashboard/health");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Sign-in failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className="mx-auto w-full max-w-md rounded-xl border border-cabin-border bg-cabin-panel/90 p-8 shadow-xl backdrop-blur select-none"
      data-kiosk-input
    >
      <h1 className="text-lg font-semibold text-white">Sign in</h1>
      <p className="mt-2 text-sm text-slate-400">
        Keyboard only: Tab between fields, Enter to sign in. Same as{" "}
        <code className="rounded bg-cabin-bg px-1.5 py-0.5 text-slate-300">
          POST /api/auth/card
        </code>{" "}
        with <code className="text-slate-300">uid</code> and{" "}
        <code className="text-slate-300">password</code>.
      </p>
      <p className="readout-sm mt-3 text-slate-500">
        API: <span className="text-slate-400">{getApiBase()}</span>
      </p>

      <div className="mt-8 space-y-4">
        <label className="block">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Username
          </span>
          <span className="mt-0.5 block text-[11px] text-slate-600">
            <code className="text-slate-500">company_id</code> in the database
          </span>
          <input
            ref={usernameRef}
            name="username"
            autoComplete="username"
            className="mt-2 w-full rounded-lg border border-cabin-border bg-cabin-bg px-3 py-2 text-slate-100 outline-none ring-sky-500/40 focus:ring-2"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                passwordRef.current?.focus();
              }
            }}
            disabled={busy}
          />
        </label>
        <label className="block">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Password
          </span>
          <input
            ref={passwordRef}
            name="password"
            type="password"
            autoComplete="current-password"
            className="mt-2 w-full rounded-lg border border-cabin-border bg-cabin-bg px-3 py-2 text-slate-100 outline-none ring-sky-500/40 focus:ring-2"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                void submit();
              }
            }}
            disabled={busy}
          />
        </label>
      </div>

      {error ? (
        <p className="mt-4 text-sm text-rose-300" role="alert">
          {error}
        </p>
      ) : null}
      {busy ? (
        <p className="readout-sm mt-4 text-slate-500">Signing in…</p>
      ) : null}
    </div>
  );
}
