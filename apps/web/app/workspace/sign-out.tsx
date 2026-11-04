"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authClient } from "@/lib/auth/client";

export function SignOutButton() {
  const [pending, setPending] = useState(false);
  const router = useRouter();

  async function signOut() {
    setPending(true);
    try {
      const result = await authClient.signOut();
      if (result.error) throw new Error(result.error.message);
      router.replace("/auth/sign-in");
      router.refresh();
    } catch {
      setPending(false);
    }
  }

  return <button className="button-secondary" type="button" onClick={signOut} disabled={pending}>{pending ? "Гарч байна…" : "Гарах"}</button>;
}
