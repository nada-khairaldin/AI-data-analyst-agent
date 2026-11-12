// SSE over a POST, parsed by hand.
//
// EventSource can only issue a GET and cannot set headers, so it could carry
// neither the question body nor X-Session-Id. fetch + ReadableStream can, at
// the cost of framing the events ourselves — which is this file.
import { ApiError } from './client';
import { getSessionId } from './session';

const BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '');

// Splits an SSE buffer into complete events. A frame ends at a blank line, so
// anything after the last one is a partial event and stays in the buffer.
function splitFrames(buffer) {
  const frames = [];
  let rest = buffer;
  let index;
  // \n\n normally; \r\n\r\n if something along the way rewrote line endings.
  while ((index = rest.search(/\r?\n\r?\n/)) !== -1) {
    const end = index + rest.slice(index).match(/^\r?\n\r?\n/)[0].length;
    frames.push(rest.slice(0, index));
    rest = rest.slice(end);
  }
  return { frames, rest };
}

function parseFrame(frame) {
  let event = 'message';
  const data = [];
  for (const line of frame.split(/\r?\n/)) {
    if (line.startsWith(':')) continue; // a keep-alive comment
    if (line.startsWith('event:')) event = line.slice(6).trim();
    else if (line.startsWith('data:')) data.push(line.slice(5).trim());
  }
  if (!data.length) return null;
  try {
    return { event, data: JSON.parse(data.join('\n')) };
  } catch {
    return null;
  }
}

/**
 * POST a question and invoke `onEvent(name, payload)` for each SSE event.
 *
 * Resolves once the stream ends. Rejects with an ApiError if the request is
 * refused before the stream opens — which is why the 4xx checks happen
 * server-side before the response starts: after the status line, an error can
 * only be an `error` event.
 */
export async function streamMessage(conversationId, content, onEvent, { signal } = {}) {
  if (!BASE) {
    throw new ApiError('VITE_API_BASE_URL is not set.', { code: 'NO_API_BASE_URL' });
  }

  let response;
  try {
    response = await fetch(
      `${BASE}/api/conversations/${conversationId}/messages/stream`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Session-Id': getSessionId(),
          Accept: 'text/event-stream',
        },
        body: JSON.stringify({ content }),
        signal,
      },
    );
  } catch (cause) {
    if (cause?.name === 'AbortError') throw cause;
    throw new ApiError(
      'Could not reach the API. It may be starting up, or the origin may not '
        + 'be allowed by CORS.',
      { code: 'NETWORK' },
    );
  }

  if (!response.ok) {
    let body = null;
    try {
      body = await response.json();
    } catch { /* not JSON */ }
    throw new ApiError(body?.error?.message || `Request failed (${response.status})`, {
      status: response.status,
      code: body?.error?.code,
      details: body?.error?.details,
    });
  }

  if (!response.body) {
    throw new ApiError('This browser cannot read a streamed response.', {
      code: 'NO_STREAM',
    });
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const { frames, rest } = splitFrames(buffer);
    buffer = rest;
    for (const frame of frames) {
      const parsed = parseFrame(frame);
      if (parsed) onEvent(parsed.event, parsed.data);
    }
  }

  // Whatever is left after the last blank line, in case the server closed
  // without a trailing newline.
  const parsed = buffer.trim() ? parseFrame(buffer) : null;
  if (parsed) onEvent(parsed.event, parsed.data);
}
