export function money(minor) {
  if (!Number.isInteger(minor)) return "—";
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(minor / 100);
}

export function label(value) { return String(value || "unknown").replaceAll("_", " ").toUpperCase(); }
export function shortHash(value) { return value ? `${value.slice(0, 14)}…${value.slice(-8)}` : "—"; }
