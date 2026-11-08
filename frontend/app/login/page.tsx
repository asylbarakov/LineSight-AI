"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { ApiError, login } from "@/lib/api";
import { ThemeToggle } from "@/components/ThemeToggle";
import { LineScan } from "@/components/auth/LineScan";
import { loginFailureText, validateLogin } from "@/lib/login";
import styles from "./login.module.css";

export default function LoginPage() {
  const router = useRouter();
  const [user, setUser] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [invalidField, setInvalidField] = useState<"username" | "password" | null>(null);
  const submitting = useRef(false);
  const usernameInput = useRef<HTMLInputElement>(null);
  const passwordInput = useRef<HTMLInputElement>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (submitting.current) return;
    const validation = validateLogin(user, password);
    if (validation) {
      setError(validation.message);
      setInvalidField(validation.field);
      (validation.field === "username" ? usernameInput : passwordInput).current?.focus();
      return;
    }
    submitting.current = true;
    setBusy(true);
    setInvalidField(null);
    setError(null);
    try {
      await login(user.trim(), password);
      router.replace("/dashboard");
    } catch (err) {
      setError(loginFailureText(err instanceof ApiError ? err.status : undefined));
      submitting.current = false;
      setBusy(false);
    }
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <ThemeToggle />
      </header>
      <main className={styles.main}>
        <section className={styles.formSide} aria-labelledby="login-title">
          <form onSubmit={submit} className={styles.form} aria-busy={busy} aria-labelledby="login-title">
            <div className={styles.formHeading}>
              <div className={styles.brand} translate="no"><span className={styles.brandMark} aria-hidden="true" />LineSight AI</div>
              <h1 id="login-title" className="page-title">Вход в систему</h1>
            </div>
            <label className={styles.field} htmlFor="login-username">
              <span>Логин</span>
              <input
                id="login-username"
                ref={usernameInput}
                name="username"
                readOnly={busy}
                autoComplete="username"
                autoCapitalize="none"
                spellCheck={false}
                aria-required="true"
                aria-invalid={invalidField === "username" || undefined}
                aria-describedby={error ? "login-error" : undefined}
                value={user}
                onChange={(e) => { setUser(e.target.value); if (!invalidField || invalidField === "username") { setError(null); setInvalidField(null); } }}
                className={styles.input}
              />
            </label>
            <div className={styles.field}>
              <label htmlFor="login-password">Пароль</label>
              <div className={styles.passwordControl}>
              <input
                id="login-password"
                ref={passwordInput}
                name="password"
                type={showPassword ? "text" : "password"}
                readOnly={busy}
                autoComplete="current-password"
                aria-required="true"
                aria-invalid={invalidField === "password" || undefined}
                aria-describedby={error ? "login-error" : undefined}
                value={password}
                onChange={(e) => { setPassword(e.target.value); if (!invalidField || invalidField === "password") { setError(null); setInvalidField(null); } }}
                className={`${styles.input} ${styles.passwordInput}`}
              />
              <button type="button" className={styles.visibilityToggle} aria-label={showPassword ? "Скрыть пароль" : "Показать пароль"}
                aria-pressed={showPassword} aria-controls="login-password" onClick={() => setShowPassword(value => !value)}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
                  <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z" /><circle cx="12" cy="12" r="3" />
                  {showPassword && <path d="m3 3 18 18" />}
                </svg>
              </button>
              </div>
            </div>
            {error && <p id="login-error" className={styles.error} role="alert">{error}</p>}
            <button type="submit" disabled={busy} aria-label={busy ? "Вход…" : "Войти"} className={`btn-primary ${styles.submit}`}>
              {busy && <svg className={styles.spinner} width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2" strokeDasharray="40 17" /></svg>}
              <span role="status">{busy ? "Вход…" : "Войти"}</span>
            </button>
          </form>
        </section>
        <LineScan />
      </main>
    </div>
  );
}
