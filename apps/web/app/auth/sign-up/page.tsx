"use client";

import Link from "next/link";
import { useActionState } from "react";
import { signUpWithEmail } from "./actions";

export default function SignUpPage() {
  const [state, action, pending] = useActionState(signUpWithEmail, null);
  return (
    <main className="auth-shell">
      <section className="auth-card">
        <Link href="/" className="brand">CARBON ESG</Link>
        <h1>Бүртгэл үүсгэх</h1>
        <p>Нүүрстөрөгчийн тайлангаа удирдаж эхлээрэй.</p>
        <form action={action} className="auth-form">
          <label htmlFor="name">Нэр</label>
          <input id="name" name="name" type="text" autoComplete="name" maxLength={120} required />
          <label htmlFor="email">Имэйл</label>
          <input id="email" name="email" type="email" autoComplete="email" required />
          <label htmlFor="password">Нууц үг</label>
          <input id="password" name="password" type="password" autoComplete="new-password" minLength={8} required />
          {state?.error && <p className="form-error" role="alert">{state.error}</p>}
          <button type="submit" disabled={pending}>{pending ? "Бүртгэж байна…" : "Бүртгүүлэх"}</button>
        </form>
        <p className="auth-foot">Бүртгэлтэй юу? <Link href="/auth/sign-in">Нэвтрэх</Link></p>
      </section>
    </main>
  );
}
