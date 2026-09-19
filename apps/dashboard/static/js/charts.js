import { money } from "./format.js";

function text(tag, value, className = "") {
  const node = document.createElement(tag); node.textContent = value; if (className) node.className = className; return node;
}

export function renderSpendChart(container, points) {
  container.replaceChildren(); container.className = "spend-chart";
  if (!points?.length) { container.className = "chart-empty"; container.textContent = "No spend points available."; return; }
  points.forEach((point) => {
    const row = document.createElement("div"); row.className = `spend-row${point.projected_minor > point.ceiling_minor ? " over" : ""}`;
    row.append(text("span", point.label.toUpperCase()));
    const track = document.createElement("div"); track.className = "bar-track"; track.setAttribute("aria-hidden", "true");
    const committed = document.createElement("span"); committed.className = "bar-committed"; committed.style.width = `${Math.min(100, point.committed_minor / point.ceiling_minor * 100)}%`;
    const reserved = document.createElement("span"); reserved.className = "bar-reserved"; reserved.style.left = `${Math.min(100, point.committed_minor / point.ceiling_minor * 100)}%`; reserved.style.width = `${Math.min(100, point.reserved_minor / point.ceiling_minor * 100)}%`;
    track.append(committed, reserved); row.append(track, text("strong", money(point.projected_minor))); container.append(row);
  });
}

export function renderRiskChart(container, projection) {
  container.replaceChildren(); container.className = "risk-meter";
  if (!projection) { container.className = "chart-empty"; container.textContent = "No risk signals available."; return; }
  container.append(text("strong", `${projection.risk_signal_score} / 100`, "risk-score"));
  const scale = document.createElement("div"); scale.className = "risk-scale"; scale.setAttribute("aria-hidden", "true"); const fill = document.createElement("span"); fill.style.width = `${projection.risk_signal_score}%`; scale.append(fill); container.append(scale);
  const points = document.createElement("div"); points.className = "risk-points";
  projection.risk_points.forEach((point) => points.append(text("span", `+${point.delta} ${point.family}`, "risk-chip")));
  if (!projection.risk_points.length) points.append(text("span", "No non-allow policy families", "risk-chip"));
  container.append(points, text("p", "20 points per unique non-allow policy family, capped at 100. Synthetic demo indicator—not a probability.", "muted-copy"));
}
