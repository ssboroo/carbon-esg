"use client";

import Link from "next/link";
import { useActionState } from "react";
import { signInWithEmail } from "./actions";

export default function SignInPage() {
  const [state, action, pending] = useActionState(signInWithEmail, null);
  return (
    <main className="auth-shell">
      <section className="auth-card">
        <Link href="/" className="brand">CARBON ESG</Link>
        <h1>Нэвтрэх</h1>
        <p>Байгууллагын нүүрстөрөгчийн бүртгэлдээ нэвтэрнэ үү.</p>
        <form action={action} className="auth-form">
          <label htmlFor="email">Имэйл</label>
          <input id="email" name="email" type="email" autoComplete="email" required />
          <label htmlFor="password">Нууц үг</label>
          <input id="password" name="password" type="password" autoComplete="current-password" required />
          {state?.error && <p className="form-error" role="alert">{state.error}</p>}
          <button type="submit" disabled={pending}>{pending ? "Нэвтэрч байна…" : "Нэвтрэх"}</button>
        </form>
        <p className="auth-foot">Бүртгэлгүй юу? <Link href="/auth/sign-up">Бүртгүүлэх</Link></p>
      </section>
    </main>
  );
}
