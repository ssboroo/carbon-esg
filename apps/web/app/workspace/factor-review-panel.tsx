"use client";

import { type FormEvent, useCallback, useEffect, useState } from "react";

type Scope = "scope_1" | "scope_2";
type ApprovalFilter = "pending" | "approved" | "rejected" | "all";
type Decision = "approved" | "rejected";

type ApiRequest = <T>(path: string, init?: RequestInit) => Promise<T>;

type FactorReviewItem = {
  id: string;
  factor_code: string;
  name: string;
  scope: Scope;
  scope_2_method: "location_based" | "market_based" | null;
  category: string;
  factor_value: string | number;
  factor_unit: string;
  gas_basis: string;
  source_name: string;
  source_url: string;
  source_document: string | null;
  factor_year: number;
  version: string;
  geography_code: string;
  geography_name: string;
  geography_boundary: "global" | "national" | "subnational" | "grid" | "market" | "facility" | "other";
  valid_from: string | null;
  valid_to: string | null;
  approval_status: "pending" | "approved" | "rejected";
  submitted_by_subject: string | null;
  reviewer_subject: string | null;
  reviewed_at: string | null;
  review_note: string | null;
  created_at: string;
};

type FactorDraft = {
  factor_code: string;
  name: string;
  scope: Scope;
  scope_2_method: "location_based" | "market_based" | null;
  category: string;
  factor_value: string;
  factor_unit: string;
  gas_basis: "CO2e";
  source_name: string;
  source_url: string;
  source_document: string;
  factor_year: string;
  version: string;
  geography_code: string;
  geography_name: string;
  geography_boundary: "" | "global" | "national" | "subnational" | "grid" | "market" | "facility" | "other";
  valid_from: string;
  valid_to: string;
};

const CATEGORY_OPTIONS: Record<Scope, { value: string; label: string }[]> = {
  scope_1: [
    { value: "stationary_combustion", label: "Суурин эх үүсвэрийн түлш" },
    { value: "mobile_combustion", label: "Тээврийн хэрэгслийн түлш" },
    { value: "process", label: "Үйлдвэрлэлийн процесс" },
    { value: "fugitive", label: "Алдагдал, дэгдэлт" }
  ],
  scope_2: [
    { value: "purchased_electricity", label: "Худалдан авсан цахилгаан" },
    { value: "purchased_heat", label: "Худалдан авсан дулаан" },
    { value: "purchased_steam", label: "Худалдан авсан уур" },
    { value: "purchased_cooling", label: "Худалдан авсан хөргөлт" }
  ]
};

const FILTER_LABELS: Record<ApprovalFilter, string> = {
  pending: "Хүлээгдэж буй",
  approved: "Баталсан",
  rejected: "Буцаасан",
  all: "Бүгд"
};

function createInitialDraft(): FactorDraft {
  return {
    factor_code: "",
    name: "",
    scope: "scope_1",
    scope_2_method: null,
    category: "stationary_combustion",
    factor_value: "",
    factor_unit: "",
    gas_basis: "CO2e",
    source_name: "",
    source_url: "",
    source_document: "",
    factor_year: String(new Date().getFullYear()),
    version: "1.0",
    geography_code: "",
    geography_name: "",
    geography_boundary: "",
    valid_from: new Date().getFullYear() + "-01-01",
    valid_to: new Date().getFullYear() + "-12-31"
  };
}

function scopeLabel(scope: Scope) {
  return scope === "scope_1" ? "Scope 1 · Шууд" : "Scope 2 · Эрчим хүч";
}

function statusLabel(status: FactorReviewItem["approval_status"]) {
  if (status === "approved") return "Баталсан";
  if (status === "rejected") return "Буцаасан";
  return "Хүлээгдэж байна";
}

function formatFactorValue(value: string | number) {
  const number = Number(value);
  return Number.isFinite(number)
    ? new Intl.NumberFormat("mn-MN", { maximumFractionDigits: 8 }).format(number)
    : String(value);
}

function errorMessage(cause: unknown) {
  return cause instanceof Error ? cause.message : "Хүсэлтийг боловсруулах боломжгүй байна.";
}

