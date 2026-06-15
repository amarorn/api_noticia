import { applyDataPulseFromHeaders } from "./dataPulseStore";

const API_BASE = import.meta.env.VITE_API_URL ?? "/api";
const API_KEY = import.meta.env.VITE_API_KEY?.trim() || undefined;

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export const API_TIMEOUT_MS = 30_000;
export const API_SYNC_TIMEOUT_MS = 180_000;
/** Sync com fetch_body (~1000 URLs); evita abort no meio da coleta. */
export const API_SYNC_FETCH_BODY_TIMEOUT_MS = 900_000;

export async function apiFetch<T>(
  path: string,
  init?: RequestInit & { timeoutMs?: number },
): Promise<T> {
  const { timeoutMs = API_TIMEOUT_MS, ...fetchInit } = init ?? {};
  const url = `${API_BASE}${path}`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  let response: Response;
  try {
    response = await fetch(url, {
      ...fetchInit,
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...(API_KEY ? { "X-API-Key": API_KEY } : {}),
        ...fetchInit.headers,
      },
    });
  } catch (err) {
    if (err instanceof Error && err.name === "AbortError") {
      throw new ApiError(
        "A requisição demorou demais. Verifique se a API está rodando (./scripts/dev-api.sh).",
        408,
      );
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }

  applyDataPulseFromHeaders(response.headers);

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      const raw = body.detail ?? body.message ?? detail;
      if (Array.isArray(raw)) {
        detail = raw
          .map((item: { msg?: string; message?: string }) => item.msg ?? item.message ?? String(item))
          .join(" · ");
      } else if (typeof raw === "object" && raw !== null) {
        detail = (raw as { message?: string }).message ?? JSON.stringify(raw);
      } else {
        detail = String(raw);
      }
    } catch {
      /* ignore */
    }
    throw new ApiError(String(detail), response.status);
  }

  return response.json() as Promise<T>;
}
