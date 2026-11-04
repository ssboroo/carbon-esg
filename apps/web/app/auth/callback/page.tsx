"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getUserManager } from "../../auth-provider";

export default function AuthCallbackPage() {
  const router = useRouter();
  const [message, setMessage] = useState("Нэвтрэлтийг баталгаажуулж байна…");

  useEffect(() => {
    let active = true;
    const manager = getUserManager();
    if (!manager) {
      setMessage("OIDC тохиргоо дутуу байна. Администраторт хандана уу.");
      return;
    }
    manager.signinRedirectCallback()
      .then(() => { if (active) router.replace("/"); })
      .catch(() => { if (active) setMessage("Нэвтрэлт амжилтгүй. Дахин оролдоно уу."); });
    return () => { active = false; };
  }, [router]);

  return <main className="auth-shell"><section className="auth-card"><div className="brand-mark">C</div><h1>Carbon ESG</h1><p>{message}</p></section></main>;
}
