"use client";

import { type FormEvent, useCallback, useEffect, useState } from "react";

type Evidence = {
  id: string;
  activity_id: string | null;
  original_filename: string;
  media_type: string;
  size_bytes: number;
  sha256: string;
  scan_status: string;
  created_at: string;
};

type ActivityOption = { id: string; name: string };
type ApiRequest = <T,>(path: string, init?: RequestInit) => Promise<T>;

const MAX_FILE_BYTES = 15 * 1024 * 1024;

function formatBytes(value: number) {
  if (value < 1024) return value + " B";
  if (value < 1024 * 1024) return (value / 1024).toFixed(1) + " KB";
  return (value / (1024 * 1024)).toFixed(1) + " MB";
}

export function EvidencePanel({
  organizationId,
  activities,
  canWrite,
  apiRequest
}: {
  organizationId: string;
  activities: ActivityOption[];
  canWrite: boolean;
  apiRequest: ApiRequest;
}) {
  const base = "/v1/organizations/" + organizationId + "/evidence";
  const [items, setItems] = useState<Evidence[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [activityId, setActivityId] = useState("");
  const [downloadUrls, setDownloadUrls] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const rows = await apiRequest<Evidence[]>(base);
      setItems(rows);
      setError("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Баримтын жагсаалт ачаалсангүй.");
    } finally {
      setLoading(false);
    }
  }, [apiRequest, base]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    apiRequest<Evidence[]>(base)
      .then((rows) => {
        if (active) {
          setItems(rows);
          setError("");
        }
      })
      .catch((cause: unknown) => {
        if (active) setError(cause instanceof Error ? cause.message : "Баримтын жагсаалт ачаалсангүй.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [apiRequest, base]);

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file || !canWrite) return;
    if (file.size > MAX_FILE_BYTES) {
      setError("Файлын хэмжээ 15 MB-аас ихгүй байна.");
      return;
    }
    const form = new FormData();
    form.append("file", file);
    if (activityId) form.append("activity_id", activityId);

    setBusy("upload");
    setError("");
    setNotice("");
    try {
      await apiRequest<Evidence>(base, { method: "POST", body: form });
      setFile(null);
      setActivityId("");
      const input = document.getElementById("evidence-file-input") as HTMLInputElement | null;
      if (input) input.value = "";
      setNotice("Баримт malware scan-аар цэвэр гэж шалгагдаж, private storage-д хадгалагдлаа.");
      await reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Баримт байршуулах боломжгүй байна.");
    } finally {
      setBusy("");
    }
  }

  async function prepareDownload(item: Evidence) {
    setBusy("download:" + item.id);
    setError("");
    try {
      const result = await apiRequest<{ download_url: string }>(base + "/" + item.id + "/download");
      setDownloadUrls((current) => ({ ...current, [item.id]: result.download_url }));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Татах холбоос үүсгэсэнгүй.");
    } finally {
      setBusy("");
    }
  }

  return (
    <section className="workspace-panel">
      <div className="section-heading">
        <div>
          <h2>Нотлох баримтын сан</h2>
          <p>Баримтыг malware scan хийж, байгууллагын private storage-д хадгална. Татах холбоос 5 минут хүчинтэй.</p>
        </div>
        <span className="count-chip">{items.length} файл</span>
      </div>

      {error && <p className="workspace-message error" role="alert">{error}</p>}
      {notice && <p className="workspace-message success" role="status">{notice}</p>}

      {canWrite ? (
        <form className="activity-form evidence-upload-form" onSubmit={upload}>
          <label className="field">
            <span>Баримт файл (PDF, PNG, JPEG, CSV, XLSX · 15 MB хүртэл)</span>
            <input
              id="evidence-file-input"
              type="file"
              accept=".pdf,.png,.jpg,.jpeg,.csv,.xlsx"
              onChange={(event) => setFile(event.target.files?.[0] || null)}
              required
            />
          </label>
          <label className="field">
            <span>Холбогдох үйл ажиллагаа (сонголтоор)</span>
            <select value={activityId} onChange={(event) => setActivityId(event.target.value)}>
              <option value="">Ерөнхий баримт</option>
              {activities.map((activity) => (
                <option key={activity.id} value={activity.id}>{activity.name}</option>
              ))}
            </select>
          </label>
          <button className="button-primary" type="submit" disabled={!file || busy !== ""}>
            {busy === "upload" ? "Шалгаж, байршуулж байна…" : "Баримт байршуулах"}
          </button>
          <p className="permission-note">Scanner эсвэл private storage тохируулаагүй үед систем файлыг хадгалахгүй, хүсэлтийг хаана.</p>
        </form>
      ) : (
        <p className="empty-state">Баримт байршуулахад owner, admin эсвэл editor эрх шаардлагатай.</p>
      )}

      {loading ? (
        <p className="empty-state">Баримтын жагсаалт ачаалж байна…</p>
      ) : items.length === 0 ? (
        <p className="empty-state">Одоогоор нотлох баримт бүртгэгдээгүй байна.</p>
      ) : (
        <div className="evidence-list">
          {items.map((item) => (
            <article className="history-item evidence-item" key={item.id}>
              <div>
                <strong>{item.original_filename}</strong>
                <small>{formatBytes(item.size_bytes)} · {item.media_type} · {new Date(item.created_at).toLocaleString("mn-MN")}</small>
                <small>SHA-256: {item.sha256}</small>
                <small>Scan: {item.scan_status === "clean" ? "Цэвэр" : item.scan_status}</small>
              </div>
              {downloadUrls[item.id] ? (
                <a className="button-secondary" href={downloadUrls[item.id]} target="_blank" rel="noreferrer">Татах</a>
              ) : (
                <button
                  type="button"
                  className="button-secondary"
                  onClick={() => void prepareDownload(item)}
                  disabled={busy !== ""}
                >
                  {busy === "download:" + item.id ? "Бэлтгэж байна…" : "Татах холбоос"}
                </button>
              )}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
