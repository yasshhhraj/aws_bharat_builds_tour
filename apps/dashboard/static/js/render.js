import { label, money, shortHash } from "./format.js";
import { renderRiskChart, renderSpendChart } from "./charts.js";

const byId = (id) => document.getElementById(id);
const text = (tag, value, className = "") => { const node = document.createElement(tag); node.textContent = value; if (className) node.className = className; return node; };
const setText = (id, value) => { byId(id).textContent = value; };

export function renderHealth(health) {
  const badge = byId("healthBadge"); badge.className = `health-badge ${health ? "health-ready" : "health-error"}`; setText("healthLabel", health ? "Ready" : "Disconnected");
  const values = health ? {
    envDeployment: health.deployment_mode,
    envRuntime: health.runtime_mode,
    envProvider: health.model_provider,
    envRequestedModel: health.requested_model_id,
    envResolvedModel: health.resolved_model_id || "Provider did not disclose",
    envRoute: `${health.provider_route_kind} · fallback ${health.provider_fallback_active ? "active" : "off"}`,
    envPolicy: `${health.policy_engine} / ${health.policy_version}${health.policy_bundle_hash ? ` · ${shortHash(health.policy_bundle_hash)}` : ""}`,
    envStorage: health.storage_mode,
    envLedger: `${health.ledger_algorithm} / ${health.ledger_schema_version}`,
    envEffects: "Synthetic · simulated",
  } : Object.fromEntries(["envDeployment", "envRuntime", "envProvider", "envRequestedModel", "envResolvedModel", "envRoute", "envPolicy", "envStorage", "envLedger"].map((key) => [key, "Unavailable"]));
  Object.entries(values).forEach(([id, value]) => setText(id, value));
  byId("tamperPanelCard").classList.toggle("hidden", !health?.demo_tamper_enabled);
  if (health) setText("deploymentFooter", `Manifest ${health.deployment_mode === "aws" ? "AWS demo" : "local prototype"} · Synthetic logistics data and simulated effects · Tamper-evident, not immutable`);
}

export function renderMessage(message = "", isError = false, focus = false) { const node = byId("appMessage"); node.textContent = message; node.className = `app-message${isError ? " error" : ""}`; if (focus) node.focus(); }

function operatorState(run, projection, verification) {
  if (verification && !verification.valid) return ["Tamper detected", `Ledger invalid at event #${verification.first_bad_sequence}. Protected controls are disabled.`, "critical"];
  if (run.status === "pending_approval") return ["Approval required", "A prepared commitment is paused and bound to the displayed approval receipt.", "warning"];
  if (run.status === "blocked") return ["Authorization denied", `${projection?.failure_code || "POLICY_BLOCKED"}: Cedar prevented the protected effect.`, "critical"];
  if (run.status === "failed") {
    const states = {
      PROVIDER_TIMEOUT: ["Provider timeout", "The run failed closed. Retry creates a new trace; no fallback occurred."],
      PROVIDER_RATE_LIMITED: ["Provider rate limited", "The run failed closed. No automatic retry or fallback occurred."],
      PROVIDER_AUTHENTICATION_ERROR: ["Provider authentication failed", "Check local provider configuration; no protected effect occurred."],
      PROVIDER_BILLING_ERROR: ["Provider billing unavailable", "The selected provider rejected billing or credits; no protected effect occurred."],
      PROVIDER_MODEL_UNAVAILABLE: ["Model unavailable", "The configured model was unavailable; no protected effect occurred."],
      PROVIDER_UNAVAILABLE: ["Provider unavailable", "The model request failed before the role completed."],
    };
    const selected = states[projection?.failure_code] || ["Run failed safely", "Inspect the retained failure event; no silent fallback occurred."];
    return [...selected, "critical"];
  }
  if (run.status === "cancelled") return ["Commitment cancelled", "The prepared action was released without confirmation.", "warning"];
  if (run.status === "completed") return ["Governed completion", "The retained trace completed and is ready for verification.", "ready"];
  return [label(run.status), "The governed trajectory is in progress.", "warning"];
}

function renderOperatorState(run, projection, verification) {
  const [state, detail, tone] = operatorState(run, projection, verification);
  setText("operatorState", state); setText("operatorDetail", detail); byId("operatorCard").dataset.tone = tone;
  const receiptLabels = {
    confirmed_once: "Confirmed once",
    confirmation_once: "Confirmation retained",
    awaiting_approval: "Awaiting approval",
    cancelled_without_confirmation: "No confirmation",
    violation: "Invariant violation",
    no_commitment: "None",
  };
  setText("receiptState", receiptLabels[projection?.exact_once_status] || "Unknown");
  setText("receiptDetail", `${projection?.booking_confirmation_count || 0} confirmations · ${projection?.notification_count || 0} notifications`);
}

function isIntervention(event) {
  if (["tool_guided", "tool_blocked", "approval_required", "approval_approved", "approval_rejected", "approval_expired", "run_paused", "run_resumed", "run_cancelled", "run_failed"].includes(event.event_type)) return true;
  return event.event_type === "policy_decided" && event.details?.policy_outcome !== "allow";
}