export function FactorReviewPanel({
  organizationId,
  role,
  apiRequest,
  onFactorsChanged
}: {
  organizationId: string;
  role: string;
  apiRequest: ApiRequest;
  onFactorsChanged: () => Promise<void>;
}) {
  const canSubmit = ["owner", "admin", "editor"].includes(role);
  const canReview = ["owner", "admin"].includes(role);
  const base = "/v1/organizations/" + organizationId + "/emission-factors";

  const [draft, setDraft] = useState<FactorDraft>(createInitialDraft);
  const [items, setItems] = useState<FactorReviewItem[]>([]);
  const [filter, setFilter] = useState<ApprovalFilter>("pending");
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const reloadQueue = useCallback(async () => {
    if (!canReview) return;
    setLoading(true);
    try {
      const rows = await apiRequest<FactorReviewItem[]>(
        base + "/review-queue?approval_status=" + filter
      );
      setItems(rows);
      setError("");
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setLoading(false);
    }
  }, [apiRequest, base, canReview, filter]);

  useEffect(() => {
    let active = true;
    if (!canReview) {
      setItems([]);
      setLoading(false);
      return () => {
        active = false;
      };
    }

    setLoading(true);
    setError("");
    void apiRequest<FactorReviewItem[]>(
      base + "/review-queue?approval_status=" + filter
    )
      .then((rows) => {
        if (active) setItems(rows);
      })
      .catch((cause: unknown) => {
        if (active) setError(errorMessage(cause));
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [apiRequest, base, canReview, filter]);

  function updateDraft<K extends keyof FactorDraft>(key: K, value: FactorDraft[K]) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  function changeScope(scope: Scope) {
    setDraft((current) => ({
      ...current,
      scope,
      scope_2_method: scope === "scope_2" ? "location_based" : null,
      category: CATEGORY_OPTIONS[scope][0].value
    }));
  }

  async function submitFactor(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit) return;

    const factorValue = draft.factor_value.trim();
    const factorYear = Number(draft.factor_year);
    if (!factorValue || !Number.isFinite(Number(factorValue)) || Number(factorValue) < 0) {
      setError("Коэффициентийн утга 0-ээс багагүй тоон утга байх ёстой.");
      return;
    }
    if (!Number.isInteger(factorYear) || factorYear < 1900 || factorYear > 2200) {
      setError("Коэффициентийн он 1900–2200 оны хооронд бүхэл тоо байна.");
      return;
    }
    if (!draft.geography_code.trim() || !draft.geography_name.trim() || !draft.geography_boundary) {
      setError("Коэффициентийн газарзүйн код, нэр болон хил заагийн төрлийг бөглөнө үү.");
      return;
    }
    if (!draft.valid_from || !draft.valid_to || draft.valid_to < draft.valid_from) {
      setError("Коэффициентийн хүчинтэй хугацааны эхлэх/дуусах огноог зөв оруулна уу.");
      return;
    }

    let sourceUrl: URL;
    try {
      sourceUrl = new URL(draft.source_url.trim());
    } catch {
      setError("Эх сурвалжийн HTTPS холбоосыг зөв оруулна уу.");
      return;
    }
    if (sourceUrl.protocol !== "https:") {
      setError("Эх сурвалжийн холбоос заавал HTTPS байх ёстой.");
      return;
    }

    setBusy("submit");
    setError("");
    setNotice("");
    try {
      await apiRequest<FactorReviewItem>(base, {
        method: "POST",
        body: JSON.stringify({
          ...draft,
          factor_value: factorValue,
          factor_year: factorYear,
          geography_code: draft.geography_code.trim().toUpperCase(),
          geography_name: draft.geography_name.trim(),
          valid_from: draft.valid_from,
          valid_to: draft.valid_to,
          source_url: sourceUrl.toString(),
          source_document: draft.source_document.trim() || null
        })
      });
      setDraft(createInitialDraft());
      setNotice("Коэффициент бүртгэгдлээ. Хараат бус хяналт дуусах хүртэл тооцоололд ашиглахгүй.");
      await reloadQueue();
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy("");
    }
  }

  async function reviewFactor(item: FactorReviewItem, decision: Decision) {
    const note = (notes[item.id] || "").trim();
    if (note.length < 10) {
      setError("Хяналтын тайлбар дор хаяж 10 тэмдэгттэй байна.");
      return;
    }

    setBusy(item.id + ":" + decision);
    setError("");
    setNotice("");
    try {
      await apiRequest<FactorReviewItem>(base + "/" + item.id + "/review", {
        method: "POST",
        body: JSON.stringify({ decision, note })
      });
      setNotes((current) => ({ ...current, [item.id]: "" }));
      setNotice(
        decision === "approved"
          ? "Коэффициент баталгаажлаа. Одоо үйл ажиллагааны бүртгэлд сонгох боломжтой."
          : "Коэффициентийг буцаалаа. Засварласан утгыг шинэ хувилбараар бүртгүүлнэ."
      );
      await reloadQueue();
      if (decision === "approved") {
        try {
          await onFactorsChanged();
        } catch {
          setNotice("Баталгаажуулалт хадгалагдсан. Коэффициентийн жагсаалтыг шинэчлэхэд алдаа гарсан тул хуудсыг дахин ачаална уу.");
        }
      }
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy("");
    }
  }

  return (
    <section className="workspace-panel factor-registry-panel">
      <div className="section-heading">
        <div>
          <h2>Ялгарлын коэффициентийн сан</h2>
          <p>Эх сурвалж, нэгж, хувилбар, газарзүйн хил зааг болон хүчинтэй хугацааг бүртгэж, хараат бус хяналтаар баталгаажуулна.</p>
        </div>
        {canReview && <span className="count-chip">{items.length} бүртгэл</span>}
      </div>

      {error && <p className="workspace-message error" role="alert">{error}</p>}
      {notice && <p className="workspace-message success" role="status">{notice}</p>}

      {canSubmit ? (
        <form className="factor-submit-form" onSubmit={submitFactor}>
          <label className="field">
            <span>Коэффициентийн код</span>
            <input
              value={draft.factor_code}
              onChange={(event) => updateDraft("factor_code", event.target.value)}
              minLength={1}
              maxLength={100}
              pattern="[A-Za-z0-9][A-Za-z0-9._:-]{0,99}"
              placeholder="MN-GRID-2026"
              required
            />
          </label>
          <label className="field">
            <span>Коэффициентийн нэр</span>
            <input
              value={draft.name}
              onChange={(event) => updateDraft("name", event.target.value)}
              minLength={2}
              maxLength={200}
              placeholder="Эх сурвалжид бичигдсэн нэр"
              required
            />
          </label>
          <label className="field">
            <span>Хамрах хүрээ</span>
            <select value={draft.scope} onChange={(event) => changeScope(event.target.value as Scope)}>
              <option value="scope_1">Scope 1 · Шууд ялгаруулалт</option>
              <option value="scope_2">Scope 2 · Худалдан авсан эрчим хүч</option>
            </select>
          </label>
          <label className="field">
            <span>Ангилал</span>
            <select value={draft.category} onChange={(event) => updateDraft("category", event.target.value)}>
              {CATEGORY_OPTIONS[draft.scope].map((category) => (
                <option key={category.value} value={category.value}>{category.label}</option>
              ))}
            </select>
          </label>
          {draft.scope === "scope_2" && (
            <label className="field">
              <span>Scope 2 тайлагналын арга</span>
              <select
                value={draft.scope_2_method || "location_based"}
                onChange={(event) => updateDraft("scope_2_method", event.target.value as "location_based" | "market_based")}
              >
                <option value="location_based">Location-based · Байршилд суурилсан</option>
                <option value="market_based">Market-based · Зах зээлд суурилсан</option>
              </select>
            </label>
          )}
          <label className="field">
            <span>Газарзүйн код</span>
            <input
              value={draft.geography_code}
              onChange={(event) => updateDraft("geography_code", event.target.value)}
              maxLength={32}
              placeholder="MNG-GRID-01 эсвэл GLOBAL"
              required
            />
          </label>
          <label className="field">
            <span>Газарзүйн нэр</span>
            <input
              value={draft.geography_name}
              onChange={(event) => updateDraft("geography_name", event.target.value)}
              maxLength={160}
              placeholder="Монголын төвийн эрчим хүчний систем"
              required
            />
          </label>
          <label className="field">
            <span>Газарзүйн хил заагийн төрөл</span>
            <select
              value={draft.geography_boundary}
              onChange={(event) => updateDraft("geography_boundary", event.target.value as FactorDraft["geography_boundary"])}
              required
            >
              <option value="">Сонгох…</option>
              <option value="global">Дэлхийн (GLOBAL)</option>
              <option value="national">Улсын</option>
              <option value="subnational">Дэд улсын / бүсийн</option>
              <option value="grid">Цахилгаан сүлжээ</option>
              <option value="market">Эрчим хүчний зах зээл</option>
              <option value="facility">Байгууламж</option>
              <option value="other">Бусад</option>
            </select>
          </label>
          <label className="field">
            <span>Хүчинтэй эхлэх огноо</span>
            <input
              type="date"
              value={draft.valid_from}
              onChange={(event) => updateDraft("valid_from", event.target.value)}
              required
            />
          </label>
          <label className="field">
            <span>Хүчинтэй дуусах огноо</span>
            <input
              type="date"
              min={draft.valid_from || undefined}
              value={draft.valid_to}
              onChange={(event) => updateDraft("valid_to", event.target.value)}
              required
            />
          </label>
          <label className="field">
            <span>Коэффициентийн утга (kgCO₂e / нэгж)</span>
            <input
              type="number"
              min="0"
              step="any"
              value={draft.factor_value}
              onChange={(event) => updateDraft("factor_value", event.target.value)}
              placeholder="Эх сурвалж дахь утга"
              required
            />
          </label>
          <label className="field">
            <span>Хуваарийн нэгж</span>
            <input
              value={draft.factor_unit}
              onChange={(event) => updateDraft("factor_unit", event.target.value)}
              maxLength={32}
              placeholder="kWh, L, m³, kg гэх мэт"
              required
            />
          </label>
          <label className="field">
            <span>Эх сурвалжийн байгууллага</span>
            <input
              value={draft.source_name}
              onChange={(event) => updateDraft("source_name", event.target.value)}
              minLength={2}
              maxLength={200}
              placeholder="Эх сурвалжийг нийтэлсэн байгууллага"
              required
            />
          </label>
          <label className="field factor-source-url">
            <span>Эх сурвалжийн HTTPS холбоос</span>
            <input
              type="url"
              value={draft.source_url}
              onChange={(event) => updateDraft("source_url", event.target.value)}
              placeholder="https://..."
              required
            />
          </label>
          <label className="field">
            <span>Баримт бичиг / хүснэгтийн нэр (сонголтоор)</span>
            <input
              value={draft.source_document}
              onChange={(event) => updateDraft("source_document", event.target.value)}
              maxLength={255}
              placeholder="Тайлангийн нэр, хүснэгт, хуудас"
            />
          </label>
          <label className="field">
            <span>Коэффициентийн он</span>
            <input
              type="number"
              min="1900"
              max="2200"
              step="1"
              value={draft.factor_year}
              onChange={(event) => updateDraft("factor_year", event.target.value)}
              required
            />
          </label>
          <label className="field">
            <span>Хувилбар</span>
            <input
              value={draft.version}
              onChange={(event) => updateDraft("version", event.target.value)}
              maxLength={80}
              placeholder="2026-v1"
              required
            />
          </label>
          <div className="factor-submit-actions">
            <p>Шинээр бүртгэсэн коэффициент <strong>хүлээгдэж буй</strong> төлөвтэй байна. Бүртгэгч өөрийн коэффициентийг батлах боломжгүй.</p>
            <button className="button-primary" type="submit" disabled={busy !== ""}>
              {busy === "submit" ? "Бүртгэж байна…" : "Коэффициент бүртгүүлэх"}
            </button>
          </div>
        </form>
      ) : (
        <p className="empty-state">Коэффициент бүртгүүлэхэд owner, admin эсвэл editor эрх шаардлагатай.</p>
      )}

      <div className="factor-accounting-note">
        Scope 2-ын location-based болон market-based коэффициентийг тусдаа бүртгэж, тусдаа тооцно. Аль нэг аргын дүнг нөгөө аргатай нэмж болохгүй.
      </div>

      {canReview && (
        <div className="factor-review-section">
          <div className="section-heading factor-review-heading">
            <div>
              <h3>Коэффициентийн хяналт</h3>
              <p>Зөвхөн owner болон admin эрхтэй, бүртгэгчээс өөр хэрэглэгч шийдвэр гаргана.</p>
            </div>
            <label className="field factor-filter">
              <span>Төлөв</span>
              <select value={filter} onChange={(event) => setFilter(event.target.value as ApprovalFilter)}>
                {(Object.keys(FILTER_LABELS) as ApprovalFilter[]).map((value) => (
                  <option key={value} value={value}>{FILTER_LABELS[value]}</option>
                ))}
              </select>
            </label>
          </div>

          {loading ? (
            <p className="empty-state">Хяналтын жагсаалт ачаалж байна…</p>
          ) : items.length === 0 ? (
            <p className="empty-state">{filter === "pending" ? "Хяналт хүлээж буй коэффициент алга." : "Сонгосон төлөвт коэффициент алга."}</p>
          ) : (
            <div className="factor-review-list">
              {items.map((item) => (
                <article className="factor-review-card" key={item.id}>
                  <div className="factor-review-card-heading">
                    <div>
                      <strong>{item.name}</strong>
                      <small>{item.factor_code} · {item.version} · {item.factor_year}</small>
                    </div>
                    <span className={"factor-status " + item.approval_status}>{statusLabel(item.approval_status)}</span>
                  </div>
                  <div className="factor-review-details">
                    <span>{scopeLabel(item.scope)}{item.scope_2_method ? " · " + (item.scope_2_method === "location_based" ? "Location-based" : "Market-based") : ""}</span>
                    <span>{CATEGORY_OPTIONS[item.scope].find((category) => category.value === item.category)?.label || item.category}</span>
                    <strong>{formatFactorValue(item.factor_value)} kgCO₂e / {item.factor_unit}</strong>
                    <span>Хийн суурь: {item.gas_basis}</span>
                    <span>Газарзүй: {item.geography_name} ({item.geography_code}) · {item.geography_boundary}</span>
                    <span>Хүчинтэй: {item.valid_from && item.valid_to ? item.valid_from + " — " + item.valid_to : "Хуучин бүртгэлд тодорхойгүй"}</span>
                  </div>
                  <div className="factor-review-source">
                    <a href={item.source_url} target="_blank" rel="noreferrer">{item.source_name} · Эх сурвалж нээх</a>
                    {item.source_document && <span>{item.source_document}</span>}
                  </div>

                  {item.approval_status === "pending" && item.scope === "scope_2" && !item.scope_2_method ? (
                    <p className="empty-state">Энэ хуучин коэффициентэд Scope 2 аргачлал тодорхойгүй байна. Location-based эсвэл market-based гэж шинэ хувилбараар дахин бүртгүүлнэ үү.</p>
                  ) : item.approval_status === "pending" ? (
                    <div className="factor-review-actions">
                      <label className="field">
                        <span>Хяналтын тайлбар (дор хаяж 10 тэмдэгт)</span>
                        <textarea
                          rows={3}
                          maxLength={2000}
                          value={notes[item.id] || ""}
                          onChange={(event) => setNotes((current) => ({ ...current, [item.id]: event.target.value }))}
                          placeholder="Эх сурвалж, он, газарзүй, нэгж болон аргачлалыг хэрхэн тулгаснаа бичнэ үү."
                        />
                      </label>
                      <div className="factor-review-buttons">
                        <button
                          type="button"
                          className="button-primary"
                          disabled={busy !== "" || (notes[item.id] || "").trim().length < 10}
                          onClick={() => void reviewFactor(item, "approved")}
                        >
                          {busy === item.id + ":approved" ? "Баталж байна…" : "Батлах"}
                        </button>
                        <button
                          type="button"
                          className="button-secondary"
                          disabled={busy !== "" || (notes[item.id] || "").trim().length < 10}
                          onClick={() => void reviewFactor(item, "rejected")}
                        >
                          {busy === item.id + ":rejected" ? "Буцааж байна…" : "Буцаах"}
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="factor-review-history">
                      <span>{item.reviewer_subject ? "Хянагч: " + item.reviewer_subject : "Хянагчийн мэдээлэл байхгүй"}</span>
                      {item.reviewed_at && <span>{new Date(item.reviewed_at).toLocaleString("mn-MN")}</span>}
                      {item.review_note && <p>{item.review_note}</p>}
                    </div>
                  )}
                </article>
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
