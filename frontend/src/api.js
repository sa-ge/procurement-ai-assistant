const BASE = import.meta.env.VITE_API_URL ?? ''

async function request(path, options) {
  const res = await fetch(`${BASE}${path}`, options)
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(body.detail || `Request failed (${res.status})`)
  return body
}

export const getHealth = () => request('/api/health')
export const getExamples = () => request('/api/examples')
export const sendMessage = (message, sessionId) =>
  request('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId }),
  })
