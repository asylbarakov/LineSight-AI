import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, downloadReport, getFindings, getMetrics, login, patchFinding, uploadInspection } from "./api";

describe("existing API integration contracts", () => {
  const storage = new Map<string, string>();
  const location = { pathname: "/inspections/test", href: "" };
  beforeEach(() => {
    storage.clear(); location.href = "";
    vi.stubGlobal("window", { location, localStorage: { getItem: (key: string) => storage.get(key) ?? null, setItem: (key: string, value: string) => storage.set(key, value), removeItem: (key: string) => storage.delete(key) } });
  });
  afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
  it("aborts a stalled JSON request and exposes a retryable error instead of loading forever", async () => {
    vi.useFakeTimers();
    let signal: AbortSignal | undefined;
    vi.stubGlobal("fetch", vi.fn((_url: string, options: RequestInit) => {
      signal = options.signal ?? undefined;
      return new Promise((_resolve, reject) => signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError"))));
    }));
    const outcome = getMetrics().catch(error => error);
    await vi.advanceTimersByTimeAsync(30_000);
    expect(signal?.aborted).toBe(true);
    expect(await outcome).toMatchObject({status: 0, message: expect.stringContaining("ответ")});
    expect(vi.getTimerCount()).toBe(0);
  });
  it("keeps the deadline active while a successful response body is stalled", async () => {
    vi.useFakeTimers();
    let signal: AbortSignal | undefined;
    vi.stubGlobal("fetch", vi.fn(async (_url: string, options: RequestInit) => {
      signal = options.signal ?? undefined;
      return {ok: true, status: 200, json: () => new Promise((_resolve, reject) => signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError"))))};
    }));
    const outcome = getMetrics().catch(error => error);
    await vi.advanceTimersByTimeAsync(30_000);
    expect(signal?.aborted).toBe(true);
    expect(await outcome).toMatchObject({status: 0});
  });
  it("bounds a stalled PDF download while allowing a longer report deadline", async () => {
    vi.useFakeTimers();
    let signal: AbortSignal | undefined;
    vi.stubGlobal("fetch", vi.fn((_url: string, options: RequestInit) => {
      signal = options.signal ?? undefined;
      return new Promise((_resolve, reject) => signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError"))));
    }));
    const outcome = downloadReport("test", "Inspection").catch(error => error);
    await vi.advanceTimersByTimeAsync(30_000);
    expect(signal?.aborted).toBe(false);
    await vi.advanceTimersByTimeAsync(60_000);
    expect(signal?.aborted).toBe(true);
    expect(await outcome).toMatchObject({status: 0});
  });
  it("stores login credentials' response token and sends authenticated finding requests", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({token: "test-session"})))
      .mockResolvedValueOnce(new Response("[]"));
    vi.stubGlobal("fetch", fetcher);
    await login("engineer", "test-only");
    await getFindings("test");
    expect(storage.get("ls_token")).toBe("test-session");
    const [path, options] = fetcher.mock.calls[1];
    expect(path).toBe("/api/inspections/test/findings");
    expect(options.headers.get("Authorization")).toBe("Bearer test-session");
    expect(options.credentials).toBe("include");
  });
  it.each(["confirmed", "rejected", "reshoot"] as const)("preserves the %s review decision contract", async status => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({id: "f1", status})));
    vi.stubGlobal("fetch", fetcher);
    expect(await patchFinding("f1", status)).toMatchObject({id: "f1", status});
    expect(fetcher.mock.calls[0][0]).toBe("/api/findings/f1");
    expect(fetcher.mock.calls[0][1]).toMatchObject({method: "PATCH", body: JSON.stringify({status})});
  });
  it("clears an expired session and redirects instead of retrying as an authenticated user", async () => {
    storage.set("ls_token", "expired");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("", {status: 401})));
    await expect(getMetrics()).rejects.toMatchObject({status: 401});
    expect(storage.has("ls_token")).toBe(false);
    expect(location.href).toBe("/login");
  });
  it("exposes network and server failures so pages can stop loading and offer retry", async () => {
    const fetcher = vi.fn().mockRejectedValueOnce(new TypeError("offline"))
      .mockResolvedValueOnce(new Response(JSON.stringify({detail: "Unavailable"}), {status: 503}))
      .mockResolvedValueOnce(new Response(JSON.stringify({inspections_total: 0})));
    vi.stubGlobal("fetch", fetcher);
    await expect(getMetrics()).rejects.toBeInstanceOf(ApiError);
    await expect(getMetrics()).rejects.toMatchObject({status: 503, message: "Unavailable"});
    await expect(getMetrics()).resolves.toMatchObject({inspections_total: 0});
  });
  it("keeps report errors visible and does not create a false download", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({detail: "Report not ready"}), {status: 503}));
    vi.stubGlobal("fetch", fetcher);
    await expect(downloadReport("test", "Inspection")).rejects.toMatchObject({status: 503, message: "Report not ready"});
    expect(fetcher.mock.calls[0][0]).toBe("/api/inspections/test/report.pdf");
  });
  it("downloads a successful PDF with authentication and a safe filename", async () => {
    storage.set("ls_token", "test-session");
    const fetcher = vi.fn().mockResolvedValue(new Response(new Blob(["%PDF-test"], {type: "application/pdf"})));
    vi.stubGlobal("fetch", fetcher);
    const anchor = {href: "", download: "", click: vi.fn(), remove: vi.fn()};
    vi.stubGlobal("document", {createElement: () => anchor, body: {appendChild: vi.fn()}});
    vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:validation-only");
    const revoke = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
    await downloadReport("test", "ЛЭП / 1");
    expect(fetcher.mock.calls[0][1].headers.get("Authorization")).toBe("Bearer test-session");
    expect(anchor.download).toBe("ЛЭП_1.pdf");
    expect(anchor.click).toHaveBeenCalledOnce();
    expect(revoke).toHaveBeenCalledWith("blob:validation-only");
  });
  it("uploads the original MP4 and title with real XHR progress and session credentials", async () => {
    storage.set("ls_token", "test-session");
    const open = vi.fn(), header = vi.fn(), progress = vi.fn();
    let submitted: FormData | undefined;
    let credentials = false;
    vi.stubGlobal("XMLHttpRequest", class {
      withCredentials = false;
      upload: {onprogress?: (event: {lengthComputable: boolean; loaded: number; total: number}) => void} = {};
      status = 201; responseText = '{"id":"uploaded"}'; onload?: () => void;
      open = open; setRequestHeader = header;
      send(form: FormData) {
        submitted = form; credentials = this.withCredentials;
        this.upload.onprogress?.({lengthComputable: true, loaded: 5, total: 10});
        this.onload?.();
      }
    });
    const file = new File(["test-mp4"], "flight.mp4", {type: "video/mp4"});
    await expect(uploadInspection(file, "Инспекция", progress)).resolves.toEqual({id: "uploaded"});
    expect(open).toHaveBeenCalledWith("POST", "/api/inspections");
    expect(header).toHaveBeenCalledWith("Authorization", "Bearer test-session");
    expect(credentials).toBe(true);
    expect(submitted?.get("title")).toBe("Инспекция");
    expect((submitted?.get("file") as File).name).toBe("flight.mp4");
    expect(progress).toHaveBeenCalledWith(.5);
  });
});
