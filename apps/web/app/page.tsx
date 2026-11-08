import Link from "next/link";

const metrics = [
  { label: "Нийт ялгаруулалт", value: "—", unit: "tCO₂e", note: "Өгөгдөл оруулсны дараа тооцно" },
  { label: "Scope 1", value: "—", unit: "tCO₂e", note: "Шууд ялгаруулалт" },
  { label: "Scope 2", value: "—", unit: "tCO₂e", note: "Худалдан авсан эрчим хүч" },
  { label: "Бүртгэсэн өгөгдөл", value: "0", unit: "мөр", note: "Үйл ажиллагааны мэдээлэл" }
];

export default function Home() {
  return (
    <main style={{ maxWidth: 1180, margin: "0 auto", padding: "44px 24px 72px" }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 20, marginBottom: 48, flexWrap: "wrap" }}>
        <div>
          <div style={{ color: "#176b4a", fontWeight: 800, letterSpacing: 1.5, fontSize: 13 }}>CARBON ESG</div>
          <div style={{ color: "#65766e", fontSize: 13, marginTop: 5 }}>Байгууллагын нүүрстөрөгчийн бүртгэл</div>
        </div>
        <div className="auth-links">
          <Link href="/auth/sign-in" className="button-secondary">Нэвтрэх</Link>
          <Link href="/auth/sign-up" className="button-primary">Бүртгүүлэх</Link>
        </div>
      </header>
      <section style={{ marginBottom: 34 }}>
        <p style={{ color: "#176b4a", fontWeight: 700, fontSize: 13, marginBottom: 10 }}>ESG & CARBON ACCOUNTING</p>
        <h1 style={{ fontSize: "clamp(32px, 5vw, 52px)", lineHeight: 1.08, letterSpacing: -1.8, maxWidth: 760, margin: "0 0 16px" }}>
          Ялгарлаа хэмж. <span style={{ color: "#176b4a" }}>Нөлөөгөө удирд.</span>
        </h1>
        <p style={{ color: "#65766e", lineHeight: 1.7, maxWidth: 650, margin: 0 }}>
          Эрчим хүч, түлшний хэрэглээг бүртгэж, Scope 1 болон Scope 2 ялгаруулалтыг эх сурвалжтай, шалгаж болохуйц байдлаар тооцох платформ.
        </p>
      </section>
      <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))", gap: 14, marginBottom: 28 }}>
        {metrics.map((item) => (
          <article key={item.label} style={{ background: "#fff", border: "1px solid #e1e9e4", borderRadius: 18, padding: 22 }}>
            <div style={{ color: "#65766e", fontSize: 13 }}>{item.label}</div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 7, margin: "18px 0 8px" }}>
              <strong style={{ fontSize: 32, letterSpacing: -1 }}>{item.value}</strong>
              <span style={{ color: "#65766e", fontSize: 12 }}>{item.unit}</span>
            </div>
            <div style={{ color: "#87958e", fontSize: 12 }}>{item.note}</div>
          </article>
        ))}
      </section>
      <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 16 }}>
        <article style={{ background: "#fff", border: "1px solid #e1e9e4", borderRadius: 18, padding: 24 }}>
          <h2 style={{ margin: "0 0 10px", fontSize: 18 }}>Дараагийн алхам</h2>
          <p style={{ color: "#65766e", lineHeight: 1.65, fontSize: 14 }}>Байгууллага, тайлант хугацаа, эрчим хүч болон түлшний хэрэглээний өгөгдөл бүртгэх хэсгийг хөгжүүлнэ.</p>
          <span style={{ display: "inline-block", marginTop: 8, color: "#176b4a", fontWeight: 700, fontSize: 13 }}>Өгөгдөл бүртгэл · Хөгжүүлж байна</span>
        </article>
        <article style={{ background: "#fff", border: "1px solid #e1e9e4", borderRadius: 18, padding: 24 }}>
          <h2 style={{ margin: "0 0 10px", fontSize: 18 }}>Тооцооллын зарчим</h2>
          <p style={{ color: "#65766e", lineHeight: 1.65, fontSize: 14 }}>CO₂e = Үйл ажиллагааны өгөгдөл × Баталгаажсан ялгарлын коэффициент. Коэффициент бүр эх сурвалж, он, нэгж, хувилбартай байна.</p>
          <span style={{ display: "inline-block", marginTop: 8, color: "#176b4a", fontWeight: 700, fontSize: 13 }}>Шалгаж болох тооцоолол</span>
        </article>
      </section>
      <footer style={{ color: "#87958e", fontSize: 12, marginTop: 42 }}>Carbon ESG · Эхний интерфэйсийн суурь хувилбар</footer>
    </main>
  );
}
