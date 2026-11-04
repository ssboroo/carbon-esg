"use server";

import { auth, authConfigured } from "@/lib/auth/server";
import { redirect } from "next/navigation";

export async function signInWithEmail(_previous: { error: string } | null, formData: FormData) {
  if (!authConfigured) return { error: "Нэвтрэх үйлчилгээ тохируулагдаагүй байна." };
  const email = String(formData.get("email") ?? "").trim().toLowerCase();
  const password = String(formData.get("password") ?? "");
  if (!email || !password) return { error: "Имэйл болон нууц үгээ оруулна уу." };

  const { error } = await auth.signIn.email({ email, password });
  if (error) return { error: error.message || "Нэвтрэхэд алдаа гарлаа." };
  redirect("/workspace");
}
