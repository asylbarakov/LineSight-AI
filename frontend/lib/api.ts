// Единый клиент API: базовый URL, токен, обработка ошибок, переключатель «мок / реальный» (задача 15).
import { clearToken, getToken, setToken } from "./auth";
import { mockDetail, mockFindings, mockInspections, mockMetrics, mockPatch } from "./mocks";
import type { Decision, Finding, InspectionDetail, InspectionSummary, Metrics } from "./types";

export const USE_MOCKS = process.env.NEXT_PUBLIC_USE_MOCKS === "true";
const BASE = process.env.NEXT_PUBLIC_API_URL ?? ""; // пусто: тот же origin, запросы идут через rewrites Next.js

export class ApiError extends Error {
  constructor(public status: number, message: string, public errorCode?: string) {
    super(message);
  }
}

function redirectToLogin(): void {
  clearToken();
  if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
    window.location.href = "/login";
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, { ...init, headers, credentials: "include" });
  } catch {
    throw new ApiError(0, "Нет связи с сервером");
  }
  if (res.status === 401 && !path.endsWith("/login")) {
    redirectToLogin();
    throw new ApiError(401, "Требуется вход");
  }
  if (!res.ok) {
    let detail = `Ошибка ${res.status}`;
    let code: string | undefined;
    try {
      const body = await res.json();
      if (body?.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
      code = body?.error_code;
    } catch {
      /* тело не JSON */
    }
    throw new ApiError(res.status, detail, code);
  }
  return (await res.json()) as T;
}

const delay = <T,>(v: T, ms = 150) => new Promise<T>((r) => setTimeout(() => r(v), ms));

export async function login(login: string, password: string): Promise<void> {
  if (USE_MOCKS) {
    if (!login || !password) throw new ApiError(401, "Неверный логин или пароль");
    setToken("mock-token");
    return delay(undefined);
  }
  const r = await request<{ token: string }>("/api/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ login, password }),
  });
  setToken(r.token);
}

export async function logout(): Promise<void> {
  clearToken();
  if (!USE_MOCKS) {
    try {
      await fetch(`${BASE}/api/logout`, { method: "POST", credentials: "include" });
    } catch {
      /* без сети токен уже очищен локально */
    }
  }
}

export const listInspections = (): Promise<InspectionSummary[]> =>
  USE_MOCKS ? delay(mockInspections) : request("/api/inspections");

export const getInspection = (id: string): Promise<InspectionDetail> =>
  USE_MOCKS ? delay(mockDetail(id)) : request(`/api/inspections/${id}`);

export const getFindings = (id: string): Promise<Finding[]> =>
  USE_MOCKS ? delay(mockFindings) : request(`/api/inspections/${id}/findings`);

export const patchFinding = (id: string, status: Decision): Promise<Finding> =>
  USE_MOCKS
    ? delay(mockPatch(id, status))
    : request(`/api/findings/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });

export const getMetrics = (): Promise<Metrics> => (USE_MOCKS ? delay(mockMetrics) : request("/api/metrics"));

/** Загрузка с прогрессом (fetch не отдаёт прогресс отправки, поэтому XMLHttpRequest). */
export function uploadInspection(
  file: File,
  title: string,
  onProgress: (fraction: number) => void,
): Promise<{ id: string }> {
  if (USE_MOCKS) return delay({ id: "mock-2" }, 400);
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${BASE}/api/inspections`);
    xhr.withCredentials = true;
    const token = getToken();
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(e.loaded / e.total);
    };
    xhr.onerror = () => reject(new ApiError(0, "Нет связи с сервером"));
    xhr.onload = () => {
      let body: { id?: string; detail?: string; error_code?: string } = {};
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        /* не JSON */
      }
      if (xhr.status === 401) {
        redirectToLogin();
        reject(new ApiError(401, "Требуется вход"));
      } else if (xhr.status >= 200 && xhr.status < 300 && body.id) {
        resolve({ id: body.id });
      } else {
        reject(new ApiError(xhr.status, body.detail ?? `Ошибка ${xhr.status}`, body.error_code));
      }
    };
    const form = new FormData();
    form.append("file", file);
    form.append("title", title);
    xhr.send(form);
  });
}

export const videoUrl = (id: string): string => `${BASE}/api/inspections/${id}/video`;
export const frameUrl = (id: string, name: string): string => `${BASE}/api/inspections/${id}/frames/${name}`;

/** Скачивание PDF как файла (с токеном). */
export async function downloadReport(id: string, title: string): Promise<void> {
  if (USE_MOCKS) {
    await delay(undefined, 600);
    throw new ApiError(0, "В режиме моков отчёт недоступен");
  }
  const headers = new Headers();
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(`${BASE}/api/inspections/${id}/report.pdf`, { headers, credentials: "include" });
  if (res.status === 401) {
    redirectToLogin();
    throw new ApiError(401, "Требуется вход");
  }
  if (!res.ok) {
    let detail = "Отчёт недоступен";
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* не JSON */
    }
    throw new ApiError(res.status, detail);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${title.replace(/[^\p{L}\p{N}_-]+/gu, "_") || "report"}.pdf`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
