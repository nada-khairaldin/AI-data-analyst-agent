// Every call to the backend goes through here.
import { getSessionId } from './session';

const BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '');

// Thrown for any non-2xx. Carries the contract's error envelope so a caller
// can branch on `code` and show `details` (the rejected-dataset screen needs
// them) instead of only a message.
export class ApiError extends Error {
  constructor(message, { status, code, details } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

function headers(extra = {}) {
  return { 'X-Session-Id': getSessionId(), ...extra };
}

async function toError(response) {
  let body = null;
  try {
    body = await response.json();
  } catch {
    // An HTML error page from a proxy, or an empty body.
  }
  const error = body?.error;
  return new ApiError(
    error?.message || `Request failed (${response.status})`,
    { status: response.status, code: error?.code, details: error?.details },
  );
}

async function request(path, options = {}) {
  if (!BASE) {
    throw new ApiError(
      'VITE_API_BASE_URL is not set, so the app does not know where the API is.',
      { code: 'NO_API_BASE_URL' },
    );
  }

  let response;
  try {
    response = await fetch(`${BASE}${path}`, options);
  } catch {
    // fetch only rejects for network-level problems, and a CORS rejection
    // looks exactly like one — so say both.
    throw new ApiError(
      'Could not reach the API. It may be starting up (a free instance takes '
        + '30-60s to wake), or the origin may not be allowed by CORS.',
      { code: 'NETWORK' },
    );
  }

  if (!response.ok) throw await toError(response);
  if (response.status === 204) return null;
  return response.json();
}

export const api = {
  health: () => request('/health'),

  listDatasets: () => request('/api/datasets', { headers: headers() }),

  getDataset: (id) => request(`/api/datasets/${id}`, { headers: headers() }),

  getReport: (id) => request(`/api/datasets/${id}/report`, { headers: headers() }),

  uploadDataset: (file) => {
    const form = new FormData();
    form.append('file', file);
    // No Content-Type: the browser must set the multipart boundary itself.
    return request('/api/datasets', {
      method: 'POST',
      headers: headers(),
      body: form,
    });
  },

  createConversation: (datasetId) =>
    request(`/api/datasets/${datasetId}/conversations`, {
      method: 'POST',
      headers: headers({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({}),
    }),

  getMessages: (conversationId) =>
    request(`/api/conversations/${conversationId}/messages`, {
      headers: headers(),
    }),
};

export { BASE as API_BASE_URL };
