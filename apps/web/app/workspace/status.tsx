"use client";

import { useEffect, useState } from "react";
import { authClient } from "@/lib/auth/client";

type Status = { loading: boolean; message: string; ok: boolean | null };

export function ApiIdentityStatus() {
  const [status, setStatus] = useState<Status>({ loading: true, message: "API баталгаажуулалтыг шалгаж байна…", ok: null });

  useEffect(() => {
    let active = true;
    async function verify() {
      try {
        const tokenResult = await authClient.token();
        if (tokenResult.error || !tokenResult.data?.token) {
          throw new Error(tokenResult.error?.message || "JWT token олдсонгүй");
        }
        const apiUrl = process.env.NEXT_PUBLIC_API_URL;
        if (!apiUrl) throw new Error("API URL тохируулаагүй байна");
        const response = await fetch(new URL("/v1/auth/me", apiUrl), {
          headers: { Authorization: `Bearer ${tokenResult.data.token}` },
          cache: "no-store"
        });
        if (!response.ok) throw new Error(response.status === 401 ? "API токеныг зөвшөөрсөнгүй" : `API алдаа: ${response.status}`);
        const identity = await response.json();
        if (active) setStatus({ loading: false, message: `API баталгаажуулалт амжилттай · ${identity.subject}`, ok: true });
      } catch (error) {
        if (active) setStatus({ loading: false, message: error instanceof Error ? error.message : "API холболтын алдаа", ok: false });
      }
    }
    verify();
    return () => { active = false; };
  }, []);

  return <p className={status.ok ? "api-status success" : status.ok === false ? "api-status error" : "api-status"}>{status.message}</p>;
}
