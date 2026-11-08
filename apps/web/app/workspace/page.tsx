import Link from "next/link";
import { auth, authConfigured } from "@/lib/auth/server";
import { ApiIdentityStatus } from "./status";
import { signOut } from "./actions";

export const dynamic = "force-dynamic";

export default async function WorkspacePage() {
  if (!authConfigured) return <main className="auth-shell"><section className="auth-card"><h1>Нэвтрэх үйлчилгээ бэлэн биш байна</h1><p>NEON_AUTH_BASE_URL болон NEON_AUTH_COOKIE_SECRET тохируулах шаардлагатай.</p></section></main>;
  const { data, error } = await auth.getSession();
  if (error || !data?.user) {
    return <main className="auth-shell"><section className="auth-card"><h1>Нэвтрэх шаардлагатай</h1><Link href="/auth/sign-in">Нэвтрэх</Link></section></main>;
  }

  return (
    <main className="dashboard-shell">
      <header className="dashboard-header">
        <div><div className="brand">CARBON ESG</div><p>Байгууллагын нүүрстөрөгчийн бүртгэл</p></div>
        <form action={signOut}><button className="button-secondary" type="submit">Гарах</button></form>
      </header>
      <section className="welcome-card">
        <p className="eyebrow">НЭВТЭРСЭН ХЭРЭГЛЭГЧ</p>
        <h1>Сайн байна уу, {data.user.name || data.user.email}</h1>
        <p>Таны бүртгэл амжилттай холбогдлоо. Байгууллагын ажлын орчин дараагийн хөгжүүлэлтээр идэвхжинэ.</p>
        <ApiIdentityStatus />
      </section>
      <Link href="/" className="text-link">Нүүр хуудас руу буцах</Link>
    </main>
  );
}
