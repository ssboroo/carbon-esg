"use server";

import { auth, authConfigured } from "@/lib/auth/server";
import { redirect } from "next/navigation";

export async function signUpWithEmail(_previous: { error: string } | null, formData: FormData) {
  if (!authConfigured) return { error: "Бүртгэлийн үйлчилгээ тохируулагдаагүй байна." };
  const name = String(formData.get("name") ?? "").trim();
  const email = String(formData.get("email") ?? "").trim().toLowerCase();
  const password = String(formData.get("password") ?? "");
  if (!name || !email || password.length < 8) {
    return { error: "Нэр, зөв имэйл болон хамгийн багадаа 8 тэмдэгттэй нууц үг оруулна уу." };
  }

  const { error } = await auth.signUp.email({ name, email, password });
  if (error) return { error: error.message || "Бүртгэл үүсгэхэд алдаа гарлаа." };
  redirect("/workspace");
}
