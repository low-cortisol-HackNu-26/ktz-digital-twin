"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Zap } from "lucide-react";
import { loginDispatcher, readStoredSession } from "@/lib/dispatcherAuth";
import { cn } from "@/lib/utils";

export default function LoginPage() {
  const router = useRouter();
  const [uid, setUid] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (readStoredSession()) router.replace("/dispatcher");
  }, [router]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await loginDispatcher(uid.trim(), password);
      router.replace("/dispatcher");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка входа");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-disp-bg px-4">
      <div className="w-full max-w-md rounded-2xl border border-white/10 bg-disp-panel/80 p-8 shadow-xl backdrop-blur">
        <div className="mb-6 flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-disp-accent/20 text-disp-accent">
            <Zap className="h-7 w-7" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white">Диспетчерская консоль</h1>
            <p className="text-sm text-slate-400">Вход через сервис диспетчеризации (порт 8002)</p>
          </div>
        </div>

        <form onSubmit={onSubmit} className="space-y-4">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-400">Идентификатор (UID)</label>
            <input
              value={uid}
              onChange={(e) => setUid(e.target.value)}
              autoComplete="username"
              className="w-full rounded-lg border border-white/15 bg-black/30 px-3 py-2 text-white outline-none focus:border-disp-accent"
              required
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-400">Пароль</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              className="w-full rounded-lg border border-white/15 bg-black/30 px-3 py-2 text-white outline-none focus:border-disp-accent"
              required
            />
          </div>
          {error ? <p className="text-sm text-red-400">{error}</p> : null}
          <button
            type="submit"
            disabled={loading}
            className={cn(
              "w-full rounded-lg bg-disp-accent py-2.5 text-sm font-semibold text-white hover:brightness-110",
              loading && "opacity-60",
            )}
          >
            {loading ? "Вход…" : "Войти"}
          </button>
        </form>

        <p className="mt-6 text-center text-xs text-slate-500">
          Первый пользователь в БД диспетчера — роль Admin через{" "}
          <code className="text-slate-400">/docs</code>. Для киоска (машинист) используйте{" "}
          <Link href={process.env.NEXT_PUBLIC_CLIENT_APP_URL ?? "http://localhost:3000"} className="text-disp-accent hover:underline">
            клиент :3000
          </Link>
          {` `}(авторизация на API :8000 после синхронизации пользователей).
        </p>
      </div>
    </div>
  );
}
