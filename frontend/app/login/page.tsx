"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ApiError, login } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [user, setUser] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!user.trim() || !password) {
      setError("Введите логин и пароль");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await login(user.trim(), password);
      router.replace("/inspections");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось войти");
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <form onSubmit={submit} className="w-full max-w-sm rounded-2xl border border-line bg-surface p-8 shadow-xl">
        <div className="mb-6 flex items-center gap-2 text-lg font-semibold">
          <span className="inline-block h-3 w-3 rounded-sm bg-accent" />
          LineSight AI
        </div>
        <p className="mb-6 text-sm text-muted">Вход для администратора</p>
        <label className="mb-4 block text-sm">
          <span className="mb-1 block text-muted">Логин</span>
          <input
            autoFocus
            autoComplete="username"
            value={user}
            onChange={(e) => setUser(e.target.value)}
            className="w-full rounded-md border border-line bg-bg px-3 py-2 outline-none focus:border-accent"
          />
        </label>
        <label className="mb-4 block text-sm">
          <span className="mb-1 block text-muted">Пароль</span>
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-md border border-line bg-bg px-3 py-2 outline-none focus:border-accent"
          />
        </label>
        {error && <p className="mb-4 text-sm text-danger" role="alert">{error}</p>}
        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-md bg-accent px-4 py-2 text-sm font-medium text-black disabled:opacity-50"
        >
          {busy ? "Вход…" : "Войти"}
        </button>
      </form>
    </div>
  );
}
