"use client";

import { FormEvent, ReactNode, useMemo, useState } from "react";

type Scope = "scope_1" | "scope_2";
type Activity = {
  id: string;
  name: string;
  scope: Scope;
  category: string;
  amount: string;
  unit: string;
  factor: string;
  source: string;
  sourceUrl: string;
  year: string;
  version: string;
  emissions?: number;
};

const apiUrl = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

const navItems = [
  { id: "overview", label: "Ерөнхий тойм", icon: "grid" },
  { id: "activities", label: "Өгөгдөл бүртгэл", icon: "layers" },
  { id: "reports", label: "Тайлан", icon: "file" },
  { id: "factors", label: "Коэффициент", icon: "leaf" },
  { id: "settings", label: "Тохиргоо", icon: "settings" }
] as const;

function Icon({ name, size = 18 }: { name: string; size?: number }) {
  const common = { width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.7, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true as const };
  const paths: Record<string, ReactNode> = {
    grid: <><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></>,
    layers: <><path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5"/><path d="m3 16 9 5 9-5"/></>,
    file: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6M8 13h8M8 17h8"/></>,
    leaf: <><path d="M20 4c-8 0-14 3-14 10a6 6 0 0 0 6 6c7 0 10-8 8-16Z"/><path d="M4 21c2-5 6-8 12-11"/></>,
    settings: <><circle cx="12" cy="12" r="3"/><path d="m19.4 15 .1.1 1.4 1.1-1.4 2.4-1.7-.7a8 8 0 0 1-1.7 1l-.3 1.8h-2.8l-.3-1.8a8 8 0 0 1-1.7-1l-1.7.7-1.4-2.4 1.4-1.1a8 8 0 0 1 0-2l-1.4-1.1 1.4-2.4 1.7.7a8 8 0 0 1 1.7-1l.3-1.8h2.8l.3 1.8a8 8 0 0 1 1.7 1l1.7-.7 1.4 2.4-1.4 1.1a8 8 0 0 1 0 2Z"/></>,
    bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"/><path d="M10 21h4"/></>,
    search: <><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></>,
    plus: <><path d="M12 5v14M5 12h14"/></>,
    arrow: <><path d="M5 12h14M13 6l6 6-6 6"/></>,
    download: <><path d="M12 3v12m-5-5 5 5 5-5"/><path d="M5 17v4h14v-4"/></>,
    check: <path d="m5 12 4 4L19 6"/>,
    zap: <><path d="m13 2-3 9h7l-6 11 2-9H6l7-11Z"/></>,
    clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
    menu: <><path d="M4 6h16M4 12h16M4 18h16"/></>,
    close: <><path d="m18 6-12 12M6 6l12 12"/></>
  };
  return <svg {...common}>{paths[name] || paths.grid}</svg>;
}

function formatNumber(value: number) {
  return new Intl.NumberFormat("mn-MN", { maximumFractionDigits: 3 }).format(value);
}