function renderTimeline(events, showAll) {
  const list = byId("timeline"); list.replaceChildren();
  const visible = showAll ? events : events.filter((event) => isIntervention(event) || ["run_started", "agent_started", "agent_completed", "agent_paused", "run_completed"].includes(event.event_type));
  if (!visible.length) { list.append(text("li", "No timeline events match this filter.", "empty-state")); return; }
  visible.forEach((event) => {
    const item = document.createElement("li"); if (isIntervention(event)) item.classList.add("intervention");
    item.append(text("span", `#${event.sequence}`, "sequence"), text("span", event.agent || "system", "event-kind"));
    const body = document.createElement("div"); body.className = "event-copy"; body.append(text("span", event.summary));
    if (showAll && Object.keys(event.details || {}).length) { const details = document.createElement("details"); details.append(text("summary", `${label(event.event_type)} details`), text("pre", JSON.stringify(event.details, null, 2))); body.append(details); }
    item.append(body); list.append(item);
  });
}

function renderDecisions(decisions) {
  const feed = byId("decisionFeed"); feed.replaceChildren(); const interventions = decisions.filter((decision) => decision.policy_outcome !== "allow");
  if (!interventions.length) { feed.append(text("p", "No interventions were required for this trace.", "empty-state")); return; }
  interventions.forEach((decision) => {
    const card = document.createElement("article"); card.className = "decision-card"; const displayOutcome = !decision.enforced ? `WOULD ${decision.policy_outcome}` : decision.policy_outcome;
    card.append(text("span", displayOutcome.toUpperCase(), `outcome outcome-${decision.policy_outcome}`), text("h3", decision.reason_code), text("p", decision.because), text("p", `${decision.agent} · ${decision.tool_name} · applied ${decision.applied_outcome}`));
    const details = document.createElement("details"); details.append(text("summary", "Policy receipt"), text("pre", JSON.stringify({ guidance: decision.guidance, signals: decision.reasons, engine: decision.engine_name, policy_version: decision.policy_version, evaluation_ms: decision.evaluation_ms }, null, 2))); card.append(details); feed.append(card);
  });
}

function renderProvenance(projection) {
  const panel = byId("provenancePanel"); panel.replaceChildren(); panel.className = ""; const provenance = projection?.weight_provenance;
  if (!provenance) { panel.className = "empty-state"; panel.textContent = "No sourced weight loaded."; return; }
  const fact = document.createElement("div"); fact.className = "provenance-fact"; fact.append(text("span", "Authoritative source"), text("strong", `${provenance.authoritative_value} ${provenance.unit}`), text("span", `${provenance.fact_id} · ${provenance.source_id}`), text("p", shortHash(provenance.source_hash), "trace-id")); panel.append(fact);
  const attempts = document.createElement("div"); attempts.className = "attempt-list";
  provenance.attempts.forEach((attempt, index) => { const row = document.createElement("div"); row.className = "attempt-row"; row.append(text("span", `Attempt ${index + 1}`), text("strong", `${attempt.attempted_value} ${attempt.unit}`), text("span", label(attempt.policy_outcome), `outcome outcome-${attempt.policy_outcome}`)); attempts.append(row); });
  if (provenance.final_value !== null) attempts.append(text("p", `Final governed dispatch value: ${provenance.final_value} ${provenance.unit}`, "muted-copy")); panel.append(attempts);
}

function field(labelValue, value) { const wrapper = document.createElement("div"); wrapper.append(text("dt", labelValue), text("dd", value)); return wrapper; }

function renderApproval(approval, run, verification, onDecision) {
  const panel = byId("approvalPanel"); panel.replaceChildren(); panel.className = "";
  if (!approval) { panel.className = "empty-state"; panel.textContent = run?.status === "completed" ? "No approval is pending. The trajectory is complete." : "No approval is pending."; return; }
  const values = document.createElement("dl"); values.className = "approval-details"; values.append(field("Status", label(approval.status)), field("Amount", money(run.selected_amount_minor)), field("Version", String(approval.version)), field("Expires", new Date(approval.expires_at).toLocaleTimeString()), field("Action hash", shortHash(approval.action_hash)), field("State hash", shortHash(approval.state_hash))); panel.append(values);
  if (approval.status !== "pending_approval") { panel.append(text("p", `Resolved: ${label(approval.status)}`, "muted-copy")); return; }
  if (!verification?.valid) { panel.append(text("p", "Approval is disabled because retained trace data failed integrity verification.", "app-message error")); return; }
  const form = document.createElement("form"); form.className = "approval-form";
  const approverLabel = document.createElement("label"); approverLabel.textContent = "Synthetic approver label"; const approverInput = document.createElement("input"); approverInput.value = "DEMO-APPROVER-OPS-1"; approverInput.pattern = "DEMO-APPROVER-[A-Z0-9-]+"; approverLabel.append(approverInput);
  const commentLabel = document.createElement("label"); commentLabel.textContent = "Comment (optional)"; const commentInput = document.createElement("textarea"); commentInput.maxLength = 280; commentLabel.append(commentInput);
  const secretLabel = document.createElement("label"); secretLabel.textContent = "Demo approval secret"; const secretInput = document.createElement("input"); secretInput.type = "password"; secretInput.autocomplete = "off"; secretInput.required = true; secretLabel.append(secretInput);
  const actions = document.createElement("div"); actions.className = "approval-actions"; const approve = text("button", "Approve", "button button-primary"); approve.type = "button"; const reject = text("button", "Reject", "button button-danger"); reject.type = "button"; reject.style.marginTop = "0";
  approve.addEventListener("click", () => onDecision("approve", { approverInput, commentInput, secretInput, buttons: [approve, reject] })); reject.addEventListener("click", () => onDecision("reject", { approverInput, commentInput, secretInput, buttons: [approve, reject] })); actions.append(approve, reject); form.append(approverLabel, commentLabel, secretLabel, actions); panel.append(form);
}

