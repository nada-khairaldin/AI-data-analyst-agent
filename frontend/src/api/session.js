// The anonymous session id. Generated once in the browser and kept in
// localStorage; sent as X-Session-Id on every request.
//
// Honest limitation, worth knowing while using this: it is a bearer
// capability, not a login. Clearing browser storage orphans every dataset
// with no way to recover them.

const KEY = 'ai-data-analyst.session-id';

function uuid() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  // Safari < 15.4 and any non-secure origin. The server only requires a
  // well-formed UUID, so a v4-shaped fallback is enough.
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
  });
}

export function getSessionId() {
  try {
    const existing = localStorage.getItem(KEY);
    if (existing) return existing;
    const fresh = uuid();
    localStorage.setItem(KEY, fresh);
    return fresh;
  } catch {
    // Private mode or blocked storage: a per-tab id still works for one
    // sitting, it just will not survive a reload.
    if (!globalThis.__sessionId) globalThis.__sessionId = uuid();
    return globalThis.__sessionId;
  }
}
