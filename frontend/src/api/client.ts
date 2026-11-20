const PRODUCTION_API = 'https://aegis-api-343322260451.europe-west2.run.app';

// Vite exposes only VITE_* variables. If VITE_API_BASE is unset, keep calling
// the current Cloud Run API so existing production builds do not break.
export const API_BASE = import.meta.env.VITE_API_BASE || PRODUCTION_API;

export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json();
}