export default function Dashboard() {
  const [active, setActive] = useState("overview");
  const [showForm, setShowForm] = useState(false);
  const [mobileNav, setMobileNav] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [activities, setActivities] = useState<Activity[]>([]);
  const [scope1, setScope1] = useState(0);
  const [scope2, setScope2] = useState(0);
  const [form, setForm] = useState({
    name: "", scope: "scope_2" as Scope, category: "purchased_electricity",
    amount: "", unit: "kWh", factor: "", source: "", sourceUrl: "",
    year: "2026", version: "1.0", start: "2026-01-01", end: "2026-12-31"
  });

  const total = scope1 + scope2;
  const recordCount = activities.length;
  const pageTitle = navItems.find((item) => item.id === active)?.label || "Ерөнхий тойм";
  const scope1Share = total > 0 ? (scope1 / total) * 100 : 0;
  const scope2Share = total > 0 ? (scope2 / total) * 100 : 0;

  const chartBars = useMemo(() => {
    const buckets = Array.from({ length: 6 }, (_, i) => ({ label: ["I", "II", "III", "IV", "V", "VI"][i], scope1: 0, scope2: 0 }));
    activities.forEach((item, index) => {
      const bucket = buckets[index % buckets.length];
      if (item.scope === "scope_1") bucket.scope1 += item.emissions || 0;
      else bucket.scope2 += item.emissions || 0;
    });
    const max = Math.max(...buckets.map((b) => b.scope1 + b.scope2), 1);
    return buckets.map((b) => ({ ...b, height: Math.max(4, ((b.scope1 + b.scope2) / max) * 100) }));
  }, [activities]);

  async function submitActivity(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setNotice("");
    try {
      const response = await fetch(`${apiUrl}/v1/calculations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          reporting_period_start: form.start,
          reporting_period_end: form.end,
          records: [{
            name: form.name,
            scope: form.scope,
            category: form.category,
            activity_amount: form.amount,
            activity_unit: form.unit,
            emission_factor_kgco2e_per_unit: form.factor,
            factor_unit: form.unit,
            factor_source_name: form.source,
            factor_source_url: form.sourceUrl,
            factor_year: Number(form.year),
            factor_version: form.version
          }]
        })
      });
      if (!response.ok) {
        const errorBody = await response.json().catch(() => null);
        throw new Error(errorBody?.detail?.[0]?.msg || errorBody?.detail || "API хүсэлтийг боловсруулахад алдаа гарлаа.");
      }
      const result = await response.json();
      const calculated = result.records?.[0];
      const emissions = Number(calculated?.emissions_tco2e || 0);
      const next: Activity = {
        id: crypto.randomUUID(), name: form.name, scope: form.scope, category: form.category,
        amount: form.amount, unit: form.unit, factor: form.factor, source: form.source,
        sourceUrl: form.sourceUrl, year: form.year, version: form.version, emissions
      };
      setActivities((current) => [next, ...current]);
      if (form.scope === "scope_1") setScope1((current) => current + emissions);
      else setScope2((current) => current + emissions);
      setNotice("Тооцоолол амжилттай. Энэ дэлгэцийн түр жагсаалтад нэмэгдлээ; мэдээлэл серверт хадгалагдаагүй.");
      setShowForm(false);
      setForm((current) => ({ ...current, name: "", amount: "", factor: "", source: "", sourceUrl: "" }));
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Тодорхойгүй алдаа гарлаа.");
    } finally {
      setBusy(false);
    }
  }

  function downloadCsv() {
    const rows = [
      ["Нэр", "Scope", "Ангилал", "Хэмжээ", "Нэгж", "kgCO2e/unit", "tCO2e", "Эх сурвалж", "Он", "Хувилбар"],
      ...activities.map((a) => [a.name, a.scope, a.category, a.amount, a.unit, a.factor, String(a.emissions ?? 0), a.source, a.year, a.version])
    ];
    const csv = rows.map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(",")).join("\n");
    const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "carbon-esg-activities.csv";
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="app-shell">
      {mobileNav && <button className="mobile-scrim" aria-label="Цэс хаах" onClick={() => setMobileNav(false)} />}
      <aside className={`sidebar ${mobileNav ? "sidebar-open" : ""}`}>
        <div className="brand-lockup">
          <div className="brand-mark"><Icon name="leaf" size={22} /></div>
          <div><div className="brand-name">carbon<span>.</span></div><div className="brand-caption">ESG INTELLIGENCE</div></div>
          <button className="mobile-close" onClick={() => setMobileNav(false)} aria-label="Цэс хаах"><Icon name="close"/></button>
        </div>
        <div className="workspace-switch">
          <div className="workspace-avatar">N</div>
          <div className="workspace-copy"><strong>Nomad workspace</strong><span>Үнэгүй ажлын орчин</span></div>
          <span className="workspace-chevron">⌄</span>
        </div>
        <div className="nav-label">WORKSPACE</div>
        <nav className="side-nav" aria-label="Үндсэн цэс">
          {navItems.map((item) => (
            <button key={item.id} className={`nav-link ${active === item.id ? "nav-active" : ""}`} onClick={() => { setActive(item.id); setMobileNav(false); }}>
              <Icon name={item.icon}/><span>{item.label}</span>{item.id === "activities" && recordCount > 0 && <em>{recordCount}</em>}
            </button>
          ))}
        </nav>
        <div className="sidebar-spacer"/>
        <div className="sidebar-help">
          <div className="help-orbit"><Icon name="leaf" size={19}/></div>
          <strong>Ногоон шилжилтээ эхлүүл</strong>
          <p>Өгөгдөл бүртгэж, байгууллагын нөлөөллөө ойлгоорой.</p>
          <button onClick={() => { setActive("factors"); setMobileNav(false); }}>Аргачлалтай танилцах <Icon name="arrow" size={14}/></button>
        </div>
        <div className="profile-row"><div className="profile-avatar">U</div><div className="profile-copy"><strong>Workspace admin</strong><span>Администратор</span></div><button aria-label="Тохиргоо" onClick={() => setActive("settings")}><Icon name="settings"/></button></div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="topbar-left"><button className="mobile-menu" aria-label="Цэс нээх" onClick={() => setMobileNav(true)}><Icon name="menu"/></button><div className="breadcrumbs">Workspace <span>/</span> <strong>{pageTitle}</strong></div></div>
          <div className="topbar-actions"><div className="period-chip"><Icon name="clock" size={15}/> 2026 оны тайлант жил <span>⌄</span></div><button className="icon-button" aria-label="Мэдэгдэл"><Icon name="bell"/></button><div className="topbar-avatar">U</div></div>
        </header>

        <div className="content-wrap">
          <div className="page-heading">
            <div><div className="eyebrow"><span className="eyebrow-dot"/> CARBON ACCOUNTING PLATFORM</div><h1>{active === "overview" ? "Сайн байна уу 👋" : pageTitle}</h1><p>{active === "overview" ? "Байгууллагынхаа нүүрстөрөгчийн ул мөрийг нэг дороос хянаарай." : "Байгууллагын тогтвортой байдлын өгөгдлөө удирдах хэсэг."}</p></div>
            <div className="heading-actions"><button className="button button-quiet" onClick={downloadCsv} disabled={!recordCount}><Icon name="download" size={16}/> Экспорт</button><button className="button button-primary" onClick={() => setShowForm(true)}><Icon name="plus" size={17}/> Өгөгдөл нэмэх</button></div>
          </div>

          {notice && <div className="notice" role="status"><span>{notice}</span><button onClick={() => setNotice("")} aria-label="Мэдэгдэл хаах"><Icon name="close" size={15}/></button></div>}

          {active === "overview" && <>
            <section className="hero-panel">
              <div className="hero-copy"><div className="hero-kicker"><span/> YOUR IMPACT, IN FOCUS</div><h2>Илүү ухаалаг шийдвэр.<br/><span>Илүү ногоон ирээдүй.</span></h2><p>Ялгарлын мэдээллээ бүртгэж, хэмжиж, бодит өөрчлөлт хийх эхний алхмаа өнөөдөр хийгээрэй.</p><button className="hero-button" onClick={() => setShowForm(true)}>Эхний өгөгдлөө бүртгэх <Icon name="arrow" size={16}/></button></div>
              <div className="hero-art" aria-hidden="true"><div className="art-ring ring-one"/><div className="art-ring ring-two"/><div className="art-glow"/><div className="art-leaf"><Icon name="leaf" size={76}/></div><div className="art-stat"><span>YOUR CARBON JOURNEY</span><strong>{recordCount.toString().padStart(2, "0")}</strong><small>Бүртгэсэн өгөгдөл</small></div><div className="art-orb orb-one"/><div className="art-orb orb-two"/></div>
              <div className="hero-foot"><span><Icon name="check" size={14}/> GHG Protocol суурь аргачлал</span><span><Icon name="zap" size={14}/> Ил тод тооцоолол</span></div>
            </section>

            <section className="metric-grid">
              <article className="metric-card metric-total"><div className="metric-top"><span>НИЙТ ЯЛГАРУУЛАЛТ</span><span className="metric-icon"><Icon name="leaf"/></span></div><div className="metric-value">{formatNumber(total)} <small>tCO₂e</small></div><div className="metric-foot"><span className="metric-neutral">Тооцоолсон дүн</span><span>2026</span></div></article>
              <article className="metric-card"><div className="metric-top"><span>SCOPE 1 · ШУУД</span><span className="metric-icon icon-amber"><Icon name="zap"/></span></div><div className="metric-value">{formatNumber(scope1)} <small>tCO₂e</small></div><div className="metric-foot"><span>Түлш, шаталт</span><span>{scope1Share.toFixed(1)}%</span></div><div className="mini-track"><i style={{width: `${scope1Share}%`}}/></div></article>
              <article className="metric-card"><div className="metric-top"><span>SCOPE 2 · ЭРЧИМ ХҮЧ</span><span className="metric-icon icon-blue"><Icon name="zap"/></span></div><div className="metric-value">{formatNumber(scope2)} <small>tCO₂e</small></div><div className="metric-foot"><span>Худалдан авсан эрчим хүч</span><span>{scope2Share.toFixed(1)}%</span></div><div className="mini-track blue-track"><i style={{width: `${scope2Share}%`}}/></div></article>
              <article className="metric-card"><div className="metric-top"><span>ӨГӨГДЛИЙН МӨР</span><span className="metric-icon icon-violet"><Icon name="layers"/></span></div><div className="metric-value">{recordCount} <small>мөр</small></div><div className="metric-foot"><span>Тооцоолсон бүртгэл</span><span>2026</span></div></article>
            </section>

            <section className="dashboard-grid">
              <article className="panel emissions-panel"><div className="panel-heading"><div><h3>Ялгарлын тойм</h3><p>Бүртгэсэн өгөгдлийн нийлбэр дүн</p></div><span className="panel-tag">tCO₂e</span></div>
                {recordCount === 0 ? <div className="chart-empty"><div className="empty-chart-icon"><Icon name="layers" size={22}/></div><strong>Одоогоор өгөгдөл алга</strong><p>Эхний хэрэглээгээ бүртгэхэд график автоматаар шинэчлэгдэнэ.</p><button className="text-action" onClick={() => setShowForm(true)}>Өгөгдөл бүртгэх <Icon name="arrow" size={14}/></button></div> : <div className="chart-area"><div className="chart-y"><span>{formatNumber(Math.max(...chartBars.map(b=>b.scope1 + b.scope2)))}</span><span>0</span></div><div className="chart-bars">{chartBars.map((bar) => <div className="chart-column" key={bar.label}><div className="bar-track"><div className="bar-stack" style={{height: `${bar.height}%`}}><i className="bar-fill-s2" style={{height: `${bar.scope2 / Math.max(bar.scope1 + bar.scope2, 0.000001) * 100}%`}}/><i className="bar-fill-s1" style={{height: `${bar.scope1 / Math.max(bar.scope1 + bar.scope2, 0.000001) * 100}%`}}/></div></div><span>{bar.label}</span></div>)}</div></div>}
                <div className="chart-legend"><span><i className="legend-dot green-dot"/> Scope 1</span><span><i className="legend-dot blue-dot"/> Scope 2</span><small>Бүртгэлийн дарааллаар харуулна</small></div>
              </article>
              <article className="panel breakdown-panel"><div className="panel-heading"><div><h3>Scope задаргаа</h3><p>Нийт ялгарлын эзлэх хувь</p></div><button className="more-button" aria-label="Дэлгэрэнгүй">•••</button></div><div className="donut-wrap"><div className="donut" style={{background: total > 0 ? `conic-gradient(#1c8158 0 ${scope1Share}%, #8bb7d8 ${scope1Share}% 100%)` : "#e9efeb"}}><div className="donut-center"><strong>{formatNumber(total)}</strong><span>tCO₂e</span></div></div></div><div className="breakdown-rows"><div><span><i className="legend-dot green-dot"/> Scope 1</span><strong>{scope1Share.toFixed(1)}%</strong></div><div><span><i className="legend-dot blue-dot"/> Scope 2</span><strong>{scope2Share.toFixed(1)}%</strong></div></div></article>
            </section>

            <section className="panel activity-panel"><div className="panel-heading"><div><h3>Сүүлийн бүртгэлүүд</h3><p>Тооцоолсон үйл ажиллагааны мэдээлэл</p></div><button className="text-action" onClick={() => setActive("activities")}>Бүгдийг харах <Icon name="arrow" size={14}/></button></div>{recordCount === 0 ? <div className="table-empty">Таны бүртгэл энд харагдана. <button onClick={() => setShowForm(true)}>Эхний бүртгэл нэмэх</button></div> : <ActivityTable activities={activities.slice(0,5)}/>}</section>
          </>}

          {active === "activities" && <section className="panel activity-panel full-panel"><div className="panel-heading"><div><h3>Үйл ажиллагааны бүртгэл</h3><p>Тооцоолсон мөрүүд болон ашигласан коэффициентийн эх сурвалж</p></div><button className="button button-primary" onClick={() => setShowForm(true)}><Icon name="plus" size={16}/> Нэмэх</button></div>{recordCount ? <ActivityTable activities={activities}/> : <div className="chart-empty"><div className="empty-chart-icon"><Icon name="layers" size={22}/></div><strong>Бүртгэл эхлээгүй байна</strong><p>Түлш эсвэл цахилгааны хэрэглээгээ нэмнэ үү.</p><button className="button button-primary" onClick={() => setShowForm(true)}>Эхний бүртгэл нэмэх</button></div>}</section>}

          {active === "reports" && <section className="panel placeholder-panel"><div className="placeholder-icon"><Icon name="file" size={25}/></div><h3>Тайлангийн төв</h3><p>Одоогийн бүртгэлүүдээ CSV хэлбэрээр экспортлох боломжтой. PDF болон GHG Protocol тайлангийн загвар дараагийн хөгжүүлэлтээр нэмэгдэнэ.</p><button className="button button-primary" onClick={downloadCsv} disabled={!recordCount}><Icon name="download" size={16}/> CSV татах</button></section>}

          {active === "factors" && <section className="panel placeholder-panel"><div className="placeholder-icon"><Icon name="leaf" size={25}/></div><h3>Ялгарлын коэффициент</h3><p>Одоогоор коэффициентын сан холбогдоогүй. Бүртгэл бүрт эх сурвалж, HTTPS холбоос, он, хувилбар бүхий коэффициентийг гараар оруулна.</p><div className="info-callout">Баталгаагүй Монголын цахилгаан, түлшний коэффициентийг системд урьдчилан оруулаагүй.</div><button className="text-action" onClick={() => setShowForm(true)}>Коэффициенттэй өгөгдөл нэмэх <Icon name="arrow" size={14}/></button></section>}

          {active === "settings" && <section className="panel settings-panel"><div className="panel-heading"><div><h3>Ажлын орчны тохиргоо</h3><p>Төслийн холболт болон тайлангийн үндсэн мэдээлэл</p></div></div><div className="setting-row"><div><strong>Workspace</strong><span>Nomad workspace</span></div><span className="setting-status">Local preview</span></div><div className="setting-row"><div><strong>API endpoint</strong><span>{apiUrl}</span></div><span className="setting-status">Тохируулж болно</span></div><div className="setting-row"><div><strong>Тайлангийн валют</strong><span>MNT · Монгол төгрөг</span></div><span className="setting-status">Суурь тохиргоо</span></div><div className="setting-row"><div><strong>Өгөгдөл хадгалалт</strong><span>Энэ хувилбарт зөвхөн браузерын санах ойд түр хадгална.</span></div><span className="setting-status status-warning">DB холбогдоогүй</span></div></section>}

          <footer className="app-footer"><span>© 2026 Carbon ESG</span><span>Designed for a lower-carbon future <i>✳</i></span><span>Methodology · Privacy · Support</span></footer>
        </div>
      </main>

      {showForm && <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setShowForm(false); }}><section className="activity-modal" role="dialog" aria-modal="true" aria-labelledby="modal-title"><div className="modal-heading"><div><div className="eyebrow">NEW ACTIVITY</div><h2 id="modal-title">Өгөгдөл бүртгэх</h2><p>Ашигласан коэффициентийн эх сурвалжийг заавал оруулна.</p></div><button className="icon-button" onClick={() => setShowForm(false)} aria-label="Хаах"><Icon name="close"/></button></div><form onSubmit={submitActivity}><div className="form-grid"><label className="field field-wide">Бүртгэлийн нэр<input required minLength={2} maxLength={160} placeholder="Жишээ: Албаны автомашины дизель түлш" value={form.name} onChange={(e)=>setForm({...form,name:e.target.value})}/></label><label className="field">Scope<select value={form.scope} onChange={(e)=>{const scope=e.target.value as Scope;setForm({...form,scope,category:scope==="scope_1"?"mobile_combustion":"purchased_electricity"});}}><option value="scope_1">Scope 1 · Шууд</option><option value="scope_2">Scope 2 · Эрчим хүч</option></select></label><label className="field">Ангилал<select value={form.category} onChange={(e)=>setForm({...form,category:e.target.value})}>{(form.scope==="scope_1"?[["stationary_combustion","Суурин шаталт"],["mobile_combustion","Тээврийн түлш"],["process","Үйлдвэрлэлийн процесс"],["fugitive","Алдагдал / хөргөлт"]]:[["purchased_electricity","Худалдан авсан цахилгаан"],["purchased_heat","Дулаан"],["purchased_steam","Уур"],["purchased_cooling","Хөргөлт"]]).map(([v,l])=><option key={v} value={v}>{l}</option>)}</select></label><label className="field">Хэрэглээний хэмжээ<input required type="number" min="0.00000001" step="any" placeholder="1000" value={form.amount} onChange={(e)=>setForm({...form,amount:e.target.value})}/></label><label className="field">Нэгж<select value={form.unit} onChange={(e)=>setForm({...form,unit:e.target.value})}><option value="kWh">kWh</option><option value="litre">Литр</option><option value="m3">м³</option><option value="kg">кг</option><option value="tonne">тонн</option></select></label><label className="field">Коэффициент (kgCO₂e / нэгж)<input required type="number" min="0" step="any" placeholder="Эх сурвалжаас авна" value={form.factor} onChange={(e)=>setForm({...form,factor:e.target.value})}/></label><label className="field">Коэффициентийн он<input required type="number" min="1900" max="2200" value={form.year} onChange={(e)=>setForm({...form,year:e.target.value})}/></label><label className="field field-wide">Эх сурвалжийн нэр<input required minLength={2} placeholder="Жишээ: Албан ёсны emission factor dataset" value={form.source} onChange={(e)=>setForm({...form,source:e.target.value})}/></label><label className="field field-wide">Эх сурвалжийн HTTPS холбоос<input required type="url" pattern="https://.+" placeholder="https://..." value={form.sourceUrl} onChange={(e)=>setForm({...form,sourceUrl:e.target.value})}/></label><label className="field">Хувилбар<input required value={form.version} onChange={(e)=>setForm({...form,version:e.target.value})}/></label><label className="field">Тайлангийн хугацаа<input required type="date" value={form.start} onChange={(e)=>setForm({...form,start:e.target.value})}/></label><label className="field">Хугацааны төгсгөл<input required type="date" value={form.end} onChange={(e)=>setForm({...form,end:e.target.value})}/></label></div><div className="form-note"><Icon name="zap" size={16}/> Тооцоолол API дээр хийгдэнэ. Энэ хувилбарын үр дүн өгөгдлийн санд хадгалагдахгүй.</div><div className="modal-actions"><button type="button" className="button button-quiet" onClick={()=>setShowForm(false)}>Болих</button><button type="submit" className="button button-primary" disabled={busy}>{busy?"Тооцоолж байна…":"Тооцоолж бүртгэх"} <Icon name="arrow" size={15}/></button></div></form></section></div>}
    </div>
  );
}

function ActivityTable({ activities }: { activities: Activity[] }) {
  return <div className="table-scroll"><table className="activity-table"><thead><tr><th>Нэр</th><th>Scope</th><th>Хэмжээ</th><th>Коэффициентын эх сурвалж</th><th>tCO₂e</th></tr></thead><tbody>{activities.map((item)=><tr key={item.id}><td><strong>{item.name}</strong><small>{item.category}</small></td><td><span className={`scope-pill ${item.scope}`}>{item.scope==="scope_1"?"Scope 1":"Scope 2"}</span></td><td>{formatNumber(Number(item.amount))} {item.unit}</td><td><strong>{item.source}</strong><small>{item.year} · v{item.version}</small></td><td className="emissions-cell">{formatNumber(item.emissions||0)}</td></tr>)}</tbody></table></div>;
}
