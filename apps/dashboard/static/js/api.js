export class ApiError extends Error {
  constructor(status, code, message, traceId = null) { super(message); this.status = status; this.code = code; this.traceId = traceId; }
}

async function request(path, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 8000);
  try {
    const response = await fetch(path, {
      ...options,
      signal: controller.signal,
      headers: { Accept: "application/json", ...(options.headers || {}) },
    });
    let body = null;
    try { body = await response.json(); } catch { body = null; }
    if (!response.ok) {
      const error = body?.error || {};
      throw new ApiError(response.status, error.code || "HTTP_ERROR", error.message || "Request failed.", error.trace_id || null);
    }
    return body;
  } catch (error) {
    if (error.name === "AbortError") throw new ApiError(0, "TIMEOUT", "The backend did not respond in time.");
    throw error;
  } finally { clearTimeout(timeout); }
}

export const api = {
  health: () => request("/health/ready"),
  orders: () => request("/v1/fixtures/orders"),
  startRun: (payload) => request("/v1/runs", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }),
  run: (traceId) => request(`/v1/runs/${encodeURIComponent(traceId)}`),
  events: (traceId) => request(`/v1/traces/${encodeURIComponent(traceId)}/events`),
  decisions: (traceId) => request(`/v1/traces/${encodeURIComponent(traceId)}/decisions`),
  projection: (traceId) => request(`/v1/traces/${encodeURIComponent(traceId)}/projection`),
  verify: (traceId) => request(`/v1/traces/${encodeURIComponent(traceId)}/verify`),
  approval: (approvalId) => request(`/v1/approvals/${encodeURIComponent(approvalId)}`),
  decideApproval: (approvalId, payload, secret) => request(`/v1/approvals/${encodeURIComponent(approvalId)}`, { method: "POST", headers: { "Content-Type": "application/json", "X-Demo-Approver-Secret": secret }, body: JSON.stringify(payload) }),
  reset: () => request("/v1/demo/reset", { method: "POST" }),
  tamper: (traceId, payload, secret) => request(`/v1/demo/traces/${encodeURIComponent(traceId)}/tamper`, { method: "POST", headers: { "Content-Type": "application/json", "X-Demo-Tamper-Secret": secret }, body: JSON.stringify(payload) }),
};
