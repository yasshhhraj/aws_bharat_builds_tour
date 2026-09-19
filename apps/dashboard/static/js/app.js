import { api } from "./api.js";
import { state, update } from "./state.js";
import { renderDisposable, renderEmpty, renderHealth, renderMessage, renderTrace, setControls } from "./render.js";

const byId = (id) => document.getElementById(id);
let pollTimer = null;

function idempotencyKey(prefix) {
  const suffix = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `${prefix}-${suffix}`;
}

function renderCurrent() {
  if (!state.run) return renderEmpty();
  renderTrace(state, { showAllEvents: state.showAllEvents, onApprovalDecision: resolveApproval });
}

function configurePolling() {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = null;
  if (state.run?.status !== "pending_approval") return;
  pollTimer = setInterval(() => { if (!document.hidden && !state.loading && state.activeTraceId) loadTrace(state.activeTraceId, true); }, 3000);
}

async function loadTrace(traceId, quiet = false) {
  update({ loading: true, error: null }); setControls({ ready: true, loading: true, hasTrace: true }); if (!quiet) renderMessage("Loading governed trace…");
  try {
    const [run, events, decisions, projection, verification] = await Promise.all([api.run(traceId), api.events(traceId), api.decisions(traceId), api.projection(traceId), api.verify(traceId)]);
    const approval = run.pending_approval_id ? await api.approval(run.pending_approval_id) : null;
    update({ activeTraceId: traceId, run, events: events.items, decisions: decisions.items, projection, verification, approval, lastUpdatedAt: new Date(), loading: false });
    history.replaceState(null, "", `/dashboard/?trace_id=${encodeURIComponent(traceId)}`); renderCurrent(); if (!quiet) renderMessage(`${events.items.length} ledger events loaded.`); configurePolling();
  } catch (error) { update({ loading: false, error }); renderMessage(`${error.code || "ERROR"}: ${error.message}`, true); }
  setControls({ ready: Boolean(state.health), loading: false, hasTrace: Boolean(state.activeTraceId) });
}

async function startRun(event) {
  event.preventDefault(); update({ loading: true }); setControls({ ready: true, loading: true, hasTrace: false }); renderMessage("Manifest is governing the shipment…");
  try { const run = await api.startRun({ order_id: byId("orderSelect").value, mode: byId("modeSelect").value, scenario: byId("scenarioSelect").value }); await loadTrace(run.trace_id); }
  catch (error) { update({ loading: false, error }); renderMessage(`${error.code || "ERROR"}: ${error.message}`, true); setControls({ ready: true, loading: false, hasTrace: false }); }
}

async function resolveApproval(decision, controls) {
  const secret = controls.secretInput.value; controls.buttons.forEach((button) => { button.disabled = true; }); renderMessage(`${decision === "approve" ? "Approving" : "Rejecting"} the exact prepared action…`);
  try {
    if (!secret) throw new Error("Enter the demo approval secret.");
    await api.decideApproval(state.approval.approval_id, { decision, approver_label: controls.approverInput.value, comment: controls.commentInput.value || null, expected_version: state.approval.version, idempotency_key: idempotencyKey(`dashboard-${decision}`) }, secret);
    await loadTrace(state.activeTraceId); renderMessage(`Approval ${decision} completed and the same trace was refreshed.`);
  } catch (error) { renderMessage(`${error.code || "APPROVAL_ERROR"}: ${error.message}`, true); await loadTrace(state.activeTraceId, true); }
  finally { controls.secretInput.value = ""; controls.buttons.forEach((button) => { button.disabled = false; }); }
}

async function resetDemo() {
  update({ loading: true }); setControls({ ready: true, loading: true, hasTrace: Boolean(state.activeTraceId) }); renderMessage("Resetting synthetic demo state…");
  try { await api.reset(); if (pollTimer) clearInterval(pollTimer); history.replaceState(null, "", "/dashboard/"); update({ activeTraceId: null, run: null, events: [], decisions: [], projection: null, verification: null, approval: null, disposableTraceId: null, disposableVerification: null, loading: false }); renderEmpty(); renderDisposable(null, null); renderMessage("Demo state reset. Ready for a clean run."); }
  catch (error) { update({ loading: false }); renderMessage(`${error.code || "RESET_ERROR"}: ${error.message}`, true); }
  setControls({ ready: Boolean(state.health), loading: false, hasTrace: false });
}

