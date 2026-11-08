"use client";

import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { authClient } from "@/lib/auth/client";
import { FactorReviewPanel } from "./factor-review-panel";
import { EvidencePanel } from "./evidence-panel";

type Organization = { id: string; name: string; slug: string; role: string };
type Inventory = {
  id: string;
  name: string;
  reporting_period_start: string;
  reporting_period_end: string;
  status: string;
  scope_2_primary_method: "location_based" | "market_based";
};
type EmissionFactor = {
  id: string;
  factor_code: string;
  name: string;
  scope: "scope_1" | "scope_2";
  scope_2_method: "location_based" | "market_based" | null;
  category: string;
  factor_value: string;
  factor_unit: string;
  gas_basis: string;
  source_name: string;
  source_url: string;
  source_document: string | null;
  factor_year: number;
  version: string;
};
type ActivityRecord = {
  id: string;
  name: string;
  scope: "scope_1" | "scope_2";
  scope_2_method: "location_based" | "market_based" | null;
  category: string;
  activity_amount: string;
  activity_unit: string;
  emission_factor_id: string;
  factor_value_snapshot: string;
  factor_unit_snapshot: string;
  factor_code: string;
  factor_version: string;
  factor_source_name: string;
  factor_source_url: string;
  factor_year: number;
  emissions_kgco2e: string;
};
type Calculation = {
  id: string;
  inventory_id: string;
  scope_1_kgco2e: string;
  scope_2_kgco2e: string;
  scope_2_primary_method: "location_based" | "market_based";
  scope_2_location_based_kgco2e: string | null;
  scope_2_market_based_kgco2e: string | null;
  total_location_based_kgco2e: string | null;
  total_market_based_kgco2e: string | null;
  total_kgco2e: string;
  methodology_version: string;
  created_at: string;
};

const CATEGORY_LABELS: Record<string, string> = {
  stationary_combustion: "Суурин эх үүсвэрийн түлш",
  mobile_combustion: "Тээврийн хэрэгслийн түлш",
  process: "Үйлдвэрлэлийн процесс",
  fugitive: "Алдагдал, дэгдэлт",
  purchased_electricity: "Худалдан авсан цахилгаан",
  purchased_heat: "Худалдан авсан дулаан",
  purchased_steam: "Худалдан авсан уур",
  purchased_cooling: "Худалдан авсан хөргөлт"
};

function scopeLabel(scope: string) {
  return scope === "scope_1" ? "Scope 1 · Шууд" : "Scope 2 · Эрчим хүч";
}

function formatNumber(value: string | number, digits = 3) {
  const number = Number(value);
  if (!Number.isFinite(number)) return String(value);
  return new Intl.NumberFormat("mn-MN", { maximumFractionDigits: digits }).format(number);
}

function formatDate(value: string) {
  return new Date(value + "T00:00:00").toLocaleDateString("mn-MN");
}

function getErrorMessage(body: unknown, status: number) {
  if (status === 401) return "Нэвтрэх хугацаа дууссан байна. Дахин нэвтэрнэ үү.";
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
  }
  return "Сервер хүсэлтийг боловсруулах боломжгүй байна (" + status + ").";
}

