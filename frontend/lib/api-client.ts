export class ApiRequestError extends Error {
  constructor(message: string, readonly canonicalResult?: Record<string, unknown>, readonly session?: unknown, readonly status?: number) { super(message); }
}

function failedRecord(payload: unknown): Record<string, unknown> | undefined {
  if (!payload || typeof payload !== "object") return;
  const detail = (payload as { detail?: unknown }).detail;
  if (!detail || typeof detail !== "object") return;
  const record = (detail as { canonical_result?: unknown }).canonical_result;
  if (!record || typeof record !== "object") return;
  const item = record as Record<string, unknown>;
  const result = item.payload as Record<string, unknown> | undefined;
  if (typeof item.schema_version === "string" && result?.status === "EXECUTION_FAILED" && result.executable === false) return item;
}

function detailMessage(payload: unknown): string | undefined {
  if (!payload || typeof payload !== "object") return;
  const detail = (payload as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object") {
    const item = detail as { reason?: unknown };
    if (typeof item.reason === "string") return item.reason;
  }
}

export async function requestJson<T>(input: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(input, init);
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new Error("Could not reach the local OpsLens API. Start FastAPI and confirm the configured API URL.");
  }

  const contentType = response.headers.get("content-type") || "unspecified content type";
  const raw = await response.text();
  let payload: unknown;
  try {
    payload = JSON.parse(raw);
  } catch {
    throw new Error("The local service returned an unreadable response. Please retry; if this continues, check the service logs.");
  }
  if (!contentType.toLowerCase().includes("json")) {
    throw new Error("The local service response could not be read. Please retry; if this continues, check the service logs.");
  }
  if (!response.ok) throw new ApiRequestError(detailMessage(payload) || `Local API request failed with HTTP ${response.status}.`, failedRecord(payload),
    (payload as { detail?: { session?: unknown } }).detail?.session, response.status);
  return payload as T;
}