async function refreshVerification() {
  if (!state.activeTraceId) return;
  try { update({ verification: await api.verify(state.activeTraceId) }); renderCurrent(); renderMessage("Ledger verification refreshed."); }
  catch (error) { renderMessage(`${error.code || "VERIFY_ERROR"}: ${error.message}`, true); }
}

async function createDisposable() {
  renderMessage("Creating a separate disposable trace…");
  try { const run = await api.startRun({ order_id: "ORD-8842", mode: "enforce", scenario: "benign" }); const verification = await api.verify(run.trace_id); update({ disposableTraceId: run.trace_id, disposableVerification: verification }); renderDisposable(run.trace_id, verification); byId("tamperButton").disabled = false; renderMessage("Disposable trace is clean and ready for the integrity demo."); }
  catch (error) { renderMessage(`${error.code || "TAMPER_SETUP_ERROR"}: ${error.message}`, true); }
}

async function tamperDisposable() {
  const secretInput = byId("tamperSecret"); const secret = secretInput.value;
  try { if (!state.disposableTraceId) throw new Error("Create a disposable trace first."); if (!secret) throw new Error("Enter the tamper demo secret."); byId("tamperButton").disabled = true; await api.tamper(state.disposableTraceId, { sequence: 5, replacement_summary: "Disposable dashboard alteration" }, secret); const verification = await api.verify(state.disposableTraceId); update({ disposableVerification: verification }); renderDisposable(state.disposableTraceId, verification); renderMessage(`Tamper detected at sequence ${verification.first_bad_sequence}.`); }
  catch (error) { renderMessage(`${error.code || "TAMPER_ERROR"}: ${error.message}`, true); byId("tamperButton").disabled = false; }
  finally { secretInput.value = ""; }
}

async function initialize() {
  setControls({ ready: false, loading: true, hasTrace: false }); renderEmpty();
  try {
    const [health, orders] = await Promise.all([api.health(), api.orders()]); update({ health, fixtures: orders.items }); renderHealth(health);
    const select = byId("orderSelect"); select.replaceChildren(); orders.items.forEach((order) => { const option = document.createElement("option"); option.value = order.order_id; option.textContent = `${order.order_id} · ${order.cargo_class}`; select.append(option); });
    setControls({ ready: true, loading: false, hasTrace: false }); renderMessage("Ready to govern a synthetic shipment."); const traceId = new URLSearchParams(location.search).get("trace_id"); if (traceId) await loadTrace(traceId);
  } catch (error) { renderHealth(null); renderMessage(`${error.code || "DISCONNECTED"}: ${error.message}`, true); setControls({ ready: false, loading: false, hasTrace: false }); }
}

byId("runForm").addEventListener("submit", startRun);
byId("refreshButton").addEventListener("click", () => state.activeTraceId && loadTrace(state.activeTraceId));
byId("resetButton").addEventListener("click", resetDemo);
byId("verifyButton").addEventListener("click", refreshVerification);
byId("timelineAll").addEventListener("click", () => { update({ showAllEvents: true }); renderCurrent(); });
byId("timelineInterventions").addEventListener("click", () => { update({ showAllEvents: false }); renderCurrent(); });
byId("createDisposableButton").addEventListener("click", createDisposable);
byId("tamperButton").addEventListener("click", tamperDisposable);
setInterval(() => {
  if (!state.lastUpdatedAt || !state.activeTraceId) return;
  const ageSeconds = Math.floor((Date.now() - state.lastUpdatedAt.getTime()) / 1000);
  if (ageSeconds >= 10) byId("lastUpdated").textContent = `Stale · ${ageSeconds}s since refresh`;
}, 1000);
initialize();
