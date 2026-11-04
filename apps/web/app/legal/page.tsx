"use client";

import { useEffect, useMemo, useState } from "react";

type LegalAct = { id: string; code: string; title: string; status: string; source_url: string };
type Standard = { id: string; code: string; title: string; status: string; source_url: string };
const api = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export default function LegalRegistryPage() {
  const [tab, setTab] = useState<"laws" | "standards">("laws");
  const [query, setQuery] = useState("");
  const [acts, setActs] = useState<LegalAct[]>([]);
  const [standards, setStandards] = useState<Standard[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    Promise.all([
      fetch(api + "/v1/legal/acts").then((r) => { if (!r.ok) throw new Error("Хуулийн сангийн API холбогдсонгүй"); return r.json(); }),
      fetch(api + "/v1/standards").then((r) => { if (!r.ok) throw new Error("Стандартын сангийн API холбогдсонгүй"); return r.json(); })
    ]).then(([lawRows, standardRows]) => {
      if (!active) return;
      setActs(lawRows);
      setStandards(standardRows);
      setError("");
    }).catch((e: unknown) => {
      if (active) setError(e instanceof Error ? e.message : "Өгөгдөл татахад алдаа гарлаа.");
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const rows = useMemo(() => {
    const source = tab === "laws" ? acts : standards;
    const normalized = query.trim().toLocaleLowerCase();
    if (!normalized) return source;
    return source.filter((row) => (row.title + " " + row.code + " " + row.status).toLocaleLowerCase().includes(normalized));
  }, [acts, standards, tab, query]);

  return (
    <main style={{ minHeight: "100vh", background: "#f5f8f5", color: "#172923", padding: "36px clamp(18px,4vw,56px)", fontFamily: "Arial,sans-serif" }}>
      <div style={{ maxWidth: 1180, margin: "0 auto" }}>
        <a href="/" style={{ color: "#24734f", textDecoration: "none", fontSize: 13, fontWeight: 700 }}>← Carbon ESG руу буцах</a>
        <div style={{ marginTop: 30, display: "flex", justifyContent: "space-between", gap: 20, alignItems: "end", flexWrap: "wrap" }}>
          <div>
            <div style={{ color: "#6b8877", fontSize: 11, letterSpacing: 2, fontWeight: 800 }}>LEGAL & STANDARDS INTELLIGENCE</div>
            <h1 style={{ fontSize: 34, letterSpacing: -1.2, margin: "10px 0" }}>Хууль, стандартын сан</h1>
            <p style={{ color: "#75857b", fontSize: 14, margin: 0 }}>Монголын ESG, MRV, байгаль орчин, ногоон санхүүжилтийн эрх зүйн эх сурвалж.</p>
          </div>
          <div style={{ border: "1px solid #dce8de", background: "white", padding: "12px 16px", borderRadius: 12, fontSize: 12, color: "#587064" }}>Албан эх сурвалжтай · Хувилбарын хяналттай</div>
        </div>
        <div style={{ marginTop: 28, display: "flex", gap: 10, flexWrap: "wrap" }}>
          <button onClick={() => setTab("laws")} style={{ border: 0, borderRadius: 9, padding: "11px 18px", background: tab === "laws" ? "#1c8158" : "white", color: tab === "laws" ? "white" : "#496256", fontWeight: 700 }}>Хууль, журам ({acts.length})</button>
          <button onClick={() => setTab("standards")} style={{ border: 0, borderRadius: 9, padding: "11px 18px", background: tab === "standards" ? "#1c8158" : "white", color: tab === "standards" ? "white" : "#496256", fontWeight: 700 }}>Стандарт ({standards.length})</button>
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Нэр, код, төлөвөөр хайх..." style={{ flex: "1 1 260px", minWidth: 220, border: "1px solid #dce8de", borderRadius: 9, padding: "11px 14px", background: "white", outlineColor: "#1c8158" }} />
        </div>
        <section style={{ marginTop: 18, background: "white", border: "1px solid #e5ece6", borderRadius: 16, overflow: "hidden", boxShadow: "0 8px 28px rgba(22,53,39,.04)" }}>
          <div style={{ padding: "18px 22px", borderBottom: "1px solid #edf1ed", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <strong style={{ fontSize: 14 }}>{tab === "laws" ? "Монгол Улсын эрх зүйн актууд" : "MNS болон олон улсын стандарт"}</strong>
            <span style={{ fontSize: 12, color: "#829087" }}>{rows.length} бүртгэл</span>
          </div>
          {loading ? <div style={{ padding: 40, textAlign: "center", color: "#7d8b82" }}>Сангаас мэдээлэл татаж байна…</div> :
            error ? <div style={{ padding: 28, color: "#9a573d" }}>{error}. PostgreSQL тохируулж, seed командыг ажиллуулсны дараа жагсаалт харагдана.</div> :
            rows.length === 0 ? <div style={{ padding: 36, textAlign: "center", color: "#829087" }}>Хайлтад тохирох бүртгэл алга.</div> :
            <div style={{ display: "grid" }}>
              {rows.map((row) => <article key={row.id} style={{ padding: "17px 22px", borderBottom: "1px solid #f0f3f0", display: "grid", gridTemplateColumns: "minmax(0,1fr) auto", gap: 16, alignItems: "center" }}>
                <div>
                  <div style={{ fontSize: 10, letterSpacing: 1, color: "#8b9990", fontWeight: 800 }}>{row.code}</div>
                  <div style={{ marginTop: 5, fontSize: 14, fontWeight: 700, lineHeight: 1.5 }}>{row.title}</div>
                  <div style={{ marginTop: 6, fontSize: 11, color: "#87958c" }}>Төлөв: {row.status}</div>
                </div>
                <a href={row.source_url} target="_blank" rel="noreferrer" style={{ color: "#1c8158", fontSize: 12, fontWeight: 700, textDecoration: "none", whiteSpace: "nowrap" }}>Албан эх сурвалж ↗</a>
              </article>)}
            </div>}
        </section>
        <div style={{ marginTop: 18, padding: 16, borderRadius: 12, background: "#edf5ef", color: "#536d5d", fontSize: 12, lineHeight: 1.7 }}>
          Хуулийн бүрэн эх болон стандартын бүрэн текстийг зөвхөн албан эх сурвалж, хүчин төгөлдөр хувилбар, ашиглах эрхийг шалгасны дараа оруулна. Сангийн бүртгэл нь дангаараа хууль зүйн нийцлийн баталгаа болохгүй.
        </div>
      </div>
    </main>
  );
}
