export const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://127.0.0.1:8000'

export function apiWsUrl(path: string): string {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  const base = new URL(API_BASE)
  const protocol = base.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${base.host}${normalizedPath}`
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`)
  if (!res.ok) throw new Error(await res.text())
  return (await res.json()) as T
}

export async function apiSend<T>(
  path: string,
  options: { method: string; body?: unknown },
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: options.method,
    headers: { 'Content-Type': 'application/json' },
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  })
  if (!res.ok) throw new Error(await res.text())
  return (await res.json()) as T
}

