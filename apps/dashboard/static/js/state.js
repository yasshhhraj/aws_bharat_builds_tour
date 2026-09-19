export const state = {
  health: null,
  fixtures: [],
  activeTraceId: null,
  run: null,
  events: [],
  decisions: [],
  projection: null,
  verification: null,
  approval: null,
  showAllEvents: false,
  disposableTraceId: null,
  disposableVerification: null,
  loading: false,
  error: null,
  lastUpdatedAt: null,
};

export function update(values) { Object.assign(state, values); }
