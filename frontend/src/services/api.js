const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1';
export const TOKEN_KEY = 'chat_clone_access_token';
export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (token) => localStorage.setItem(TOKEN_KEY, token);
export const clearToken = () => localStorage.removeItem(TOKEN_KEY);
async function request(path, { method = 'GET', body, token = getToken() } = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;
  let response;
  try { response = await fetch(`${BASE_URL}${path}`, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) }); }
  catch { throw new Error('Cannot connect to backend. Check FastAPI and CORS settings.'); }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.detail;
    throw new Error(typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map(x => x.msg).join(', ') : `Request failed (${response.status})`);
  }
  return data;
}
export const api = {
  register: (payload) => request('/auth/register', { method: 'POST', body: payload, token: null }),
  login: (payload) => request('/auth/login', { method: 'POST', body: payload, token: null }),
  me: () => request('/auth/me'),
  chat: (message, conversation_id = null) => request('/chat', { method: 'POST', body: { message, conversation_id } }),
  conversations: () => request('/conversations'),
  conversation: (id) => request(`/conversations/${id}`),
};


// Streaming POST with JWT. Reads complete SSE frames across arbitrary byte chunks.
export async function streamChat(message, conversationId, { onMeta, onToken, onDone, signal } = {}) {
  const headers = { 'Content-Type': 'application/json' };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${BASE_URL}/chat/stream`, {
    method: 'POST', headers, body: JSON.stringify({ message, conversation_id: conversationId }), signal
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Chat failed (${response.status}): ${detail}`);
  }
  if (!response.body) throw new Error('Streaming is unavailable');
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let finished = false;
  function frame(text) {
    let event = 'message';
    const dataLines = [];
    for (const line of text.split('\n')) {
      if (line.startsWith('event:')) event = line.slice(6).trim();
      if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart());
    }
    if (!dataLines.length) return;
    const data = JSON.parse(dataLines.join('\n'));
    if (event === 'meta') onMeta?.(data);
    else if (event === 'token') onToken?.(data.content || '');
    else if (event === 'done') { finished = true; onDone?.(data); }
    else if (event === 'error') throw new Error(data.message || 'Generation failed');
  }
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      buffer = buffer.replace(/\r\n/g, '\n');
      let idx;
      while ((idx = buffer.indexOf('\n\n')) !== -1) {
        frame(buffer.slice(0, idx));
        buffer = buffer.slice(idx + 2);
      }
    }
    buffer += decoder.decode();
    if (buffer.trim()) frame(buffer);
    if (!finished) throw new Error('Stream ended without completion');
  } finally { reader.releaseLock(); }
}
