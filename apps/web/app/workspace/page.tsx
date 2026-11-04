import Link from "next/link";
import { auth } from "@/lib/auth/server";
import { ApiIdentityStatus } from "./status";
import { SignOutButton } from "./sign-out";

export const dynamic = "force-dynamic";

export default async function WorkspacePage() {
  const { data, error } = await auth.getSession();
  if (error || !data?.user) {
    return <main className="auth-shell"><section className="auth-card"><h1>Нэвтрэх шаардлагатай</h1><Link href="/auth/sign-in">Нэвтрэх</Link></section></main>;
  }

  return (
    <main className="dashboard-shell">
      <header className="dashboard-header">
        <div><div className="brand">CARBON ESG</div><p>Байгууллагын нүүрстөрөгчийн бүртгэл</p></div>
        <SignOutButton />
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
