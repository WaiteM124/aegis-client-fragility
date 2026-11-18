// NOTE: If CORS errors occur at runtime, the live API must be called directly.
// No Vite proxy is used — requests go directly to the production API.
export const API_BASE = 'https://aegis-api-343322260451.europe-west2.run.app';

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
