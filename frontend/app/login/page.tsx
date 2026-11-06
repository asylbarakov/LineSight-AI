"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ApiError, login } from "@/lib/api";
import { ThemeToggle } from "@/components/ThemeToggle";
import { LineScan } from "@/components/auth/LineScan";
import styles from "./login.module.css";

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
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось войти");
      setBusy(false);
    }
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div className={styles.brand}><span className={styles.brandMark} aria-hidden="true" />LineSight AI</div>
        <ThemeToggle />
      </header>
      <main className={styles.main}>
        <section className={styles.formSide} aria-labelledby="login-title">
          <form onSubmit={submit} className={styles.form} aria-busy={busy} aria-describedby="login-description">
            <div className={styles.formHeading}>
              <h1 id="login-title" className="page-title">Вход в систему</h1>
              <p id="login-description" className={styles.description}>Видеоинспекции линий электропередачи.<br className={styles.desktopBreak} /> Анализ находок и решения инженера.</p>
            </div>
            <label className={styles.field} htmlFor="login-username">
              <span>Логин</span>
              <input
                id="login-username"
                name="username"
                autoFocus
                autoComplete="username"
                autoCapitalize="none"
                spellCheck={false}
                aria-required="true"
                aria-describedby={error ? "login-error" : undefined}
                value={user}
                onChange={(e) => setUser(e.target.value)}
                className={styles.input}
              />
            </label>
            <label className={styles.field} htmlFor="login-password">
              <span>Пароль</span>
              <input
                id="login-password"
                name="password"
                type="password"
                autoComplete="current-password"
                aria-required="true"
                aria-describedby={error ? "login-error" : undefined}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={styles.input}
              />
            </label>
            {error && <p id="login-error" className={styles.error} role="alert">{error}</p>}
            <button type="submit" disabled={busy} className={`btn-primary ${styles.submit}`}>
              {busy ? "Вход…" : "Войти"}
            </button>
          </form>
        </section>
        <LineScan />
      </main>
    </div>
  );
}