export function WorkspaceDashboard({ userLabel }: { userLabel: string }) {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [organizationId, setOrganizationId] = useState("");
  const [inventories, setInventories] = useState<Inventory[]>([]);
  const [inventoryId, setInventoryId] = useState("");
  const [factors, setFactors] = useState<EmissionFactor[]>([]);
  const [activities, setActivities] = useState<ActivityRecord[]>([]);
  const [calculations, setCalculations] = useState<Calculation[]>([]);
  const [initialLoading, setInitialLoading] = useState(true);
  const [organizationLoading, setOrganizationLoading] = useState(false);
  const [inventoryLoading, setInventoryLoading] = useState(false);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [showOrganizationForm, setShowOrganizationForm] = useState(false);
  const [organizationName, setOrganizationName] = useState("");
  const [inventoryName, setInventoryName] = useState("");
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");
  const [scope2PrimaryMethod, setScope2PrimaryMethod] = useState<"location_based" | "market_based">("location_based");
  const [activityName, setActivityName] = useState("");
  const [activityAmount, setActivityAmount] = useState("");
  const [factorId, setFactorId] = useState("");

  const apiRequest = useCallback(async <T,>(path: string, init: RequestInit = {}): Promise<T> => {
    const apiBase = process.env.NEXT_PUBLIC_API_URL;
    if (!apiBase) throw new Error("NEXT_PUBLIC_API_URL тохируулаагүй байна.");

    const tokenResult = await authClient.token();
    const token = tokenResult.data?.token;
    if (tokenResult.error || !token) {
      throw new Error(tokenResult.error?.message || "Нэвтрэх токен олдсонгүй. Дахин нэвтэрнэ үү.");
    }

    const headers = new Headers(init.headers);
    headers.set("Authorization", "Bearer " + token);
    const isFormData = typeof FormData !== "undefined" && init.body instanceof FormData;
    if (init.body && !headers.has("Content-Type") && !isFormData) {
      headers.set("Content-Type", "application/json");
    }

    const base = apiBase.endsWith("/") ? apiBase : apiBase + "/";
    const response = await fetch(new URL(path, base), {
      ...init,
      headers,
      cache: "no-store"
    });
    const raw = await response.text();
    let body: unknown = null;
    if (raw) {
      try {
        body = JSON.parse(raw);
      } catch {
        body = raw;
      }
    }
    if (!response.ok) throw new Error(getErrorMessage(body, response.status));
    return body as T;
  }, []);

  const selectedOrganization = useMemo(
    () => organizations.find((item) => item.id === organizationId) || null,
    [organizations, organizationId]
  );
  const selectedInventory = useMemo(
    () => inventories.find((item) => item.id === inventoryId) || null,
    [inventories, inventoryId]
  );
  const selectedFactor = useMemo(
    () => factors.find((item) => item.id === factorId) || null,
    [factors, factorId]
  );
  const canWrite = Boolean(
    selectedOrganization && ["owner", "admin", "editor"].includes(selectedOrganization.role)
  );
  const latestCalculation = calculations[0] || null;

  const refreshFactors = useCallback(async () => {
    if (!organizationId) return;
    const rows = await apiRequest<EmissionFactor[]>(
      "/v1/organizations/" + organizationId + "/emission-factors"
    );
    setFactors(rows);
    setFactorId((current) =>
      rows.some((item) => item.id === current) ? current : rows[0]?.id || ""
    );
  }, [apiRequest, organizationId]);

  useEffect(() => {
    const year = new Date().getFullYear();
    setPeriodStart((value) => value || year + "-01-01");
    setPeriodEnd((value) => value || year + "-12-31");
  }, []);

  useEffect(() => {
    let active = true;
    async function loadOrganizations() {
      setInitialLoading(true);
      setError("");
      try {
        const rows = await apiRequest<Organization[]>("/v1/organizations");
        if (!active) return;
        setOrganizations(rows);
        setOrganizationId((current) =>
          rows.some((item) => item.id === current) ? current : rows[0]?.id || ""
        );
      } catch (cause) {
        if (active) setError(cause instanceof Error ? cause.message : "Байгууллагын мэдээлэл ачаалсангүй.");
      } finally {
        if (active) setInitialLoading(false);
      }
    }
    void loadOrganizations();
    return () => {
      active = false;
    };
  }, [apiRequest]);

  useEffect(() => {
    if (!organizationId) {
      setInventories([]);
      setInventoryId("");
      setFactors([]);
      setFactorId("");
      return;
    }
    let active = true;
    async function loadOrganizationData() {
      setOrganizationLoading(true);
      setError("");
      try {
        const prefix = "/v1/organizations/" + organizationId;
        const [inventoryRows, factorRows] = await Promise.all([
          apiRequest<Inventory[]>(prefix + "/inventories"),
          apiRequest<EmissionFactor[]>(prefix + "/emission-factors")
        ]);
        if (!active) return;
        setInventories(inventoryRows);
        setInventoryId((current) =>
          inventoryRows.some((item) => item.id === current) ? current : inventoryRows[0]?.id || ""
        );
        setFactors(factorRows);
        setFactorId((current) =>
          factorRows.some((item) => item.id === current) ? current : factorRows[0]?.id || ""
        );
      } catch (cause) {
        if (active) setError(cause instanceof Error ? cause.message : "Ажлын орчны мэдээлэл ачаалсангүй.");
      } finally {
        if (active) setOrganizationLoading(false);
      }
    }
    void loadOrganizationData();
    return () => {
      active = false;
    };
  }, [organizationId, apiRequest]);

  useEffect(() => {
    if (!organizationId || !inventoryId) {
      setActivities([]);
      setCalculations([]);
      return;
    }
    let active = true;
    async function loadInventoryData() {
      setInventoryLoading(true);
      setError("");
      const prefix = "/v1/organizations/" + organizationId + "/inventories/" + inventoryId;
      try {
        const [activityRows, calculationRows] = await Promise.all([
          apiRequest<ActivityRecord[]>(prefix + "/activities"),
          apiRequest<Calculation[]>(prefix + "/calculations")
        ]);
        if (!active) return;
        setActivities(activityRows);
        setCalculations(calculationRows);
      } catch (cause) {
        if (active) setError(cause instanceof Error ? cause.message : "Тайлангийн мэдээлэл ачаалсангүй.");
      } finally {
        if (active) setInventoryLoading(false);
      }
    }
    void loadInventoryData();
    return () => {
      active = false;
    };
  }, [organizationId, inventoryId, apiRequest]);

  async function createOrganization(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy("organization");
    setError("");
    setNotice("");
    try {
      const organization = await apiRequest<Organization>("/v1/organizations", {
        method: "POST",
        body: JSON.stringify({ name: organizationName.trim() })
      });
      setOrganizations((current) => [...current, organization]);
      setOrganizationId(organization.id);
      setInventories([]);
      setInventoryId("");
      setFactors([]);
      setFactorId("");
      setOrganizationName("");
      setShowOrganizationForm(false);
      setNotice("Байгууллагын ажлын орчин үүслээ.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Байгууллага үүсгэсэнгүй.");
    } finally {
      setBusy("");
    }
  }

  async function createInventory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!organizationId) return;
    if (periodEnd < periodStart) {
      setError("Тайлант хугацааны дуусах өдөр эхлэх өдрөөс өмнө байж болохгүй.");
      return;
    }
    setBusy("inventory");
    setError("");
    setNotice("");
    try {
      const inventory = await apiRequest<Inventory>(
        "/v1/organizations/" + organizationId + "/inventories",
        {
          method: "POST",
          body: JSON.stringify({
            name: inventoryName.trim(),
            reporting_period_start: periodStart,
            reporting_period_end: periodEnd,
            scope_2_primary_method: scope2PrimaryMethod
          })
        }
      );
      setInventories((current) => [inventory, ...current]);
      setInventoryId(inventory.id);
      setInventoryName("");
      setScope2PrimaryMethod("location_based");
      setNotice("Тайлант бүртгэл үүслээ. Одоо баталгаажсан коэффициенттэй үйл ажиллагааны мэдээлэл нэмнэ үү.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Тайлант бүртгэл үүсгэсэнгүй.");
    } finally {
      setBusy("");
    }
  }

  async function createActivity(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!organizationId || !inventoryId || !selectedFactor) return;
    setBusy("activity");
    setError("");
    setNotice("");
    try {
      const activity = await apiRequest<ActivityRecord>(
        "/v1/organizations/" + organizationId + "/inventories/" + inventoryId + "/activities",
        {
          method: "POST",
          body: JSON.stringify({
            name: activityName.trim() || selectedFactor.name,
            scope: selectedFactor.scope,
            category: selectedFactor.category,
            activity_amount: activityAmount,
            activity_unit: selectedFactor.factor_unit,
            emission_factor_id: selectedFactor.id
          })
        }
      );
      setActivities((current) => [...current, activity]);
      setActivityName("");
      setActivityAmount("");
      setNotice("Үйл ажиллагааны мөр эх сурвалж, коэффициентийн хувилбарын хамт хадгалагдлаа.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Үйл ажиллагааны мэдээлэл хадгалагдсангүй.");
    } finally {
      setBusy("");
    }
  }

  async function calculateInventory() {
    if (!organizationId || !inventoryId) return;
    setBusy("calculate");
    setError("");
    setNotice("");
    try {
      const calculation = await apiRequest<Calculation>(
        "/v1/organizations/" + organizationId + "/inventories/" + inventoryId + "/calculate",
        { method: "POST" }
      );
      setCalculations((current) => [calculation, ...current]);
      setNotice("Scope 1 болон Scope 2 тооцооллыг аудитын snapshot болгон хадгаллаа.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Тооцоолол амжилтгүй боллоо.");
    } finally {
      setBusy("");
    }
  }

  function changeOrganization(value: string) {
    setOrganizationId(value);
    setInventoryId("");
    setInventories([]);
    setFactors([]);
    setFactorId("");
    setActivities([]);
    setCalculations([]);
    setError("");
    setNotice("");
  }

  function exportInventoryCsv() {
    if (!selectedOrganization || !selectedInventory || activities.length === 0) return;
    const rows: (string | number)[][] = [
      ["CARBON ESG — Тайлангийн өгөгдөл"],
      ["Байгууллага", selectedOrganization.name],
      ["Тайлан", selectedInventory.name],
      ["Эхлэх огноо", selectedInventory.reporting_period_start],
      ["Дуусах огноо", selectedInventory.reporting_period_end],
      ["Scope 2 үндсэн арга", selectedInventory.scope_2_primary_method],
      ["Scope 2 location-based (kgCO2e)", latestCalculation?.scope_2_location_based_kgco2e || ""],
      ["Scope 2 market-based (kgCO2e)", latestCalculation?.scope_2_market_based_kgco2e || ""],
      ["Нийт location-based (kgCO2e)", latestCalculation?.total_location_based_kgco2e || ""],
      ["Нийт market-based (kgCO2e)", latestCalculation?.total_market_based_kgco2e || ""],
      ["Сүүлийн аргачлал", latestCalculation?.methodology_version || "Тооцоолоогүй"],
      ["Сүүлийн тооцооллын огноо", latestCalculation?.created_at || ""],
      [],
      ["Үйл ажиллагаа", "Scope", "Scope 2 method", "Ангилал", "Хэмжээ", "Нэгж", "Factor code", "Factor version", "Factor value", "Factor denominator unit", "Source", "Source URL", "Factor year", "Ялгаруулалт (kgCO2e)"],
      ...activities.map((item) => [
        item.name, item.scope, item.scope_2_method || "", item.category, item.activity_amount, item.activity_unit,
        item.factor_code, item.factor_version, item.factor_value_snapshot,
        item.factor_unit_snapshot, item.factor_source_name, item.factor_source_url,
        item.factor_year, item.emissions_kgco2e
      ])
    ];
    const csv = rows.map((row) => row.map((value) => {
      const raw = String(value ?? "");
      const safe = /^[=+@\\-]/.test(raw) ? "'" + raw : raw;
      return '"' + safe.replace(/"/g, '""') + '"';
    }).join(",")).join("\\r\\n");
    const blob = new Blob(["\\uFEFF", csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "carbon-esg-" + selectedInventory.reporting_period_start + "-" + selectedInventory.reporting_period_end + ".csv";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  return (
    <section className="workspace-dashboard">
      <div className="workspace-intro">
        <div>
          <p className="eyebrow">ТАНЫ АЖЛЫН ОРЧИН</p>
          <h1>Сайн байна уу, {userLabel}</h1>
          <p>Байгууллагаа сонгож, тайлант хугацаа болон хүлэмжийн хийн мэдээллээ удирдаарай.</p>
        </div>
        {selectedOrganization && (
          <div className="role-chip">
            <span>{selectedOrganization.name}</span>
            <strong>{selectedOrganization.role}</strong>
          </div>
        )}
      </div>

      {error && <p className="workspace-message error" role="alert">{error}</p>}
      {notice && <p className="workspace-message success" role="status">{notice}</p>}

      {initialLoading ? (
        <div className="workspace-panel loading-panel">Ажлын орчны мэдээлэл ачаалж байна…</div>
      ) : (
        <>
          <section className="workspace-panel">
            <div className="section-heading">
              <div>
                <h2>Байгууллага</h2>
                <p>Өгөгдөл байгууллага тус бүрээр тусгаарлагдана.</p>
              </div>
              {organizations.length > 0 && (
                <button
                  type="button"
                  className="button-secondary"
                  onClick={() => setShowOrganizationForm((value) => !value)}
                >
                  {showOrganizationForm ? "Хаах" : "Байгууллага нэмэх"}
                </button>
              )}
            </div>

            {organizations.length > 1 && (
              <label className="field organization-picker">
                <span>Ажиллах байгууллага</span>
                <select value={organizationId} onChange={(event) => changeOrganization(event.target.value)}>
                  {organizations.map((item) => (
                    <option key={item.id} value={item.id}>{item.name}</option>
                  ))}
                </select>
              </label>
            )}

            {organizations.length === 0 && (
              <p className="empty-state">Таны хэрэглэгчид одоогоор байгууллага холбогдоогүй байна. Шинэ ажлын орчин үүсгэнэ үү.</p>
            )}

            {(organizations.length === 0 || showOrganizationForm) && (
              <form className="inline-form" onSubmit={createOrganization}>
                <label className="field">
                  <span>Байгууллагын нэр</span>
                  <input
                    value={organizationName}
                    onChange={(event) => setOrganizationName(event.target.value)}
                    minLength={2}
                    maxLength={200}
                    placeholder="Жишээ: Монгол компани ХХК"
                    required
                  />
                </label>
                <button className="button-primary" type="submit" disabled={busy !== ""}>
                  {busy === "organization" ? "Үүсгэж байна…" : "Байгууллага үүсгэх"}
                </button>
              </form>
            )}
          </section>

          {selectedOrganization && (
            <section className="workspace-panel">
              <div className="section-heading">
                <div>
                  <h2>Тайлант бүртгэл</h2>
                  <p>Байгууллагын Scope 1, Scope 2 өгөгдлийг тайлант хугацаагаар хадгална.</p>
                </div>
                <span className="count-chip">{inventories.length} тайлан</span>
              </div>

              {canWrite && (
                <form className="inventory-form" onSubmit={createInventory}>
                  <label className="field">
                    <span>Тайлангийн нэр</span>
                    <input
                      value={inventoryName}
                      onChange={(event) => setInventoryName(event.target.value)}
                      minLength={2}
                      maxLength={200}
                      placeholder="2026 оны хүлэмжийн хийн тайлан"
                      required
                    />
                  </label>
                  <label className="field">
                    <span>Эхлэх огноо</span>
                    <input type="date" value={periodStart} onChange={(event) => setPeriodStart(event.target.value)} required />
                  </label>
                  <label className="field">
                    <span>Дуусах огноо</span>
                    <input type="date" value={periodEnd} onChange={(event) => setPeriodEnd(event.target.value)} min={periodStart || undefined} required />
                  </label>
                  <label className="field">
                    <span>Нийт тайланд ашиглах үндсэн Scope 2 арга</span>
                    <select value={scope2PrimaryMethod} onChange={(event) => setScope2PrimaryMethod(event.target.value as "location_based" | "market_based")}>
                      <option value="location_based">Location-based</option>
                      <option value="market_based">Market-based</option>
                    </select>
                  </label>
                  <button className="button-primary" type="submit" disabled={busy !== ""}>
                    {busy === "inventory" ? "Хадгалж байна…" : "Тайлан үүсгэх"}
                  </button>
                </form>
              )}

              {organizationLoading ? (
                <p className="empty-state">Тайлан болон коэффициентийн мэдээлэл ачаалж байна…</p>
              ) : inventories.length === 0 ? (
                <p className="empty-state">Одоогоор тайлан алга. {canWrite ? "Дээрх хэсгээс эхний тайлангаа үүсгэнэ үү." : "Байгууллагын засварлах эрхтэй хэрэглэгч тайлан үүсгэнэ."}</p>
              ) : (
                <div className="inventory-list">
                  {inventories.map((item) => (
                    <button
                      type="button"
                      key={item.id}
                      className={"inventory-item" + (item.id === inventoryId ? " selected" : "")}
                      onClick={() => setInventoryId(item.id)}
                    >
                      <span className="inventory-item-main">
                        <strong>{item.name}</strong>
                        <small>{formatDate(item.reporting_period_start)} — {formatDate(item.reporting_period_end)}</small>
                      </span>
                      <span className="status-chip">{item.status === "draft" ? "Ноорог" : item.status}</span>
                    </button>
                  ))}
                </div>
              )}
            </section>
          )}

          {selectedOrganization && (
            <FactorReviewPanel
              organizationId={selectedOrganization.id}
              role={selectedOrganization.role}
              apiRequest={apiRequest}
              onFactorsChanged={refreshFactors}
            />
          )}

          {selectedOrganization && selectedInventory && (
            <>
              <section className="workspace-panel">
                <div className="section-heading">
                  <div>
                    <h2>Үйл ажиллагааны өгөгдөл</h2>
                    <p>{selectedInventory.name} · {formatDate(selectedInventory.reporting_period_start)} — {formatDate(selectedInventory.reporting_period_end)}</p>
                  </div>
                  <span className="count-chip">{activities.length} мөр</span>
                </div>

                {inventoryLoading ? (
                  <p className="empty-state">Өгөгдөл ачаалж байна…</p>
                ) : factors.length === 0 ? (
                  <div className="empty-state">
                    <strong>Баталгаажсан ялгарлын коэффициент одоогоор алга.</strong>
                    <p>Эх сурвалж, он, нэгж, хувилбартай коэффициентийг эрх бүхий хянагч баталгаажуулсны дараа үйл ажиллагааны мөр нэмэх болон тооцоолол хийх боломжтой. Систем зохиомол коэффициент ашиглахгүй.</p>
                  </div>
                ) : canWrite ? (
                  <form className="activity-form" onSubmit={createActivity}>
                    <label className="field">
                      <span>Үйл ажиллагааны нэр</span>
                      <input
                        value={activityName}
                        onChange={(event) => setActivityName(event.target.value)}
                        maxLength={200}
                        placeholder="Жишээ: Үйлдвэрийн цахилгаан хэрэглээ"
                      />
                    </label>
                    <label className="field">
                      <span>Баталгаажсан коэффициент</span>
                      <select value={factorId} onChange={(event) => setFactorId(event.target.value)} required>
                        {factors.map((factor) => (
                          <option key={factor.id} value={factor.id}>
                            {scopeLabel(factor.scope)} · {CATEGORY_LABELS[factor.category] || factor.category} · {factor.name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="field">
                      <span>Хэрэглээний хэмжээ {selectedFactor ? "(" + selectedFactor.factor_unit + ")" : ""}</span>
                      <input
                        type="number"
                        min="0.00000001"
                        step="any"
                        value={activityAmount}
                        onChange={(event) => setActivityAmount(event.target.value)}
                        placeholder="0.00"
                        required
                      />
                    </label>
                    {selectedFactor && (
                      <div className="factor-provenance">
                        <strong>{selectedFactor.factor_code} · {selectedFactor.version}</strong>
                        <span>{formatNumber(selectedFactor.factor_value, 8)} kgCO₂e / {selectedFactor.factor_unit}</span>
                        <a href={selectedFactor.source_url} target="_blank" rel="noreferrer">{selectedFactor.source_name} · {selectedFactor.factor_year} оны эх сурвалж</a>
                      </div>
                    )}
                    <button className="button-primary" type="submit" disabled={busy !== "" || !selectedFactor}>
                      {busy === "activity" ? "Хадгалж байна…" : "Өгөгдөл нэмэх"}
                    </button>
                  </form>
                ) : (
                  <p className="empty-state">Таны эрх зөвхөн харах боломжтой. Үйл ажиллагааны мөр нэмэхэд owner, admin эсвэл editor эрх шаардлагатай.</p>
                )}

                {activities.length > 0 && (
                  <div className="table-scroll">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Үйл ажиллагаа</th>
                          <th>Хамрах хүрээ</th>
                          <th>Хэмжээ</th>
                          <th>Коэффициент</th>
                          <th>Ялгаруулалт</th>
                          <th>Эх сурвалж</th>
                        </tr>
                      </thead>
                      <tbody>
                        {activities.map((item) => (
                          <tr key={item.id}>
                            <td><strong>{item.name}</strong><small>{CATEGORY_LABELS[item.category] || item.category}</small></td>
                            <td>{scopeLabel(item.scope)}{item.scope_2_method && <small>{item.scope_2_method === "location_based" ? "Location-based" : "Market-based"}</small>}</td>
                            <td>{formatNumber(item.activity_amount, 4)} {item.activity_unit}</td>
                            <td>{item.factor_code}<small>{item.factor_version} · {formatNumber(item.factor_value_snapshot, 8)} / {item.factor_unit_snapshot}</small></td>
                            <td><strong>{formatNumber(item.emissions_kgco2e, 4)} kg</strong></td>
                            <td><a href={item.factor_source_url} target="_blank" rel="noreferrer">{item.factor_source_name} · {item.factor_year}</a></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>

              {selectedOrganization && (
                <EvidencePanel
                  organizationId={selectedOrganization.id}
                  activities={activities.map((item) => ({ id: item.id, name: item.name }))}
                  canWrite={canWrite}
                  apiRequest={apiRequest}
                />
              )}

              <section className="workspace-panel">
                <div className="section-heading">
                  <div>
                    <h2>Scope 1 ба Scope 2 тооцоолол</h2>
                    <p>Сервер дээр Decimal арифметикаар тооцож, эх өгөгдөл болон коэффициентийн snapshot хадгална.</p>
                  </div>
                  <div className="section-actions">
                    {activities.length > 0 && (
                      <button type="button" className="button-secondary" onClick={exportInventoryCsv}>
                        CSV тайлан татах
                      </button>
                    )}
                    {canWrite && (
                      <button
                        type="button"
                        className="button-primary"
                        onClick={calculateInventory}
                        disabled={busy !== "" || activities.length === 0}
                      >
                        {busy === "calculate" ? "Тооцоолж байна…" : "Тооцоолол хийх"}
                      </button>
                    )}
                  </div>
                </div>

                {latestCalculation ? (
                  <>
                    <div className="calculation-grid">
                      <article><span>Scope 1 · Шууд</span><strong>{formatNumber(Number(latestCalculation.scope_1_kgco2e) / 1000)} tCO₂e</strong></article>
                      <article><span>Scope 2 · Location-based</span><strong>{latestCalculation.scope_2_location_based_kgco2e === null ? "—" : formatNumber(Number(latestCalculation.scope_2_location_based_kgco2e) / 1000) + " tCO₂e"}</strong></article>
                      <article><span>Scope 2 · Market-based</span><strong>{latestCalculation.scope_2_market_based_kgco2e === null ? "—" : formatNumber(Number(latestCalculation.scope_2_market_based_kgco2e) / 1000) + " tCO₂e"}</strong></article>
                      <article className="calculation-total"><span>Нийт · {latestCalculation.scope_2_primary_method === "location_based" ? "Location-based" : "Market-based"}</span><strong>{formatNumber(Number(latestCalculation.total_kgco2e) / 1000)} tCO₂e</strong></article>
                    </div>
                    <p className="calculation-meta">Аргачлал: {latestCalculation.methodology_version} · {new Date(latestCalculation.created_at).toLocaleString("mn-MN")}</p>
                  </>
                ) : (
                  <p className="empty-state">Одоогоор тооцооллын үр дүн алга. Үйл ажиллагааны мөр нэмсний дараа тооцоолно.</p>
                )}

                {calculations.length > 1 && (
                  <div className="history-list">
                    <h3>Өмнөх тооцооллууд</h3>
                    {calculations.slice(1).map((item) => (
                      <div className="history-item" key={item.id}>
                        <span>{new Date(item.created_at).toLocaleString("mn-MN")}</span>
                        <strong>{formatNumber(Number(item.total_kgco2e) / 1000)} tCO₂e</strong>
                        <small>{item.methodology_version}</small>
                      </div>
                    ))}
                  </div>
                )}
                {!canWrite && <p className="permission-note">Тооцоолол үүсгэхэд owner, admin эсвэл editor эрх шаардлагатай.</p>}
              </section>
            </>
          )}
        </>
      )}
    </section>
  );
}