function renderIntegrity(verification) {
  const panel = byId("integrityPanel"); panel.replaceChildren();
  if (!verification) { panel.className = "empty-state"; panel.textContent = "Verification details will appear after a run."; return; }
  panel.className = `integrity-card ${verification.valid ? "integrity-valid" : "integrity-invalid"}`; panel.append(text("strong", verification.valid ? "VALID" : "INVALID"), text("p", verification.valid ? `${verification.checked_event_count} linked events verified.` : `First invalid sequence: ${verification.first_bad_sequence} (${verification.failure_code}).`));
  const values = document.createElement("dl"); values.append(field("Algorithm", verification.algorithm), field("Schema", verification.schema_version), field("Head", shortHash(verification.stored_head_hash)), field("Sequence", String(verification.stored_head_sequence))); panel.append(values);
}

export function renderTrace(data, options = {}) {
  const { run, events, decisions, projection, verification, approval } = data;
  setText("runStatus", label(run.status)); setText("runStage", label(run.workflow_stage)); setText("traceId", run.trace_id); setText("spendValue", money(run.projected_spend_minor)); setText("spendCeiling", `${money(run.spend_ceiling_minor)} ceiling`); setText("riskValue", projection ? `${projection.risk_signal_score} / 100` : "—");
  const ratio = run.spend_ceiling_minor ? Math.min(100, run.projected_spend_minor / run.spend_ceiling_minor * 100) : 0; const bar = byId("spendBar"); bar.style.width = `${ratio}%`; bar.classList.toggle("over", run.projected_spend_minor > run.spend_ceiling_minor);
  setText("integrityValue", verification?.valid ? "Valid" : "Invalid"); setText("integrityDetail", verification ? `${verification.checked_event_count} events checked` : "Not verified"); setText("lastUpdated", `Fresh · ${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}`);
  renderSpendChart(byId("spendChart"), projection?.spend_points); renderRiskChart(byId("riskChart"), projection); renderTimeline(events, options.showAllEvents); renderDecisions(decisions); renderProvenance(projection); renderApproval(approval, run, verification, options.onApprovalDecision); renderIntegrity(verification); byId("timelineAll").classList.toggle("active", options.showAllEvents); byId("timelineInterventions").classList.toggle("active", !options.showAllEvents);
  renderOperatorState(run, projection, verification);
}

export function renderEmpty() {
  setText("runStatus", "Waiting"); setText("runStage", "Start a run"); setText("traceId", "No trace"); setText("spendValue", "—"); setText("spendCeiling", "No active mandate"); setText("riskValue", "—"); setText("integrityValue", "Unknown"); setText("integrityDetail", "Not verified"); setText("lastUpdated", "No trace loaded"); byId("spendBar").style.width = "0";
  setText("operatorState", "Ready"); setText("operatorDetail", "No governed trace loaded"); setText("receiptState", "None"); setText("receiptDetail", "0 confirmations · 0 notifications"); byId("operatorCard").dataset.tone = "ready";
  byId("timeline").replaceChildren(text("li", "Run a shipment to see agents, tools, and decisions in sequence.", "empty-state")); byId("decisionFeed").replaceChildren(text("p", "Policy decisions will appear after a run.", "empty-state")); byId("provenancePanel").replaceChildren(text("p", "No sourced weight loaded.", "empty-state")); byId("approvalPanel").replaceChildren(text("p", "No approval is pending.", "empty-state")); renderIntegrity(null); renderSpendChart(byId("spendChart"), []); renderRiskChart(byId("riskChart"), null);
}

export function renderDisposable(traceId, verification) { const status = byId("disposableStatus"); status.textContent = !traceId ? "No disposable trace created." : `${traceId} · ${verification?.valid ? "VALID" : `INVALID at #${verification?.first_bad_sequence}`}`; }

export function setControls({ ready, loading, hasTrace }) { byId("runButton").disabled = !ready || loading; byId("refreshButton").disabled = !hasTrace || loading; byId("resetButton").disabled = !ready || loading; byId("verifyButton").disabled = !hasTrace || loading; byId("orderSelect").disabled = !ready || loading; }
