export class ApiError extends Error {
  constructor(status, code, message, traceId = null) { super(message); this.status = status; this.code = code; this.traceId = traceId; }
}

async function request(path, options = {}) {
  const { timeoutMs = 8000, ...fetchOptions } = options;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(path, {
      ...fetchOptions,
      signal: controller.signal,
      headers: { Accept: "application/json", ...(fetchOptions.headers || {}) },
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

function mutationHeaders(accessSecret, extra = {}) {
  return {
    ...extra,
    ...(accessSecret ? { "X-Manifest-Demo-Secret": accessSecret } : {}),
  };
}

export const api = {
  health: () => request("/health/ready"),
  orders: () => request("/v1/fixtures/orders"),
  startRun: (payload, accessSecret = "") => request("/v1/runs", { method: "POST", headers: mutationHeaders(accessSecret, { "Content-Type": "application/json" }), body: JSON.stringify(payload), timeoutMs: 240000 }),
  run: (traceId) => request(`/v1/runs/${encodeURIComponent(traceId)}`),
  events: (traceId) => request(`/v1/traces/${encodeURIComponent(traceId)}/events`),
  decisions: (traceId) => request(`/v1/traces/${encodeURIComponent(traceId)}/decisions`),
  projection: (traceId) => request(`/v1/traces/${encodeURIComponent(traceId)}/projection`),
  verify: (traceId) => request(`/v1/traces/${encodeURIComponent(traceId)}/verify`),
  approval: (approvalId) => request(`/v1/approvals/${encodeURIComponent(approvalId)}`),
  decideApproval: (approvalId, payload, secret, accessSecret = "") => request(`/v1/approvals/${encodeURIComponent(approvalId)}`, { method: "POST", headers: mutationHeaders(accessSecret, { "Content-Type": "application/json", "X-Demo-Approver-Secret": secret }), body: JSON.stringify(payload), timeoutMs: 240000 }),
  reset: (accessSecret = "") => request("/v1/demo/reset", { method: "POST", headers: mutationHeaders(accessSecret) }),
  tamper: (traceId, payload, secret, accessSecret = "") => request(`/v1/demo/traces/${encodeURIComponent(traceId)}/tamper`, { method: "POST", headers: mutationHeaders(accessSecret, { "Content-Type": "application/json", "X-Demo-Tamper-Secret": secret }), body: JSON.stringify(payload) }),
};
